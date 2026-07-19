"""WO-77 acceptance (charter 34 phase 1, D200): the declared
material-removal vocabulary end to end.

- The `ribbed_panel.hema` fixture's emitted ``FeatureProgram`` carries
  the `Ribs` op with planner-tagged bounded `count`/`thickness` slots.
- The optimizer pins BOTH through EXISTING machinery only -- the
  cycle-30 discrete driver over the integer `count` bounds composed
  with golden-section over the `thickness` interval, every candidate
  REALIZED through the real OCCT interpreter (mass is measured, never
  synthesized) -- and the winners pin as lockfile rows with
  ``cause: optimize(mass, trace=<digest>)`` (INV-21).
- The `std.removal` DFM rows fire on an infeasible LITERAL twin
  (charter: "manufacturability is not optional").
- Promotion honesty: literal `PocketGrid`/`Shell` parts convert and
  realize with no hand-authored program; the bounded-`Ribs` part and
  the `Lattice` part stay pending with their reasons NAMED.
"""

from __future__ import annotations

import json
import logging
import re

from regolith import compiler
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    OptimizationTrace,
    optimize_continuous_golden_section,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.programs import emitted_realizer_programs
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    BlankOp,
    FeatureProgram,
    Point2,
    ResolvedParam,
    RibsOp,
    Sketch,
    Stage,
)

_FIXTURE = "examples/tracks/hematite/ribbed_panel.hema"
_PACK = "examples/tracks/hematite/std_removal.hema"

# The fixture panel: 120mm x 80mm x 18mm AL 6061 (see ribbed_panel.hema).
_L, _W, _T = 0.120, 0.080, 0.018
_AL_DENSITY_KG_M3 = 2700.0
# The test's stand-in feasibility floor (the FEA-class stiffness claim's
# role in the charter's story): a rib section proxy count * t_mm^3 >= K.
# K = 250 puts the per-count optimal thickness at (K/count)^(1/3) mm --
# interior to the fixture's declared [2mm, 5mm] for every count in
# [4, 8], so the winner is decided by the search, not by a bound.
_STIFFNESS_FLOOR = 250.0


def _check_fixture() -> dict:
    out = compiler.check(
        (
            _FIXTURE,
            _PACK,
        )
    )
    assert out.is_ok, out
    return json.loads(out.danger_ok.payload_json)


def _ribs_op_params(payload: dict) -> dict:
    program = next(
        p for p in payload["feature_programs"] if p["part_name"] == "RibbedPanel"
    )
    op = next(f for f in program["features"] if f["kind"] == "ribs")
    return op["params"]


def test_the_fixture_program_carries_the_bounded_ribs_op() -> None:
    """Acceptance line 1a: FeatureProgram carries the op, bounded slots
    planner-tagged, literals literal -- and the whole fixture compiles
    with ZERO diagnostics (the DFM rows defer on bounds, never guess)."""
    payload = _check_fixture()
    assert payload["diagnostics"] == []
    params = _ribs_op_params(payload)
    assert params["count"]["text"] == "[4, 8]"
    assert params["count"]["cause"] == "planner"
    assert params["thickness"]["text"] == "[2mm, 5mm]"
    assert params["thickness"]["cause"] == "planner"
    assert params["pitch"]["cause"] == "literal"
    assert params["height"]["text"] == "12mm"


def _panel_program(count: int, thickness_m: float) -> FeatureProgram:
    """The RibbedPanel realizer program at one pinned candidate --
    exactly what the staged evaluator realizes once the planner slots
    are pinned (the WO-62 composition-proof shape)."""
    sketch = Sketch(
        name="PanelOutline",
        outline=(
            Point2(x=0.0, y=0.0),
            Point2(x=_L, y=0.0),
            Point2(x=_L, y=_W),
            Point2(x=0.0, y=_W),
        ),
    )
    body = BlankOp(name="body", sketch=sketch, thickness=ResolvedParam(value=_T))
    ribs = RibsOp(
        name="lightening",
        count=count,
        pitch=ResolvedParam(value=0.020),
        thickness=ResolvedParam(value=thickness_m),
        height=ResolvedParam(value=0.012),
    )
    return FeatureProgram(
        part_name="RibbedPanel",
        stages=(Stage(name="milled", process="cnc_mill", features=(body, ribs)),),
    )


