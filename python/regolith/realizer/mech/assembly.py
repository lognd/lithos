"""The mate-graph solve + STEP assembly export + extraction (WO-62
slice B deliverable 5; charter `30-geometry-lowering.md` sec. 1.4).

INPUT: a hand-declared [`AssemblyDef`] -- parts (id + a realized
[`RealizedGeometryArtifact`] + an explicit mass, since no material-
density table exists anywhere in this realizer, WO-22 cut #2's
precedent extended honestly) and mates (id, a provenance-only `kind`
label naming the hematite/03 sec. 3 align/coincident/distance/angle
vocabulary word, the two part ids, and the rigid [`MateTransform`] the
mate imposes from its `from_part` to its `to_part`).

INTEGRATION SEAM (recorded honestly, same posture as `model.py`'s own
docstring for `geometry_realizable`): a full mating-graph reader over
the compiler's contract-graph payload (`ContractGraphPayload`, WO-61)
would need to interpret each mating's `align:`/`dof:` clause text into
a numeric transform -- that lowering does not exist yet (no
`regolith-lower` pass emits numeric mate transforms, only the
readable node/edge summary). Until it does, this module is exercised
by callers that already know the assembly's mate transforms (the
exemplar, tests) -- exactly the shape a future contract-graph-backed
producer would build.

SOLVE (charter sec. 1.4): deterministic sequential placement over a
spanning order of the mate graph -- root part (first in `AssemblyDef.
parts` order) at identity, each other part placed by composing mate
transforms along the first tree edge that reaches it (BFS in
declaration order, AD-6 deterministic). A mate NOT on the spanning
tree (a loop edge) is checked for closure: composing the tree
placements of its two parts must agree with the mate's own transform
within `interface_tolerance_m`/`interface_tolerance_deg`; a
disagreement is `MateLoopResidual`, naming every mate on the loop
(the tree path between the two parts, plus the loop-closing mate
itself).

STEP EXPORT: reuses `interpreter._export_step_bytes` (the ONE STEP
writer + timestamp-normalization seam, AD-1/WO-22) over a
`b3d.Compound` of every part's own STEP-reimported solid, placed at
its solved [`Transform`].

EXTRACTION: mass is the declared per-part mass sum (T2 fact); COM is
the mass-weighted average of each part's OWN realized center-of-mass
(topology, mm), transformed into world frame by its solved placement.
Interference is the v1 axis-aligned-bounding-box overlap test over
every pairwise combination of PLACED (non-underconstrained) parts,
each part's own bbox corners world-transformed before the AABB
re-derivation (the WO body's own scoping: "the placement solve is
nominal + tolerance-residual checks", charter sec. 3 non-goals).
"""

from __future__ import annotations

import math
import re
from collections import deque
from collections.abc import Sequence
from typing import cast

import build123d as b3d
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import AssemblyPart as WireAssemblyPart
from regolith._schema.models import Interference as WireInterference
from regolith._schema.models import RealizedAssembly
from regolith._schema.models import Transform as WireTransform
from regolith.logging_setup import get_logger
from regolith.realizer.mech.errors import (
    AssemblyRealizeError,
    MateLoopResidual,
    UnknownMatePart,
)
from regolith.realizer.mech.interpreter import (
    RealizedGeometryArtifact,
    _export_step_bytes,  # noqa: PLC2701 -- the ONE STEP writer seam, reused not duplicated
)

_log = get_logger(__name__)

# Millimetre/metre conversion factor at this module's boundary, matching
# `interpreter._MM_PER_M`'s convention exactly (schema is SI metres,
# build123d is native millimetres).
_MM_PER_M = 1000.0

# The v1 mate-loop closure tolerance (charter sec. 1.4: "a mate loop
# whose closure residual exceeds the interface tolerance is a
# diagnostic"). Not sourced from any design-log tolerance-stack
# entry -- an owner-level tolerance decision, flagged here rather than
# silently invented, same posture as `interpreter._BORE_AREA_REL_TOL`.
DEFAULT_INTERFACE_TOLERANCE_M = 1.0e-4
DEFAULT_INTERFACE_TOLERANCE_DEG = 1.0e-2


