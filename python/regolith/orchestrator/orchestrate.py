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
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith._schema.models import FlownetPayload, Obligation
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry, default_registry
from regolith.harness.attest import conferred_tier
from regolith.harness.plugin import PackLoadError
from regolith.logging_setup import get_logger
from regolith.magnetite.trust import LocalSigningKey, TrustKeySet, tier_from_name
from regolith.orchestrator.cache import CacheStats, EvidenceStore
from regolith.orchestrator.discharge import ObligationResult, discharge_all
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.programs import emitted_realizer_programs
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.mech.interpreter import (
    RealizedGeometryArtifact,
    realize_feature_program,
)
from regolith.realizer.mech.schema import FeatureProgram

_log = get_logger(__name__)

# WO-42 deliverable 5 / INV-21: the realizer pack name folded into a
# realized-IR lockfile row's `cause: realizer(<pack>)`. Only the mech
# realizer has a store `put` emission seam today (deliverable 4); the
# elec `layout.realized` producer is still blocked on a real KiCad
# backend (deliverable 2's own note) so it names no pack here yet.
REALIZER_PACK_MECH = "mech"

# WO-42 deliverable 5: a safety cap on staged-build iterations, well
# above any real subject count, so a producer bug that never converges
# (repeatedly claims a "new" digest for an unchanging input) fails loud
# with a logged warning instead of looping forever. Normal convergence
# is bounded by `len(feature_programs)` (each iteration resolves at
# least one previously-unresolved subject or stops), so this is a
# backstop, not the expected exit path.
_STAGED_BUILD_MAX_ITERATIONS = 16


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
    # Plugins skipped LOUDLY at registry composition (WO-20/AD-19,
    # renamed WO-44/AD-26 with the one-seam generalization): a bad
    # plugin is named here, never a silent partial load.
    plugin_errors: tuple[PackLoadError, ...] = ()
    # The raw `BuildOutput.payload_json()` bytes this build produced
    # (WO-42 deliverable 5): populated for every tier, including T0
    # `check`, so a caller (the staged build loop) can inspect the
    # lowered flownet edges for pending `GeomExtract` placeholders
    # without a second core call.
    payload_json: bytes = b""
    # The ONE renderer's text (AD-7) for this build's diagnostics, exactly
    # as `BuildOutcome.rendered` returned it -- WO-43's `regolith build`
    # prints this verbatim (never a second renderer) for its human-default
    # stdout form, the same precedent `check` already established.
    rendered: str = ""

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


def put_realized_geometry(
    store: PayloadStore, artifact: RealizedGeometryArtifact
) -> str:
    """Store ``artifact.geometry`` (kind ``geometry.realized``) into the
    WO-30 payload store, returning its content digest.

    WO-42 deliverable 4's realizer emission seam: the mech realizer
    (`regolith.realizer.mech.interpreter.realize_feature_program`) has
    no Rust-computed AD-18 canonical digest to pin, unlike
    :func:`_put_flownet_payloads`'s flownets -- a `RealizedGeometry` is
    produced standalone, before any compile pass has referenced it in
    an `Obligation.payloads` ref (there is no upstream digest to
    reproduce). This function therefore uses :meth:`PayloadStore.put`
    (fresh blake3 digest of the JSON bytes), not `put_at`: the RETURNED
    digest becomes the identity a later staged build (WO-42 deliverable
    5, not built by this dispatch) supplies as a `RealizedInput` key
    when re-lowering with this geometry.

    The staged-loop wiring that calls this after a `realize_feature_program`
    success and feeds the returned digest back into the next `lower()`
    pass is WO-42 deliverable 5's job (out of this dispatch's scope,
    per design-log 2026-07-08-cycle-25's "Dispatch effects" -- (c) needs
    only the validate-and-emit pass + this emission seam, not the loop).
    """
    data = artifact.geometry.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.debug(
        "payload store: put geometry.realized for part=%s digest=%s",
        artifact.geometry.feature_program_hash,
        digest,
    )
    return digest


def build(
    paths: tuple[str, ...],
    tier: BuildTier,
    *,
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    realized_inputs: tuple[compiler.RealizedInput, ...] = (),
) -> Result[BuildReport, OrchestratorError]:
    """Run an orchestrated build of ``paths`` at ``tier``.

    T0 (``check``) is the static core pass only. T1+ additionally routes
    obligations through the harness (with the evidence cache). T2+ runs the
    lazy loop over ``hooks``. T3 (``release``) applies the release gate and
    fails the build if any obligation is unresolved (INV-24). A core
    infrastructure failure is an ``Err`` value (``CoreFailure`` mapped);
    a failing *check* is a report with ``ok=False`` (claims-as-data).

    ``realized_inputs`` (WO-42 deliverable 3, AD-25/D128) is the caller-
    resolved realized-domain IR channel threaded straight through to the
    core; empty by default (the pre-realization placeholder path). The
    staged build loop (deliverable 5, :func:`staged_build`) is the only
    caller that supplies a non-empty set today.
    """
    registry = registry or default_registry()

    if tier.runs_discharge:
        outcome = compiler.compile(
            paths, registry_version=registry.version, realized_inputs=realized_inputs
        )
    else:
        outcome = compiler.check(paths, realized_inputs=realized_inputs)
    if outcome.is_err:
        return Err(
            OrchestratorError(
                kind="core_failure", message=str(outcome.danger_err.message)
            )
        )
    built = outcome.danger_ok

    if not tier.runs_discharge:
        _log.debug("tier %s: static-only, no harness discharge", tier.name)
        return Ok(
            BuildReport(
                tier=tier,
                ok=built.ok,
                plugin_errors=registry.plugin_errors,
                payload_json=built.payload_json,
                rendered=built.rendered,
            )
        )

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
            plugin_errors=registry.plugin_errors,
            payload_json=built.payload_json,
            rendered=built.rendered,
        )
    )


