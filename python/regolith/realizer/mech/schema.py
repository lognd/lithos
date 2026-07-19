"""The serialized feature-program IR the mech realizer consumes (AD-4/AD-5).

WO-22 status (see the WO file's "Cuts recorded this cycle" section):
`regolith-lower`/`BuildPayload` does not yet emit a stage/feature-op
structure -- WO-19's promised typed lowering surface for feature
programs does not exist in this checkout (confirmed against
`crates/regolith-api/src/session.rs::BuildPayload`, which carries only
diagnostics/resolutions/obligations/snapshots/evidence/ledger). Adding
that emission is `regolith-lower` work, explicitly out of WO-22's scope
per its own dispatch (touching `regolith-lower`/`regolith-sem` is
WO-28's territory). This module is therefore the FORWARD CONTRACT: the
schema a future lowering pass must emit, and the only form
:mod:`regolith.realizer.mech` ever consumes (AD-4: the Python realizer
never sees the CST). Until that producer lands, the realizer is
exercised directly against hand-built ``FeatureProgram`` values (see
``tests/realizer/mech/fixtures.py``).

Units: SI base (metres), matching every other harness input (house
convention, see e.g. `regolith.harness.models.sheet_bend`) -- NOT
build123d's native millimetre convention. The interpreter module is the
one place that converts at the OCCT boundary.

``schema_version`` follows the AD-5 precedent (WO-20/21/23): bump it on
any incompatible shape change; the realizer refuses an unknown version
rather than guessing.

Schema v2 (design-log `2026-07-08-cycle-25.md` D130, WO-42 deliverable 4
amended): adds part-level ``flow_paths`` and ``material_props``. The
wetted-path decomposition of a part -- which voids are wetted, how a
cavity decomposes into 1D routed segments, what the wall material's
modulus is -- is DECLARED design intent, never derived from the B-rep
solid (WO-22's "total and honest" posture: reconstructing a hydraulic
network from raw geometry is research-grade guessing the realizer must
never do). ``FlowPath``/``FlowSegment`` mirror the field list
``regolith-lower::extract``'s seam reads verbatim (`role`, `flow_area`,
`length`, optional `bend`, `roughness_class`, `elevation_change`,
optional `wall`), so the realizer's v1 duty is validate-and-emit: check
declared segments against the realized solid where geometry fixes the
answer, then emit the declared measures -- never derive-and-guess. The
selector convention for mech-emitted paths is pinned:
``<stage_name>.wetted`` (matches the WO-32 hand fixtures' coolant
example, `crates/regolith-lower/src/extract.rs`). The eventual producer
is hematite's `.cavity(inlet=...)` surface (`docs/spec/hematite/02-language.md`
sec. 6); until that lowering lands, hand-authored ``FeatureProgram``
fixtures declaring ``flow_paths`` are legitimate producers (AD-22).
Deferred with a reopen criterion in `docs/spec/hematite/07-open-questions.md`
sec. 2a.

``roughness_class`` is a free-string label validated against
``regolith-lower::extract``'s ``ROUGHNESS_TABLE`` on the Rust consumer
side (the single home for that table stays there, NO DUPLICATION); an
unknown label surfaces as the existing typed ``ExtractError`` there,
not here. ``wall`` on a ``FlowSegment`` is geometry only (thickness,
diameter) -- Young's modulus comes from the part-level
``material_props`` below, never from ``wall`` (WO-22 cut #2: the
realizer owns no physics table, so E is always producer-declared).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Bumped on any incompatible change to this module's shapes (AD-5).
# frob:doc docs/modules/py-realizer.md#mech-schema
FEATURE_PROGRAM_SCHEMA_VERSION = 2


# frob:doc docs/modules/py-realizer.md#mech-schema
class ResolvedParam(BaseModel):
    """One already-resolved scalar parameter, with its Cause tag (INV-21).

    ``cause`` mirrors the compiler's resolution-cause vocabulary at the
    string level only (v1 cut: the richer typed `Cause` enum -- literal /
    dfm(...) / derived(...) -- is not modeled here since no producer
    emits it yet; see the module docstring).
    """

    model_config = ConfigDict(frozen=True)

    value: float
    cause: str = "literal"


# frob:doc docs/modules/py-realizer.md#mech-schema
class Point2(BaseModel):
    """A resolved 2D point in a sketch's own plane, metres."""

    model_config = ConfigDict(frozen=True)

    x: float
    y: float

    # frob:doc docs/modules/py-realizer.md#mech-schema
    def as_tuple(self) -> tuple[float, float]:
        """The plain ``(x, y)`` pair (interpreter/build123d boundary)."""
        return (self.x, self.y)