class MateTransform(BaseModel):
    """A rigid placement delta: translation (m) + intrinsic XYZ Euler
    rotation (degrees) -- the wire shape `Transform` mirrors verbatim
    (`regolith_oblig::assembly::Transform`)."""

    model_config = ConfigDict(frozen=True)

    translation_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)


class AssemblyPartDef(BaseModel):
    """One declared assembly part: its id, realized geometry, and mass."""

    model_config = ConfigDict(frozen=True)

    id: str
    geometry: RealizedGeometryArtifact
    mass_kg: float
    geometry_digest: str


class MateDef(BaseModel):
    """One declared mate (hematite/03 sec. 3 vocabulary): the
    connection-class word (`align` | `coincident` | `distance` |
    `angle` -- provenance only, kept verbatim, never re-derived), the
    two part ids, and the rigid transform the mate imposes FROM
    `from_part` TO `to_part` (i.e. `to_part`'s placement = `from_part`'s
    placement composed with this transform)."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    from_part: str
    to_part: str
    transform: MateTransform = MateTransform()


class AssemblyDef(BaseModel):
    """The full mate-graph input to :func:`solve_assembly`: every part
    (declaration order = source order, AD-6) and every mate."""

    model_config = ConfigDict(frozen=True)

    parts: tuple[AssemblyPartDef, ...]
    mates: tuple[MateDef, ...]
    mating_graph_hash: str


def _euler_deg_to_matrix(rotation_deg: Sequence[float]) -> list[list[float]]:
    """Intrinsic XYZ Euler rotation (degrees) -> a 3x3 rotation matrix."""
    rx, ry, rz = (math.radians(a) for a in rotation_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # R = Rz * Ry * Rx (intrinsic X, then Y, then Z).
    rot_x: list[list[float]] = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    rot_y: list[list[float]] = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]
    rot_z: list[list[float]] = [[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]]
    return _mat_mul(_mat_mul(rot_z, rot_y), rot_x)


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)
    ]


def _mat_vec(m: list[list[float]], v: Sequence[float]) -> tuple[float, float, float]:
    result = tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))
    return (result[0], result[1], result[2])


def _matrix_to_euler_deg(m: list[list[float]]) -> tuple[float, float, float]:
    """Best-effort XYZ Euler extraction (residual-comparison use only --
    never round-tripped through a gimbal-sensitive case in this v1
    exemplar's mate set)."""
    sy = -m[2][0]
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)
    rx = math.atan2(m[2][1], m[2][2])
    rz = math.atan2(m[1][0], m[0][0])
    return (math.degrees(rx), math.degrees(ry), math.degrees(rz))


def _compose(
    parent: WireTransform, delta: MateTransform | WireTransform
) -> WireTransform:
    """World placement of a child given its parent's world placement and
    the delta transform from parent to child (rotate the delta's
    translation by the parent's rotation, then add parent's own
    translation; compose rotations)."""
    parent_rot = _euler_deg_to_matrix(parent.rotation_deg)
    delta_translation = tuple(delta.translation_m)
    delta_rotation = tuple(delta.rotation_deg)
    rotated_translation = _mat_vec(
        parent_rot, cast("tuple[float, float, float]", delta_translation)
    )
    world_translation = tuple(
        p + d
        for p, d in zip(tuple(parent.translation_m), rotated_translation, strict=True)
    )
    delta_rot = _euler_deg_to_matrix(delta_rotation)
    world_rot = _mat_mul(parent_rot, delta_rot)
    world_rotation = _matrix_to_euler_deg(world_rot)
    return WireTransform(
        translation_m=list(world_translation),
        rotation_deg=list(world_rotation),
    )


def _identity() -> WireTransform:
    return WireTransform(translation_m=[0.0, 0.0, 0.0], rotation_deg=[0.0, 0.0, 0.0])


