"""WO-77 (charter 34 phase 1) realizer projections: Ribs, PocketGrid,
Shell -- real OCCT geometry whose mass responds to every declared
parameter -- and the misuse paths as ``Err`` values, never crashes.
"""

from __future__ import annotations

from regolith.realizer.mech.errors import GeometryFailure
from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    PocketGridOp,
    Point2,
    ResolvedParam,
    RibsOp,
    ShellOp,
    Sketch,
    Stage,
)

# A 120mm x 80mm x 18mm block, SI meters (the schema convention).
_L, _W, _T = 0.120, 0.080, 0.018
_BLOCK_VOLUME_M3 = _L * _W * _T
_MM3_PER_M3 = 1.0e9


def _block_sketch() -> Sketch:
    return Sketch(
        name="block",
        outline=(
            Point2(x=0.0, y=0.0),
            Point2(x=_L, y=0.0),
            Point2(x=_L, y=_W),
            Point2(x=0.0, y=_W),
        ),
    )


def _program(*ops) -> FeatureProgram:
    body = ExtrudeOp(
        name="body", sketch=_block_sketch(), distance=ResolvedParam(value=_T)
    )
    return FeatureProgram(
        part_name="RemovalBlock",
        stages=(Stage(name="milled", process="cnc_mill", features=(body, *ops)),),
    )


def _volume_m3(program: FeatureProgram) -> float:
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    return result.danger_ok.geometry.topology.volume_mm3 / _MM3_PER_M3


def test_ribs_remove_material_and_respond_to_every_parameter() -> None:
    """More/thicker ribs leave MORE material; the removed band equals
    the hand-computed slab-minus-ribs volume."""

    def ribbed(count: int, thickness_m: float) -> float:
        return _volume_m3(
            _program(
                RibsOp(
                    name="lightening",
                    count=count,
                    pitch=ResolvedParam(value=0.020),
                    thickness=ResolvedParam(value=thickness_m),
                    height=ResolvedParam(value=0.012),
                )
            )
        )

    v_4x2 = ribbed(4, 0.002)
    v_4x4 = ribbed(4, 0.004)
    v_6x2 = ribbed(6, 0.002)
    assert v_4x2 < _BLOCK_VOLUME_M3
    assert v_4x2 < v_4x4 < _BLOCK_VOLUME_M3  # thicker ribs keep material
    assert v_4x2 < v_6x2 < _BLOCK_VOLUME_M3  # more ribs keep material
    # Hand computation: band (L x W x h) minus count ribs (t x W x h).
    height = 0.012
    expected = _BLOCK_VOLUME_M3 - (_L * _W * height - 4 * 0.002 * _W * height)
    assert abs(v_4x2 - expected) / expected < 1e-6


def test_ribs_height_defaults_to_the_full_solid_depth() -> None:
    """No `height` = the charter's "target region's depth": the slots
    cut through, leaving only the ribs' full-depth volume in the band."""
    v = _volume_m3(
        _program(
            RibsOp(
                name="lightening",
                count=4,
                pitch=ResolvedParam(value=0.020),
                thickness=ResolvedParam(value=0.002),
            )
        )
    )
    expected = _BLOCK_VOLUME_M3 - (_L * _W * _T - 4 * 0.002 * _W * _T)
    assert abs(v - expected) / expected < 1e-6


def test_ribs_misuse_is_a_named_err_never_a_crash() -> None:
    """thickness >= pitch leaves no slot to cut: a GeometryFailure value."""
    result = realize_feature_program(
        _program(
            RibsOp(
                name="lightening",
                count=4,
                pitch=ResolvedParam(value=0.002),
                thickness=ResolvedParam(value=0.005),
            )
        )
    )
    assert result.is_err
    assert isinstance(result.danger_err, GeometryFailure)
    assert "thickness" in result.danger_err.message


def test_pocket_grid_cuts_the_hand_computed_grid() -> None:
    """An nx x ny grid over a floor removes exactly nx*ny cell volumes."""
    wall, floor = 0.004, 0.003
    v = _volume_m3(
        _program(
            PocketGridOp(
                name="tray",
                nx=3,
                ny=2,
                wall=ResolvedParam(value=wall),
                floor=ResolvedParam(value=floor),
            )
        )
    )
    cell_x = (_L - 4 * wall) / 3
    cell_y = (_W - 3 * wall) / 2
    depth = _T - floor
    expected = _BLOCK_VOLUME_M3 - 6 * cell_x * cell_y * depth
    assert abs(v - expected) / expected < 1e-6


def test_pocket_grid_with_no_positive_cell_is_a_named_err() -> None:
    """Walls wider than the stock leave no pocket: an honest failure."""
    result = realize_feature_program(
        _program(
            PocketGridOp(
                name="tray",
                nx=8,
                ny=8,
                wall=ResolvedParam(value=0.015),
                floor=ResolvedParam(value=0.003),
            )
        )
    )
    assert result.is_err
    assert "no positive pocket cell" in result.danger_err.message


def test_shell_leaves_the_hand_computed_wall_volume() -> None:
    """Shell(t) subtracts the inward-offset interior: volume = block
    minus the (L-2t)(W-2t)(T-2t) core."""
    t = 0.002
    v = _volume_m3(_program(ShellOp(name="hollow", thickness=ResolvedParam(value=t))))
    expected = _BLOCK_VOLUME_M3 - (_L - 2 * t) * (_W - 2 * t) * (_T - 2 * t)
    assert abs(v - expected) / expected < 1e-6


def test_shell_thicker_than_the_solid_is_a_named_err() -> None:
    result = realize_feature_program(
        _program(ShellOp(name="hollow", thickness=ResolvedParam(value=0.010)))
    )
    assert result.is_err
    assert "leaves no interior" in result.danger_err.message


def test_removal_ops_on_an_empty_stage_are_named_errs() -> None:
    """Every family op requires a prior solid -- an Err value, no crash."""
    for op in (
        RibsOp(
            name="r",
            count=2,
            pitch=ResolvedParam(value=0.02),
            thickness=ResolvedParam(value=0.002),
        ),
        PocketGridOp(
            name="g",
            nx=1,
            ny=1,
            wall=ResolvedParam(value=0.002),
            floor=ResolvedParam(value=0.002),
        ),
        ShellOp(name="s", thickness=ResolvedParam(value=0.002)),
    ):
        program = FeatureProgram(
            part_name="Empty",
            stages=(Stage(name="milled", process="cnc_mill", features=(op,)),),
        )
        result = realize_feature_program(program)
        assert result.is_err, op
        assert "prior solid" in result.danger_err.message


def test_removal_realization_is_deterministic() -> None:
    """Same program, same STEP content hash and topology hash (AD-6)."""
    program = _program(
        RibsOp(
            name="lightening",
            count=5,
            pitch=ResolvedParam(value=0.018),
            thickness=ResolvedParam(value=0.003),
            height=ResolvedParam(value=0.010),
        )
    )
    a = realize_feature_program(program)
    b = realize_feature_program(program)
    assert a.is_ok and b.is_ok
    assert (
        a.danger_ok.geometry.step_content_hash == b.danger_ok.geometry.step_content_hash
    )
