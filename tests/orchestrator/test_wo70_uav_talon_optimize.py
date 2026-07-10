"""WO-70 (D183 required surface): a real `regolith optimize` run
pinning `airframe.hema`'s `WingSpar.SparCapFlat.b = in [3mm, 8mm]
minimize` (spar-cap thickness) via the landed continuous golden-
section evaluator over the REALIZED part's own mass -- the same
recipe `tests/orchestrator/test_wo64_printer_optimize.py` proves for
`printer_k1`'s `bed.hema`/`xy_gantry.hema` dims -- and a `by select`
motor-class pin over `propulsion.cupr`'s `PropulsionEsc.impl
MotorClass by select(bl_2814_900kv, bl_3520_650kv, bl_4020_450kv)`,
run against the REAL flagship source's `choice_points` payload (the
`ebi_decode`/`printer_k1.controller.ControllerBoard` recipe,
`domains_from_choice_points` + `optimize_discrete`), under a declared
mass/cost policy. Both produce a real `LockRow.cause = optimize(...)`.
"""

from __future__ import annotations

import json

from regolith import compiler
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    EvalOutcome,
    domains_from_choice_points,
    optimize_continuous_golden_section,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

_AL7075_DENSITY_KG_M3 = 2810.0


def _spar_cap_program(b_m: float, a_m: float = 0.900) -> FeatureProgram:
    """Mirrors `airframe.hema`'s `SparCapFlat` profile (900mm run,
    `b` the optimized cap-thickness dim) and `WingSpar.cut` stage
    (3mm laser-cut AL7075-T6 sheet)."""
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=a_m, y=0.0),
        Point2(x=a_m, y=b_m),
        Point2(x=0.0, y=b_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.003))
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name="WingSpar", material="AL7075_T6", stages=(stage,))


def test_spar_cap_thickness_pinned_by_continuous_optimize(tmp_path) -> None:
    """The spar cap's realized mass grows monotonically with cap
    thickness `b` (fixed 900mm run, fixed 3mm sheet), so the true
    minimizer sits at `b`'s lower bound, 3mm -- the search should
    favor it (WO-70's spar-cap dims `in [lo, hi] minimize` surface)."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (b_m,) = assignment
        realized = realize_feature_program(_spar_cap_program(b_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL7075_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"WingSpar mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.003, 0.008), evaluator=evaluator, budget_evals=40, tol=1e-6
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.0035, f"expected the search to favor 3mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "WingSpar.SparCapFlat.b", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


def test_propulsion_motor_class_select_pin(tmp_path) -> None:
    """The `ebi_decode` discrete-select recipe run against the REAL
    flagship source: `uav_talon.propulsion.PropulsionEsc`'s own `impl
    MotorClass by select(...)` (WO-70's `by select` motor-class
    surface, over a declared candidate list + cost/mass policy)."""
    result = compiler.check(("examples/flagships/uav_talon",))
    assert result.is_ok, result
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert "PropulsionEsc.MotorClass" in choice_points

    # Cost/mass policy (WO-70: "cost/mass policy"): approximate
    # landed-cost + mass proxy per motor class, cheapest/lightest
    # (bl_4020_450kv, the low-KV/high-torque class) should win.
    costs = {
        "PropulsionEsc.MotorClass": {
            "bl_2814_900kv": 42.0,
            "bl_3520_650kv": 58.0,
            "bl_4020_450kv": 39.0,
        }
    }
    domains, evaluator, screen, objective = domains_from_choice_points(
        choice_points, costs
    )
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=0,
        budget_evals=100,
        screen=screen,
        nogood_cache=NogoodCache(),
    )
    assert trace.winner is not None

    store = PayloadStore(str(tmp_path))
    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "PropulsionEsc.MotorClass", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")
