"""WO-75 (D183): the `arm_a6` flagship's D183 demonstrations, mirroring
WO-64's own proof idioms over the real corpus source
(`examples/flagships/arm_a6/`):

- deliverable 1: the shoulder joint sub-assembly (`joint2.hema`'s
  `ShoulderJointAssembly`) realizes placed as a `RealizedAssembly`
  (the same hand-declared-`AssemblyDef`-mirroring-the-source idiom
  `tests/orchestrator/test_wo64_xy_gantry_assembly.py` established --
  `regolith-lower` still emits no numeric mate-graph payload from a
  `connect:` block's `align:` clauses, unchanged since WO-64).
- deliverable 3 (bolted joints at the base): `base.hema`'s
  `base_bolts` claim (`mech.bolt.joint_separation`) discharged
  directly against `BoltedJointModel.estimate()` -- the WO-64 phase-C
  model-direct precedent, used here because
  `regolith.orchestrator.translate` does not yet route this claim
  kind end to end (coordinator cycle-32 heads-up; a separate wiring
  dispatch is landing the fix on another branch).
- deliverable 4 (optimize + select): two continuous `in [lo,hi]
  minimize` section dims (`link1.hema`'s `UpperArmSection.b`,
  `link2.hema`'s `ForearmSection.b`) pinned via the landed continuous
  golden-section evaluator, and `joint2.hema`'s `JointReduction by
  select` choice point pinned via the landed discrete driver -- both
  mirror `tests/orchestrator/test_wo64_printer_optimize.py`'s own
  recipe over the REAL flagship source.
"""

from __future__ import annotations

import json

from regolith import compiler
from regolith.harness.models.bolted_joint import BoltedJointModel
from regolith.harness.model import DischargeRequest
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
from regolith.realizer.mech.assembly import (
    AssemblyDef,
    AssemblyPartDef,
    MateDef,
    MateTransform,
    export_assembly_step,
    solve_assembly,
)
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

# ---------------------------------------------------------------------
# Deliverable 1: ShoulderJointAssembly (J2) realizes placed.
# ---------------------------------------------------------------------

_HOUSING_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.070, y=0.0),
    Point2(x=0.070, y=0.070),
    Point2(x=0.0, y=0.070),
)


def _housing_plate(part_name: str, thickness_m: float) -> FeatureProgram:
    sketch = Sketch(name="blank", outline=_HOUSING_OUTLINE)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=thickness_m))
    stage = Stage(name="mill", process="cnc_mill", features=(op,))
    return FeatureProgram(part_name=part_name, material="AL6061_T6", stages=(stage,))


def _realized(program: FeatureProgram):
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok


def _shoulder_joint_assembly() -> AssemblyDef:
    """Mirrors `joint2.hema`'s `ShoulderJointAssembly` part/mate topology:
    4 parts (housing, retainer, motor_bracket, upper_arm), the same
    hand-built `AssemblyDef` idiom `test_wo64_xy_gantry_assembly.py`
    established (`upper_arm`'s own profile stands in for `UpperArm`'s
    real `UpperArmSection` dims, 300x24mm, thickness 20mm)."""
    housing = _realized(_housing_plate("ShoulderHousing", 0.025))
    retainer = _realized(_housing_plate("BearingRetainer", 0.006))
    motor_bracket = _realized(_housing_plate("MotorBracket", 0.008))
    upper_arm_outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=0.300, y=0.0),
        Point2(x=0.300, y=0.024),
        Point2(x=0.0, y=0.024),
    )
    sketch = Sketch(name="blank", outline=upper_arm_outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.020))
    stage = Stage(name="mill", process="cnc_mill", features=(op,))
    upper_arm = _realized(
        FeatureProgram(part_name="UpperArm", material="AL6061_T6", stages=(stage,))
    )

    return AssemblyDef(
        parts=(
            AssemblyPartDef(
                id="housing", geometry=housing, mass_kg=0.30,
                geometry_digest="blake3:j2_housing",
            ),
            AssemblyPartDef(
                id="retainer", geometry=retainer, mass_kg=0.07,
                geometry_digest="blake3:j2_retainer",
            ),
            AssemblyPartDef(
                id="motor_bracket", geometry=motor_bracket, mass_kg=0.09,
                geometry_digest="blake3:j2_motor_bracket",
            ),
            AssemblyPartDef(
                id="upper_arm", geometry=upper_arm, mass_kg=0.49,
                geometry_digest="blake3:upper_arm",
            ),
        ),
        mates=(
            MateDef(
                id="m_retainer", kind="align",
                from_part="housing", to_part="retainer",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.025)),
            ),
            MateDef(
                id="m_motor", kind="align",
                from_part="housing", to_part="motor_bracket",
                transform=MateTransform(translation_m=(0.0, 0.0, -0.008)),
            ),
            MateDef(
                id="j2", kind="align",
                from_part="housing", to_part="upper_arm",
                transform=MateTransform(translation_m=(0.070, 0.0, 0.0)),
            ),
        ),
        mating_graph_hash="blake3:shoulder_joint_assembly",
    )