def solve_assembly(
    assembly: AssemblyDef,
    *,
    interface_tolerance_m: float = DEFAULT_INTERFACE_TOLERANCE_M,
    interface_tolerance_deg: float = DEFAULT_INTERFACE_TOLERANCE_DEG,
) -> Result[RealizedAssembly, AssemblyRealizeError]:
    """Solve `assembly`'s mate graph to a placed [`RealizedAssembly`]
    (charter sec. 1.4): deterministic sequential placement, loop
    residual diagnostics, extracted mass/COM, pairwise interference.
    """
    part_ids = [p.id for p in assembly.parts]
    parts_by_id = {p.id: p for p in assembly.parts}
    for mate in assembly.mates:
        for pid in (mate.from_part, mate.to_part):
            if pid not in parts_by_id:
                _log.warning(
                    "assembly solve: mate=%s names unknown part=%s", mate.id, pid
                )
                return Err(UnknownMatePart(mate_id=mate.id, part_id=pid))

    # Undirected adjacency: part -> [(neighbor, mate, forward)]. `forward`
    # is True when the mate's declared `from_part -> to_part` direction
    # matches this traversal direction (so the transform composes as-is);
    # False means the INVERSE transform must be applied.
    adjacency: dict[str, list[tuple[str, MateDef, bool]]] = {
        pid: [] for pid in part_ids
    }
    for mate in assembly.mates:
        adjacency[mate.from_part].append((mate.to_part, mate, True))
        adjacency[mate.to_part].append((mate.from_part, mate, False))

    root = part_ids[0]
    world: dict[str, WireTransform] = {root: _identity()}
    dof_states: dict[str, str] = {root: "fixed"}
    tree_edges: set[str] = set()  # mate ids used by the spanning tree
    parent_edge: dict[str, tuple[str, MateDef, bool]] = {}

    queue: deque[str] = deque([root])
    visited = {root}
    while queue:
        current = queue.popleft()
        for neighbor, mate, forward in adjacency[current]:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            tree_edges.add(mate.id)
            parent_edge[neighbor] = (current, mate, forward)
            delta = mate.transform if forward else _invert(mate.transform)
            world[neighbor] = _compose(world[current], delta)
            dof_states[neighbor] = "placed"
            queue.append(neighbor)

    for pid in part_ids:
        if pid not in visited:
            dof_states[pid] = "underconstrained"
            _log.warning("assembly solve: part=%s unreachable from root=%s", pid, root)

    # Loop residual check: every mate NOT on the spanning tree closes a
    # cycle -- compare its declared transform against the two parts'
    # already-solved world placements.
    for mate in assembly.mates:
        if mate.id in tree_edges:
            continue
        if mate.from_part not in world or mate.to_part not in world:
            continue  # one side underconstrained -- no residual to check
        expected = _compose(world[mate.from_part], mate.transform)
        actual = world[mate.to_part]
        translation_residual = math.sqrt(
            sum(
                (e - a) ** 2
                for e, a in zip(
                    expected.translation_m, actual.translation_m, strict=True
                )
            )
        )
        rotation_residual = math.sqrt(
            sum(
                (e - a) ** 2
                for e, a in zip(expected.rotation_deg, actual.rotation_deg, strict=True)
            )
        )
        if (
            translation_residual > interface_tolerance_m
            or rotation_residual > interface_tolerance_deg
        ):
            loop_mates = _loop_mate_ids(mate, parent_edge)
            _log.warning(
                "assembly solve: mate loop residual exceeds tolerance "
                "mates=%s translation_residual_m=%s rotation_residual_deg=%s",
                loop_mates,
                translation_residual,
                rotation_residual,
            )
            return Err(
                MateLoopResidual(
                    mate_ids=loop_mates,
                    translation_residual_m=translation_residual,
                    rotation_residual_deg=rotation_residual,
                    tolerance_m=interface_tolerance_m,
                )
            )

    wire_parts = [
        WireAssemblyPart(
            id=pid,
            geometry_digest=parts_by_id[pid].geometry_digest,
            transform=world.get(pid, _identity()),
        )
        for pid in sorted(part_ids)
    ]

    mass_kg = sum(p.mass_kg for p in assembly.parts)
    com_m = _extract_com(assembly, world, mass_kg)
    interferences = _find_interferences(assembly, world, dof_states)

    realized = RealizedAssembly(
        mating_graph_hash=assembly.mating_graph_hash,
        parts=wire_parts,
        dof_states=dict(sorted(dof_states.items())),
        mass_kg=mass_kg,
        com_m=list(com_m),
        interferences=interferences,
    )
    _log.info(
        "assembly solved: parts=%d mates=%d mass_kg=%s interferences=%d",
        len(assembly.parts),
        len(assembly.mates),
        mass_kg,
        len(interferences),
    )
    return Ok(realized)


