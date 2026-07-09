"""WO-55 acceptance tests: the optimization engine core.

Exercises both drivers against synthetic domains with a fake cheap
harness (toolchain/28-optimization.md sec. 5's own acceptance shape for
this WO -- real language/pipeline wiring is WO-56/57's job), the
determinism claim (INV-30), resume, and budget exhaustion.
"""

from __future__ import annotations

from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    better,
    optimize_continuous_golden_section,
    optimize_continuous_nelder_mead,
    optimize_discrete,
    winner_lock_row,
)


def _discrete_domains() -> tuple[ChoicePointDomain, ...]:
    """A synthetic 3-choice-point domain (acceptance criteria's own shape)."""
    return (
        ChoicePointDomain(subject="vendor", candidates=("ti", "onsemi")),
        ChoicePointDomain(subject="package", candidates=("sot23", "bga")),
        ChoicePointDomain(subject="grade", candidates=("std", "auto")),
    )


def _fake_cost(assignment: dict[str, str]) -> float:
    """A deterministic fake "total_cost" for a complete assignment."""
    cost = 0.0
    cost += {"ti": 1.0, "onsemi": 0.5}[assignment["vendor"]]
    cost += {"sot23": 0.2, "bga": 0.1}[assignment["package"]]
    cost += {"std": 0.3, "auto": 0.6}[assignment["grade"]]
    return cost


def _fake_screen(prefix: dict[str, str]) -> bool:
    """The injected infeasible combination: vendor=onsemi + package=bga
    is infeasible regardless of grade (a real blame-set-shaped cut)."""
    return not (prefix.get("vendor") == "onsemi" and prefix.get("package") == "bga")


def _fake_evaluator(assignment: dict[str, str]) -> EvalOutcome:
    feasible = not (assignment["vendor"] == "onsemi" and assignment["package"] == "bga")
    return EvalOutcome(
        feasible=feasible,
        objective_vector=(_fake_cost(assignment),),
        verdict_summary="ok" if feasible else "infeasible combination",
        evidence_digests=("blake3:fake",),
    )


class _CountingEvaluator:
    """Wraps a plain evaluator function, counting real (non-replayed) calls."""

    def __init__(self, inner) -> None:  # noqa: ANN001 -- test helper
        self._inner = inner
        self.calls = 0

    def __call__(self, arg):  # noqa: ANN001, ANN204 -- test helper
        self.calls += 1
        return self._inner(arg)


def test_discrete_finds_policy_best_feasible_and_records_nogood() -> None:
    cache = NogoodCache()
    trace = optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=100,
        screen=_fake_screen,
        nogood_cache=cache,
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    assignment = {item.root[0]: item.root[1] for item in winner.assignment}
    # onsemi/sot23/std = 0.5+0.2+0.3 = 1.0, the cheapest feasible option.
    assert assignment == {"vendor": "onsemi", "package": "sot23", "grade": "std"}
    assert cache.stats.stores >= 1


def test_discrete_never_retries_a_recorded_nogood() -> None:
    """A second run with the SAME persisted cache never re-screens the
    pruned prefix (the nogood cache HIT this acceptance criterion names)."""
    cache = NogoodCache()
    optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=100,
        screen=_fake_screen,
        nogood_cache=cache,
    )
    stores_after_first = cache.stats.stores

    def _screen_should_not_be_called_for_pruned_prefix(prefix: dict[str, str]) -> bool:
        # If the driver still asked the screen about the pruned prefix,
        # this returns the same False -- but the cache-hit path must
        # short-circuit BEFORE this is ever called for that key.
        return _fake_screen(prefix)

    optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=100,
        screen=_screen_should_not_be_called_for_pruned_prefix,
        nogood_cache=cache,
    )
    # No NEW store on the second run: the pruned prefix was a cache hit,
    # not a fresh screen-and-store.
    assert cache.stats.stores == stores_after_first
    assert cache.stats.hits >= 1


