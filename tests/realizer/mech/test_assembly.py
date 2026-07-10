"""WO-62 slice B deliverable 5: mate solve + STEP assembly export +
extraction (`regolith.realizer.mech.assembly`).

Covers: deterministic sequential placement (root at identity), byte-
identical `RealizedAssembly` + STEP across two solves of the same
input (charter `30-geometry-lowering.md` sec. 1.4 acceptance),
extracted mass/COM, a deliberate-interference variant caught with both
part names + an overlap measure, and a mate-loop overconstraint
fixture yielding the loop diagnostic naming every mate on the loop.
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
from regolith.realizer.mech.errors import MateLoopResidual, UnknownMatePart
from regolith.realizer.mech.interpreter import realize_feature_program

from tests.realizer.mech.fixtures import bracket_program, plate_program


def _realized(program):
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok


def _two_part_assembly(offset_m: float = 0.02) -> AssemblyDef:
    base = _realized(plate_program("Base"))
    arm = _realized(bracket_program("Arm"))
    return AssemblyDef(
        parts=(
            AssemblyPartDef(
                id="Base", geometry=base, mass_kg=1.0, geometry_digest="blake3:base"
            ),
            AssemblyPartDef(
                id="Arm", geometry=arm, mass_kg=0.3, geometry_digest="blake3:arm"
            ),
        ),
        mates=(
            MateDef(
                id="m_base_arm",
                kind="distance",
                from_part="Base",
                to_part="Arm",
                transform=MateTransform(translation_m=(0.0, 0.0, offset_m)),
            ),
        ),
        mating_graph_hash="blake3:two_part",
    )


def test_root_part_is_placed_at_identity() -> None:
    assembly = _two_part_assembly()
    realized = solve_assembly(assembly).danger_ok
    base = next(p for p in realized.parts if p.id == "Base")
    assert base.transform.translation_m == [0.0, 0.0, 0.0]
    assert base.transform.rotation_deg == [0.0, 0.0, 0.0]
    assert realized.dof_states["Base"] == "fixed"


def test_second_part_places_by_the_mate_transform() -> None:
    assembly = _two_part_assembly(offset_m=0.05)
    realized = solve_assembly(assembly).danger_ok
    arm = next(p for p in realized.parts if p.id == "Arm")
    assert arm.transform.translation_m[2] == 0.05
    assert realized.dof_states["Arm"] == "placed"


def test_solve_is_deterministic_across_two_runs() -> None:
    assembly = _two_part_assembly()
    a = solve_assembly(assembly).danger_ok
    b = solve_assembly(assembly).danger_ok
    assert a.model_dump_json() == b.model_dump_json()


def test_step_export_is_byte_identical_across_two_runs() -> None:
    assembly = _two_part_assembly()
    realized = solve_assembly(assembly).danger_ok
    step_a = export_assembly_step(assembly, realized)
    step_b = export_assembly_step(assembly, realized)
    assert step_a == step_b
    assert len(step_a) > 0


def test_mass_and_com_are_extracted() -> None:
    assembly = _two_part_assembly()
    realized = solve_assembly(assembly).danger_ok
    assert realized.mass_kg == 1.3
    # COM lies between the two parts' own centers, biased toward Base
    # (the heavier part): a smoke check, not a closed-form derivation.
    assert 0.0 <= realized.com_m[2] <= 0.05


def test_unknown_mate_part_is_an_honest_error() -> None:
    base = _realized(plate_program("Base"))
    assembly = AssemblyDef(
        parts=(
            AssemblyPartDef(id="Base", geometry=base, mass_kg=1.0, geometry_digest="d"),
        ),
        mates=(
            MateDef(
                id="m1",
                kind="distance",
                from_part="Base",
                to_part="Ghost",
            ),
        ),
        mating_graph_hash="blake3:x",
    )
    result = solve_assembly(assembly)
    assert result.is_err
    assert isinstance(result.danger_err, UnknownMatePart)
    assert result.danger_err.part_id == "Ghost"


def test_deliberate_interference_variant_names_both_parts_and_a_measure() -> None:
    """The exemplar's interference fixture: placing Arm at zero offset
    (instead of clear of Base) overlaps the two solids -- charter sec.
    1.4: "an interference is a release-gated diagnostic with both part
    names and the overlap measure"."""
    assembly = _two_part_assembly(offset_m=0.0)
    realized = solve_assembly(assembly).danger_ok
    assert len(realized.interferences) == 1
    interference = realized.interferences[0]
    assert {interference.part_a, interference.part_b} == {"Arm", "Base"}
    assert interference.overlap_mm3 > 0.0


def test_clear_offset_has_no_interference() -> None:
    assembly = _two_part_assembly(offset_m=0.05)
    realized = solve_assembly(assembly).danger_ok
    assert realized.interferences == []


def test_mate_loop_overconstraint_names_every_mate_on_the_loop() -> None:
    """A closing mate whose declared transform disagrees with the
    spanning-tree placement it loops back to is a `MateLoopResidual`
    citing the loop's mates -- never silently absorbed (charter sec.
    1.4)."""
    base = _realized(plate_program("Base"))
    arm = _realized(plate_program("Arm"))
    cap = _realized(plate_program("Cap"))
    assembly = AssemblyDef(
        parts=(
            AssemblyPartDef(id="Base", geometry=base, mass_kg=1.0, geometry_digest="b"),
            AssemblyPartDef(id="Arm", geometry=arm, mass_kg=0.2, geometry_digest="a"),
            AssemblyPartDef(id="Cap", geometry=cap, mass_kg=0.1, geometry_digest="c"),
        ),
        mates=(
            MateDef(
                id="m1",
                kind="distance",
                from_part="Base",
                to_part="Arm",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.02)),
            ),
            MateDef(
                id="m2",
                kind="distance",
                from_part="Arm",
                to_part="Cap",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.02)),
            ),
            # Inconsistent with m1 + m2's composed 0.04m: a real loop.
            MateDef(
                id="m3",
                kind="distance",
                from_part="Base",
                to_part="Cap",
                transform=MateTransform(translation_m=(0.0, 0.0, 0.10)),
            ),
        ),
        mating_graph_hash="blake3:loop",
    )
    result = solve_assembly(assembly)
    assert result.is_err
    err = result.danger_err
    assert isinstance(err, MateLoopResidual)
    assert set(err.mate_ids) == {"m1", "m2", "m3"}
    assert err.translation_residual_m > err.tolerance_m
