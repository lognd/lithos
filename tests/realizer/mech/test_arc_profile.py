"""WO-104: the mech realizer promotes profile arcs to REAL arc edges
(the Rust ``ClosureSegment.arc`` promotion realized in OCCT), never a
chord approximation -- proven by the arc edge appearing as a real
CIRCLE-geometry edge, and by the extrusion realizing to a valid solid.
"""

from __future__ import annotations

import build123d as b3d
from regolith.realizer.mech.interpreter import (
    _extrude_solid,
    _profile_face,
    realize_feature_program,
)
from regolith.realizer.mech.schema import (
    ExtrudeOp,
    FeatureProgram,
    Point2,
    ProfileArc,
    ResolvedParam,
    Sketch,
    Stage,
)


def _rounded_square() -> Sketch:
    """A 50mm square whose top-right segment is a real arc edge."""
    return Sketch(
        name="rounded",
        outline=(
            Point2(x=0.0, y=0.0),
            Point2(x=0.050, y=0.0),
            Point2(x=0.050, y=0.050),
            Point2(x=0.0, y=0.050),
        ),
        arcs=(
            ProfileArc(
                to=Point2(x=0.050, y=0.050),
                radius=ResolvedParam(value=0.050),
                sense="left",
            ),
        ),
    )


def test_arc_profile_yields_a_real_arc_edge() -> None:
    face = _profile_face(_rounded_square()).faces()[0]
    edges = face.edges()
    # Four boundary edges; exactly one is a real circular arc (not a chord).
    assert len(edges) == 4
    arc_edges = [e for e in edges if e.geom_type == b3d.GeomType.CIRCLE]
    assert len(arc_edges) == 1


def test_straight_only_profile_has_no_arc_edges() -> None:
    straight = Sketch(
        name="plain",
        outline=(
            Point2(x=0.0, y=0.0),
            Point2(x=0.050, y=0.0),
            Point2(x=0.050, y=0.050),
            Point2(x=0.0, y=0.050),
        ),
    )
    face = _profile_face(straight).faces()[0]
    assert all(e.geom_type == b3d.GeomType.LINE for e in face.edges())


def test_arc_profile_extrudes_to_a_valid_solid() -> None:
    solid = _extrude_solid(_rounded_square(), height_mm=10.0)
    assert len(solid.solids()) == 1
    assert solid.volume > 0.0


def test_arc_profile_extrusion_realizes_end_to_end() -> None:
    program = FeatureProgram(
        part_name="ArcBeam",
        stages=(
            Stage(
                name="cut",
                process="extrusion",
                features=(
                    ExtrudeOp(
                        name="body",
                        sketch=_rounded_square(),
                        distance=ResolvedParam(value=0.010),
                    ),
                ),
            ),
        ),
    )
    result = realize_feature_program(program)
    assert result.is_ok, result.danger_err
    assert result.danger_ok.geometry.topology.volume_mm3 > 0.0
