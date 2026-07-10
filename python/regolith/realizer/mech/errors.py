"""Realizer error VALUES (AD-7 house style): never a bare exception.

Every fallible realizer operation returns a typani ``Result`` whose
``Err`` is one of these frozen models. An unsupported op or a schema
version skew is a recoverable, honest deferral (INDETERMINATE
evidence upstream); an OCCT boolean-operation failure on otherwise
well-formed input is recorded as a value too -- it is a property of the
INPUT geometry (self-intersecting profile, degenerate bend), not a
programmer bug.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnsupportedFeature(BaseModel):
    """A feature op (or a variant of one) outside the v1 corpus feature set.

    Never a crash, never a silent skip (WO-22 acceptance): the caller
    turns this into an explicit `indeterminate geometry_realizable`
    evidence value naming the op.
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    op: str
    detail: str = ""


class SchemaVersionMismatch(BaseModel):
    """The ``FeatureProgram``'s ``schema_version`` is not one this realizer
    speaks (AD-5): refuse rather than guess at an incompatible shape."""

    model_config = ConfigDict(frozen=True)

    expected: int
    got: int


class GeometryFailure(BaseModel):
    """An OCCT/build123d operation failed on otherwise well-formed input.

    E.g. a self-intersecting sketch outline, a boolean cut that leaves
    no material, a degenerate bend line. The underlying exception
    message is captured for diagnostics; this VALUE is what every
    caller sees (never the raw exception, per house style).
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    op: str
    message: str


class BoreReferenceNotFound(BaseModel):
    """A declared flow segment's ``bore`` names no feature op in the program.

    D130's realizer duty: cross-validate a declared segment's ``bore``
    reference against the `FeatureProgram` that supposedly cuts it.
    A dangling reference is a producer-side inconsistency -- never a
    silent skip.
    """

    model_config = ConfigDict(frozen=True)

    selector: str
    role: str
    stage: str
    feature: str


class FlowAreaMismatch(BaseModel):
    """A declared segment's ``flow_area`` disagrees with its bore's
    resolved diameter beyond the realizer's tolerance (D130: "the
    geometry fixes the answer" -- a disagreement is data, never a
    silent preference for either side).
    """

    model_config = ConfigDict(frozen=True)

    selector: str
    role: str
    declared_area_m2: float
    bore_area_m2: float
    relative_error: float


class MissingMaterialProps(BaseModel):
    """A segment declares a ``wall`` record but the program has no
    part-level ``material_props`` to source Young's modulus from
    (WO-22 cut #2: the realizer owns no physics table, so E must
    always be producer-declared -- there is nothing to fall back to).
    """

    model_config = ConfigDict(frozen=True)

    role: str


class MateLoopResidual(BaseModel):
    """A mate-graph loop's closure residual exceeds the interface
    tolerance (charter `30-geometry-lowering.md` sec. 1.4: "a mate
    loop whose closure residual exceeds the interface tolerance is a
    DIAGNOSTIC citing the loop's mates -- the tolerance-stack
    machinery owns slack, the solver never hides it"). Never silently
    absorbed into either placement.
    """

    model_config = ConfigDict(frozen=True)

    mate_ids: tuple[str, ...]
    translation_residual_m: float
    rotation_residual_deg: float
    tolerance_m: float


class UnknownMatePart(BaseModel):
    """A mate names a part id absent from the assembly's declared part set."""

    model_config = ConfigDict(frozen=True)

    mate_id: str
    part_id: str


RealizeError = (
    UnsupportedFeature
    | SchemaVersionMismatch
    | GeometryFailure
    | BoreReferenceNotFound
    | FlowAreaMismatch
    | MissingMaterialProps
)

AssemblyRealizeError = MateLoopResidual | UnknownMatePart
