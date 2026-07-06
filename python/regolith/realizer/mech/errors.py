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


RealizeError = UnsupportedFeature | SchemaVersionMismatch | GeometryFailure
