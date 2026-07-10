"""WO-64 phase B: `examples/flagships/printer_k1/xy_gantry.hema`'s
`XYGantryAssembly` (>= 4 parts, >= 5 mates, one real mate loop) proven
to realize placed through the LANDED WO-62 slice B machinery, exactly
like `tests/orchestrator/test_wo62_assembly_composition.py` proves
`GantryCarriage`: this module's own docstring records the same
integration-seam gap (`regolith-lower` emits no numeric mate-graph
payload from a `connect:` block's `align:` clauses yet), so the
`AssemblyDef` here is hand-declared to mirror the source file's own
part/mate topology (4 parts: `x_carriage`, `rail_l`, `rail_r`,
`y_carriage`; 5 mates, one loop: x_carriage -> rail_l -> y_carriage ->
x_carriage) rather than derived from `xy_gantry.hema` end to end.

Each part's `FeatureProgram` is a flat-plate fixture sized to
`xy_gantry.hema`'s own declared profile dimensions (`CarriagePlateFlat`
60x40mm, `RailBracketFlat` 40x20mm) so the assembly's placement,
interference check, and STEP export exercise real part-scale
geometry, not an arbitrary stand-in.
"""

from __future__ import annotations

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

_CARRIAGE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.060, y=0.0),
    Point2(x=0.060, y=0.040),
    Point2(x=0.0, y=0.040),
)
_BRACKET_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.040, y=0.0),
    Point2(x=0.040, y=0.020),
    Point2(x=0.0, y=0.020),
)


def _plate(part_name: str, outline, thickness_m: float = 0.003) -> FeatureProgram:
    sketch = Sketch(name="blank", outline=outline)
    op = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=thickness_m)
    )
    stage = Stage(name="cut", process="laser_cut", features=(op,))
    return FeatureProgram(part_name=part_name, material="AL6061_T6", stages=(stage,))


def _realized(program: FeatureProgram):
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok


def _xy_gantry_assembly() -> AssemblyDef:
    """Mirrors `xy_gantry.hema`'s `XYGantryAssembly` part/mate topology."""
    x_carriage = _realized(_plate("XCarriage", _CARRIAGE_OUTLINE))
    rail_l = _realized(_plate("XRailBracketLeft", _BRACKET_OUTLINE))
    rail_r = _realized(_plate("XRailBracketRight", _BRACKET_OUTLINE))
    y_carriage = _realized(_plate("YCarriage", _CARRIAGE_OUTLINE))

    return AssemblyDef(
        parts=(
            AssemblyPartDef(
                id="x_carriage",
                geometry=x_carriage,
                mass_kg=0.05,
                geometry_digest="blake3:x_carriage",
            ),
            AssemblyPartDef(
                id="rail_l",
                geometry=rail_l,
                mass_kg=0.02,
                geometry_digest="blake3:rail_l",
            ),
            AssemblyPartDef(
                id="rail_r",
                geometry=rail_r,
                mass_kg=0.02,
                geometry_digest="blake3:rail_r",
            ),
            AssemblyPartDef(
                id="y_carriage",
                geometry=y_carriage,
                mass_kg=0.05,
                geometry_digest="blake3:y_carriage",
            ),
        ),
        mates=(
            MateDef(
                id="m_x_rail_l",
                kind="align",
                from_part="x_carriage",
                to_part="rail_l",
                transform=MateTransform(translation_m=(0.0, 0.045, 0.0)),
            ),
            MateDef(
                id="m_x_rail_r",
                kind="align",
                from_part="x_carriage",
                to_part="rail_r",
                transform=MateTransform(translation_m=(0.0, -0.025, 0.0)),
            ),
            MateDef(
                id="m_x_y",
                kind="align",
                from_part="x_carriage",
                to_part="y_carriage",
                transform=MateTransform(translation_m=(0.070, 0.0, 0.0)),
            ),
            # Loop-closing mates: rail_l/rail_r -> y_carriage must agree
            # with the tree placement composed through x_carriage.
            MateDef(
                id="m_rail_l_y",
                kind="align",
                from_part="rail_l",
                to_part="y_carriage",
                transform=MateTransform(translation_m=(0.070, -0.045, 0.0)),
            ),
            MateDef(
                id="m_rail_r_y",
                kind="align",
                from_part="rail_r",
                to_part="y_carriage",
                transform=MateTransform(translation_m=(0.070, 0.025, 0.0)),
            ),
        ),
        mating_graph_hash="blake3:xy_gantry_assembly",
    )


def test_xy_gantry_assembly_solves_with_no_loop_residual() -> None:
    assembly = _xy_gantry_assembly()
    result = solve_assembly(assembly)
    assert result.is_ok, result.danger_err


def test_xy_gantry_assembly_has_no_interference() -> None:
    assembly = _xy_gantry_assembly()
    realized = solve_assembly(assembly).danger_ok
    assert realized.interferences == []


def test_xy_gantry_assembly_step_export_is_deterministic() -> None:
    assembly = _xy_gantry_assembly()
    realized = solve_assembly(assembly).danger_ok
    step_a = export_assembly_step(assembly, realized)
    step_b = export_assembly_step(assembly, realized)
    assert step_a == step_b
    assert len(step_a) > 0


def test_xy_gantry_assembly_mass_is_the_sum_of_its_four_parts() -> None:
    assembly = _xy_gantry_assembly()
    realized = solve_assembly(assembly).danger_ok
    assert realized.mass_kg == 0.05 + 0.02 + 0.02 + 0.05
