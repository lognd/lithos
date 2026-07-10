"""WO-64 phase C: the two mech sites wall W4's fix (phase B, commit
354cdff) unblocked, both proven realizing to STEP the same way the
phase-B ledger proved `bed.hema`/`xy_gantry.hema` (`realize_feature_
program` over a hand-built `FeatureProgram` mirroring the source
file's own declared geometry -- no `.hema` source in this repo reaches
a full CLI `ship` end-to-end yet, `tests/backends/test_ship.py`'s own
documented wall, unchanged this dispatch):

- `z_motion.hema`'s `BedCarriage`: one milled block carrying both
  `LeadscrewMount.bearing_bore` (a through `Bore`, projecting to the
  realizer's `HoleOp` -- the exact op `coolant_bracket_program`'s own
  `coolant_bore` fixture proves, `tests/realizer/mech/fixtures.py`)
  and `BuildPlatformMount.platform` (the block's own top face).
- `xy_gantry.hema`'s `YCarriage.HotendPocket`: the sheet blank
  continues into a `cnc_mill` stage (`from=cut`, `pedal_box.hema`'s
  own cross-process chaining precedent) that mills a blind internal
  bore (`HoleOp` WITH a `depth`, distinguishing it from a `Pierce`
  through-hole) rather than colliding a second `Blank` declaration
  into the sheet-metal one.
"""

from __future__ import annotations

import math

from regolith.realizer.mech.interpreter import realize_feature_program
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    HoleOp,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

# Mirrors `z_motion.hema`'s `CarriageBlockOutline` (230mm square) and
# `BedCarriage.milled` stage (12mm-deep block, 8mm through bore on the
# leadscrew axis).
_BLOCK_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.230, y=0.0),
    Point2(x=0.230, y=0.230),
    Point2(x=0.0, y=0.230),
)
_BLOCK_DEPTH_M = 0.012
_BORE_DIAMETER_M = 0.008


def _bed_carriage_program() -> FeatureProgram:
    sketch = Sketch(name="body", outline=_BLOCK_OUTLINE)
    extrude = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=_BLOCK_DEPTH_M)
    )
    bore = HoleOp(
        name="z_nut_bore",
        center=Point2(x=0.115, y=0.115),
        diameter=ResolvedParam(value=_BORE_DIAMETER_M),
        depth=ResolvedParam(value=_BLOCK_DEPTH_M),
    )
    stage = Stage(name="milled", process="cnc_mill", features=(extrude, bore))
    return FeatureProgram(
        part_name="BedCarriage", material="AL6061_T6", stages=(stage,)
    )


def test_bed_carriage_milled_block_with_bore_realizes_to_step() -> None:
    result = realize_feature_program(_bed_carriage_program())
    assert result.is_ok, result.danger_err
    realized = result.danger_ok

    # A real solid: nonzero volume, and less than the un-bored block's
    # volume (the bore actually removed material).
    unbored_volume_mm3 = (
        (_BLOCK_OUTLINE[1].x - _BLOCK_OUTLINE[0].x)
        * (_BLOCK_OUTLINE[2].y - _BLOCK_OUTLINE[1].y)
        * _BLOCK_DEPTH_M
        * 1.0e9
    )
    assert 0.0 < realized.geometry.topology.volume_mm3 < unbored_volume_mm3

    step_bytes = realized.step_bytes
    assert step_bytes.startswith(b"ISO-10303-21;")

    # Byte-identical STEP across two independent realizes (the same
    # determinism bar `test_wo64_xy_gantry_assembly.py`'s own assembly
    # proof holds parts to, AD-6).
    again = realize_feature_program(_bed_carriage_program())
    assert again.is_ok, again.danger_err
    assert again.danger_ok.step_bytes == step_bytes


# Mirrors `xy_gantry.hema`'s `YCarriageFlat` (60x40mm) 3mm sheet plate
# plus the `pocket` stage's 18mm-diameter, 2mm-deep blind bore.
_Y_CARRIAGE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.060, y=0.0),
    Point2(x=0.060, y=0.040),
    Point2(x=0.0, y=0.040),
)
_Y_CARRIAGE_SHEET_M = 0.003
_HOTEND_BORE_DIAMETER_M = 0.018
_HOTEND_BORE_DEPTH_M = 0.002


def _y_carriage_program() -> FeatureProgram:
    sketch = Sketch(name="blank", outline=_Y_CARRIAGE_OUTLINE)
    extrude = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=_Y_CARRIAGE_SHEET_M)
    )
    cut_stage = Stage(name="cut", process="laser_cut", features=(extrude,))

    bore = HoleOp(
        name="hotend_bore",
        center=Point2(x=0.030, y=0.020),
        diameter=ResolvedParam(value=_HOTEND_BORE_DIAMETER_M),
        depth=ResolvedParam(value=_HOTEND_BORE_DEPTH_M),
    )
    pocket_stage = Stage(name="pocket", process="cnc_mill", features=(bore,))

    return FeatureProgram(
        part_name="YCarriage", material="AL6061_T6", stages=(cut_stage, pocket_stage)
    )


def test_y_carriage_milled_blind_bore_pocket_realizes_to_step() -> None:
    """A blind (depth-limited) `HoleOp` -- the projection of `xy_gantry
    .hema`'s `Bore(dia 18mm, depth=2mm)` -- distinguishes the pocket
    from a through `Pierce`: it must remove LESS volume than a through
    hole of the same diameter would (the bore does not reach the
    sheet's far face)."""
    result = realize_feature_program(_y_carriage_program())
    assert result.is_ok, result.danger_err
    realized = result.danger_ok

    plate_volume_mm3 = (
        (_Y_CARRIAGE_OUTLINE[1].x - _Y_CARRIAGE_OUTLINE[0].x)
        * (_Y_CARRIAGE_OUTLINE[2].y - _Y_CARRIAGE_OUTLINE[1].y)
        * _Y_CARRIAGE_SHEET_M
        * 1.0e9
    )
    through_bore_removed_mm3 = (
        math.pi * (_HOTEND_BORE_DIAMETER_M / 2.0) ** 2 * _Y_CARRIAGE_SHEET_M * 1.0e9
    )
    assert 0.0 < realized.geometry.topology.volume_mm3 < plate_volume_mm3
    assert (
        realized.geometry.topology.volume_mm3
        > plate_volume_mm3 - through_bore_removed_mm3
    )

    step_bytes = realized.step_bytes
    assert step_bytes.startswith(b"ISO-10303-21;")
    again = realize_feature_program(_y_carriage_program())
    assert again.is_ok, again.danger_err
    assert again.danger_ok.step_bytes == step_bytes
