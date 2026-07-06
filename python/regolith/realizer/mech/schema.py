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
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Bumped on any incompatible change to this module's shapes (AD-5).
FEATURE_PROGRAM_SCHEMA_VERSION = 1


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


class Point2(BaseModel):
    """A resolved 2D point in a sketch's own plane, metres."""

    model_config = ConfigDict(frozen=True)

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        """The plain ``(x, y)`` pair (interpreter/build123d boundary)."""
        return (self.x, self.y)


class ProfileHole(BaseModel):
    """A circular hole cut directly into a sketch profile (`hole:` block)."""

    model_config = ConfigDict(frozen=True)

    name: str
    center: Point2
    diameter: ResolvedParam


class Sketch(BaseModel):
    """A resolved, closed 2D profile: an outline polygon plus interior holes.

    v1 cut: only straight `line` segments are represented (the resolved
    outline is already a closed polygon of points) -- `walk:` arcs and
    filleted profile corners are not in the v1 corpus feature set and
    are named-unsupported at the op level if encountered (never guessed
    at silently).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    outline: tuple[Point2, ...] = Field(min_length=3)
    holes: tuple[ProfileHole, ...] = ()


class ExtrudeOp(BaseModel):
    """Extrude a sketch profile by a resolved distance."""

    model_config = ConfigDict(frozen=True)

    op: Literal["extrude"] = "extrude"
    name: str
    sketch: Sketch
    distance: ResolvedParam


class PocketOp(BaseModel):
    """Cut a pocket of a resolved depth into the current solid's top face."""

    model_config = ConfigDict(frozen=True)

    op: Literal["pocket"] = "pocket"
    name: str
    sketch: Sketch
    depth: ResolvedParam


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


class BlankOp(BaseModel):
    """A sheet-metal flat blank: extrude a profile by the sheet gauge."""

    model_config = ConfigDict(frozen=True)

    op: Literal["blank"] = "blank"
    name: str
    sketch: Sketch
    thickness: ResolvedParam


class PierceOp(BaseModel):
    """A sheet-metal pierced hole -- geometrically a through hole."""

    model_config = ConfigDict(frozen=True)

    op: Literal["pierce"] = "pierce"
    name: str
    center: Point2
    diameter: ResolvedParam


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


FeatureOp = Annotated[
    ExtrudeOp | PocketOp | HoleOp | FilletOp | BlankOp | PierceOp | BendOp | PatternOp,
    Field(discriminator="op"),
]


class Stage(BaseModel):
    """One manufacturing stage: a named process and its ordered feature ops."""

    model_config = ConfigDict(frozen=True)

    name: str
    process: str
    features: tuple[FeatureOp, ...]


class FeatureProgram(BaseModel):
    """The whole deterministic, resolved feature program for one part.

    The realizer's ONLY input (AD-4): no CST, no unresolved expressions.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = FEATURE_PROGRAM_SCHEMA_VERSION
    part_name: str
    material: str | None = None
    stages: tuple[Stage, ...]

    def canonical_json(self) -> str:
        """Canonical (sorted-key, no-whitespace) JSON for content hashing."""
        return self.model_dump_json(exclude_none=False)

    def content_hash(self) -> str:
        """SHA-256 of the canonical JSON -- the determinism anchor (AD-6)."""
        import hashlib

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
