"""The optimization engine (WO-55; toolchain/28-optimization.md, AD-30).

ONE engine home (`regolith.orchestrator.optimize`, AD-1): two drivers,
one contract. `optimize_discrete` is a policy-ordered greedy/backjumping
search over declared candidate domains (`ChoicePoint`-shaped: registry
queries, `by select(...)` lists -- D161, WO-56); `optimize_continuous`
is bounded `in [lo, hi]` refinement via in-house, deterministic, seeded
strategies (`golden_section`, `nelder_mead`; no scipy, AD-30).

Evaluation IS the pipeline (charter sec. 1.2): neither driver ever
scores a candidate itself. Both take an ``Evaluator`` callable that the
CALLER wires to the real `build`/`staged_build` + discharge path (T2
tier); this module only ever calls the injected evaluator, never
touches the compiler or harness directly. This is the seam WO-57 (the
staged-loop realized-domain optimizer) plugs `staged_build` into without
any change here: it only needs a different ``Evaluator`` closure, same
driver signatures.

Objective extraction (deliverable 2) is likewise a caller-supplied
``tuple[ObjectiveDirection, ...]`` in declared lexicographic order
(regolith/03 sec. 2, regolith/12 sec. 4: per-variable `minimize`/
`maximize`, then a `policy: minimize` list) -- this module never parses
`policy:` blocks itself (no new grammar); WO-56/57 are the callers that
read the lowered payload/lockfile surfaces and build this tuple.

Determinism (INV-30): every domain is an ordered ``tuple`` (AD-6), every
strategy is a pure seeded function, and the trace is content-addressed
(`OptimizationTrace.content_digest`-equivalent: `PayloadStore.put`'s
fresh blake3 of the JSON bytes -- the WO-42/WO-54 precedent for
Python-produced payloads with no Rust-computed AD-18 digest to
reproduce, `costing.py::persist_estimates`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    AssignmentItem,
    CandidateEntry,
    ObjectiveDirection1,
    ObjectiveDirection2,
    OptimizationTrace,
    TerminationStatus1,
    TerminationStatus2,
    TerminationStatus3,
)
from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# The D96 payload kind an `OptimizationTrace` is stored/pinned under
# (charter sec. 1.4; the vocabulary lives free-form on `PayloadRef.kind`
# -- see `harness/payloads.py`'s docstring for why this one is NOT in
# that pack-signature tuple: it is an orchestrator-internal ref kind,
# never a solver-pack input/output port).
OPTIMIZE_TRACE_PAYLOAD_KIND = "optimize.trace"
OPTIMIZE_CHOICE_PAYLOAD_KIND = "optimize.choice"

ObjectiveDirection = ObjectiveDirection1 | ObjectiveDirection2
TerminationStatus = TerminationStatus1 | TerminationStatus2 | TerminationStatus3

# This driver's own version, folded into every trace it emits (INV-30:
# "a strategy version bump is itself a declared input"). Bump on any
# behavior change to the search order.
DISCRETE_STRATEGY_VERSION = "1"
GOLDEN_SECTION_STRATEGY_VERSION = "1"
NELDER_MEAD_STRATEGY_VERSION = "1"

# Golden ratio constant for `golden_section` (standard 1-D bracketing).
_GOLDEN_RATIO = (5**0.5 - 1) / 2


class EvalOutcome(BaseModel):
    """One evaluator call's result: feasibility + the objective vector.

    ``feasible`` is "all demands dischargeable" (charter sec. 1.3,
    applied strictly first); ``objective_vector`` has one entry per
    declared objective component, same order. ``verdict_summary`` and
    ``evidence_digests`` are the trace's audit trail back to the real
    evidence store (never re-derived from this value alone).
    """

    model_config = ConfigDict(frozen=True)

    feasible: bool
    objective_vector: tuple[float, ...]
    verdict_summary: str = ""
    evidence_digests: tuple[str, ...] = ()


# The discrete driver's domain shape: a `ChoicePoint`-equivalent -- a
# subject id plus its closed, ordered candidate list (D161; registry
# queries and `by select(...)` lists both reach the driver as this same
# shape, per the charter's "all reach the driver as the same
# domain-of-candidates shape").
class ChoicePointDomain(BaseModel):
    """One discrete decision: a subject and its ordered candidate list."""

    model_config = ConfigDict(frozen=True)

    subject: str
    candidates: tuple[str, ...]


Assignment = tuple[tuple[str, str], ...]  # ((subject, candidate), ...), declared order

# The full evaluator: called ONLY on complete assignments (lazy full
# discharge, charter sec. 1.1). The caller wires this to `build`/
# `staged_build` + `discharge_all` (T2 tier); this module never calls
# the compiler/harness directly (AD-22's private-scoring-path ban).
DiscreteEvaluator = Callable[[Mapping[str, str]], EvalOutcome]

# An OPTIONAL cheap-tier screen over a PARTIAL assignment (charter sec.
# 1.1 step 1: "screened only by the cheap tier"): returns False iff the
# partial assignment is already known infeasible regardless of how the
# remaining domains are filled in. This is what makes backjumping/nogood
# pruning real instead of degenerating to full enumeration -- a `None`
# screen means every candidate reaches full evaluation once complete.
CheapScreen = Callable[[Mapping[str, str]], bool]

# The continuous evaluator: an N-tuple of bounded values in, one
# `EvalOutcome` out.
ContinuousEvaluator = Callable[[tuple[float, ...]], EvalOutcome]


def _direction_value(direction: ObjectiveDirection) -> Literal["minimize", "maximize"]:
    """The direction's plain string, whichever split-enum arm it is."""
    return "minimize" if direction.value == "minimize" else "maximize"


