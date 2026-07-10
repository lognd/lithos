"""WO-64 phase B: two `in [lo, hi] minimize` dims pinned via the
landed continuous golden-section evaluator (mirrors
`tests/orchestrator/test_wo62_assembly_composition.py`'s recipe --
`duct_vane` per the WO body's phrasing does not exist as a corpus
member yet, `tests/backends/test_parity.py`'s own module docstring
records the same substitution) and the `AddressDecodeGlue by select`
pin over the REAL `printer_k1.controller.ControllerBoard` (the
`ebi_decode` recipe, `tests/backends/test_parity.py`'s
`test_ebi_decode_optimize_cause_classifies_as_optimize`, run here
against the flagship's own source instead of the standalone
`ebi_decode.cupr` exemplar). All three produce a real `regolith.lock`
row with `cause: optimize(...)` -- the parity ledger's own decision
provenance class.

The two continuous dims: `bed.hema`'s `BedPlateFlat.a` (`in [220mm,
240mm] minimize`) and `xy_gantry.hema`'s `CarriagePlateFlat.b` (`in
[35mm, 45mm] minimize`). Both minimize the realized part's own mass
(volume x density), so the true minimizer sits at each dim's lower
bound -- exactly `test_wo62_assembly_composition.py`'s own assertion
shape.
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

_AL_DENSITY_KG_M3 = 2700.0


def _plate_program(a_m: float, b_m: float = 0.230) -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=a_m, y=0.0),
        Point2(x=a_m, y=b_m),
        Point2(x=0.0, y=b_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.004))
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(
        part_name="HeatedBed", material="AL5083_H111", stages=(stage,)
    )


def test_bed_plate_edge_length_pinned_by_continuous_optimize(tmp_path) -> None:
    """`bed.hema`'s `BedPlateFlat.a = in [220mm, 240mm] minimize`: the
    plate's mass grows monotonically with `a` (fixed thickness/depth),
    so the search should land near the lower bound, 220mm."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (a_m,) = assignment
        realized = realize_feature_program(_plate_program(a_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"HeatedBed mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.220, 0.240), evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.225, f"expected the search to favor 220mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "HeatedBed.BedPlateFlat.a", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


def test_xy_carriage_plate_edge_length_pinned_by_continuous_optimize(tmp_path) -> None:
    """`xy_gantry.hema`'s `CarriagePlateFlat.b = in [35mm, 45mm]
    minimize`, the second declared continuous dim (WO body: "at least
    two")."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (b_m,) = assignment
        realized = realize_feature_program(_plate_program(0.060, b_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"XCarriage mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.035, 0.045), evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.040, f"expected the search to favor 35mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "XCarriage.CarriagePlateFlat.b", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


def test_printer_k1_controller_address_decode_glue_select_pin(tmp_path) -> None:
    """The `ebi_decode` recipe run against the REAL flagship source:
    `printer_k1.controller.ControllerBoard`'s own `impl
    AddressDecodeGlue by select(...)` (carried over verbatim from
    `ebi_decode.cupr`, `controller.cupr`'s own header comment)."""
    result = compiler.check(("examples/flagships/printer_k1",))
    assert result.is_ok, result
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert "ControllerBoard.AddressDecodeGlue" in choice_points

    costs = {
        "ControllerBoard.AddressDecodeGlue": {
            "nor_glue": 2.40,
            "cpld": 1.10,
            "mcu_chip_selects": 0.0,
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
        trace, "ControllerBoard.AddressDecodeGlue", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")