def _invert(t: MateTransform) -> MateTransform:
    """The inverse rigid transform (used when a mate is traversed from
    its `to_part` back to its `from_part`)."""
    rot = _euler_deg_to_matrix(t.rotation_deg)
    rot_t = [[rot[j][i] for j in range(3)] for i in range(3)]  # transpose == inverse
    inv_translation = _mat_vec(
        rot_t, cast("tuple[float, float, float]", tuple(-c for c in t.translation_m))
    )
    return MateTransform(
        translation_m=inv_translation,
        rotation_deg=_matrix_to_euler_deg(rot_t),
    )


def _loop_mate_ids(
    closing_mate: MateDef, parent_edge: dict[str, tuple[str, MateDef, bool]]
) -> tuple[str, ...]:
    """Every mate on the cycle `closing_mate` closes: walk both parts'
    tree paths back to their common ancestor (here: back to the root,
    v1 -- every exemplar's mate graph is a single connected component
    with one cycle at most, so a full LCA search is not needed to name
    every mate a caller needs to inspect)."""
    ids: list[str] = [closing_mate.id]
    for start in (closing_mate.from_part, closing_mate.to_part):
        node = start
        while node in parent_edge:
            parent, mate, _forward = parent_edge[node]
            ids.append(mate.id)
            node = parent
    # Sorted + deduped for deterministic diagnostic output (AD-6).
    return tuple(sorted(set(ids)))


def _extract_com(
    assembly: AssemblyDef,
    world: dict[str, WireTransform],
    total_mass_kg: float,
) -> tuple[float, float, float]:
    """Mass-weighted world-frame center of mass (charter sec. 1.4:
    "extracted mass/COM into the measured entity DB like any T2
    fact")."""
    if total_mass_kg <= 0.0:
        return (0.0, 0.0, 0.0)
    acc = [0.0, 0.0, 0.0]
    for part in assembly.parts:
        transform = world.get(part.id)
        if transform is None:
            continue
        com_mm = part.geometry.geometry.topology.center_of_mass_mm
        com_m_local = tuple(c / _MM_PER_M for c in com_mm)
        rot = _euler_deg_to_matrix(transform.rotation_deg)
        world_com = tuple(
            t + r
            for t, r in zip(
                transform.translation_m,
                _mat_vec(rot, com_m_local),
                strict=True,
            )
        )
        for i in range(3):
            acc[i] += part.mass_kg * world_com[i]
    return cast("tuple[float, float, float]", tuple(a / total_mass_kg for a in acc))