def better(
    a: tuple[float, ...],
    b: tuple[float, ...],
    objective: tuple[ObjectiveDirection, ...],
) -> bool:
    """True iff `a` beats `b` under `objective`'s lexicographic order.

    Compares component 0 first; ties fall through to component 1, and so
    on (regolith/12 sec. 4: "lexicographic, after all claims are
    satisfiable"). A component list shorter than the vectors compares
    only the covered prefix (defensive; callers keep lengths equal).
    """
    for direction, av, bv in zip(objective, a, b, strict=False):
        if av == bv:
            continue
        if _direction_value(direction) == "minimize":
            return av < bv
        return av > bv
    return False


def _partial_key(prefix: Assignment) -> str:
    """A stable string key for a (partial) assignment prefix.

    Domain-of-candidates search state today; when WO-56 wires registry
    candidates the key folds consumed record revisions too (the D75
    discipline `nogood_cache_key` already implements for the harness's
    own allocation search) -- tracked as a WO-56 integration item, not
    invented here (no registry records exist to fold yet in this WO's
    synthetic-domain scope).
    """
    return "|".join(f"{subject}={candidate}" for subject, candidate in prefix)


def _termination(status: Literal["converged", "budget_exhausted", "infeasible"]):
    if status == "converged":
        return TerminationStatus1.converged
    if status == "budget_exhausted":
        return TerminationStatus2.budget_exhausted
    return TerminationStatus3.infeasible


def _objective_direction(
    direction: Literal["minimize", "maximize"],
) -> ObjectiveDirection:
    return (
        ObjectiveDirection1.minimize
        if direction == "minimize"
        else ObjectiveDirection2.maximize
    )