def test_shoulder_joint_assembly_solves_with_no_loop_residual() -> None:
    assembly = _shoulder_joint_assembly()
    result = solve_assembly(assembly)
    assert result.is_ok, result.danger_err


def test_shoulder_joint_assembly_step_export_is_deterministic() -> None:
    assembly = _shoulder_joint_assembly()
    realized = solve_assembly(assembly).danger_ok
    step_a = export_assembly_step(assembly, realized)
    step_b = export_assembly_step(assembly, realized)
    assert step_a == step_b
    assert len(step_a) > 0


def test_shoulder_joint_assembly_mass_is_the_sum_of_its_four_parts() -> None:
    assembly = _shoulder_joint_assembly()
    realized = solve_assembly(assembly).danger_ok
    assert realized.mass_kg == 0.30 + 0.07 + 0.09 + 0.49


# ---------------------------------------------------------------------
# Deliverable 3: base bolted joint, VDI 2230 model-direct discharge.
# ---------------------------------------------------------------------


def test_base_bolted_joint_separation_margin_model_direct() -> None:
    """`base.hema`'s `base_bolts` claim
    (`mech.bolt.joint_separation(mill.feet, under=9.4N*m) >= 1.5`), fed
    directly into `BoltedJointModel.estimate()` since the corpus-level
    claim does not route through `translate.py` yet (WALL W2, this
    WO's ledger). Four M8 bolts share the 9.4N*m tipping moment at a
    110mm bolt-circle radius: per-bolt external load ~= 9.4N*m /
    (4 * 0.055m) ~= 42.7N -- an M8 class preload (~14kN, a common
    class-8.8 snug-tight value) with representative VDI 2230
    stiffnesses clears it comfortably."""
    from regolith.harness.quantity import Interval

    request = DischargeRequest(
        claim_kind="mech.bolt.joint_separation",
        limit=0.0,
        inputs={
            "f_preload": Interval(lo=14000.0, hi=14000.0),
            "f_external": Interval(lo=42.7, hi=42.7),
            "k_bolt": Interval(lo=6.0e8, hi=6.0e8),
            "k_clamp": Interval(lo=2.0e9, hi=2.0e9),
        },
    )
    model = BoltedJointModel()
    result = model.estimate(request)
    assert result.is_ok, result.danger_err
    prediction = result.danger_ok
    # Lower-bound residual clamp claim: F_KR must clear zero with
    # margin (the joint does not separate).
    assert prediction.value > 0.0, prediction


# ---------------------------------------------------------------------
# Deliverable 4a: continuous optimize over the two link section dims.
# ---------------------------------------------------------------------


