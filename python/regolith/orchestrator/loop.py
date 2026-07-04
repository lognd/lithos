"""The lazy optimization loop with sensitivity hooks (substrate/12).

The default build resolves once (eager) and discharges once. ``optimize``
(tier T2) adds this loop: after a discharge pass, each registered
:class:`SensitivityHook` may propose a *refined* obligation set -- a
tightened tolerance, a re-allocated budget share, a narrowed choice -- and
the loop re-discharges only when something actually moved (lazy). It runs
to a fixpoint (no hook proposes a change) or a bounded iteration cap, and
is deterministic: hooks are consulted in registration order and the first
one that proposes a change wins the round (INV-10).

Crucially, the loop only ever changes *inputs* and re-keys obligations
(INV-2 ladder safety): it can never relabel a verdict, because every
proposed obligation set is discharged afresh through the same total
harness path. A wrong refinement can only fail to converge, never lie.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import Obligation
from regolith.errors import OrchestratorError
from regolith.harness import ModelRegistry
from regolith.logging_setup import get_logger
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import ObligationResult, discharge_all

_log = get_logger(__name__)


class SensitivityHook(Protocol):
    """A refinement proposer consulted between discharge passes.

    Given the current obligation set and its results, a hook returns a
    refined obligation set to try next, or ``None`` if it is satisfied and
    proposes no change. Hooks must be *monotone* toward a fixpoint (each
    proposal genuinely different) so the loop terminates; the cap is the
    backstop when they are not.
    """

    def propose(
        self,
        obligations: tuple[Obligation, ...],
        results: tuple[ObligationResult, ...],
    ) -> tuple[Obligation, ...] | None:
        """Propose a refined obligation set, or ``None`` for no change."""
        ...


class LoopOutcome(BaseModel):
    """The result of running the lazy loop: final results plus convergence."""

    model_config = ConfigDict(frozen=True)

    results: tuple[ObligationResult, ...]
    iterations: int
    converged: bool


def lazy_loop(
    obligations: tuple[Obligation, ...],
    *,
    registry: ModelRegistry,
    store: EvidenceStore,
    hooks: tuple[SensitivityHook, ...] = (),
    max_iters: int = 16,
) -> Result[LoopOutcome, OrchestratorError]:
    """Run the discharge/refine loop to a fixpoint or the iteration cap.

    Each round discharges the current obligation set, then consults hooks
    in order; the first hook that proposes a *different* set drives the
    next round. With no hooks (or none proposing a change) the loop is a
    single discharge pass -- the eager-resolution default. An exceeded cap
    is an ``Err`` value (a non-converging refinement is a caller-visible
    condition, not a silent truncation).
    """
    current = obligations
    last_results: tuple[ObligationResult, ...] = ()
    for iteration in range(1, max_iters + 1):
        last_results = discharge_all(list(current), registry=registry, store=store)
        proposed: tuple[Obligation, ...] | None = None
        for hook in hooks:
            candidate = hook.propose(current, last_results)
            if candidate is not None and candidate != current:
                proposed = candidate
                break
        if proposed is None:
            _log.debug("lazy loop converged after %d iteration(s)", iteration)
            return Ok(
                LoopOutcome(results=last_results, iterations=iteration, converged=True)
            )
        _log.debug(
            "lazy loop iteration %d: a hook refined the obligation set", iteration
        )
        current = proposed

    _log.warning("lazy loop hit iteration cap %d without converging", max_iters)
    return Err(
        OrchestratorError(
            kind="loop_did_not_converge",
            message=f"lazy loop exceeded {max_iters} iterations without a fixpoint",
        )
    )
