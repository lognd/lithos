"""OCCT incremental-mesh tessellation of pinned STEP bytes into a
deterministic triangle mesh (WO-100 deliverable 3, the GLB's front end).

Fixed tessellation parameters (`_LINEAR_DEFLECTION_MM`,
`_ANGULAR_DEFLECTION_RAD`) and full coordinate quantization + canonical
vertex/triangle ordering make the emitted mesh reproducible across runs
(AD-6): the same STEP bytes always yield the same vertex buffer and index
buffer, byte-for-byte. OCP is imported lazily so a host without it
degrades (the caller emits no 3D artifact) rather than failing import.
"""

from __future__ import annotations

from dataclasses import dataclass

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# Fixed tessellation quality (mm / rad). Named so the GLB is
# deterministic AND so a future quality knob has exactly one home.
_LINEAR_DEFLECTION_MM = 0.1
_ANGULAR_DEFLECTION_RAD = 0.5

# Vertex coordinates are rounded to this many decimals (mm) before
# packing, so sub-grid OCCT float noise cannot perturb the buffer bytes.
_VERTEX_DECIMALS = 4


# frob:doc docs/modules/py-backends.md#three-d-tessellate
@dataclass(frozen=True)
class TriMesh:
    """A canonical, deterministic triangle mesh: a flat ``positions``
    list (x, y, z per vertex, mm) and a flat ``indices`` list (three
    uint indices per triangle, into ``positions``)."""

    positions: tuple[tuple[float, float, float], ...]
    indices: tuple[int, ...]


def _q(value: float) -> float:
    """Quantize one coordinate to the fixed decimal grid (determinism)."""
    r = round(value, _VERTEX_DECIMALS)
    return 0.0 if r == 0.0 else r


# frob:doc docs/modules/py-backends.md#three-d-tessellate
def tessellate_step(step_bytes: bytes) -> TriMesh | None:
    """Mesh ``step_bytes`` into a canonical :class:`TriMesh`.

    Returns ``None`` when OCP is unavailable on the host (toolenv
    gating) or the STEP cannot be imported -- the caller then emits no
    3D artifact for the subject rather than crashing.
    """
    try:
        import os
        import tempfile

        from OCP.BRep import BRep_Tool
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS
    except ImportError as exc:  # pragma: no cover - host without OCP
        _log.warning("tessellate: OCP unavailable (%s); no GLB emitted", exc)
        return None

    # OCCT's STEP reader needs a real filesystem path, so delete=False +
    # manual unlink in `finally` is the correct idiom here (no context mgr).
    tmp = tempfile.NamedTemporaryFile(suffix=".step", delete=False)  # noqa: SIM115
    try:
        tmp.write(step_bytes)
        tmp.close()
        reader = STEPControl_Reader()
        if reader.ReadFile(tmp.name) != IFSelect_RetDone:
            _log.warning("tessellate: STEP read failed; no GLB emitted")
            return None
        reader.TransferRoots()
        shape = reader.OneShape()
    finally:
        os.unlink(tmp.name)
    if shape.IsNull():
        _log.warning("tessellate: imported shape is null; no GLB emitted")
        return None

    BRepMesh_IncrementalMesh(
        shape, _LINEAR_DEFLECTION_MM, False, _ANGULAR_DEFLECTION_RAD, True
    )

    # Collect every triangle as a triple of quantized global vertices,
    # preserving winding (for outward normals).
    triangles: list[tuple[tuple[float, float, float], ...]] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        reversed_face = face.Orientation().name == "TopAbs_REVERSED"
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            nodes: dict[int, tuple[float, float, float]] = {}
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(trsf)
                nodes[i] = (_q(p.X()), _q(p.Y()), _q(p.Z()))
            for t in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(t).Get()
                if reversed_face:
                    a, c = c, a
                triangles.append((nodes[a], nodes[b], nodes[c]))
        exp.Next()

    if not triangles:
        _log.warning("tessellate: no triangles produced; no GLB emitted")
        return None

    # Canonical order: sort triangles by their vertex key (independent of
    # OCCT traversal), then assign vertex indices by sorted unique
    # coordinate so both buffers are fully reproducible.
    triangles.sort()
    unique = sorted({v for tr in triangles for v in tr})
    index_of = {v: i for i, v in enumerate(unique)}
    indices: list[int] = []
    for tr in triangles:
        indices.extend(index_of[v] for v in tr)

    _log.info("tessellate: %d vertices, %d triangles", len(unique), len(triangles))
    return TriMesh(positions=tuple(unique), indices=tuple(indices))