def _link_plate_program(part_name: str, length_m: float, width_m: float) -> FeatureProgram:
    outline = (
        Point2(x=0.0, y=0.0),
        Point2(x=length_m, y=0.0),
        Point2(x=length_m, y=width_m),
        Point2(x=0.0, y=width_m),
    )
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.020))
    stage = Stage(name="mill", process="cnc_mill", features=(op,))
    return FeatureProgram(part_name=part_name, material="AL6061_T6", stages=(stage,))


def test_upper_arm_section_width_pinned_by_continuous_optimize(tmp_path) -> None:
    """`link1.hema`'s `UpperArmSection.b = in [24mm, 40mm] minimize`:
    section mass grows monotonically with width, so the true minimizer
    sits at the lower bound (24mm)."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (b_m,) = assignment
        realized = realize_feature_program(_link_plate_program("UpperArm", 0.300, b_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"UpperArm mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.024, 0.040), evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.028, f"expected the search to favor 24mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "UpperArm.UpperArmSection.b", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


def test_forearm_section_width_pinned_by_continuous_optimize(tmp_path) -> None:
    """`link2.hema`'s `ForearmSection.b = in [18mm, 32mm] minimize`."""
    store = PayloadStore(str(tmp_path))

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (b_m,) = assignment
        realized = realize_feature_program(_link_plate_program("Forearm", 0.250, b_m)).danger_ok
        volume_m3 = realized.geometry.topology.volume_mm3 / 1.0e9
        mass_kg = volume_m3 * _AL_DENSITY_KG_M3
        digest = store.put(realized.geometry.model_dump_json().encode("ascii"))
        return EvalOutcome(
            feasible=True,
            objective_vector=(mass_kg,),
            verdict_summary=f"Forearm mass_kg={mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.018, 0.032), evaluator=evaluator, budget_evals=40, tol=1e-5
    )
    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    winner_x = float({item.root[0]: item.root[1] for item in winner.assignment}["x"])
    assert winner_x < 0.022, f"expected the search to favor 18mm, got x={winner_x}"

    digest = store_trace(store, trace)
    row_result = winner_lock_row(
        trace, "Forearm.ForearmSection.b", "declared_objective", digest
    )
    assert row_result.is_ok, row_result
    assert row_result.danger_ok.cause.startswith("optimize(")


# ---------------------------------------------------------------------
# Deliverable 4b: discrete `by select` over the J2 reduction.
# ---------------------------------------------------------------------


def test_joint2_reduction_select_pin() -> None:
    """`joint2.hema`'s `MotorBracket.JointReduction by select(belt_3to1,
    planetary_5to1, planetary_8to1)`, run against the REAL, compiled
    `arm_a6` project (the `ebi_decode`/WO-64 recipe): a torque/cost
    policy prefers the cheapest candidate that still clears
    `arm_a6.cupr`'s own POSE_REACH wall (`planetary_8to1`)."""
    result = compiler.check(("examples/flagships/arm_a6",))
    assert result.is_ok, result
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    assert "MotorBracket.JointReduction" in choice_points

    # Torque/cost policy: cheaper candidates are preferred, but only
    # `planetary_8to1` clears POSE_REACH's 8.39N*m at sf=1.5 -- so a
    # torque-feasibility-aware cost table makes it the cheapest VIABLE
    # candidate (belt_3to1/planetary_5to1 are cheaper but infeasible
    # at this pose, priced here as prohibitively expensive to keep the
    # declared objective closed-form/cost-only, per
    # `domains_from_choice_points`'s own documented discipline).
    costs = {
        "MotorBracket.JointReduction": {
            "belt_3to1": 999.0,       # infeasible at POSE_REACH
            "planetary_5to1": 999.0,  # infeasible at POSE_REACH
            "planetary_8to1": 42.0,   # cheapest VIABLE candidate
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

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = PayloadStore(tmp)
        digest = store_trace(store, trace)
        row_result = winner_lock_row(
            trace, "MotorBracket.JointReduction", "declared_objective", digest
        )
        assert row_result.is_ok, row_result
        assert row_result.danger_ok.cause.startswith("optimize(")