def _pending_geom_extract_subjects(payload_json: bytes) -> frozenset[str]:
    """Subjects still lowered to the pre-realization ``GeomExtract``
    placeholder (AD-25/D128) across every flownet in ``payload_json``.

    A `from=<ref>` flow edge lowers to ``EdgeParams::GeomExtract{record,
    selector}`` (`regolith-lower::flownet_lower`) with an EMPTY
    ``record.digest`` exactly when no realized-geometry input matched
    its subject (`RealizedFlownetInputs::geometry`, deliverable 3); a
    non-empty digest means a prior iteration's realized input already
    backs it (whether or not `extract_path` itself then succeeded --
    an extraction failure is D5's own diagnostic, not this loop's
    concern: re-realizing an unchanged subject would not change the
    outcome, INV-10). ``record.name``/``selector`` both carry the exact
    `from=` ref text, which is also the subject string
    `compiler.RealizedInput.subject` must match byte-for-byte
    (`RealizedFlownetInputs::geometry`'s `input.subject == from_ref`).
    """
    if not payload_json:
        return frozenset()
    payload = json.loads(payload_json)
    flownets = payload.get("flownets", {})
    if not isinstance(flownets, dict):
        return frozenset()
    subjects: set[str] = set()
    for flownet in flownets.values():
        if not isinstance(flownet, dict):
            continue
        for edge in flownet.get("edges", []) or []:
            params = edge.get("params") or {}
            if params.get("source") != "geom_extract":
                continue
            record = params.get("record") or {}
            if record.get("digest"):
                continue  # already backed by a realized-input digest
            name = record.get("name") or ""
            if name:
                subjects.add(name)
    return frozenset(subjects)


def realized_lock_rows(
    realized_inputs: tuple[compiler.RealizedInput, ...],
    pack: str = REALIZER_PACK_MECH,
) -> tuple[LockRow, ...]:
    """Lockfile rows for realized-domain IRs supplied to a build (WO-42
    deliverable 5, INV-21): each row's cause is ``realizer(<pack>)``,
    following the existing ``dfm(...)``/``drc(...)``/``budget(...)``
    cause-string convention documented in ``lockfile.py``. ``slot``
    names the subject's realized-geometry pin (``<subject>.geometry``,
    the D96 ``geometry.realized`` kind today -- a future
    ``layout.realized`` producer would name its own slot shape);
    ``value`` is the payload-store digest a re-``check``/``compile``
    pass supplies back as that subject's ``RealizedInput.digest``.
    Rows are returned in subject-sorted order (AD-6: deterministic
    lockfile row order is `render`'s own job, but a stable INPUT order
    keeps this function's output reproducible independent of dict
    iteration order too).
    """
    return tuple(
        LockRow(
            slot=f"{ri.subject}.geometry",
            value=ri.digest,
            cause=f"realizer({pack})",
        )
        for ri in sorted(realized_inputs, key=lambda r: r.subject)
    )


class StagedBuildReport(BaseModel):
    """The outcome of WO-42 deliverable 5's staged build loop (AD-25/D128):
    lower -> realize (producing new realized-domain IRs) -> re-lower with
    them, to a fixed point.

    ``final`` is the last :class:`BuildReport` (the fixed-point build --
    the one whose ``payload_json`` no longer names a realizable pending
    subject). ``iterations`` counts how many core ``check``/``compile``
    passes ran (always >= 1: the loop always runs at least once, even
    with no ``feature_programs`` supplied). ``realized_inputs`` is every
    realized-domain IR supplied to the FINAL pass, and ``lock_rows`` are
    their INV-21 lockfile rows (:func:`realized_lock_rows`).
    """

    model_config = ConfigDict(frozen=True)

    final: BuildReport
    iterations: int
    realized_inputs: tuple[compiler.RealizedInput, ...] = ()
    lock_rows: tuple[LockRow, ...] = ()


