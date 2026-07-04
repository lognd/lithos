"""The build driver: tiers -> discharge -> loop -> release gate (AD-1).

This is the top of the orchestrator: it drives the compiler facade to get
obligations, routes them through the harness at the tiers that discharge
(T1+), runs the lazy loop at the optimizing tier (T2+), and enforces
release-gate totality at T3 (INV-24). It owns the caching and ordering;
the harness owns selection and physics; the core owns everything static.

The release gate is the load-bearing honesty property: a ``--release``
report contains zero unaccepted ``violated`` or ``indeterminate``
obligations. This layer has no waiver/assume ledger yet (substrate/12
rungs 6-7 land later), so it accepts nothing -- every non-``discharged``
obligation fails the gate and is named. That is strictly conservative:
adding acceptances can only ever let MORE builds pass, never fewer.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry, default_registry
from regolith.logging_setup import get_logger
from regolith.orchestrator.cache import CacheStats, EvidenceStore
from regolith.orchestrator.discharge import ObligationResult, discharge_all
from regolith.orchestrator.loop import LoopOutcome, SensitivityHook, lazy_loop
from regolith.orchestrator.tiers import BuildTier

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

    @property
    def obligations_discharged(self) -> int:
        """How many obligations a model discharged (status ``discharged``)."""
        return sum(1 for r in self.results if r.is_resolved)


def release_gate(
    results: tuple[ObligationResult, ...],
) -> Result[None, OrchestratorError]:
    """Enforce INV-24 totality: no unaccepted violated/indeterminate result.

    Returns ``Ok`` iff every obligation discharged; otherwise ``Err`` names
    how many remain unresolved. Deferrals count as indeterminate (an
    obligation that never formed is not proven).
    """
    unresolved = tuple(r for r in results if not r.is_resolved)
    if not unresolved:
        return Ok(None)
    violated = sum(1 for r in unresolved if r.is_violated)
    indeterminate = len(unresolved) - violated
    _log.warning(
        "release gate FAILED: %d violated, %d indeterminate/deferred",
        violated,
        indeterminate,
    )
    return Err(
        OrchestratorError(
            kind="release_gate_failed",
            message=(
                f"--release refused: {violated} violated and "
                f"{indeterminate} indeterminate/deferred obligation(s) "
                "unaccepted (no waiver/assume ledger)"
            ),
        )
    )


def _parse_obligations(payload_json: bytes) -> tuple[Obligation, ...]:
    """Extract the obligation list from a build payload (source order)."""
    payload = json.loads(payload_json)
    raw = payload.get("obligations", [])
    return tuple(Obligation.model_validate(o) for o in raw)


def build(
    paths: tuple[str, ...],
    tier: BuildTier,
    *,
    registry: ModelRegistry | None = None,
    hooks: tuple[SensitivityHook, ...] = (),
    persist: bool = False,
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
        return Ok(BuildReport(tier=tier, ok=built.ok))

    obligations = _parse_obligations(built.payload_json)
    store_result = EvidenceStore.load(paths[0]) if persist else Ok(EvidenceStore())
    if store_result.is_err:
        return Err(store_result.danger_err)
    store = store_result.danger_ok

    if tier.runs_loop:
        loop_result = lazy_loop(
            obligations, registry=registry, store=store, hooks=hooks
        )
        if loop_result.is_err:
            return Err(loop_result.danger_err)
        loop: LoopOutcome = loop_result.danger_ok
        results, iterations = loop.results, loop.iterations
    else:
        results = discharge_all(list(obligations), registry=registry, store=store)
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
        )
    )