# frob:doc docs/modules/py-realizer.md#mech-schema
class ProfileHole(BaseModel):
    """A circular hole cut directly into a sketch profile (`hole:` block)."""

    model_config = ConfigDict(frozen=True)

    name: str
    center: Point2
    diameter: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class ProfileArc(BaseModel):
    """A tangent/radius arc edge of a resolved profile walk (WO-104): the
    arc from the previous vertex to ``to``, bulging ``sense`` (`left` =
    counter-clockwise, `right` = clockwise) with signed ``radius``. The
    realizer builds a REAL arc edge (b3d ``RadiusArc``) -- the Rust IR's
    ``ClosureSegment.arc`` promoted into geometry, never a chord
    approximation.
    """

    model_config = ConfigDict(frozen=True)

    to: Point2
    radius: ResolvedParam
    sense: str = "left"


# frob:doc docs/modules/py-realizer.md#mech-schema
class Sketch(BaseModel):
    """A resolved, closed 2D profile: an outline polygon plus interior
    holes, optionally with arc edges (WO-104).

    ``outline`` is the closed polygon of straight-segment vertices. When
    ``arcs`` is non-empty, the profile is built as a mixed line/arc walk:
    each ``ProfileArc`` replaces the STRAIGHT segment ENDING at its ``to``
    vertex with a real arc edge (the Rust ``ClosureSegment.arc``
    promotion realized). An empty ``arcs`` is the straight-line-only path
    (unchanged v1 behaviour).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    outline: tuple[Point2, ...] = Field(min_length=3)
    holes: tuple[ProfileHole, ...] = ()
    arcs: tuple[ProfileArc, ...] = ()


# frob:doc docs/modules/py-realizer.md#mech-schema
class ExtrudeOp(BaseModel):
    """Extrude a sketch profile by a resolved distance."""

    model_config = ConfigDict(frozen=True)

    op: Literal["extrude"] = "extrude"
    name: str
    sketch: Sketch
    distance: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class PocketOp(BaseModel):
    """Cut a pocket of a resolved depth into the current solid's top face."""

    model_config = ConfigDict(frozen=True)

    op: Literal["pocket"] = "pocket"
    name: str
    sketch: Sketch
    depth: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class HoleOp(BaseModel):
    """A round hole at a point, resolved diameter, optional resolved depth.

    ``depth is None`` means through-all (the v1 through-hole default).
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["hole"] = "hole"
    name: str
    center: Point2
    diameter: ResolvedParam
    depth: ResolvedParam | None = None


# frob:doc docs/modules/py-realizer.md#mech-schema
class FilletOp(BaseModel):
    """Round edges matched by ``selector`` with a resolved radius.

    v1 cut: edge selection is coarse (``"all"``, ``"top"``, ``"bottom"``,
    ``"vertical"``) -- named-edge/topological-reference selection (e.g.
    "the edge produced by feature X") needs a feature-to-edge naming
    scheme the corpus's lowering does not define yet; recorded as a cut
    in the WO file rather than invented here.
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["fillet"] = "fillet"
    name: str
    selector: Literal["all", "top", "bottom", "vertical"]
    radius: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class BlankOp(BaseModel):
    """A sheet-metal flat blank: extrude a profile by the sheet gauge."""

    model_config = ConfigDict(frozen=True)

    op: Literal["blank"] = "blank"
    name: str
    sketch: Sketch
    thickness: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class PierceOp(BaseModel):
    """A sheet-metal pierced hole -- geometrically a through hole."""

    model_config = ConfigDict(frozen=True)

    op: Literal["pierce"] = "pierce"
    name: str
    center: Point2
    diameter: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class BendOp(BaseModel):
    """A sheet-metal bend about a line, by a resolved angle and radius.

    v1 cut (recorded in the WO file): this is a RIGID rotation of the
    material on one side of ``line`` -- no bend-allowance / K-factor flat-
    pattern length correction is modeled (that needs a sheet-metal
    unfold model this WO does not own). The realized part's overall
    envelope after a bend is therefore only approximate versus a real
    shop's flat-pattern practice; it is real, checkable OCCT geometry,
    never a crash and never a silent no-op.
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["bend"] = "bend"
    name: str
    line: tuple[Point2, Point2]
    angle_deg: ResolvedParam
    radius: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class PatternOp(BaseModel):
    """Repeat one base feature op at a set of resolved planar offsets.

    v1 cut: only translation offsets (grid/linear patterns) are modeled;
    the base op is itself a single non-pattern feature (no nested
    patterns) -- the corpus's `PatternOf<Pierce<...>>(n=4, grid(...))`
    lowers to this shape with ``offsets`` already the resolved instance
    centers.
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["pattern"] = "pattern"
    name: str
    base: Annotated[
        ExtrudeOp | PocketOp | HoleOp | PierceOp,
        Field(discriminator="op"),
    ]
    offsets: tuple[Point2, ...] = Field(min_length=1)


