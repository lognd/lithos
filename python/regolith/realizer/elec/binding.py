"""Component binding: allocation search over registry records (regolith/07 sec. 7).

The orchestrator-owned allocation-search loop binds abstract blocks
(parts declared in a `.cupr` design) to concrete registry records,
screened by capability arithmetic (a candidate must satisfy every
block requirement) and by aggregate design budgets (e.g. total power).
A candidate that would blow a budget is recorded as a NOGOOD -- D75:
nogoods are solver state kept for the duration of the search, never
written to the lockfile -- and the search backtracks to try the next
candidate, chronologically, until a feasible assignment is found or
every candidate is exhausted. Every successful binding is reported as
a :class:`PlannerPin`, the shape the caller renders as a
`regolith.orchestrator.lockfile.LockRow` with cause `planner` (every
binding is lockfile-pinned, WO-24 deliverable 1).

Scope note: this module operates on the explicit
:class:`BlockRequirement` / :class:`ComponentCandidate` input model, not
on a `.cupr` AST or lowering output directly -- translating lowered
facts into that input model is an orchestrator-bridge concern the WO-24
plan records as a cut (no such bridge exists yet; WO-19/WO-26
territory). The search ENGINE below is what WO-24 delivers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.realizer.elec.errors import NoFeasibleBinding

_log = get_logger(__name__)


class ComponentCandidate(BaseModel):
    """One registry record eligible to fill a block, with its capabilities.

    ``record_key`` is the `package/key@revision` string a caller resolves
    against `regolith.quarry.records.RecordStore`; capabilities are named
    scalar amounts the candidate provides (e.g. `gpio`, `ram_kb`,
    `power_mw`) that a :class:`BlockRequirement` screens against.
    """

    model_config = ConfigDict(frozen=True)

    record_key: str
    content_hash: str
    capabilities: Mapping[str, float] = {}
    cost: int = 1


class BlockRequirement(BaseModel):
    """One abstract block's minimum capability demand.

    A candidate satisfies the requirement iff, for every named
    capability, the candidate's amount is >= the demanded minimum
    (capability arithmetic, WO-16). Unlisted capabilities are
    unconstrained.
    """

    model_config = ConfigDict(frozen=True)

    block: str
    min_capabilities: Mapping[str, float] = {}


class Budget(BaseModel):
    """An aggregate design budget checked across every bound block.

    E.g. total system power: the sum of each bound candidate's
    ``capability`` amount must stay <= ``limit``.
    """

    model_config = ConfigDict(frozen=True)

    capability: str
    limit: float


class PlannerPin(BaseModel):
    """One successful binding: the lockfile row shape, cause `planner`."""

    model_config = ConfigDict(frozen=True)

    block: str
    record_key: str
    content_hash: str
    cause: str = "planner"


class Bindings(BaseModel):
    """The total feasible assignment: one pin per requirement, in order."""

    model_config = ConfigDict(frozen=True)

    pins: tuple[PlannerPin, ...]


def _satisfies(candidate: ComponentCandidate, requirement: BlockRequirement) -> bool:
    """Capability-arithmetic screen: candidate amount >= every minimum."""
    return all(
        candidate.capabilities.get(name, 0.0) >= minimum
        for name, minimum in requirement.min_capabilities.items()
    )


def _ordered(candidates: Sequence[ComponentCandidate]) -> list[ComponentCandidate]:
    """Deterministic candidate order: (cost, record_key) ascending."""
    return sorted(candidates, key=lambda c: (c.cost, c.record_key))


def _budget_ok(
    budgets: Sequence[Budget],
    chosen: Sequence[ComponentCandidate],
) -> Budget | None:
    """The first budget ``chosen`` violates, or ``None`` if all hold."""
    for budget in budgets:
        total = sum(c.capabilities.get(budget.capability, 0.0) for c in chosen)
        if total > budget.limit:
            return budget
    return None


def bind_all(
    requirements: Sequence[BlockRequirement],
    candidates: Mapping[str, Sequence[ComponentCandidate]],
    budgets: Sequence[Budget] = (),
) -> Result[Bindings, NoFeasibleBinding]:
    """Chronological-backtracking allocation search (regolith/07 sec. 7).

    Assigns blocks in the given order; each assignment is screened by
    capability arithmetic (:func:`_satisfies`) then by every aggregate
    :class:`Budget` computed over the blocks bound SO FAR. A budget
    violation is recorded as a nogood over the offending
    ``(block, record_key)`` pair (D75: solver state only) and the
    search retries the next candidate for the SAME block; when a
    block's candidates are exhausted the search backjumps to the
    previous block and advances ITS candidate cursor -- standard
    chronological backjumping, sufficient for the WO-24 fixture
    (a single rigged nogood forcing exactly one retry).
    """
    nogoods: set[tuple[str, str]] = set()
    order = [req.block for req in requirements]
    req_by_block = {req.block: req for req in requirements}
    ordered_candidates = {block: _ordered(cands) for block, cands in candidates.items()}
    # cursor[i] = index into ordered_candidates[order[i]] currently tried
    cursor = [0] * len(order)
    chosen: list[ComponentCandidate | None] = [None] * len(order)

    i = 0
    while 0 <= i < len(order):
        block = order[i]
        req = req_by_block[block]
        pool = ordered_candidates.get(block, [])
        placed = False
        while cursor[i] < len(pool):
            cand = pool[cursor[i]]
            cursor[i] += 1
            if (block, cand.record_key) in nogoods:
                continue
            if not _satisfies(cand, req):
                _log.debug(
                    "candidate %s fails capability screen for %s",
                    cand.record_key,
                    block,
                )
                continue
            trial = [c for c in chosen[:i] if c is not None] + [cand]
            blown = _budget_ok(budgets, trial)
            if blown is not None:
                _log.info(
                    "binding %s=%s blows budget %s (nogood recorded, D75)",
                    block,
                    cand.record_key,
                    blown.capability,
                )
                nogoods.add((block, cand.record_key))
                continue
            chosen[i] = cand
            placed = True
            break
        if placed:
            i += 1
            continue
        # exhausted this block's candidates: backjump to the previous one
        cursor[i] = 0
        chosen[i] = None
        i -= 1
        if i >= 0:
            _log.info("backjumping to %s after exhausting %s", order[i], block)

    if i < 0:
        failed_block = order[0] if order else ""
        return Err(
            NoFeasibleBinding(
                block=failed_block,
                nogoods_considered=len(nogoods),
                message="allocation search exhausted every candidate "
                f"combination ({len(nogoods)} nogoods recorded)",
            )
        )
    pins = tuple(
        PlannerPin(block=b, record_key=c.record_key, content_hash=c.content_hash)
        for b, c in zip(order, chosen, strict=True)
        if c is not None
    )
    return Ok(Bindings(pins=pins))
