"""The build driver: tiers -> discharge -> loop -> release gate (AD-1).

This is the top of the orchestrator: it drives the compiler facade to get
obligations, routes them through the harness at the tiers that discharge
(T1+), runs the lazy loop at the optimizing tier (T2+), and enforces
release-gate totality at T3 (INV-24). It owns the caching and ordering;
the harness owns selection and physics; the core owns everything static.

The release gate is the load-bearing honesty property: a ``--release``
report contains zero unaccepted ``violated`` or ``indeterminate``
obligations. This layer has no waiver/assume ledger yet (regolith/12
rungs 6-7 land later), so it accepts nothing -- every non-``discharged``
obligation fails the gate and is named. That is strictly conservative:
adding acceptances can only ever let MORE builds pass, never fewer.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith._schema.models import FlownetPayload, Obligation
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry, default_registry
from regolith.harness.attest import conferred_tier
from regolith.harness.plugin import PackLoadError
from regolith.logging_setup import get_logger
from regolith.orchestrator.cache import CacheStats, EvidenceStore
from regolith.orchestrator.discharge import ObligationResult, discharge_all
from regolith.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.tiers import BuildTier
from regolith.quarry.trust import LocalSigningKey, TrustKeySet, tier_from_name

_log = get_logger(__name__)


class BuildReport(BaseModel):
    """The outcome of one orchestrated build at a given tier."""

    model_config = ConfigDict(frozen=True)

    tier: BuildTier
    ok: bool  # the core's static verdict (diagnostics-clean)
    results: tuple[ObligationResult, ...] = ()
    unresolved: tuple[ObligationResult, ...] = ()
    cache_stats: CacheStats = CacheStats()
    release_ok: bool = True
    loop_iterations: int = 0
    # Model packs skipped LOUDLY at registry composition (WO-20/AD-19):
    # a bad pack is named here, never a silent partial load.
    pack_errors: tuple[PackLoadError, ...] = ()

    @property
    def obligations_discharged(self) -> int:
        """How many obligations a model discharged (status ``discharged``)."""
        return sum(1 for r in self.results if r.is_resolved)


def _meets_trust_floor(result: ObligationResult) -> bool:
    """True iff ``result``'s conferred tier satisfies its claim trust floor.

    A claim without a floor always passes. An unparseable floor is treated
    conservatively as unmet (it is a floor the gate cannot certify). An
    indeterminate attestation confers no tier, so any floor is unmet
    (INV-14/INV-28: below-floor computed evidence is not a pass).
    """
    if result.trust_floor is None:
        return True
    floor = tier_from_name(result.trust_floor)
    if floor.is_err:
        _log.warning(
            "claim %s has an unparseable trust floor %r; treating as unmet",
            result.subject_ref,
            result.trust_floor,
        )
        return False
    conferred = conferred_tier(result.attestation)
    if conferred is None:
        return False
    return conferred.meets(floor.danger_ok)


def release_gate(
    results: tuple[ObligationResult, ...],
) -> Result[None, OrchestratorError]:
    """Enforce INV-24 totality plus INV-28 trust floors on computed evidence.

    Returns ``Ok`` iff every obligation discharged AND every discharged
    result meets its claim's ``trust: >= tier`` floor. Otherwise ``Err``
    names the counts, keeping trust-floor refusals DISTINCT from violated
    and indeterminate/deferred (report/exit-code distinction, D-E).
    Deferrals count as indeterminate (an obligation that never formed is
    not proven).
    """
    unresolved = tuple(r for r in results if not r.is_resolved)
    below_floor = tuple(
        r for r in results if r.is_resolved and not _meets_trust_floor(r)
    )
    if not unresolved and not below_floor:
        return Ok(None)
    violated = sum(1 for r in unresolved if r.is_violated)
    indeterminate = len(unresolved) - violated
    _log.warning(
        "release gate FAILED: %d violated, %d indeterminate/deferred, "
        "%d below trust floor",
        violated,
        indeterminate,
        len(below_floor),
    )
    return Err(
        OrchestratorError(
            kind="release_gate_failed",
            message=(
                f"--release refused: {violated} violated, "
                f"{indeterminate} indeterminate/deferred, and "
                f"{len(below_floor)} below-trust-floor obligation(s) "
                "unaccepted (no waiver/assume ledger)"
            ),
        )
    )


def _parse_obligations(payload: dict[str, object]) -> tuple[Obligation, ...]:
    """Extract the obligation list from a parsed build payload (source order)."""
    raw = payload.get("obligations", [])
    if not isinstance(raw, list):
        return ()
    return tuple(Obligation.model_validate(o) for o in raw)


def _project_root(paths: tuple[str, ...]) -> str:
    """The `.regolith/`-rooting directory for `paths[0]` (AD-10).

    `paths[0]` is a single source FILE for a one-file build (every test
    fixture in this repo passes one); `.regolith/` roots beside the
    project, not inside a file. Falls back to the path itself when it
    is already a directory (or does not exist yet), matching the one
    convention this module and `EvidenceStore` both need.
    """
    candidate = Path(paths[0])
    if candidate.is_file():
        return str(candidate.parent)
    return paths[0]


def _put_flownet_payloads(
    project_root: str,
    payload: dict[str, object],
    obligations: tuple[Obligation, ...],
) -> None:
    """Store every flownet a `kind: flownet` `PayloadRef` resolves to.

    WO-32 D4b: the FIRST orchestrator `PayloadStore` producer. Each
    obligation's `payloads` may carry a `PayloadRef{ kind: "flownet",
    digest, origin }` (D129); `BuildPayload.flownets` (name -> payload,
    AD-6 source order) is where the referenced content actually lives.
    The digest was already computed Rust-side through the AD-18
    canonical encoder (`FlownetPayload.content_digest()`) -- this
    function stores bytes under that EXACT digest via
    `PayloadStore.put_at` rather than recomputing one, so a later
    `resolve(digest)` at discharge time is a hit (per fluorite/03 sec.
    2 / D129's payload-ref channel).

    A `PayloadRef` naming a flownet absent from `payload["flownets"]`
    is logged and skipped, not raised: the referenced obligation's
    discharge will honestly fail to resolve the payload later (a
    recoverable, already-modeled outcome -- `PayloadStore.resolve`
    returns `Err(payload_not_found)`), rather than crashing the build
    over a producer-side inconsistency that should not occur but is
    not this function's job to treat as fatal.
    """
    flownets_raw = payload.get("flownets", {})
    if not isinstance(flownets_raw, dict) or not flownets_raw:
        return
    store = PayloadStore(project_root)
    seen_digests: set[str] = set()
    for obligation in obligations:
        for ref in obligation.payloads or ():
            if ref.kind != "flownet" or ref.digest in seen_digests:
                continue
            raw = flownets_raw.get(ref.origin)
            if raw is None:
                _log.warning(
                    "flownet payload ref origin=%r digest=%s names no "
                    "flownet in this build's payload; skipping store put",
                    ref.origin,
                    ref.digest,
                )
                continue
            flownet = FlownetPayload.model_validate(raw)
            data = flownet.model_dump_json().encode("utf-8")
            store.put_at(ref.digest, data)
            seen_digests.add(ref.digest)
    _log.debug(
        "payload store: put %d flownet payload(s) for this build",
        len(seen_digests),
    )


def build(
    paths: tuple[str, ...],
    tier: BuildTier,
    *,
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
) -> Result[BuildReport, OrchestratorError]:
    """Run an orchestrated build of ``paths`` at ``tier``.

    T0 (``check``) is the static core pass only. T1+ additionally routes
    obligations through the harness (with the evidence cache). T2+ runs the
    lazy loop over ``hooks``. T3 (``release``) applies the release gate and
    fails the build if any obligation is unresolved (INV-24). A core
    infrastructure failure is an ``Err`` value (``CoreFailure`` mapped);
    a failing *check* is a report with ``ok=False`` (claims-as-data).
    """
    registry = registry or default_registry()

    if tier.runs_discharge:
        outcome = compiler.compile(paths, registry_version=registry.version)
    else:
        outcome = compiler.check(paths)
    if outcome.is_err:
        return Err(
            OrchestratorError(
                kind="core_failure", message=str(outcome.danger_err.message)
            )
        )
    built = outcome.danger_ok

    if not tier.runs_discharge:
        _log.debug("tier %s: static-only, no harness discharge", tier.name)
        return Ok(BuildReport(tier=tier, ok=built.ok, pack_errors=registry.pack_errors))

    build_payload = json.loads(built.payload_json)
    obligations = _parse_obligations(build_payload)
    # WO-32 D4b: put every referenced flownet payload into the WO-30
    # store BEFORE discharge, so a model's `resolve(digest)` call
    # (harness/registry, D96 sec. 8.3) can find it.
    _put_flownet_payloads(_project_root(paths), build_payload, obligations)
    store_result = EvidenceStore.load(paths[0]) if persist else Ok(EvidenceStore())
    if store_result.is_err:
        return Err(store_result.danger_err)
    store = store_result.danger_ok

    if tier.runs_loop:
        loop_result = lazy_loop(
            obligations,
            registry=registry,
            store=store,
            hooks=hooks,
            signer=signer,
            trust_keys=trust_keys,
        )
        if loop_result.is_err:
            return Err(loop_result.danger_err)
        loop: LoopOutcome = loop_result.danger_ok
        results, iterations = loop.results, loop.iterations
    else:
        results = discharge_all(
            list(obligations),
            registry=registry,
            store=store,
            signer=signer,
            trust_keys=trust_keys,
        )
        iterations = 1

    if persist:
        saved = store.save(paths[0])
        if saved.is_err:
            return Err(saved.danger_err)

    unresolved = tuple(r for r in results if not r.is_resolved)
    release_ok = True
    if tier.is_release:
        gate = release_gate(results)
        release_ok = gate.is_ok

    _log.debug(
        "build tier=%s obligations=%d discharged=%d unresolved=%d release_ok=%s",
        tier.name,
        len(results),
        sum(1 for r in results if r.is_resolved),
        len(unresolved),
        release_ok,
    )
    return Ok(
        BuildReport(
            tier=tier,
            ok=built.ok,
            results=results,
            unresolved=unresolved,
            cache_stats=store.stats,
            release_ok=release_ok,
            loop_iterations=iterations,
            pack_errors=registry.pack_errors,
        )
    )