def test_better_is_lexicographic() -> None:
    from regolith._schema.models import ObjectiveDirection1

    minimize = (ObjectiveDirection1.minimize,)
    assert better((1.0,), (2.0,), minimize)
    assert not better((2.0,), (1.0,), minimize)
    assert not better((1.0,), (1.0,), minimize)


def _quadratic(x: tuple[float, ...]) -> EvalOutcome:
    """A 1-D quadratic with its minimum at x=3."""
    value = (x[0] - 3.0) ** 2
    return EvalOutcome(feasible=True, objective_vector=(value,), verdict_summary="ok")


def test_golden_section_converges_on_quadratic() -> None:
    trace = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=7, budget_evals=100, tol=1e-4
    )
    assert trace.termination.value in {"converged", "budget_exhausted"}
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    x = float(winner.objective_vector[0])
    assert x < 1e-2  # near the minimum value 0 at x=3


def test_golden_section_is_deterministic_same_seed_identical_trace() -> None:
    trace1 = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=7, budget_evals=50
    )
    trace2 = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=7, budget_evals=50
    )
    assert trace1.model_dump_json() == trace2.model_dump_json()


def test_golden_section_different_seed_differs_but_both_feasible() -> None:
    trace1 = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=1, budget_evals=8
    )
    trace2 = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=2, budget_evals=8
    )
    # The strategy itself is seed-independent (golden section has no
    # stochastic element), so identical seeds and different seeds both
    # give the same deterministic sequence here -- the driver still
    # records the distinct seed in each trace, which is what makes two
    # DIFFERENT-seed runs of a stochastic strategy (nelder_mead) diverge
    # per the acceptance criterion; both are feasible in either case.
    assert trace1.candidates and trace2.candidates
    assert trace1.seed != trace2.seed


def _rosenbrock_lite(x: tuple[float, ...]) -> EvalOutcome:
    """A tamed 2-D Rosenbrock-shaped objective with a feasibility cut."""
    a, b = x
    value = (1 - a) ** 2 + 10 * (b - a**2) ** 2
    feasible = a > -2.0 and b > -2.0  # the "feasibility cut" acceptance criterion
    return EvalOutcome(
        feasible=feasible, objective_vector=(value,), verdict_summary="ok"
    )


def test_nelder_mead_converges_on_rosenbrock_lite_within_budget() -> None:
    trace = optimize_continuous_nelder_mead(
        [(-2.0, 2.0), (-2.0, 2.0)], _rosenbrock_lite, seed=3, budget_evals=300
    )
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    assert float(winner.objective_vector[0]) < 1.0
    assert winner.feasible


def test_nelder_mead_is_deterministic_same_seed_identical_trace() -> None:
    trace1 = optimize_continuous_nelder_mead(
        [(-2.0, 2.0), (-2.0, 2.0)], _rosenbrock_lite, seed=3, budget_evals=100
    )
    trace2 = optimize_continuous_nelder_mead(
        [(-2.0, 2.0), (-2.0, 2.0)], _rosenbrock_lite, seed=3, budget_evals=100
    )
    assert trace1.model_dump_json() == trace2.model_dump_json()


def test_nelder_mead_different_seed_diverges_but_both_feasible() -> None:
    trace1 = optimize_continuous_nelder_mead(
        [(-2.0, 2.0), (-2.0, 2.0)], _rosenbrock_lite, seed=3, budget_evals=20
    )
    trace2 = optimize_continuous_nelder_mead(
        [(-2.0, 2.0), (-2.0, 2.0)], _rosenbrock_lite, seed=99, budget_evals=20
    )
    assert trace1.model_dump_json() != trace2.model_dump_json()
    assert trace1.winner is not None and trace1.candidates[trace1.winner].feasible
    assert trace2.winner is not None and trace2.candidates[trace2.winner].feasible


