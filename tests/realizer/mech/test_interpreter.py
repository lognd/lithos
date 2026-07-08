"""The build123d/OCCT interpreter: v1 feature set, determinism, deferral.

Covers: STEP export re-imports cleanly with matching volume (WO-22
acceptance), a schema version mismatch is an honest ``Err`` (never a
crash), an unsupported op is a named deferral (never a silent skip),
and same-program-same-hash determinism (AD-6).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import build123d as b3d
from regolith.realizer.mech.errors import (
    BoreReferenceNotFound,
    FlowAreaMismatch,
    MissingMaterialProps,
    SchemaVersionMismatch,
    UnsupportedFeature,
)
from regolith.realizer.mech.interpreter import _apply_feature, realize_feature_program
from regolith.realizer.mech.schema import FEATURE_PROGRAM_SCHEMA_VERSION

from tests.realizer.mech.fixtures import (
    COOLANT_BORE_AREA_M2,
    PLATE_BBOX_M,
    PLATE_VOLUME_M3,
    bracket_program,
    coolant_bracket_program,
    plate_program,
    pocketed_block_program,
)


def test_plate_realizes_and_reimports_cleanly() -> None:
    """A bare extruded plate realizes; the STEP bytes re-import in a fresh session."""
    result = realize_feature_program(plate_program())
    assert result.is_ok, result.danger_err
    realized = result.danger_ok

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plate.step"
        path.write_bytes(realized.step_bytes)
        reimported = b3d.import_step(str(path))
        assert reimported is not None
        assert abs(reimported.volume - realized.geometry.topology.volume_mm3) < 1e-6


def test_plate_volume_matches_hand_computed_prediction() -> None:
    """The realized plate's volume/bbox match the hand-derived box measures."""
    realized = realize_feature_program(plate_program()).danger_ok
    topo = realized.geometry.topology
    assert abs(topo.volume_mm3 / 1e9 - PLATE_VOLUME_M3) < 1e-9
    bbox_m = tuple(
        (topo.bbox_max_mm[i] - topo.bbox_min_mm[i]) / 1000.0 for i in range(3)
    )
    for actual, expected in zip(bbox_m, PLATE_BBOX_M, strict=True):
        assert abs(actual - expected) < 1e-9


def test_bracket_pattern_and_fillet_apply() -> None:
    """The 2x2 mount-hole pattern and vertical-edge fillet apply cleanly."""
    result = realize_feature_program(bracket_program())
    assert result.is_ok, result.danger_err
    topo = result.danger_ok.geometry.topology
    # 4 pattern holes + 1 profile hole cut real volume out of the plate.
    assert topo.volume_mm3 < PLATE_VOLUME_M3 * 1e9


def test_pocket_cuts_into_top_face() -> None:
    """A pocket reduces volume without opening the block (still one solid)."""
    result = realize_feature_program(pocketed_block_program())
    assert result.is_ok, result.danger_err
    topo = result.danger_ok.geometry.topology
    assert topo.num_solids == 1
    full_volume = 0.08 * 0.05 * 0.010 * 1e9
    assert topo.volume_mm3 < full_volume


def test_schema_version_mismatch_is_an_honest_err() -> None:
    """An unrecognized schema_version refuses rather than guesses (AD-5)."""
    program = plate_program()
    bumped = program.model_copy(
        update={"schema_version": FEATURE_PROGRAM_SCHEMA_VERSION + 1}
    )
    result = realize_feature_program(bumped)
    assert result.is_err
    assert isinstance(result.danger_err, SchemaVersionMismatch)


class _FakeUnsupportedOp:
    """A stand-in for a real feature op outside the v1 discriminated union."""

    op = "weldment_fillet_weld"


def test_unsupported_op_is_a_named_deferral_never_a_crash() -> None:
    """An op outside the v1 set is a named ``UnsupportedFeature``, not a crash."""
    result = _apply_feature(None, _FakeUnsupportedOp(), stage="weld")
    assert result.is_err
    err = result.danger_err
    assert isinstance(err, UnsupportedFeature)
    assert err.op == "weldment_fillet_weld"
    assert err.stage == "weld"


def test_determinism_same_program_same_hashes() -> None:
    """Realizing the same program twice gives byte-identical STEP + hashes (AD-6)."""
    first = realize_feature_program(bracket_program()).danger_ok
    second = realize_feature_program(bracket_program()).danger_ok
    assert first.geometry.feature_program_hash == second.geometry.feature_program_hash
    assert first.geometry.step_content_hash == second.geometry.step_content_hash
    assert first.step_bytes == second.step_bytes
    assert first.geometry.topology == second.geometry.topology


def test_feature_program_content_hash_changes_with_geometry() -> None:
    """A different part name changes the feature-program content hash."""
    a = plate_program(part_name="a")
    b = plate_program(part_name="b")
    assert a.content_hash() != b.content_hash()


def test_declared_flow_path_validates_and_emits() -> None:
    """A declared `flow_paths` entry consistent with its bore emits a
    selector-keyed `RoutedPath` with degenerate-point intervals (D130/D131).
    """
    result = realize_feature_program(coolant_bracket_program())
    assert result.is_ok, result.danger_err
    geometry = result.danger_ok.geometry
    assert set(geometry.paths) == {"coolant.wetted"}
    segment = geometry.paths["coolant.wetted"].segments[0]
    assert segment.role == "coolant_jacket"
    assert segment.flow_area[0] == segment.flow_area[1] == COOLANT_BORE_AREA_M2
    assert segment.roughness_class == "drawn_tube"
    assert segment.wall is not None
    assert segment.wall.youngs_modulus[0] == 2.0e11
    assert segment.wall.thickness[0] == 0.002
    assert segment.wall.diameter[0] == 0.012


def test_flow_area_mismatch_against_bore_is_a_named_error() -> None:
    """A declared `flow_area` wildly inconsistent with the bore's resolved
    diameter is a `FlowAreaMismatch` value, never a silent preference."""
    program = coolant_bracket_program(declared_flow_area_m2=1.0)
    result = realize_feature_program(program)
    assert result.is_err
    assert isinstance(result.danger_err, FlowAreaMismatch)


def test_dangling_bore_reference_is_a_named_error() -> None:
    """A `bore` ref naming no feature op in the program is a named error."""
    program = coolant_bracket_program()
    bad_segment = (
        program.flow_paths[0]
        .segments[0]
        .model_copy(
            update={
                "bore": program.flow_paths[0]
                .segments[0]
                .bore.model_copy(update={"feature": "does_not_exist"})
            }
        )
    )
    bad_program = program.model_copy(
        update={
            "flow_paths": (
                program.flow_paths[0].model_copy(update={"segments": (bad_segment,)}),
            )
        }
    )
    result = realize_feature_program(bad_program)
    assert result.is_err
    assert isinstance(result.danger_err, BoreReferenceNotFound)


def test_wall_without_material_props_is_a_named_error() -> None:
    """A segment declaring `wall` with no part-level `material_props` to
    source Young's modulus from is a named error (WO-22 cut #2)."""
    program = coolant_bracket_program(with_material_props=False)
    result = realize_feature_program(program)
    assert result.is_err
    assert isinstance(result.danger_err, MissingMaterialProps)
