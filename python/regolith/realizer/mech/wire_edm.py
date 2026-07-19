"""Wire-EDM profile-cut program kind (WO-166 slice b, D268 item 3, AD-47
sec. 5 charter 44).

Mirrors WO-77's `Ribs`/`PocketGrid`/`Shell`/`Lattice` feature-op idiom
at the PLAIN-pydantic realizer layer (the same T-0043/D272 posture
`PerfboardNetlist` (WO-165) took: a brand-new capability's own input IR
lives beside its realizer, not inside the frozen `FeatureProgram`
schema -- no `crates/regolith-syntax`/`regolith-lower` change, no
`SCHEMA_VERSION` bump; promotable into parsed hematite grammar later if
a real WO opens that seam). `WireEdmProfile` is a THROUGH-CUT along a
closed or open 2D contour -- distinct from a milling removal op
(`Pocket`/`Bore`): the wire travels the ENTIRE declared contour, never
stopping partway to remove interior stock.

Corner radii are DECLARED per vertex (the caller states the fillet
radius it wants cut at each interior corner) rather than derived from
raw polyline geometry -- an honest v1 simplification (no arc-fitting
geometry engine here); `realize_wire_edm_profile` grounds each declared
radius against `check_wire_edm_corner_radius`
(:mod:`regolith.harness.models.dfm.checks`, WO-169 wave 1) and the
closed/start-hole pair against `check_wire_edm_start_hole`, refusing
(an `Err`) if either DFM check is violated -- never silently accepting
an un-machinable profile.

Emission (:func:`profile_drawing_model`) reuses the SAME `DrawingModel`
-> DXF renderer path every other drawing-producing track feeds
(`regolith.backends.drawings.renderer_dxf.render_dxf`, AD-27): the
kerf/lead-in/corner-radius metadata rides as `Annotation`/`Dimension`
entries on the SAME DXF file the contour geometry renders to, per this
WO's own preference ("prefer reusing DXF's existing role as a
transparent output format over inventing a new file format") -- this
is DXF's first OUTPUT-side use (previously input-only for sheet-metal
flat patterns, per the recon dossier).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    Annotation,
    DrawingModel,
    EntityIndice,
    Kind2,
    Point,
    Sheet,
    SheetSize2,
    TitleBlock,
    View,
    ViewSource,
)
from regolith._schema.models import (
    Entity3 as PolylineEntity,
)
from regolith.harness.models.cam.checks import CamOutcome
from regolith.harness.models.dfm.checks import (
    check_wire_edm_corner_radius,
    check_wire_edm_start_hole,
)
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

#: The D96-style realized-kind tag for this program's realized payload
#: (mirrors `board_assignment.realized`'s naming convention).
# frob:doc docs/modules/py-realizer.md#mech-wire-edm
EDM_PROFILE_DOMAIN_TAG = "edm_profile.realized"

#: The v1 provenance tier stamped on every EDM emission (WO-160/AD-45):
#: no real EDM-machine toolpath post-processor is claimed -- the profile
#: geometry and setup-sheet metadata are computed in-process.
# frob:doc docs/modules/py-realizer.md#mech-wire-edm
EDM_PROVENANCE_TIER = "deterministic"


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
class ProfileVertex(BaseModel):
    """One vertex of the 2D contour: an (x, y) point in mm plus the
    DECLARED fillet radius at this vertex (0.0 for a sharp corner the
    caller is not filleting -- still checked against the kerf/spark-gap
    floor by :func:`realize_wire_edm_profile`, since a wire physically
    cannot cut a zero-radius internal corner)."""

    model_config = ConfigDict(frozen=True)

    x_mm: float
    y_mm: float
    corner_radius_mm: float = Field(default=0.0, ge=0.0)


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
class LeadIn(BaseModel):
    """The wire's lead-in: where it threads onto the contour and
    whether a start hole is declared (required for a `closed` profile,
    per `check_wire_edm_start_hole` -- an open profile can lead in from
    outside stock, no start hole needed)."""

    model_config = ConfigDict(frozen=True)

    start_x_mm: float
    start_y_mm: float
    has_start_hole: bool = False


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
class WireEdmProfile(BaseModel):
    """This program's own input IR (see module docstring): a 2D
    contour, its closedness, kerf/spark-gap geometry, and lead-in --
    mirroring `PerfboardNetlist`'s "new capability, own minimal IR"
    precedent."""

    model_config = ConfigDict(frozen=True)

    profile_ref: str
    material_ref: str
    vertices: tuple[ProfileVertex, ...] = Field(min_length=2)
    closed: bool
    kerf_mm: float = Field(gt=0.0)
    spark_gap_mm: float = Field(ge=0.0)
    lead_in: LeadIn


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
class WireEdmError(BaseModel):
    """A wire-EDM realize failure VALUE (house Result doctrine): a
    corner-radius or start-hole DFM violation, never a bare exception
    for this recoverable, caller-facing condition."""

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
class RealizedWireEdmProfile(BaseModel):
    """The `edm_profile.realized` payload: the profile plus its two
    discharged DFM outcomes, kept alongside the geometry so a consumer
    (the die-set assembly, the demo's PROOF.md) can cite the SAME
    outcome object the realize step already computed rather than
    re-deriving it."""

    model_config = ConfigDict(frozen=True)

    profile: WireEdmProfile
    corner_radius_outcomes: tuple[CamOutcome, ...]
    start_hole_outcome: CamOutcome


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
def realize_wire_edm_profile(
    profile: WireEdmProfile,
) -> Result[RealizedWireEdmProfile, WireEdmError]:
    """Ground `profile` against the two REAL wire-EDM DFM checks WO-169
    wave 1 already landed (never re-derived here): every declared
    interior corner radius against the kerf/2 + spark-gap floor
    (:func:`check_wire_edm_corner_radius`), and the closed-profile /
    start-hole sequencing predicate
    (:func:`check_wire_edm_start_hole`). Refuses (an `Err`) on the
    FIRST violated corner or a violated start-hole gate -- a profile
    that cannot actually be cut is never realized."""
    corner_outcomes: list[CamOutcome] = []
    for i, vertex in enumerate(profile.vertices):
        outcome = check_wire_edm_corner_radius(
            vertex.corner_radius_mm, profile.kerf_mm, profile.spark_gap_mm
        )
        corner_outcomes.append(outcome)
        if outcome.violated:
            _log.error(
                "wire edm profile %r: vertex %d corner radius violated -- %s",
                profile.profile_ref,
                i,
                outcome.note,
            )
            return Err(
                WireEdmError(
                    kind="corner_radius_violation",
                    message=f"vertex {i}: {outcome.note}",
                )
            )

    start_hole_outcome = check_wire_edm_start_hole(
        profile.closed, profile.lead_in.has_start_hole
    )
    if start_hole_outcome.violated:
        _log.error(
            "wire edm profile %r: start-hole gate violated -- %s",
            profile.profile_ref,
            start_hole_outcome.note,
        )
        return Err(
            WireEdmError(
                kind="start_hole_violation",
                message=start_hole_outcome.note,
            )
        )

    _log.info(
        "wire edm profile %r: realized, %d vertex/vertices, closed=%s",
        profile.profile_ref,
        len(profile.vertices),
        profile.closed,
    )
    return Ok(
        RealizedWireEdmProfile(
            profile=profile,
            corner_radius_outcomes=tuple(corner_outcomes),
            start_hole_outcome=start_hole_outcome,
        )
    )


# frob:doc docs/modules/py-realizer.md#mech-wire-edm
def profile_drawing_model(realized: RealizedWireEdmProfile) -> DrawingModel:
    """Project a `RealizedWireEdmProfile` into a `DrawingModel` sheet:
    the contour as one closed/open polyline entity, plus kerf/lead-in/
    corner-radius metadata as annotations -- rendered to DXF by the
    EXISTING `render_dxf` path (AD-27, this module never draws bytes
    itself)."""
    profile = realized.profile
    points = [Point([v.x_mm, v.y_mm]) for v in profile.vertices]
    if profile.closed:
        points.append(points[0])
    entities = [PolylineEntity(kind=Kind2.polyline, points=points)]

    annotations = [
        Annotation(
            text=f"kerf={profile.kerf_mm:.3f}mm spark_gap={profile.spark_gap_mm:.3f}mm",
            anchor=[profile.vertices[0].x_mm, profile.vertices[0].y_mm],
            text_height_mm=2.0,
            datum_refs=[],
            per=None,
        ),
        Annotation(
            text=(
                f"lead-in ({profile.lead_in.start_x_mm:.3f}, "
                f"{profile.lead_in.start_y_mm:.3f}) "
                f"start_hole={profile.lead_in.has_start_hole}"
            ),
            anchor=[profile.lead_in.start_x_mm, profile.lead_in.start_y_mm],
            text_height_mm=2.0,
            datum_refs=[],
            per=None,
        ),
    ]
    for _i, vertex in enumerate(profile.vertices):
        if vertex.corner_radius_mm > 0.0:
            annotations.append(
                Annotation(
                    text=f"R{vertex.corner_radius_mm:.3f}",
                    anchor=[vertex.x_mm, vertex.y_mm],
                    text_height_mm=1.5,
                    datum_refs=[],
                    per=None,
                )
            )

    view = View(
        name="edm_profile",
        plane="schematic",
        scale=1.0,
        source=ViewSource(
            source_digest="sha256:" + profile.profile_ref,
            source_kind=EDM_PROFILE_DOMAIN_TAG,
        ),
        entity_indices=[EntityIndice(0)],
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{profile.profile_ref} wire-EDM profile cut",
            drawing_number=f"EDM-{profile.profile_ref}",
            revision="A",
            scale_label="NTS",
            subject=profile.profile_ref,
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=annotations,
        tables=[],
    )
    _log.info(
        "wire edm profile drawing: %s -> %d vertex/vertices, %d annotation(s)",
        profile.profile_ref,
        len(profile.vertices),
        len(annotations),
    )
    return DrawingModel(subject=profile.profile_ref, sheets=[sheet])


__all__ = [
    "EDM_PROFILE_DOMAIN_TAG",
    "EDM_PROVENANCE_TIER",
    "LeadIn",
    "ProfileVertex",
    "RealizedWireEdmProfile",
    "WireEdmError",
    "WireEdmProfile",
    "profile_drawing_model",
    "realize_wire_edm_profile",
]