# frob:doc docs/modules/py-realizer.md#mech-schema
class RibsOp(BaseModel):
    """A declared rib-pattern material removal (WO-77, charter 34 phase 1).

    Removes a band of depth ``height`` from the current solid's TOP
    face, leaving ``count`` ribs of ``thickness`` spaced at ``pitch``
    (centre-to-centre), centred on the solid's X midline and running
    the full Y extent. ``height is None`` means the full solid depth
    (the charter's "defaults to the target region's depth").

    v1 semantics are deliberately primitive (axis-aligned, top-face,
    full-Y ribs) -- real, checkable OCCT geometry whose mass responds
    to every parameter, never a fake. Orientation control is future
    vocabulary, not silently guessed here.
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["ribs"] = "ribs"
    name: str
    count: int = Field(ge=1)
    pitch: ResolvedParam
    thickness: ResolvedParam
    height: ResolvedParam | None = None


# frob:doc docs/modules/py-realizer.md#mech-schema
class PocketGridOp(BaseModel):
    """A declared pocket-grid material removal (WO-77).

    Cuts an ``nx`` x ``ny`` grid of rectangular pockets into the
    current solid's top face, separated (and bordered) by walls of
    ``wall`` thickness, leaving a ``floor`` of stock under each pocket.
    ``depth is None`` derives the pocket depth as the solid depth minus
    ``floor`` (the charter's "through-depth minus floor").
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["pocket_grid"] = "pocket_grid"
    name: str
    nx: int = Field(ge=1)
    ny: int = Field(ge=1)
    wall: ResolvedParam
    floor: ResolvedParam
    depth: ResolvedParam | None = None


# frob:doc docs/modules/py-realizer.md#mech-schema
class ShellOp(BaseModel):
    """A declared shell/hollow-out removal (WO-77): subtract the solid
    deflated by ``thickness`` from itself, leaving a closed shell of
    that wall thickness (a closed internal void -- whether a PROCESS
    can actually make it is the DFM tier's question, not geometry's).
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["shell"] = "shell"
    name: str
    thickness: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class RectPocketOp(BaseModel):
    """A declared rectangular interior pocket (WO-104): cut ONE centered
    rectangular cavity -- ``width`` x ``depth_xy`` cross-section, cut
    ``height`` deep from the current solid's top face -- the RectTube
    stock cavity. ``corner_radius``, when spelled, rounds the four
    vertical edges (a real end-mill cannot cut a sharp internal corner);
    ``None`` leaves them sharp (the geometry-only nominal).
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["rect_pocket"] = "rect_pocket"
    name: str
    width: ResolvedParam
    depth_xy: ResolvedParam
    height: ResolvedParam
    corner_radius: ResolvedParam | None = None


FeatureOp = Annotated[
    ExtrudeOp
    | PocketOp
    | HoleOp
    | FilletOp
    | BlankOp
    | PierceOp
    | BendOp
    | PatternOp
    | RibsOp
    | PocketGridOp
    | ShellOp
    | RectPocketOp,
    Field(discriminator="op"),
]


# frob:doc docs/modules/py-realizer.md#mech-schema
class Stage(BaseModel):
    """One manufacturing stage: a named process and its ordered feature ops."""

    model_config = ConfigDict(frozen=True)

    name: str
    process: str
    features: tuple[FeatureOp, ...]


# frob:doc docs/modules/py-realizer.md#mech-schema
class FeatureOpRef(BaseModel):
    """A reference to one feature op by (stage name, op name) -- for
    cross-validating a declared flow segment's ``bore`` against the
    `FeatureProgram` that actually cuts it (D130). Validation-only: not
    consumed by anything else in v1.
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    feature: str


# frob:doc docs/modules/py-realizer.md#mech-schema
class Bend(BaseModel):
    """Resolved bend geometry on a routed flow segment: turn angle and
    centreline radius, Cause-tagged like every other resolved param.
    """

    model_config = ConfigDict(frozen=True)

    angle: ResolvedParam
    radius: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class FlowWall(BaseModel):
    """Geometry-only wall record on a flow segment (thickness, diameter).

    E/modulus is NOT here (WO-22 cut #2: the realizer owns no physics
    table) -- it comes from the part-level `MaterialProps` below.
    """

    model_config = ConfigDict(frozen=True)

    thickness: ResolvedParam
    diameter: ResolvedParam


# frob:doc docs/modules/py-realizer.md#mech-schema
class FlowSegment(BaseModel):
    """One declared routed segment of a wetted flow path (D130).

    Mirrors, field-for-field, what `regolith-lower::extract`'s seam
    reads: ``role`` (the seam's per-segment environment slot, a free
    string shared with the WO-34 wire-run convention -- not a closed
    enum), an optional ``bore`` reference for realizer cross-validation
    against the solid, resolved ``flow_area``/``length``/
    ``elevation_change``, optional ``bend``, a ``roughness_class`` label
    (validated against the `ROUGHNESS_TABLE` on the Rust consumer side,
    not here), and an optional geometry-only ``wall``.
    """

    model_config = ConfigDict(frozen=True)

    role: str
    bore: FeatureOpRef | None = None
    flow_area: ResolvedParam
    length: ResolvedParam
    elevation_change: ResolvedParam
    bend: Bend | None = None
    roughness_class: str
    wall: FlowWall | None = None


# frob:doc docs/modules/py-realizer.md#mech-schema
class FlowPath(BaseModel):
    """One selector-keyed, ordered routed path (D130).

    ``selector`` convention for mech-emitted paths is pinned:
    ``<stage_name>.wetted`` (matches the WO-32 hand fixtures' example,
    `crates/regolith-lower/src/extract.rs`).
    """

    model_config = ConfigDict(frozen=True)

    selector: str
    segments: tuple[FlowSegment, ...]


# frob:doc docs/modules/py-realizer.md#mech-schema
class MaterialProps(BaseModel):
    """Resolved material property VALUES, Cause-tagged, resolved
    PRODUCER-side (D130) -- the realizer never derives these (WO-22 cut
    #2's "no physics table in the realizer" stands unchanged).
    """

    model_config = ConfigDict(frozen=True)

    youngs_modulus: ResolvedParam
    density: ResolvedParam | None = None


# frob:doc docs/modules/py-realizer.md#mech-schema
class FeatureProgram(BaseModel):
    """The whole deterministic, resolved feature program for one part.

    The realizer's ONLY input (AD-4): no CST, no unresolved expressions.

    v2 (D130): ``flow_paths`` and ``material_props`` are the DECLARED
    wetted-path/material design intent a v1 realizer validates against
    the realized solid and emits verbatim -- see the module docstring.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = FEATURE_PROGRAM_SCHEMA_VERSION
    part_name: str
    material: str | None = None
    stages: tuple[Stage, ...]
    flow_paths: tuple[FlowPath, ...] = ()
    material_props: MaterialProps | None = None

    # frob:doc docs/modules/py-realizer.md#mech-schema
    def canonical_json(self) -> str:
        """Canonical (sorted-key, no-whitespace) JSON for content hashing."""
        return self.model_dump_json(exclude_none=False)

    # frob:doc docs/modules/py-realizer.md#mech-schema
    def content_hash(self) -> str:
        """SHA-256 of the canonical JSON -- the determinism anchor (AD-6)."""
        import hashlib

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
