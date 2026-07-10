"""WO-93 flagship promotion: one real `in [lo, hi] minimize` continuous
optimizer pin over the compiled `examples/flagships/cubesat/` design,
mirroring `tests/orchestrator/test_wo64_printer_optimize.py`'s recipe
(the golden-section evaluator over a hand-built `FeatureProgram`,
`bed.hema`'s own precedent for the same v1-promotion-surface gap:
`solve.sketch.promote` cannot thread `in [lo, hi] minimize` through
the walk promoter yet, WO-64's own recorded wall, so the pin is
proven directly against the realizer the way every flagship in the
fleet already does).

`structure.hema`'s `PanelOutline.a` (`in [94mm, 96mm] minimize`): the
90mm `CardBay` bolt patterns need >= 94mm of panel width for edge
margin, and the CubeSat Design Specification's panel-width tolerance
allows shrinking from the fixed 96mm envelope down to that floor.
`SidePanel`'s mass grows monotonically with `a` at fixed thickness
(1.2mm) and depth (96mm), so golden-section search should land near
the 94mm lower bound.
"""

from __future__ import annotations

from regolith.orchestrator.optimize import (
    EvalOutcome,
    optimize_continuous_golden_section,
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

_AL6061_T6_DENSITY_KG_M3 = 2700.0
_PANEL_THICKNESS_M = 0.0012
_PANEL_DEPTH_M = 0.096


def _panel_program(a_m: float) -> FeatureProgram:
    """A flat `SidePanel` blank at edge length `a_m` x the fixed 96mm
    depth, laser-cut at the corpus's declared 1.2mm sheet thickness."""
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=a_m, y=0.0),
        Point2(x=a_m, y=_PANEL_DEPTH_M),
        Point2(x=0.0, y=_PANEL_DEPTH_M),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=_PANEL_THICKNESS_M)
    )
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name="SidePanel", material="AL6061_T6", stages=(stage,))


def test_side_panel_edge_length_pinned_by_continuous_optimize(tmp_path) -> None:
    """`structure.hema`'s `PanelOutline.a = in [94mm, 96mm] minimize`
    discharges via the landed continuous golden-section evaluator,
    producing a real `regolith.lock` row with `cause: optimize(...)`."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (a_m,) = assignment
        realized = realize_feature_program(_panel_program(a_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL6061_T6_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"SidePanel mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.094, 0.096), evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.095, f"expected the search to favor 94mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "SidePanel.PanelOutline.a", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")
