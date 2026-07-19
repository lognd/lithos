"""WO-62 slice B deliverable 6: the COMPOSITION PROOF.

One ``in [lo, hi] minimize`` dimension (a plate's sheet thickness)
optimized against an assembly-level mass claim through the LANDED
cycle-30 staged evaluator (`regolith.orchestrator.optimize.
optimize_continuous_golden_section`), with ZERO engine changes: the
evaluator closure below is the only new code -- it realizes a fresh
`FeatureProgram` at each candidate thickness, solves the assembly
(`regolith.realizer.mech.assembly.solve_assembly`, WO-62 slice B
deliverable 5), `put`s the resulting `RealizedAssembly` into a real
`PayloadStore` (the same WO-30 store citizen every other realized-
domain producer uses), and returns the assembly's extracted mass as
the objective -- exactly the shape charter `30-geometry-lowering.md`
sec. 1.5 describes ("assembly-realized facts ... are ordinary evidence
... the engine is untouched").
"""

from __future__ import annotations

from regolith.orchestrator.optimize import (
    EvalOutcome,
    optimize_continuous_golden_section,
    winner_lock_row,
)
from regolith.orchestrator.orchestrate import put_realized_assembly
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.mech.assembly import (
    AssemblyDef,
    AssemblyPartDef,
    MateDef,
    MateTransform,
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

_STEEL_DENSITY_KG_M3 = 7850.0
_BASE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.1, y=0.0),
    Point2(x=0.1, y=0.1),
    Point2(x=0.0, y=0.1),
)
_ARM_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.05, y=0.0),
    Point2(x=0.05, y=0.05),
    Point2(x=0.0, y=0.05),
)


def _base_artifact():
    sketch = Sketch(name="base", outline=_BASE_OUTLINE)
    op = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.01))
    program = FeatureProgram(
        part_name="Base", stages=(Stage(name="s", process="mill", features=(op,)),)
    )
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok


def _arm_artifact(thickness_m: float):
    """Realize the optimized part at a candidate sheet thickness."""
    sketch = Sketch(name="arm", outline=_ARM_OUTLINE)
    op = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=thickness_m)
    )
    program = FeatureProgram(
        part_name="Arm", stages=(Stage(name="s", process="laser_cut", features=(op,)),)
    )
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok


def _assembly_for(thickness_m: float) -> AssemblyDef:
    base = _base_artifact()
    arm = _arm_artifact(thickness_m)
    base_volume_m3 = base.geometry.topology.volume_mm3 / 1.0e9
    arm_volume_m3 = arm.geometry.topology.volume_mm3 / 1.0e9
    return AssemblyDef(
        parts=(
            AssemblyPartDef(
                id="Base",
                geometry=base,
                mass_kg=base_volume_m3 * _STEEL_DENSITY_KG_M3,
                geometry_digest="blake3:base",
            ),
            AssemblyPartDef(
                id="Arm",
                geometry=arm,
                mass_kg=arm_volume_m3 * _STEEL_DENSITY_KG_M3,
                geometry_digest="blake3:arm",
            ),
        ),
        mates=(
            MateDef(
                id="m_base_arm",
                kind="distance",
                from_part="Base",
                to_part="Arm",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.01)),
            ),
        ),
        mating_graph_hash=f"blake3:composition_{thickness_m}",
    )


# frob:tests python/regolith/orchestrator/orchestrate.py::put_realized_assembly
def test_mass_minimizing_thickness_composes_through_the_staged_evaluator(
    tmp_path,
) -> None:
    store = PayloadStore(str(tmp_path))
    evidence_digests: list[str] = []

    def evaluator(assignment: tuple[float, ...]) -> EvalOutcome:
        (thickness_m,) = assignment
        assembly = _assembly_for(thickness_m)
        solved = solve_assembly(assembly)
        assert solved.is_ok, solved.danger_err
        realized = solved.danger_ok
        digest = put_realized_assembly(store, realized)
        evidence_digests.append(digest)
        return EvalOutcome(
            feasible=True,
            objective_vector=(realized.mass_kg,),
            verdict_summary=f"assembly mass_kg={realized.mass_kg:.6f}",
            evidence_digests=(digest,),
        )

    trace = optimize_continuous_golden_section(
        bounds=(0.001, 0.003),
        evaluator=evaluator,
        budget_evals=40,
        tol=1e-5,
    )

    assert trace.termination.value == "converged"
    assert trace.winner is not None
    winner = trace.candidates[trace.winner]
    assignment_pairs = {item.root[0]: item.root[1] for item in winner.assignment}
    winner_x = float(assignment_pairs["x"])
    # Mass grows monotonically with thickness for this fixture (fixed
    # footprint, varying extrusion depth), so the true minimizer sits
    # at the lower bound -- the search should land near it.
    assert winner_x < 0.0015, (
        f"expected the search to favor the thin end, got x={winner_x}"
    )

    # STAGED REALIZATION IN EVIDENCE: every evaluation actually solved
    # a fresh assembly and put a real payload into the store (never a
    # synthetic/mocked score) -- the trace's own evidence trail proves
    # this composition ran through real realized-domain facts, not a
    # bypass.
    assert len(evidence_digests) == trace.budget_spent
    for digest in evidence_digests:
        resolved = store.resolve(digest)
        assert resolved.is_ok, resolved.danger_err

    # ZERO ENGINE CHANGES: the trace round-trips through the generated
    # schema exactly like every other `OptimizationTrace` (WO-55
    # acceptance, unmodified by this WO).
    from regolith._schema.models import OptimizationTrace

    dumped = trace.model_dump(mode="json")
    OptimizationTrace.model_validate(dumped)

    # WO-62 slice B acceptance: "the optimize run pins the dim with
    # cause: optimize(...)" -- the ONE lockfile-row mechanism (WO-55,
    # unmodified), applied to this assembly-mass composition.
    lock_row = winner_lock_row(
        trace,
        slot="Arm.blank.thickness",
        objective_name="assembly_mass_kg",
        trace_digest="deadbeef",
    )
    assert lock_row.is_ok, lock_row.danger_err
    assert lock_row.danger_ok.cause == "optimize(assembly_mass_kg, trace=deadbeef)"