class _ReplayEvaluator:
    """Wraps an evaluator so a `--resume` run replays cached candidates.

    Deliverable 5: "`--resume <trace>` skips evaluated candidates
    (evidence-cache hits, zero new discharges)". Both drivers are
    deterministic given the same seed/budget/domain (INV-30), so a
    resumed run proposes the EXACT same sequence of candidates for as
    many steps as the prior run covered; this wrapper serves those steps
    straight from `resume_trace.candidates` (by call order) and only
    calls the real evaluator once the replay is exhausted, counting only
    those as `new_evaluations` (the resume test's own assertion).
    """

    def __init__(
        self,
        evaluator: Callable[..., EvalOutcome],
        resume_trace: OptimizationTrace | None,
    ) -> None:
        self._evaluator = evaluator
        self._cached: tuple[CandidateEntry, ...] = (
            tuple(resume_trace.candidates) if resume_trace is not None else ()
        )
        self._calls = 0
        self.new_evaluations = 0

    def __call__(self, arg: object) -> EvalOutcome:
        index = self._calls
        self._calls += 1
        if index < len(self._cached):
            cached = self._cached[index]
            _log.debug(
                "optimize: resume replay hit for candidate #%d (no discharge)", index
            )
            return EvalOutcome(
                feasible=cached.feasible,
                objective_vector=tuple(cached.objective_vector),
                verdict_summary=cached.verdict_summary,
                evidence_digests=tuple(cached.evidence_digests),
            )
        self.new_evaluations += 1
        return self._evaluator(arg)


def _candidate_entry(assignment: Assignment, outcome: EvalOutcome) -> CandidateEntry:
    return CandidateEntry(
        assignment=[
            AssignmentItem([subject, candidate]) for subject, candidate in assignment
        ],
        objective_vector=list(outcome.objective_vector),
        feasible=outcome.feasible,
        verdict_summary=outcome.verdict_summary,
        evidence_digests=list(outcome.evidence_digests),
    )


def optimize_discrete(
    domains: Sequence[ChoicePointDomain],
    evaluator: DiscreteEvaluator,
    objective: Sequence[Literal["minimize", "maximize"]],
    *,
    seed: int = 0,
    budget_evals: int,
    screen: CheapScreen | None = None,
    nogood_cache: NogoodCache | None = None,
    resume_trace: OptimizationTrace | None = None,
) -> OptimizationTrace:
    """Conflict-driven greedy search over `domains` (regolith/07 sec. 7).

    Enumerates candidate combinations depth-first in each domain's
    DECLARED order (AD-6 source-ordered enumeration -- `seed` is
    accepted and recorded for interface uniformity with the continuous
    driver and future randomized tie-breaking, but v1's discrete order
    is deterministic from declaration order alone). Before descending
    into domain `i+1`, `screen` (if given) is consulted on the partial
    assignment so far -- a `False` result is recorded as a nogood
    (`nogood_cache`, D75's persistence class) and the ENTIRE subtree
    under that prefix is pruned without ever calling `evaluator`
    (backjumping: the prefix IS the blame set here, since a fake/cheap
    harness names no finer-grained blame). Complete assignments always
    reach `evaluator` (lazy full discharge) exactly once each, in
    depth-first order, budget-permitting.

    Termination: `converged` when the whole (unpruned) domain was
    enumerated inside budget; `budget_exhausted` when the evaluation cap
    was hit first (best-feasible-so-far is still the winner);
    `infeasible` when every reachable leaf was infeasible.
    """
    replay = _ReplayEvaluator(evaluator, resume_trace)
    candidates: list[CandidateEntry] = []
    nogood_keys: list[str] = []
    best_index: int | None = None
    best_vector: tuple[float, ...] | None = None
    exhausted = True
    budget_hit = False

    directions = tuple(_objective_direction(d) for d in objective)

    def visit(depth: int, prefix: Assignment) -> None:
        nonlocal best_index, best_vector, exhausted, budget_hit
        if budget_hit:
            return
        if depth == len(domains):
            if len(candidates) >= budget_evals:
                budget_hit = True
                exhausted = False
                return
            outcome = replay(dict(prefix))
            entry = _candidate_entry(prefix, outcome)
            candidates.append(entry)
            if outcome.feasible and (
                best_vector is None
                or better(outcome.objective_vector, best_vector, directions)
            ):
                best_index = len(candidates) - 1
                best_vector = outcome.objective_vector
            return

        if screen is not None and prefix:
            key = _partial_key(prefix)
            cache_hit = (
                nogood_cache.get(key)
                if nogood_cache is not None
                else key in nogood_keys
            )
            if cache_hit:
                _log.info("optimize_discrete: nogood cache hit, pruning %s", key)
                return
            if not screen(dict(prefix)):
                _log.info("optimize_discrete: cheap screen rejects prefix %s", key)
                nogood_keys.append(key)
                if nogood_cache is not None:
                    nogood_cache.put(key)
                return

        for candidate in domains[depth].candidates:
            if budget_hit:
                return
            visit(depth + 1, prefix + ((domains[depth].subject, candidate),))

    visit(0, ())

    if best_index is not None:
        status = "converged" if exhausted else "budget_exhausted"
    elif budget_hit:
        status = "budget_exhausted"
    else:
        status = "infeasible"

    trace = OptimizationTrace(
        strategy_id="optimize_discrete",
        strategy_version=DISCRETE_STRATEGY_VERSION,
        seed=seed,
        budget_declared=budget_evals,
        budget_spent=len(candidates),
        objective=list(directions),
        candidates=candidates,
        nogood_keys=nogood_keys,
        winner=best_index,
        termination=_termination(status),
    )
    _log.info(
        "optimize_discrete: %d candidate(s) evaluated, %d nogood(s), termination=%s",
        len(candidates),
        len(nogood_keys),
        status,
    )
    return trace