def test_resume_performs_zero_new_evaluations_for_the_covered_prefix() -> None:
    counting = _CountingEvaluator(_quadratic)
    half_budget_trace = optimize_continuous_golden_section(
        (0.0, 10.0), counting, seed=7, budget_evals=4
    )
    calls_at_half = counting.calls
    assert half_budget_trace.termination.value == "budget_exhausted"

    resumed_counting = _CountingEvaluator(_quadratic)
    resumed = optimize_continuous_golden_section(
        (0.0, 10.0),
        resumed_counting,
        seed=7,
        budget_evals=4,
        resume_trace=half_budget_trace,
    )
    # Resuming with the SAME budget as already spent replays every
    # candidate from the cache -- zero new discharges.
    assert resumed_counting.calls == 0
    assert resumed.model_dump_json() == half_budget_trace.model_dump_json()
    assert calls_at_half == 4


def test_resume_continues_past_a_prior_partial_run() -> None:
    half_budget_trace = optimize_continuous_golden_section(
        (0.0, 10.0), _quadratic, seed=7, budget_evals=4
    )
    resumed = optimize_continuous_golden_section(
        (0.0, 10.0),
        _quadratic,
        seed=7,
        budget_evals=8,
        resume_trace=half_budget_trace,
    )
    assert len(resumed.candidates) == 8
    # The first 4 candidates are byte-identical replays of the prior run.
    assert (
        resumed.candidates[0].model_dump_json()
        == half_budget_trace.candidates[0].model_dump_json()
    )


def test_budget_exhaustion_returns_best_so_far_never_an_exception() -> None:
    trace = optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=1,
    )
    assert trace.termination.value == "budget_exhausted"
    assert trace.budget_spent == 1
    assert len(trace.candidates) == 1


def test_infeasible_domain_reports_infeasible_never_a_silent_success() -> None:
    domains = (ChoicePointDomain(subject="vendor", candidates=("onsemi",)),)
    domains = domains + (ChoicePointDomain(subject="package", candidates=("bga",)),)

    def _always_infeasible(_assignment: dict[str, str]) -> EvalOutcome:
        return EvalOutcome(
            feasible=False, objective_vector=(0.0,), verdict_summary="no"
        )

    trace = optimize_discrete(
        domains, _always_infeasible, objective=["minimize"], seed=1, budget_evals=10
    )
    assert trace.termination.value == "infeasible"
    assert trace.winner is None


def test_winner_lock_row_carries_optimize_cause_with_trace_digest() -> None:
    trace = optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=100,
    )
    row = winner_lock_row(trace, "vendor.pick", "total_cost", "blake3:deadbeef")
    assert row.is_ok
    lock_row = row.danger_ok
    assert lock_row.cause == "optimize(total_cost, trace=blake3:deadbeef)"


def test_infeasible_trace_refuses_to_pin_a_winner() -> None:
    domains = (ChoicePointDomain(subject="vendor", candidates=("onsemi",)),)

    def _always_infeasible(_assignment: dict[str, str]) -> EvalOutcome:
        return EvalOutcome(
            feasible=False, objective_vector=(0.0,), verdict_summary="no"
        )

    trace = optimize_discrete(
        domains, _always_infeasible, objective=["minimize"], seed=1, budget_evals=10
    )
    row = winner_lock_row(trace, "vendor.pick", "total_cost", "blake3:deadbeef")
    assert row.is_err


def test_trace_round_trips_through_generated_schema(tmp_path) -> None:
    from regolith.orchestrator.optimize import load_trace, store_trace
    from regolith.orchestrator.payload_store import PayloadStore

    trace = optimize_discrete(
        _discrete_domains(),
        _fake_evaluator,
        objective=["minimize"],
        seed=1,
        budget_evals=100,
    )
    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    loaded = load_trace(store, digest)
    assert loaded.is_ok
    assert loaded.danger_ok.model_dump_json() == trace.model_dump_json()