def _realized_mass_kg(count: int, thickness_m: float) -> float:
    result = realize_feature_program(_panel_program(count, thickness_m))
    assert result.is_ok, result.danger_err
    volume_m3 = result.danger_ok.geometry.topology.volume_mm3 / 1.0e9
    return volume_m3 * _AL_DENSITY_KG_M3


def _bounds_from_fixture() -> tuple[list[int], tuple[float, float]]:
    """The search space read off the EMITTED planner slots -- the
    declared source, never re-invented in the test."""
    params = _ribs_op_params(_check_fixture())
    lo, hi = (int(x) for x in re.findall(r"\d+", params["count"]["text"]))
    t_lo, t_hi = (
        float(x) / 1000.0 for x in re.findall(r"[\d.]+", params["thickness"]["text"])
    )
    return (list(range(lo, hi + 1)), (t_lo, t_hi))


def test_the_optimizer_pins_count_and_thickness_with_a_trace(tmp_path) -> None:
    """Acceptance line 1b: the optimizer pins count/thickness with a
    trace through EXISTING machinery -- optimize_discrete over the
    integer count bounds, golden-section over the thickness interval,
    each candidate realized through the real interpreter, winners pinned
    as `cause: optimize(mass, trace=<digest>)` lockfile rows."""
    counts, t_bounds = _bounds_from_fixture()
    store = PayloadStore(str(tmp_path))
    inner_traces: dict[str, OptimizationTrace] = {}
    realizations = 0

    def thickness_evaluator_for(count: int):
        def evaluate(assignment: tuple[float, ...]) -> EvalOutcome:
            nonlocal realizations
            (thickness_m,) = assignment
            mass_kg = _realized_mass_kg(count, thickness_m)
            realizations += 1
            t_mm = thickness_m * 1000.0
            feasible = count * t_mm**3 >= _STIFFNESS_FLOOR
            return EvalOutcome(
                feasible=feasible,
                objective_vector=(mass_kg,),
                verdict_summary=f"count={count} t={t_mm:.3f}mm mass={mass_kg:.6f}kg",
            )

        return evaluate

    def count_evaluator(assignment) -> EvalOutcome:
        count = int(assignment["RibbedPanel.lightening.count"])
        inner = optimize_continuous_golden_section(
            bounds=t_bounds,
            evaluator=thickness_evaluator_for(count),
            budget_evals=16,
            tol=1e-5,
        )
        inner_traces[str(count)] = inner
        if inner.winner is None:
            return EvalOutcome(feasible=False, objective_vector=(float("inf"),))
        best = inner.candidates[inner.winner]
        return EvalOutcome(
            feasible=True,
            objective_vector=tuple(best.objective_vector),
            verdict_summary=best.verdict_summary,
        )

    trace = optimize_discrete(
        domains=[
            ChoicePointDomain(
                subject="RibbedPanel.lightening.count",
                candidates=tuple(str(c) for c in counts),
            )
        ],
        evaluator=count_evaluator,
        objective=("minimize",),
        budget_evals=len(counts),
    )

    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    pairs = {item.root[0]: item.root[1] for item in winner.assignment}
    winner_count = pairs["RibbedPanel.lightening.count"]
    # Mass rises with count * thickness while the stiffness floor sets
    # the per-count minimum thickness ~ (K/count)^(1/3): the fewest ribs
    # win, at an interior thickness -- decided by the search over REAL
    # realized mass, not by an authored answer.
    assert winner_count == str(counts[0]), pairs
    # Every objective number came from a REAL OCCT realization -- the
    # inner traces' spent budgets account for every interpreter call.
    assert realizations == sum(t.budget_spent for t in inner_traces.values())

    # The count winner pins with cause optimize(mass, trace=<digest>).
    count_digest = store_trace(store, trace)
    row = winner_lock_row(trace, "RibbedPanel.lightening.count", "mass", count_digest)
    assert row.is_ok, row
    assert row.danger_ok.cause == f"optimize(mass, trace={count_digest})"
    assert row.danger_ok.value.endswith(winner_count)

    # ... and so does the winning count's thickness (the inner trace).
    inner = inner_traces[winner_count]
    thickness_digest = store_trace(store, inner)
    t_row = winner_lock_row(
        inner,
        "RibbedPanel.lightening.thickness",
        "mass",
        thickness_digest,
    )
    assert t_row.is_ok, t_row
    assert t_row.danger_ok.cause == f"optimize(mass, trace={thickness_digest})"
    assert inner.winner is not None
    winner_t_m = float(
        dict(item.root for item in inner.candidates[inner.winner].assignment)["x"]
    )
    # The stiffness floor puts the optimum near (K/count)^(1/3) mm.
    expected_t_m = (_STIFFNESS_FLOOR / int(winner_count)) ** (1.0 / 3.0) / 1000.0
    assert abs(winner_t_m - expected_t_m) < 3.0e-4, (winner_t_m, expected_t_m)