def _splitmix64(seed: int, index: int) -> float:
    """A tiny deterministic PRNG (splitmix64) mapped to `[0, 1)`.

    In-house, seeded, and platform-independent (INV-30/AD-30: no
    third-party RNG, no OS entropy) -- used only for deterministic
    initial-simplex jitter in `nelder_mead`.
    """
    z = (seed + index * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    z = z ^ (z >> 31)
    return (z & 0xFFFFFFFF) / 0xFFFFFFFF


def optimize_continuous_golden_section(
    bounds: tuple[float, float],
    evaluator: ContinuousEvaluator,
    *,
    seed: int = 0,
    budget_evals: int,
    tol: float = 1e-6,
    resume_trace: OptimizationTrace | None = None,
) -> OptimizationTrace:
    """1-D golden-section search over `bounds = (lo, hi)` (charter sec. 1.1).

    A pure, deterministic proposer: each round narrows the bracket by
    the golden ratio and reuses one of the two interior evaluations
    (the standard algorithm), so a converged run makes exactly two new
    evaluations per round after the first. Feasibility: an infeasible
    candidate's objective is treated as `+inf`/`-inf` (whichever the
    single objective direction disfavors) so the search steers away from
    it without ever silently accepting an infeasible winner.
    """
    replay = _ReplayEvaluator(evaluator, resume_trace)
    lo, hi = bounds
    direction = ObjectiveDirection1.minimize
    candidates: list[CandidateEntry] = []
    best_index: int | None = None
    best_score: float = float("inf")
    budget_hit = False

    def evaluate(x: float) -> float:
        """Evaluate `x` and record its candidate; caller must budget-check first."""
        nonlocal best_index, best_score
        outcome = replay((x,))
        entry = _candidate_entry((("x", repr(x)),), outcome)
        candidates.append(entry)
        s = outcome.objective_vector[0] if outcome.feasible else float("inf")
        if s < best_score:
            best_score = s
            best_index = len(candidates) - 1
        return s

    def try_evaluate(x: float) -> float | None:
        """`evaluate(x)`, or `None` (and sets `budget_hit`) if out of budget."""
        nonlocal budget_hit
        if len(candidates) >= budget_evals:
            budget_hit = True
            return None
        return evaluate(x)

    c = hi - _GOLDEN_RATIO * (hi - lo)
    d = lo + _GOLDEN_RATIO * (hi - lo)
    score_c = try_evaluate(c)
    score_d = try_evaluate(d) if score_c is not None else None

    converged = False
    while score_c is not None and score_d is not None and (hi - lo) > tol:
        if score_c < score_d:
            hi, d, score_d = d, c, score_c
            c = hi - _GOLDEN_RATIO * (hi - lo)
            score_c = try_evaluate(c)
        else:
            lo, c, score_c = c, d, score_d
            d = lo + _GOLDEN_RATIO * (hi - lo)
            score_d = try_evaluate(d)
    else:
        if not budget_hit:
            converged = True

    status = "converged" if converged else "budget_exhausted"
    if best_index is None:
        status = "infeasible" if not budget_hit else "budget_exhausted"

    trace = OptimizationTrace(
        strategy_id="optimize_continuous.golden_section",
        strategy_version=GOLDEN_SECTION_STRATEGY_VERSION,
        seed=seed,
        budget_declared=budget_evals,
        budget_spent=len(candidates),
        objective=[direction],
        candidates=candidates,
        nogood_keys=[],
        winner=best_index,
        termination=_termination(status),
    )
    _log.info(
        "optimize_continuous.golden_section: %d evaluation(s), termination=%s",
        len(candidates),
        status,
    )
    return trace


def optimize_continuous_nelder_mead(
    bounds: Sequence[tuple[float, float]],
    evaluator: ContinuousEvaluator,
    *,
    seed: int = 0,
    budget_evals: int,
    max_no_improve: int = 20,
    resume_trace: OptimizationTrace | None = None,
) -> OptimizationTrace:
    """N-D Nelder-Mead simplex search (charter sec. 1.1): reflect/expand/
    contract/shrink, deterministic seeded initialization from `bounds`'s
    corners plus a small `_splitmix64` jitter (never true randomness).

    Feasibility cut: an infeasible vertex scores `+inf`, so the simplex
    is repelled from infeasible regions without ever adopting one as the
    winner; convergence is declared after `max_no_improve` consecutive
    rounds with no improving vertex, or the budget is exhausted first.
    """
    n = len(bounds)
    replay = _ReplayEvaluator(evaluator, resume_trace)
    candidates: list[CandidateEntry] = []
    directions = [ObjectiveDirection1.minimize] * n

    def clamp(point: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(
            min(max(v, lo), hi) for v, (lo, hi) in zip(point, bounds, strict=True)
        )

    def evaluate(point: tuple[float, ...]) -> float:
        clamped = clamp(point)
        outcome = replay(clamped)
        entry = _candidate_entry(
            tuple((f"x{i}", repr(v)) for i, v in enumerate(clamped)), outcome
        )
        candidates.append(entry)
        return outcome.objective_vector[0] if outcome.feasible else float("inf")

    # Deterministic initial simplex: each bounds corner-derived vertex,
    # perturbed by a tiny seeded jitter fraction of the bound span so the
    # n+1 vertices are never degenerate.
    base = tuple(lo + 0.5 * (hi - lo) for lo, hi in bounds)
    simplex: list[tuple[float, ...]] = [base]
    for i in range(n):
        lo, hi = bounds[i]
        jitter = 0.25 * (hi - lo) * (_splitmix64(seed, i + 1) - 0.5)
        vertex = tuple(v + (jitter if j == i else 0.0) for j, v in enumerate(base))
        simplex.append(vertex)

    scores = [evaluate(v) for v in simplex]
    budget_hit = len(candidates) >= budget_evals
    no_improve = 0
    converged = False

    while not budget_hit and no_improve < max_no_improve:
        order = sorted(range(len(simplex)), key=lambda i: scores[i])
        simplex = [simplex[i] for i in order]
        scores = [scores[i] for i in order]
        best_score = scores[0]

        centroid = tuple(sum(v[i] for v in simplex[:-1]) / n for i in range(n))
        worst = simplex[-1]
        reflected = tuple(
            centroid[i] + 1.0 * (centroid[i] - worst[i]) for i in range(n)
        )
        if len(candidates) >= budget_evals:
            budget_hit = True
            break
        reflected_score = evaluate(reflected)

        if reflected_score < scores[0]:
            expanded = tuple(
                centroid[i] + 2.0 * (reflected[i] - centroid[i]) for i in range(n)
            )
            if len(candidates) < budget_evals:
                expanded_score = evaluate(expanded)
                if expanded_score < reflected_score:
                    simplex[-1], scores[-1] = expanded, expanded_score
                else:
                    simplex[-1], scores[-1] = reflected, reflected_score
            else:
                simplex[-1], scores[-1] = reflected, reflected_score
                budget_hit = True
        elif reflected_score < scores[-2]:
            simplex[-1], scores[-1] = reflected, reflected_score
        else:
            contracted = tuple(
                centroid[i] + 0.5 * (worst[i] - centroid[i]) for i in range(n)
            )
            if len(candidates) >= budget_evals:
                budget_hit = True
                break
            contracted_score = evaluate(contracted)
            if contracted_score < scores[-1]:
                simplex[-1], scores[-1] = contracted, contracted_score
            else:
                shrunk = []
                shrunk_scores = []
                for v in simplex:
                    point = tuple(
                        simplex[0][i] + 0.5 * (v[i] - simplex[0][i]) for i in range(n)
                    )
                    if len(candidates) >= budget_evals:
                        budget_hit = True
                        shrunk.append(point)
                        shrunk_scores.append(float("inf"))
                        continue
                    shrunk.append(point)
                    shrunk_scores.append(evaluate(point))
                simplex, scores = shrunk, shrunk_scores

        if min(scores) < best_score - 1e-12:
            no_improve = 0
        else:
            no_improve += 1

    if not budget_hit and no_improve >= max_no_improve:
        converged = True

    best_score = min(scores) if scores else float("inf")
    best_vertex_index = scores.index(best_score) if scores else None
    # Map back to the last CandidateEntry for that exact vertex/score:
    # the most recent candidate with a matching feasible score.
    best_index: int | None = None
    if best_vertex_index is not None and best_score != float("inf"):
        for idx in range(len(candidates) - 1, -1, -1):
            if (
                candidates[idx].feasible
                and abs(candidates[idx].objective_vector[0] - best_score) < 1e-9
            ):
                best_index = idx
                break

    status = "converged" if converged else "budget_exhausted"
    if best_index is None:
        status = "infeasible" if not budget_hit else "budget_exhausted"

    trace = OptimizationTrace(
        strategy_id="optimize_continuous.nelder_mead",
        strategy_version=NELDER_MEAD_STRATEGY_VERSION,
        seed=seed,
        budget_declared=budget_evals,
        budget_spent=len(candidates),
        objective=list(directions),
        candidates=candidates,
        nogood_keys=[],
        winner=best_index,
        termination=_termination(status),
    )
    _log.info(
        "optimize_continuous.nelder_mead: %d evaluation(s), termination=%s",
        len(candidates),
        status,
    )
    return trace


def store_trace(store: PayloadStore, trace: OptimizationTrace) -> str:
    """Persist `trace` to the D96 payload store, returning its digest.

    `PayloadStore.put` (fresh blake3 of the JSON bytes) -- the WO-42/
    WO-54 precedent for Python-produced payloads with no Rust-computed
    AD-18 digest to reproduce (`costing.py::persist_estimates`).
    """
    data = trace.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.info(
        "optimize: stored trace %s (%d candidate(s))", digest, len(trace.candidates)
    )
    return digest


def load_trace(
    store: PayloadStore, digest: str
) -> Result[OptimizationTrace, OrchestratorError]:
    """Resolve a previously stored trace by digest (the `--resume` input)."""
    resolved = store.resolve(digest)
    if resolved.is_err:
        return Err(resolved.danger_err)
    return Ok(OptimizationTrace.model_validate_json(resolved.danger_ok))


def winner_lock_row(
    trace: OptimizationTrace, slot: str, objective_name: str, trace_digest: str
) -> Result[LockRow, OrchestratorError]:
    """The lockfile row pinning `trace`'s winner (charter sec. 1.5, INV-21):
    `cause: optimize(<objective>, trace=<digest>)`. An `Infeasible` trace
    (no winner) is an `Err` -- there is nothing honest to pin.
    """
    if trace.winner is None:
        return Err(
            OrchestratorError(
                kind="optimize_infeasible",
                message="cannot pin a winner: optimization trace has no feasible "
                "candidate",
            )
        )
    winner = trace.candidates[trace.winner]
    value = ", ".join(f"{item.root[0]}={item.root[1]}" for item in winner.assignment)
    return Ok(
        LockRow(
            slot=slot,
            value=value,
            cause=f"optimize({objective_name}, trace={trace_digest})",
        )
    )


def discrete_domains_from_spec(
    spec: Mapping[str, object],
) -> tuple[
    tuple[ChoicePointDomain, ...],
    DiscreteEvaluator,
    CheapScreen,
    list[Literal["minimize", "maximize"]],
]:
    """Build a `(domains, evaluator, screen, objective)` tuple from a
    closed-form JSON spec (the CLI's `regolith optimize --spec` input):

        {"domains": [{"subject": "vendor", "candidates": ["ti", "onsemi"]}],
         "costs": {"vendor": {"ti": 1.0, "onsemi": 0.5}},
         "infeasible_prefixes": [{"vendor": "onsemi", "package": "bga"}],
         "objective": ["minimize"]}

    This is a PLACEHOLDER evaluator surface for the CLI to be exercisable
    end to end today: it sums declared `costs` per candidate (a closed
    form, never arbitrary code -- no `eval`), and treats an assignment as
    infeasible iff it is a superset of any `infeasible_prefixes` entry.
    WO-56 replaces this with real objective extraction from the lowered
    payload/lockfile surfaces (`policy:` blocks, `by select(...)`
    candidates) and real pipeline evaluation (`build`/`staged_build` +
    discharge) -- this module's driver signatures do not change; only
    the caller wiring here does.
    """
    domains_raw = cast("list[dict[str, object]]", spec.get("domains", []))
    domains = tuple(
        ChoicePointDomain(
            subject=str(row["subject"]),
            candidates=tuple(str(c) for c in cast("list[object]", row["candidates"])),
        )
        for row in domains_raw
    )
    costs = cast("dict[str, dict[str, object]]", spec.get("costs", {}))
    infeasible_prefixes = cast(
        "list[dict[str, object]]", spec.get("infeasible_prefixes", [])
    )
    objective = cast(
        'list[Literal["minimize", "maximize"]]',
        [str(d) for d in cast("list[object]", spec.get("objective", ["minimize"]))],
    )

    def _cost(assignment: Mapping[str, str]) -> float:
        total = 0.0
        for subject, candidate in assignment.items():
            table = costs.get(subject, {})
            total += float(cast("float", table.get(candidate, 0.0)))
        return total

    def _matches_infeasible(partial: Mapping[str, str]) -> bool:
        for prefix in infeasible_prefixes:
            if all(partial.get(k) == v for k, v in prefix.items()):
                return True
        return False

    def evaluator(assignment: Mapping[str, str]) -> EvalOutcome:
        feasible = not _matches_infeasible(assignment)
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(_cost(assignment),),
            verdict_summary="ok"
            if feasible
            else "matches an infeasible_prefixes entry",
        )

    def screen(partial: Mapping[str, str]) -> bool:
        return not _matches_infeasible(partial)

    return domains, evaluator, screen, objective