def _world_bbox_mm(
    part: AssemblyPartDef, transform: WireTransform
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The part's local-frame AABB corners, world-transformed, then
    re-derived into a fresh AABB (the v1 interference test's own
    conservative approximation -- a rotated box's true hull is a
    tighter oriented box, out of this v1 scope, charter sec. 3)."""
    topo = part.geometry.geometry.topology
    lo, hi = topo.bbox_min_mm, topo.bbox_max_mm
    rot = _euler_deg_to_matrix(transform.rotation_deg)
    translation_mm = tuple(c * _MM_PER_M for c in transform.translation_m)
    corners = [
        (
            lo[0] if bit & 1 else hi[0],
            lo[1] if bit & 2 else hi[1],
            lo[2] if bit & 4 else hi[2],
        )
        for bit in range(8)
    ]
    world_corners = [
        tuple(
            t + r
            for t, r in zip(
                translation_mm,
                _mat_vec(rot, c),
                strict=True,
            )
        )
        for c in corners
    ]
    mins = cast(
        "tuple[float, float, float]",
        tuple(min(c[i] for c in world_corners) for i in range(3)),
    )
    maxs = cast(
        "tuple[float, float, float]",
        tuple(max(c[i] for c in world_corners) for i in range(3)),
    )
    return mins, maxs


def _find_interferences(
    assembly: AssemblyDef,
    world: dict[str, WireTransform],
    dof_states: dict[str, str],
) -> list[WireInterference]:
    """Every pairwise AABB overlap among placed (non-underconstrained)
    parts, sorted by `(part_a, part_b)` (AD-6)."""
    placed = [p for p in assembly.parts if dof_states.get(p.id) != "underconstrained"]
    out: list[WireInterference] = []
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            a_lo, a_hi = _world_bbox_mm(a, world[a.id])
            b_lo, b_hi = _world_bbox_mm(b, world[b.id])
            overlap_dims = [
                max(0.0, min(a_hi[k], b_hi[k]) - max(a_lo[k], b_lo[k]))
                for k in range(3)
            ]
            if all(d > 0.0 for d in overlap_dims):
                overlap_mm3 = overlap_dims[0] * overlap_dims[1] * overlap_dims[2]
                pair = tuple(sorted((a.id, b.id)))
                out.append(
                    WireInterference(
                        part_a=pair[0], part_b=pair[1], overlap_mm3=overlap_mm3
                    )
                )
    out.sort(key=lambda i: (i.part_a, i.part_b))
    return out


def export_assembly_step(assembly: AssemblyDef, realized: RealizedAssembly) -> bytes:
    """Export the solved assembly's STEP bytes: every part's own
    STEP-reimported solid, placed at its solved [`RealizedAssembly`]
    transform, unioned into one `b3d.Compound` (the existing exporter
    seam, `interpreter._export_step_bytes`, reused verbatim -- AD-1,
    the one STEP writer)."""
    parts_by_id = {p.id: p for p in assembly.parts}
    placed_by_id = {p.id: p for p in realized.parts}
    solids: list[b3d.Shape] = []
    for part_id, part in parts_by_id.items():
        placement = placed_by_id.get(part_id)
        if placement is None:
            continue
        imported = _import_step_bytes(part.geometry.step_bytes)
        translation_mm = placement.transform.translation_m
        rotation = placement.transform.rotation_deg
        position = (
            translation_mm[0] * _MM_PER_M,
            translation_mm[1] * _MM_PER_M,
            translation_mm[2] * _MM_PER_M,
        )
        orientation = (rotation[0], rotation[1], rotation[2])
        location = b3d.Location(position, orientation)
        solids.append(imported.located(location))
    compound = cast("b3d.Part", b3d.Compound(children=solids))
    raw = _export_step_bytes(compound)
    return _normalize_assembly_usage_occurrence_ids(raw)


# OCCT's STEP writer numbers `NEXT_ASSEMBLY_USAGE_OCCURRENCE`'s first
# field from a process-global counter that is NOT reset between calls
# (unlike the per-part export path, this is the one place a compound
# assembly export exposed a second real non-determinism beyond the
# `FILE_NAME` timestamp `interpreter._export_step_bytes` already
# normalizes): the same geometry exported twice in one process gets
# different occurrence ids. Renumbered here, sequentially by order of
# first appearance, so `export_assembly_step`'s output is genuinely
# byte-deterministic (WO-62 slice B acceptance: "byte-identical ...
# STEP across two runs").
_ASSEMBLY_USAGE_RE = re.compile(rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[^']*(')")


def _normalize_assembly_usage_occurrence_ids(raw: bytes) -> bytes:
    counter = {"n": 0}

    def _renumber(match: re.Match[bytes]) -> bytes:
        # Renumber unconditionally by occurrence order in the byte
        # stream (not by original value): OCCT's own numbering is the
        # non-deterministic part, so ordinal position -- which IS
        # deterministic for a fixed part/mate declaration order, AD-6
        # -- is the only stable key available here.
        counter["n"] += 1
        new_id = str(counter["n"]).encode("ascii")
        return match.group(1) + new_id + match.group(2)

    return _ASSEMBLY_USAGE_RE.sub(_renumber, raw)


def _import_step_bytes(step_bytes: bytes) -> b3d.Shape:
    """Re-import a part's own pinned STEP bytes as a `b3d.Shape` (the
    exporter seam has no in-memory reader either -- a temp file is the
    same private idiom `_export_step_bytes` already uses)."""
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".step")
    os.close(fd)
    try:
        with open(path, "wb") as handle:
            handle.write(step_bytes)
        return cast("b3d.Shape", b3d.import_step(path))
    finally:
        os.remove(path)