def test_dfm_rows_fire_on_an_infeasible_literal_twin(tmp_path) -> None:
    """Acceptance line 1c: the same design with LITERAL infeasible
    values (1mm ribs under the 2mm floor, a 5mm slot under the 6mm
    slot-width floor) trips the `std.removal` rows as E0601 errors
    naming the rules."""
    twin = tmp_path / "ribbed_panel_twin.hema"
    twin.write_text(
        "part RibbedPanelTwin:\n"
        "    material: AL_6061_T6\n"
        "    stage milled: process=cnc_mill(std.removal)\n"
        "        then:\n"
        "            lightening = Ribs(count=6, pitch=6mm, thickness=1mm)\n"
    )
    out = compiler.check(
        (
            str(twin),
            _PACK,
        )
    )
    assert out.is_ok, out
    payload = json.loads(out.danger_ok.payload_json)
    messages = [d["message"] for d in payload["diagnostics"]]
    assert any(
        "std.removal.min_rib_thickness" in m and "violated" in m for m in messages
    ), messages
    assert any(
        "std.removal.rib_slot_tool_access" in m and "violated" in m for m in messages
    ), messages


# frob:tests python/regolith/orchestrator/programs.py::emitted_realizer_programs
def test_promotion_honesty_across_the_four_families(caplog) -> None:
    """WO-77 d3: literal PocketGrid/Shell parts promote and REALIZE with
    no hand-authored program; the bounded-Ribs part and the Lattice
    part stay pending with NAMED reasons (never guessed geometry)."""
    out = compiler.check(
        (
            _FIXTURE,
            _PACK,
        )
    )
    assert out.is_ok, out
    with caplog.at_level(logging.INFO, logger="regolith.orchestrator.programs"):
        programs = emitted_realizer_programs(out.danger_ok.payload_json)

    assert set(programs) == {"PocketedTray.body", "ShellHousing.body"}
    for subject, program in programs.items():
        kinds = [op.op for op in program.stages[0].features]
        assert kinds[0] == "blank"
        assert kinds[1] in ("pocket_grid", "shell"), subject
        realized = realize_feature_program(program)
        assert realized.is_ok, realized.danger_err
        # The removal genuinely removed material: less volume than the
        # blank alone.
        blank = program.stages[0].features[0]
        assert isinstance(blank, BlankOp), f"expected a blank feature, got {blank!r}"
        blank_volume_mm3 = (
            abs(
                (blank.sketch.outline[2].x - blank.sketch.outline[0].x)
                * (blank.sketch.outline[2].y - blank.sketch.outline[0].y)
            )
            * blank.thickness.value
            * 1.0e9
        )
        assert realized.danger_ok.geometry.topology.volume_mm3 < blank_volume_mm3

    text = caplog.text
    assert "RibbedPanel" in text and "unpinned" in text
    assert "lattice has no v1 projection" in text
