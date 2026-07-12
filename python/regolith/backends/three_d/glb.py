"""Deterministic binary glTF (GLB) writer over canonical triangle meshes
(WO-100 deliverable 3; charter 38 sec. 1 decision 6).

A GLB is a 12-byte header + a JSON chunk + a BIN chunk. This writer emits
NO timestamp, a FIXED ``generator`` string, sorted/canonical buffers (the
mesh comes already canonicalized by
:mod:`regolith.backends.three_d.tessellate`), and stable float32/uint32
packing -- so the same meshes always produce byte-identical GLB, the
two-run property `tests/backends/test_wo100_glb.py` proves.

Only POSITION + indices are emitted (no NORMAL accessor): the bundled
viewer computes flat normals in-shader from screen-space derivatives, so
the binary carries no derived data that could desync.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass

from regolith.backends.three_d.tessellate import TriMesh
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

_GLB_MAGIC = 0x46546C67  # "glTF"
_GLB_VERSION = 2
_CHUNK_JSON = 0x4E4F534A  # "JSON"
_CHUNK_BIN = 0x004E4942  # "BIN\0"

_COMP_FLOAT = 5126
_COMP_UINT = 5125
_TARGET_ARRAY_BUFFER = 34962
_TARGET_ELEMENT_ARRAY = 34963

# A fixed generator string (never a versioned/timestamped one) so the
# JSON chunk is byte-stable.
_GENERATOR = "regolith-3d"


@dataclass(frozen=True)
class GlbNode:
    """One placed instance in the scene: a name (hovered in the viewer),
    the index of the mesh it draws, and an optional 16-float column-major
    world matrix (``None`` == identity)."""

    name: str
    mesh: int
    matrix: tuple[float, ...] | None = None


def matrix_from_transform(
    rotation_deg: tuple[float, float, float], translation_mm: tuple[float, float, float]
) -> tuple[float, ...]:
    """A column-major glTF matrix from XYZ intrinsic Euler degrees + a
    millimetre translation (the mesh space is millimetres). Deterministic
    trig -> stable float32 once packed."""
    rx, ry, rz = (math.radians(a) for a in rotation_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # R = Rz @ Ry @ Rx (row-major 3x3)
    r00 = cz * cy
    r01 = cz * sy * sx - sz * cx
    r02 = cz * sy * cx + sz * sx
    r10 = sz * cy
    r11 = sz * sy * sx + cz * cx
    r12 = sz * sy * cx - cz * sx
    r20 = -sy
    r21 = cy * sx
    r22 = cy * cx
    tx, ty, tz = translation_mm
    # Column-major layout expected by glTF.
    return (
        r00,
        r10,
        r20,
        0.0,
        r01,
        r11,
        r21,
        0.0,
        r02,
        r12,
        r22,
        0.0,
        tx,
        ty,
        tz,
        1.0,
    )


def _pad4(data: bytes, fill: bytes) -> bytes:
    """Pad ``data`` up to a 4-byte boundary with ``fill``."""
    rem = (-len(data)) % 4
    return data + fill * rem


def write_glb(meshes: tuple[TriMesh, ...], nodes: tuple[GlbNode, ...]) -> bytes:
    """Assemble ``meshes`` + ``nodes`` into one deterministic GLB.

    Every mesh contributes a POSITION accessor (float32 VEC3, with min/max)
    and an indices accessor (uint32 SCALAR); every node references its
    mesh and carries its optional world matrix. Nodes are emitted in the
    caller's order (the caller sorts by part id) so the scene node list
    is reproducible.
    """
    bin_blob = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    gltf_meshes: list[dict] = []

    for mesh in meshes:
        # POSITION buffer view + accessor.
        pos_bytes = bytearray()
        for x, y, z in mesh.positions:
            pos_bytes += struct.pack("<fff", x, y, z)
        pos_offset = len(bin_blob)
        bin_blob += pos_bytes
        bin_blob += b"\x00" * ((-len(pos_bytes)) % 4)
        xs = [p[0] for p in mesh.positions]
        ys = [p[1] for p in mesh.positions]
        zs = [p[2] for p in mesh.positions]
        pos_view = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": pos_offset,
                "byteLength": len(pos_bytes),
                "target": _TARGET_ARRAY_BUFFER,
            }
        )
        pos_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": pos_view,
                "componentType": _COMP_FLOAT,
                "count": len(mesh.positions),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        # Indices buffer view + accessor.
        idx_bytes = struct.pack(f"<{len(mesh.indices)}I", *mesh.indices)
        idx_offset = len(bin_blob)
        bin_blob += idx_bytes
        bin_blob += b"\x00" * ((-len(idx_bytes)) % 4)
        idx_view = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": idx_offset,
                "byteLength": len(idx_bytes),
                "target": _TARGET_ELEMENT_ARRAY,
            }
        )
        idx_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": idx_view,
                "componentType": _COMP_UINT,
                "count": len(mesh.indices),
                "type": "SCALAR",
            }
        )
        gltf_meshes.append(
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": pos_accessor},
                        "indices": idx_accessor,
                        "mode": 4,
                    }
                ]
            }
        )

    gltf_nodes: list[dict] = []
    for node in nodes:
        entry: dict = {"name": node.name, "mesh": node.mesh}
        if node.matrix is not None:
            entry["matrix"] = list(node.matrix)
        gltf_nodes.append(entry)

    gltf = {
        "asset": {"version": "2.0", "generator": _GENERATOR},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(gltf_nodes)))}],
        "nodes": gltf_nodes,
        "meshes": gltf_meshes,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_blob)}],
    }

    json_bytes = _pad4(
        json.dumps(
            gltf, separators=(",", ":"), sort_keys=True, ensure_ascii=True
        ).encode("ascii"),
        b" ",
    )
    bin_bytes = _pad4(bytes(bin_blob), b"\x00")

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    out = bytearray()
    out += struct.pack("<III", _GLB_MAGIC, _GLB_VERSION, total)
    out += struct.pack("<II", len(json_bytes), _CHUNK_JSON) + json_bytes
    out += struct.pack("<II", len(bin_bytes), _CHUNK_BIN) + bin_bytes
    _log.info(
        "glb: %d mesh(es), %d node(s), %d bytes", len(meshes), len(nodes), len(out)
    )
    return bytes(out)
