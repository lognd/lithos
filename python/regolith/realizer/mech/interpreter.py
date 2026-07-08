"""The build123d/OCCT interpreter for a resolved v1 ``FeatureProgram``.

AD-1: OCCT via build123d, exclusively -- this is the one module that
imports it. AD-4: consumes ONLY the serialized ``FeatureProgram``
(``regolith.realizer.mech.schema``), never the CST. AD-6 determinism:
the same ``FeatureProgram`` always drives the exact same sequence of
build123d calls in the exact same order, so the resulting STEP content
hash and topology summary are reproducible on one platform. OCCT's STEP
writer stamps a real wall-clock export timestamp in ``FILE_NAME(...)``;
:func:`_export_step_bytes` normalizes it to a fixed sentinel so
``step_content_hash`` is genuinely byte-deterministic rather than
merely "close" (recorded here since it is the one place a real
non-determinism was found and closed). ``TopologySummary.content_hash``
is the CROSS-platform golden (OCCT's own STEP serialization is not
byte-stable across builds/platforms, WO-22 acceptance).

Coordinates: the schema is metres (SI base, house convention); build123d
is natively millimetre-scaled, so every point/scalar is converted at
this module's boundary (``_MM_PER_M``) and nowhere else.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import cast

import build123d as b3d
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    Bend as WireBend,
)
from regolith._schema.models import (
    PathSegment,
    RealizedGeometry,
    RoutedPath,
    TopologySummary,
)
from regolith._schema.models import (
    Wall as WireWall,
)
from regolith.logging_setup import get_logger
from regolith.realizer.mech.errors import (
    BoreReferenceNotFound,
    FlowAreaMismatch,
    GeometryFailure,
    MissingMaterialProps,
    RealizeError,
    SchemaVersionMismatch,
    UnsupportedFeature,
)
from regolith.realizer.mech.schema import (
    FEATURE_PROGRAM_SCHEMA_VERSION,
    BendOp,
    BlankOp,
    ExtrudeOp,
    FeatureOpRef,
    FeatureProgram,
    FilletOp,
    FlowSegment,
    HoleOp,
    MaterialProps,
    PatternOp,
    PierceOp,
    PocketOp,
    Sketch,
)

_log = get_logger(__name__)

# Conversion factor at the ONE boundary between the schema's SI metres
# and build123d's native millimetre scale.
_MM_PER_M = 1000.0

# Generous overcut margin (mm) so a through cutter always fully clears
# the solid it is subtracted from, regardless of stage height ordering.
_THROUGH_MARGIN_MM = 50.0


class RealizedGeometryArtifact(BaseModel):
    """One realized part: raw STEP bytes (side artifact) + the promoted
    ``RealizedGeometry`` semantic payload (AD-25/D128, WO-42 deliverable 1).

    AD-22 promotion: WO-22's hand-written ``TopologySummary``/
    ``RealizedGeometry`` forward-contract classes are DELETED here -- the
    schema is now sourced in Rust (``regolith_oblig::geometry``) and
    generated into ``regolith._schema.models.RealizedGeometry`` (AD-5).
    The generated model carries only the semantic payload (mass
    properties, topology, selector-keyed wetted-geometry paths); the raw
    STEP bytes stay a pinned side artifact per the WO body ("STEP stays
    a pinned side artifact + evidence"), so this thin non-schema wrapper
    bundles the two together for this module's callers.

    ``paths`` is populated by :func:`_validate_and_emit_flow_paths` (D130/
    D131, WO-42 deliverable 4): every declared ``FlowPath`` on the input
    `FeatureProgram` is cross-validated against the program's feature
    ops (bore existence; declared ``flow_area`` vs. a bored segment's
    resolved diameter) and, on agreement, emitted verbatim as
    degenerate-interval ``PathSegment`` records keyed by the pinned
    ``<stage_name>.wetted`` selector convention. Cavity-volume
    cross-checks against the realized solid are deferred until the
    `.cavity` surface lands (D130); a v1 realizer never derives a
    wetted-path decomposition from raw geometry.
    """

    model_config = ConfigDict(frozen=True)

    step_bytes: bytes
    geometry: RealizedGeometry


def _profile_face(sketch: Sketch) -> b3d.Sketch:
    """Build the (mm) outline-minus-holes face for a resolved ``Sketch``."""
    pts_mm = [(p.x * _MM_PER_M, p.y * _MM_PER_M) for p in sketch.outline]
    face = b3d.Sketch() + b3d.Polygon(*pts_mm, align=None)
    for hole in sketch.holes:
        r_mm = (hole.diameter.value * _MM_PER_M) / 2.0
        cx_mm = hole.center.x * _MM_PER_M
        cy_mm = hole.center.y * _MM_PER_M
        cutter = b3d.Circle(r_mm).located(b3d.Location((cx_mm, cy_mm, 0)))
        face = face - cutter
    return cast("b3d.Sketch", face)


def _extrude_solid(sketch: Sketch, height_mm: float) -> b3d.Part:
    """Extrude a resolved sketch (outline minus holes) by ``height_mm``."""
    return b3d.extrude(_profile_face(sketch), amount=height_mm)


def _through_cutter(
    center_x_mm: float, center_y_mm: float, radius_mm: float
) -> b3d.Part:
    """A round cutter tall enough to clear any v1 part, for a through hole."""
    circle = b3d.Circle(radius_mm).located(
        b3d.Location((center_x_mm, center_y_mm, -_THROUGH_MARGIN_MM / 2.0))
    )
    face = cast("b3d.Sketch", b3d.Sketch() + circle)
    return b3d.extrude(face, amount=_THROUGH_MARGIN_MM)


def _fillet_selector(part: b3d.Part, selector: str) -> object:
    """Resolve the v1 coarse fillet edge selector (schema.FilletOp docstring)."""
    edges = part.edges()
    if selector == "all":
        return edges
    if selector == "vertical":
        return edges.filter_by(b3d.Axis.Z)
    bbox = part.bounding_box()
    if selector == "top":
        return edges.filter_by_position(b3d.Axis.Z, bbox.max.Z, bbox.max.Z)
    return edges.filter_by_position(b3d.Axis.Z, bbox.min.Z, bbox.min.Z)


def _apply_base_cutter_or_solid(
    state: b3d.Part | None, op: ExtrudeOp | PocketOp | HoleOp | PierceOp, *, stage: str
) -> Result[b3d.Part, RealizeError]:
    """Apply one non-pattern base op to ``state`` (union or subtract)."""
    if isinstance(op, ExtrudeOp):
        solid = _extrude_solid(op.sketch, op.distance.value * _MM_PER_M)
        return Ok(solid if state is None else cast("b3d.Part", state + solid))
    if state is None:
        return Err(
            GeometryFailure(
                stage=stage,
                op=op.op,
                message=f"{op.op} '{op.name}' requires a prior solid in this stage",
            )
        )
    if isinstance(op, PocketOp):
        bbox = state.bounding_box()
        depth_mm = op.depth.value * _MM_PER_M
        face = _profile_face(op.sketch)
        cutter = b3d.extrude(face, amount=-(depth_mm)).moved(
            b3d.Location((0, 0, bbox.max.Z))
        )
        return Ok(cast("b3d.Part", state - cutter))
    if isinstance(op, (HoleOp, PierceOp)):
        cx_mm = op.center.x * _MM_PER_M
        cy_mm = op.center.y * _MM_PER_M
        r_mm = (op.diameter.value * _MM_PER_M) / 2.0
        cutter = _through_cutter(cx_mm, cy_mm, r_mm)
        return Ok(cast("b3d.Part", state - cutter))
    return Err(UnsupportedFeature(stage=stage, op=op.op))


def _apply_feature(
    state: b3d.Part | None, op: object, *, stage: str
) -> Result[b3d.Part, RealizeError]:
    """Dispatch one feature op onto the running solid state (Result-total)."""
    try:
        if isinstance(op, BlankOp):
            solid = _extrude_solid(op.sketch, op.thickness.value * _MM_PER_M)
            return Ok(solid if state is None else cast("b3d.Part", state + solid))
        if isinstance(op, (ExtrudeOp, PocketOp, HoleOp, PierceOp)):
            return _apply_base_cutter_or_solid(state, op, stage=stage)
        if isinstance(op, FilletOp):
            if state is None:
                return Err(
                    GeometryFailure(
                        stage=stage, op=op.op, message="fillet on empty state"
                    )
                )
            edges = cast(
                "b3d.ShapeList[b3d.Edge]", _fillet_selector(state, op.selector)
            )
            filleted = cast(
                "b3d.Part",
                b3d.fillet(edges, radius=op.radius.value * _MM_PER_M),
            )
            return Ok(filleted)
        if isinstance(op, BendOp):
            return _apply_bend(state, op, stage=stage)
        if isinstance(op, PatternOp):
            return _apply_pattern(state, op, stage=stage)
        return Err(UnsupportedFeature(stage=stage, op=getattr(op, "op", "?")))
    except Exception as exc:  # noqa: BLE001 -- OCCT failures are data, not bugs
        _log.info("geometry op failed: stage=%s op=%r error=%s", stage, op, exc)
        return Err(
            GeometryFailure(stage=stage, op=getattr(op, "op", "?"), message=str(exc))
        )


def _apply_bend(
    state: b3d.Part | None, op: BendOp, *, stage: str
) -> Result[b3d.Part, RealizeError]:
    """Rigid-rotation bend approximation (schema.BendOp: no bend allowance)."""
    if state is None:
        return Err(
            GeometryFailure(stage=stage, op=op.op, message="bend on empty state")
        )
    p0 = (op.line[0].x * _MM_PER_M, op.line[0].y * _MM_PER_M, 0.0)
    p1 = (op.line[1].x * _MM_PER_M, op.line[1].y * _MM_PER_M, 0.0)
    axis = b3d.Axis(p0, (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]))
    plane = b3d.Plane(origin=p0, z_dir=(p1[1] - p0[1], -(p1[0] - p0[0]), 0.0))
    try:
        far, near = state.split(plane, keep=b3d.Keep.BOTH)
    except ValueError:
        return Err(
            GeometryFailure(
                stage=stage, op=op.op, message="bend line does not split the solid"
            )
        )
    far_part = cast("b3d.Part", far)
    near_part = cast("b3d.Part", near)
    rotated = far_part.rotate(axis, op.angle_deg.value)
    joined = cast("b3d.Part", near_part + rotated)
    radius_mm = op.radius.value * _MM_PER_M
    if radius_mm <= 0.0:
        return Ok(joined)
    try:
        crease_edges = (
            joined.edges()
            .filter_by(b3d.Axis.Z)
            .filter_by(
                lambda e: (
                    abs(e.center().X - p0[0]) < 1e-6
                    and abs(e.center().Y - p0[1]) < 1e-6
                )
            )
        )
        if len(crease_edges) == 0:
            return Ok(joined)
        return Ok(cast("b3d.Part", b3d.fillet(crease_edges, radius=radius_mm)))
    except Exception as exc:  # noqa: BLE001 -- crease fillet is best-effort
        _log.info("bend crease fillet skipped: %s", exc)
        return Ok(joined)


def _apply_pattern(
    state: b3d.Part | None, op: PatternOp, *, stage: str
) -> Result[b3d.Part, RealizeError]:
    """Replicate ``op.base`` at each resolved offset (schema.PatternOp)."""
    current = state
    for offset in op.offsets:
        shifted = op.base.model_copy(
            update=_shifted_fields(op.base, offset.x, offset.y)
        )
        result = _apply_feature(current, shifted, stage=stage)
        if result.is_err:
            return Err(result.danger_err)
        current = result.danger_ok
    if current is None:
        return Err(GeometryFailure(stage=stage, op=op.op, message="empty pattern"))
    return Ok(current)


def _shifted_fields(base: object, dx: float, dy: float) -> dict[str, object]:
    """The field update shifting ``base``'s placement by ``(dx, dy)`` metres."""
    if isinstance(base, (HoleOp, PierceOp)):
        return {
            "center": base.center.__class__(x=base.center.x + dx, y=base.center.y + dy)
        }
    if isinstance(base, (ExtrudeOp, PocketOp)):
        shifted_outline = tuple(
            p.__class__(x=p.x + dx, y=p.y + dy) for p in base.sketch.outline
        )
        shifted_holes = tuple(
            h.model_copy(
                update={
                    "center": h.center.__class__(x=h.center.x + dx, y=h.center.y + dy)
                }
            )
            for h in base.sketch.holes
        )
        return {
            "sketch": base.sketch.model_copy(
                update={"outline": shifted_outline, "holes": shifted_holes}
            )
        }
    return {}


def _topology_summary(part: b3d.Part) -> TopologySummary:
    """Snapshot every measure the post-geometry verification pass needs."""
    bbox = part.bounding_box()
    com = part.center()
    return TopologySummary(
        num_solids=len(part.solids()),
        num_faces=len(part.faces()),
        num_edges=len(part.edges()),
        num_vertices=len(part.vertices()),
        volume_mm3=part.volume,
        area_mm2=part.area,
        bbox_min_mm=[bbox.min.X, bbox.min.Y, bbox.min.Z],
        bbox_max_mm=[bbox.max.X, bbox.max.Y, bbox.max.Z],
        center_of_mass_mm=[com.X, com.Y, com.Z],
    )


# Scale-free relative-error margin, reused verbatim from
# `regolith.realizer.mech.model._relative_error` (NO DUPLICATION -- the
# formula is imported at call time below rather than copied here to
# avoid a module-level circular import: `model.py` imports this module
# at its top level for `RealizedGeometryArtifact`, so importing
# `model.py` back at THIS module's top level would cycle).
#
# ESCALATION (recorded, not silently invented): the codebase has no
# existing PINNED NUMERIC tolerance for "declared design value vs.
# geometry-derived value" of this kind -- `GeometryRealizableModel`
# (model.py) uses the same relative-error formula but leaves the
# actual pass/fail threshold to its `Prediction(eps=...)`/harness
# margin caller, which this validate-and-emit pass has no equivalent
# of (it runs standalone, at realize time, not through a `Model`
# discharge). 1e-3 (0.1%) is picked here as a conservative default
# tight enough to catch a real declared/bore mismatch while tolerating
# ordinary floating-point noise from the diameter -> area conversion;
# it is NOT cited from any design-log entry. If a stricter or looser
# value is wanted, that is an owner-level tolerance decision, not an
# implementation detail -- flagged here rather than buried.
_BORE_AREA_REL_TOL = 1.0e-3


def _bore_diameter_m(op: object) -> float | None:
    """The resolved bore diameter (m) of a `HoleOp`/`PierceOp`, else ``None``.

    Only these two op kinds cut a round bore in the v1 feature set
    (schema.py); any other referenced op has no diameter to compare
    against, so a `FlowSegment.bore` naming one is validated for
    EXISTENCE only, never area consistency.
    """
    if isinstance(op, (HoleOp, PierceOp)):
        return op.diameter.value
    return None


def _find_feature_op(program: FeatureProgram, ref: FeatureOpRef) -> object | None:
    """Look up the feature op ``ref`` names, or ``None`` if it does not exist."""
    for stage in program.stages:
        if stage.name != ref.stage:
            continue
        for op in stage.features:
            if getattr(op, "name", None) == ref.feature:
                return op
    return None


def _emit_segment(
    seg: FlowSegment, material_props: MaterialProps | None
) -> Result[PathSegment, RealizeError]:
    """Emit one declared `FlowSegment` verbatim as a degenerate-interval
    wire `PathSegment` (D130/D131: validate-and-emit, never derive).
    """
    wall: WireWall | None = None
    if seg.wall is not None:
        if material_props is None:
            return Err(MissingMaterialProps(role=seg.role))
        modulus = material_props.youngs_modulus.value
        wall = WireWall(
            youngs_modulus=[modulus, modulus],
            thickness=[seg.wall.thickness.value, seg.wall.thickness.value],
            diameter=[seg.wall.diameter.value, seg.wall.diameter.value],
        )
    bend: WireBend | None = None
    if seg.bend is not None:
        bend = WireBend(
            angle=[seg.bend.angle.value, seg.bend.angle.value],
            radius=[seg.bend.radius.value, seg.bend.radius.value],
        )
    return Ok(
        PathSegment(
            role=seg.role,
            flow_area=[seg.flow_area.value, seg.flow_area.value],
            length=[seg.length.value, seg.length.value],
            bend=bend,
            roughness_class=seg.roughness_class,
            elevation_change=[seg.elevation_change.value, seg.elevation_change.value],
            wall=wall,
        )
    )


def _validate_flow_segment(
    program: FeatureProgram, selector: str, seg: FlowSegment
) -> Result[None, RealizeError]:
    """Cross-check ``seg`` against the program's feature ops (D130's
    "geometry fixes the answer" rule) -- bore existence, then, where a
    diameter is resolvable, declared ``flow_area`` vs. the bore's
    resolved circular area.
    """
    if seg.bore is None:
        return Ok(None)
    op = _find_feature_op(program, seg.bore)
    if op is None:
        return Err(
            BoreReferenceNotFound(
                selector=selector,
                role=seg.role,
                stage=seg.bore.stage,
                feature=seg.bore.feature,
            )
        )
    diameter_m = _bore_diameter_m(op)
    if diameter_m is None:
        return Ok(None)
    bore_area_m2 = math.pi * (diameter_m / 2.0) ** 2
    from regolith.realizer.mech.model import _relative_error  # avoid import cycle

    rel_err = _relative_error(seg.flow_area.value, bore_area_m2)
    if rel_err > _BORE_AREA_REL_TOL:
        return Err(
            FlowAreaMismatch(
                selector=selector,
                role=seg.role,
                declared_area_m2=seg.flow_area.value,
                bore_area_m2=bore_area_m2,
                relative_error=rel_err,
            )
        )
    return Ok(None)


def _validate_and_emit_flow_paths(
    program: FeatureProgram,
) -> Result[dict[str, RoutedPath], RealizeError]:
    """The D130 realizer duty: validate every declared `FlowPath` against
    the program's feature ops, then emit the declared measures verbatim
    as selector-keyed `RoutedPath`s (D131 wire shape). Cavity-volume
    cross-checks against the realized solid are explicitly deferred
    ("once the `.cavity` surface lands", D130) -- not attempted here.
    """
    paths: dict[str, RoutedPath] = {}
    for flow_path in program.flow_paths:
        segments: list[PathSegment] = []
        for seg in flow_path.segments:
            validated = _validate_flow_segment(program, flow_path.selector, seg)
            if validated.is_err:
                return Err(validated.danger_err)
            emitted = _emit_segment(seg, program.material_props)
            if emitted.is_err:
                return Err(emitted.danger_err)
            segments.append(emitted.danger_ok)
        paths[flow_path.selector] = RoutedPath(segments=segments)
    return Ok(paths)


def realize_feature_program(
    program: FeatureProgram,
) -> Result[RealizedGeometryArtifact, RealizeError]:
    """Interpret ``program`` end to end: solid -> STEP bytes -> evidence record.

    Total and honest (WO-22 acceptance): an op outside the v1 set or an
    OCCT failure returns an ``Err`` value naming the stage/op, never a
    crash and never a silent skip. Determinism (AD-6): the same program
    drives the exact same call sequence, so ``step_content_hash`` and
    ``topology`` are reproducible on one platform/OCCT build.
    """
    if program.schema_version != FEATURE_PROGRAM_SCHEMA_VERSION:
        return Err(
            SchemaVersionMismatch(
                expected=FEATURE_PROGRAM_SCHEMA_VERSION, got=program.schema_version
            )
        )
    state: b3d.Part | None = None
    for stage in program.stages:
        for op in stage.features:
            result = _apply_feature(state, op, stage=stage.name)
            if result.is_err:
                _log.info(
                    "realize deferred: part=%s stage=%s error=%r",
                    program.part_name,
                    stage.name,
                    result.danger_err,
                )
                return Err(result.danger_err)
            state = result.danger_ok
    if state is None:
        return Err(
            GeometryFailure(
                stage="", op="", message="feature program produced no solid"
            )
        )
    paths_result = _validate_and_emit_flow_paths(program)
    if paths_result.is_err:
        _log.info(
            "realize deferred: part=%s flow-path validation error=%r",
            program.part_name,
            paths_result.danger_err,
        )
        return Err(paths_result.danger_err)
    step_path = _export_step_bytes(state)
    topo = _topology_summary(state)
    return Ok(
        RealizedGeometryArtifact(
            step_bytes=step_path,
            geometry=RealizedGeometry(
                feature_program_hash=program.content_hash(),
                step_content_hash=hashlib.sha256(step_path).hexdigest(),
                topology=topo,
                paths=paths_result.danger_ok,
            ),
        )
    )


# OCCT's STEP writer stamps `FILE_NAME(...)`'s second field with the
# real wall-clock export time -- the one non-deterministic byte range
# in an otherwise reproducible export. Normalized to a fixed sentinel
# so `step_content_hash` is genuinely byte-deterministic for the same
# geometry (AD-6/WO-22 acceptance); a re-imported STEP is unaffected
# (the timestamp is metadata, not geometry).
_STEP_TIMESTAMP_RE = re.compile(r"(FILE_NAME\('[^']*',')[^']*(',)".encode("ascii"))
_STEP_TIMESTAMP_SENTINEL = b"1970-01-01T00:00:00"


def _export_step_bytes(part: b3d.Part) -> bytes:
    """Export ``part`` to AP242 STEP, normalize the export timestamp, read back.

    build123d's exporter writes to a path (no in-memory STEP writer);
    a temp file keeps this a private implementation detail.
    """
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".step")
    os.close(fd)
    try:
        b3d.export_step(part, path)
        with open(path, "rb") as handle:
            raw = handle.read()
    finally:
        os.remove(path)
    return _STEP_TIMESTAMP_RE.sub(
        rb"\g<1>" + _STEP_TIMESTAMP_SENTINEL + rb"\g<2>", raw, count=1
    )