def staged_build(
    paths: tuple[str, ...],
    tier: BuildTier,
    feature_programs: Mapping[str, FeatureProgram] = MappingProxyType({}),
    *,
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
    signer: LocalSigningKey | None = None,
    trust_keys: TrustKeySet | None = None,
    max_iterations: int = _STAGED_BUILD_MAX_ITERATIONS,
) -> Result[StagedBuildReport, OrchestratorError]:
    """Run the WO-42 deliverable 5 staged build loop over ``paths``.

    lower -> realize -> re-lower to a fixed point (AD-25/D128):

    1. Run :func:`build` with the realized inputs collected so far
       (initially empty -- the pre-realization placeholder path).
    2. Scan the resulting payload for subjects still lowered to the
       ``GeomExtract`` placeholder (:func:`_pending_geom_extract_subjects`)
       that a ``FeatureProgram`` backs: PIPELINE-PRODUCED first (WO-51
       deliverable 4 -- ``lower.programs`` emits programs with
       cavity-derived ``flow_paths``, promoted into the realizer
       contract by :func:`emitted_realizer_programs`, subject =
       selector), with the caller-supplied ``feature_programs`` mapping
       kept as an OVERRIDE channel (tests, hand fixtures -- the AD-22
       posture). A program the emitted IR cannot honestly complete is
       skipped by the converter with a named reason and its subject
       stays pending.
    3. Realize every such subject not already realized or already known
       to have failed realization this call (`realize_feature_program`,
       WO-42 deliverable 4's validate-and-emit pass), `put` each result
       into the WO-30 store (:func:`put_realized_geometry`), and fold it
       into the next iteration's realized-input set.
    4. Repeat from (1) until an iteration adds no new realized input --
       the fixed point. Termination proof (AD-25): a subject once
       realized is never re-realized by this loop (its digest is fixed
       going forward, matching D128's "unchanged realized-IR digest ->
       byte-identical re-lower", INV-10), and each iteration either
       realizes >= 1 previously-unrealized-or-unattempted subject or
       stops -- so the loop closes in at most
       ``len(feature_programs) + 1`` iterations, well inside
       ``max_iterations``'s safety cap (which exists only to fail loudly
       on a producer bug, not as the expected exit path).

    A subject whose realization fails (:class:`RealizeError`) is logged
    and left pending permanently for this call (never retried in a
    later iteration -- retrying an input that has not changed cannot
    produce a different outcome, and retrying forever would never
    converge); its dependent obligations stay honestly indeterminate,
    naming the missing IR, exactly as the D128 placeholder rule
    requires for a subject with no ``FeatureProgram`` supplied at all.

    Every iteration is logged with the subjects realized and the
    digests that changed (AD-25's own observability requirement).
    """
    project_root = _project_root(paths)
    store = PayloadStore(project_root)
    realized_by_subject: dict[str, compiler.RealizedInput] = {}
    failed_subjects: set[str] = set()
    report: BuildReport | None = None
    iteration = 0

    while True:
        iteration += 1
        build_result = build(
            paths,
            tier,
            registry=registry,
            hooks=hooks,
            persist=persist,
            signer=signer,
            trust_keys=trust_keys,
            realized_inputs=tuple(realized_by_subject.values()),
        )
        if build_result.is_err:
            return Err(build_result.danger_err)
        report = build_result.danger_ok

        pending = _pending_geom_extract_subjects(report.payload_json)
        # WO-51 d4: pipeline-produced programs from the emitted payload,
        # with the caller channel as the override (caller wins per key).
        effective_programs: dict[str, FeatureProgram] = {
            **emitted_realizer_programs(report.payload_json),
            **dict(feature_programs),
        }
        to_realize = sorted(
            subject
            for subject in pending
            if subject in effective_programs
            and subject not in realized_by_subject
            and subject not in failed_subjects
        )
        if not to_realize:
            _log.debug(
                "staged build: fixed point reached after %d iteration(s), "
                "%d realized input(s) supplied",
                iteration,
                len(realized_by_subject),
            )
            break
        if iteration >= max_iterations:
            _log.warning(
                "staged build: hit max_iterations=%d with %d subject(s) "
                "still pending realization: %s -- stopping without "
                "realizing them (dependent obligations stay indeterminate)",
                max_iterations,
                len(to_realize),
                to_realize,
            )
            break

        changed_digests: list[str] = []
        for subject in to_realize:
            realized = realize_feature_program(effective_programs[subject])
            if realized.is_err:
                _log.warning(
                    "staged build: realization failed for subject=%r: %r "
                    "(not retried; dependent obligations stay indeterminate)",
                    subject,
                    realized.danger_err,
                )
                failed_subjects.add(subject)
                continue
            artifact = realized.danger_ok
            digest = put_realized_geometry(store, artifact)
            realized_by_subject[subject] = compiler.RealizedInput(
                digest=digest,
                kind="geometry.realized",
                subject=subject,
                payload_bytes=artifact.geometry.model_dump_json().encode("utf-8"),
            )
            changed_digests.append(digest)
        _log.info(
            "staged build iteration %d: realized %d subject(s) subjects=%s digests=%s",
            iteration,
            len(changed_digests),
            to_realize,
            changed_digests,
        )

    assert report is not None  # the loop always runs >= 1 iteration
    realized_inputs = tuple(realized_by_subject.values())
    return Ok(
        StagedBuildReport(
            final=report,
            iterations=iteration,
            realized_inputs=realized_inputs,
            lock_rows=realized_lock_rows(realized_inputs),
        )
    )
