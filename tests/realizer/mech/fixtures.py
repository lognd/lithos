"""Hand-built ``FeatureProgram`` fixtures standing in for the WO-19 producer.

The real lowering pass that would emit these does not exist yet (see
``regolith.realizer.mech.schema``'s module docstring / the WO-22 cuts
section) -- these fixtures ARE the contract's worked examples, loosely
modeled on ``examples/tracks/hematite/sheet_bracket.hema``'s flat-plate-plus-mount-
holes shape (the bend/press-brake stage is a separate fixture since it
exercises the reduced-fidelity bend approximation).
"""

from __future__ import annotations

from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    FilletOp,
    HoleOp,
    PatternOp,
    PocketOp,
    Point2,
    ProfileHole,
    ResolvedParam,
    Sketch,
    Stage,
)

# A simple 80mm x 50mm x 1.5mm plate -- SI metres.
_PLATE_OUTLINE = (
    Point2(x=0.0, y=0.0),
    Point2(x=0.08, y=0.0),
    Point2(x=0.08, y=0.05),
    Point2(x=0.0, y=0.05),
)
PLATE_VOLUME_M3 = 0.08 * 0.05 * 0.0015
PLATE_BBOX_M = (0.08, 0.05, 0.0015)


def plate_program(part_name: str = "flat_plate") -> FeatureProgram:
    """A bare extruded plate: the smallest well-formed feature program."""
    sketch = Sketch(name="plate", outline=_PLATE_OUTLINE)
    extrude = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=0.0015)
    )
    stage = Stage(name="cut", process="laser_cut", features=(extrude,))
    return FeatureProgram(part_name=part_name, material="AISI_304", stages=(stage,))


def bracket_program(part_name: str = "bracket") -> FeatureProgram:
    """A plate with a mount-hole pattern and an eased vertical edge.

    Mirrors ``examples/tracks/hematite/sheet_bracket.hema``'s cut stage: a plate
    profile with a `PatternOf<Pierce<...>>` 2x2 grid and a fillet pass.
    """
    sketch = Sketch(
        name="plate",
        outline=_PLATE_OUTLINE,
        holes=(
            ProfileHole(
                name="wire_pass",
                center=Point2(x=0.032, y=0.025),
                diameter=ResolvedParam(value=0.008),
            ),
        ),
    )
    extrude = ExtrudeOp(
        name="body", sketch=sketch, distance=ResolvedParam(value=0.0015)
    )
    pattern = PatternOp(
        name="mounts",
        base=HoleOp(
            name="mount",
            center=Point2(x=0.012, y=0.017),
            diameter=ResolvedParam(value=0.0045),
        ),
        offsets=(
            Point2(x=0.0, y=0.0),
            Point2(x=0.056, y=0.0),
            Point2(x=0.0, y=0.030),
            Point2(x=0.056, y=0.030),
        ),
    )
    fillet = FilletOp(
        name="ease", selector="vertical", radius=ResolvedParam(value=0.001)
    )
    stage = Stage(name="cut", process="laser_cut", features=(extrude, pattern, fillet))
    return FeatureProgram(part_name=part_name, material="AISI_304", stages=(stage,))


def pocketed_block_program(part_name: str = "pocketed_block") -> FeatureProgram:
    """A block extrusion with a shallow pocket cut into its top face."""
    sketch = Sketch(name="block", outline=_PLATE_OUTLINE)
    extrude = ExtrudeOp(name="body", sketch=sketch, distance=ResolvedParam(value=0.010))
    pocket_sketch = Sketch(
        name="pocket",
        outline=(
            Point2(x=0.02, y=0.01),
            Point2(x=0.06, y=0.01),
            Point2(x=0.06, y=0.04),
            Point2(x=0.02, y=0.04),
        ),
    )
    pocket = PocketOp(
        name="recess", sketch=pocket_sketch, depth=ResolvedParam(value=0.003)
    )
    stage = Stage(name="mill", process="cnc_mill", features=(extrude, pocket))
    return FeatureProgram(part_name=part_name, stages=(stage,))
