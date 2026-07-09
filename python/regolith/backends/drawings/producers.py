"""Per-track `DrawingModel` producers (charter sec. 1 decision 2):
PROJECT realized IRs into the documentation IR -- never author page
description, never compute geometry (AD-27).

Mech, fluid, elec-BOM, and civil (WO-50 final slice, once WO-48's
`frame` payload landed) are in scope for this dispatch. The civil
producer builds ONLY against `FramePayload` (calcite/03 sec. 4) itself
plus name-only record refs -- `std.civil` record CONTENT (slice C) is
being authored in parallel and is not on master; a sheet field that
genuinely needs a `std.civil` record this schema does not yet resolve
(e.g. an unresolved `section: free` member, an unresolved support
fixity) is honestly OMITTED from dimensions/annotations rather than
fabricated (the AD-25 GeomExtract idiom, applied to drafting: an
unresolved value never becomes a drawn number).

A view's `source_digest` is a blake3 digest over the realized IR's own
canonical JSON bytes (`model_dump_json(by_alias=True)`), NOT the Rust
`content_address` (that algorithm lives behind the FFI boundary this
package may not cross -- `regolith-py` marshalling only, AD-4/AD-27).
It is stable across identical inputs (same determinism property the
charter's byte-identical-goldens rule needs) and still lets a consumer
recompute/verify it independently; this is recorded as a documented
simplification, not silently passed off as the canonical address.
"""

from __future__ import annotations

import blake3

from regolith._schema.models import (
    Annotation,
    Dimension,
    DrawingModel,
    Entity2,
    Entity3,
    EntityIndice,
    FlowEdge,
    FlownetPayload,
    FrameMember,
    FramePayload,
    HarnessPayload,
    Kind,
    Kind3,
    Kind5,
    MemberRole1,
    MemberRole2,
    MemberRole3,
    MemberRole4,
    MemberRole5,
    MemberRole6,
    MemberRole7,
    RealizedGeometry,
    Sheet,
    SheetSize1,
    SheetSize2,
    Table,
    TableRow,
    TitleBlock,
    View,
    ViewSource,
)
from regolith._schema.models import (
    Entity1 as SegmentEntity,
)
from regolith._schema.models import (
    Entity4 as SymbolEntity,
)
from regolith._schema.models import (
    Provenance2 as RecordProvenance,
)
from regolith.backends.drawings.layout import layered_positions, standoff_ladder
from regolith.logging_setup import get_logger

_Entity = SegmentEntity | Entity2 | Entity3 | SymbolEntity

_log = get_logger(__name__)


def _digest_of(payload_json: bytes) -> str:
    """A stable blake3 hex digest over already-serialized IR bytes."""
    return blake3.blake3(payload_json).hexdigest()


def mech_part_drawing(subject: str, geometry: RealizedGeometry) -> DrawingModel:
    """Project a `RealizedGeometry` into a one-sheet part drawing.

    Emits ONE view: a bounding-box-derived rectangle OUTLINE (four
    segments, width x depth) stand-in for the projected front silhouette
    -- v1's mechanical, non-aesthetic layout rule, charter sec. 1
    decision 5 -- plus a width and a depth dimension anchored beside
    their respective edges, each carrying `Provenance.Record` citing the
    geometry's own digest (the source IR IS the record). Height has no
    projection in this single-view stand-in, so it renders as a note
    annotation beside the view rather than a fabricated second view.
    """
    source_bytes = geometry.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)
    bbox_min = geometry.topology.bbox_min_mm
    bbox_max = geometry.topology.bbox_max_mm
    width = bbox_max[0] - bbox_min[0]
    depth = bbox_max[1] - bbox_min[1]
    height = bbox_max[2] - bbox_min[2]

    # The projected front view stand-in (v1 charter honesty: this is the
    # bbox OUTLINE, not a real projected silhouette) -- four segments
    # forming the width x depth rectangle, in declaration order so
    # `entity_indices` stays a stable identity map.
    entities: list[_Entity] = [
        SegmentEntity(kind=Kind.segment, **{"from": [0.0, 0.0]}, to=[width, 0.0]),
        SegmentEntity(kind=Kind.segment, **{"from": [width, 0.0]}, to=[width, depth]),
        SegmentEntity(kind=Kind.segment, **{"from": [width, depth]}, to=[0.0, depth]),
        SegmentEntity(kind=Kind.segment, **{"from": [0.0, depth]}, to=[0.0, 0.0]),
    ]
    view = View(
        name="front",
        plane="XY",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="geometry.realized"),
        entity_indices=[EntityIndice(i) for i in range(len(entities))],
    )
    dims = [
        Dimension(
            role="bbox.width",
            value=width,
            unit="mm",
            tolerance=None,
            # Anchored below the bottom edge (y=depth is the outline's
            # far edge in this local view space; the SVG renderer adds
            # its own standoff on top of this).
            anchor=[width / 2, depth],
            view_name="front",
            provenance=RecordProvenance(kind=Kind5.record, digest=digest),
        ),
        Dimension(
            role="bbox.depth",
            value=depth,
            unit="mm",
            tolerance=None,
            # Anchored left of the left edge.
            anchor=[0.0, depth / 2],
            view_name="front",
            provenance=RecordProvenance(kind=Kind5.record, digest=digest),
        ),
    ]
    annotations = [
        # Height has no projection in this single-view v1 stand-in, so
        # it renders as a note beside the view rather than a dimension
        # on geometry that isn't drawn (the mech producer's own honesty
        # rule: never fabricate a second view to hang it on).
        Annotation(
            text=f"height: {height:.4f} mm",
            anchor=[width + 8.0, depth / 2],
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        ),
    ]
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title=subject,
            drawing_number=f"DWG-{subject}",
            revision="A",
            scale_label="1:1",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=dims,
        annotations=annotations,
        tables=[],
    )
    _log.info(
        "mech drawing producer: %s -> 1 sheet, %d dimension(s)", subject, len(dims)
    )
    return DrawingModel(subject=subject, sheets=[sheet])


def fluid_pid(subject: str, flownet: FlownetPayload) -> DrawingModel:
    """Project a `FlownetPayload` into a schematic P&ID sheet.

    Net-derived diagrams cannot disagree with what was verified (charter
    sec. 1 decision 6): one symbol entity per node (a generic junction
    glyph, `record_digest` citing the flownet's own digest since v1 has
    no per-node symbol RECORD to cite -- CUT, named below) laid out on a
    deterministic grid by sorted node id, and one segment entity per
    edge connecting its two endpoints' grid positions. Every edge gets
    one dimension-less annotation carrying its id and kind (a P&ID has
    no toleranced dimensions of its own; the coverage check therefore
    has nothing to demand here by construction).
    """
    source_bytes = flownet.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)
    nodes = sorted(flownet.nodes)
    positions = {name: [float(i) * 40.0, 0.0] for i, name in enumerate(nodes)}

    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    for i, name in enumerate(nodes):
        entities.append(
            SymbolEntity(
                kind=Kind3.symbol,
                record_digest=digest,
                origin=positions[name],
                rotation=0.0,
            )
        )
        entity_indices.append(EntityIndice(i))

    edges: list[FlowEdge] = sorted(flownet.edges, key=lambda e: e.id)
    for edge in edges:
        a_pos = positions.get(edge.a, [0.0, 0.0])
        b_pos = positions.get(edge.b, [0.0, 0.0])
        entities.append(SegmentEntity(kind=Kind.segment, **{"from": a_pos}, to=b_pos))
        entity_indices.append(EntityIndice(len(entities) - 1))

    view = View(
        name="pid",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="flownet"),
        entity_indices=entity_indices,
    )
    annotations = [
        Annotation(
            text=f"{edge.id}: {edge.kind}",
            anchor=positions.get(edge.a, [0.0, 0.0]),
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        )
        for edge in edges
    ]
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} P&ID",
            drawing_number=f"PID-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=annotations,
        tables=[],
    )
    _log.info(
        "fluid P&ID producer: %s -> %d node(s), %d edge(s)",
        subject,
        len(nodes),
        len(edges),
    )
    return DrawingModel(subject=subject, sheets=[sheet])


def _endpoint(text: str) -> tuple[str, str]:
    """Split a run endpoint's `component.port` text (`RunRecord.from_`/
    `.to`, WO-34 D99) into its component and pin name; a malformed
    endpoint with no `.` yields an empty pin rather than raising (never
    fabricated, honestly labeled)."""
    block, _, port = text.partition(".")
    return block, port or "(unnamed)"


def elec_blocks(subject: str, harness: HarnessPayload) -> DrawingModel:
    """Project a `HarnessPayload` into a bdf-shaped structural block
    diagram (interaction-surface/29 sec. 1.6, D165): one rectangle per
    component block referenced by a run endpoint, one port-name
    annotation per distinct pin, and one orthogonally-routed polyline
    per declared run.

    Named simplification (WO-34's own escalation, `docs/workflow/
    work-orders/WO-34-routed-runs.md`'s D3/E0306 note): cuprite NET
    membership (which schematic net a `component.port` belongs to) is
    not exposed to any existing seam today -- this producer therefore
    reads a harness's RUN endpoints as its block/port/net-like
    structure (real, landed WO-34 payload data) rather than resolving
    or inventing a net graph AD-22 already forbids. This is an honest
    substitution, not the eventual `diagram.elec_blocks` shape once a
    net-membership seam lands (a future WO, not this one's gap to
    close).
    """
    source_bytes = harness.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    run_names = sorted(harness.runs)
    blocks: set[str] = set()
    ports: dict[str, set[str]] = {}
    edges: list[tuple[str, str, str, str, str]] = []
    for run_name in run_names:
        run = harness.runs[run_name]
        a_block, a_port = _endpoint(run.from_)
        b_block, b_port = _endpoint(run.to)
        blocks.add(a_block)
        blocks.add(b_block)
        ports.setdefault(a_block, set()).add(a_port)
        ports.setdefault(b_block, set()).add(b_port)
        edges.append((run_name, a_block, a_port, b_block, b_port))

    node_order = tuple(sorted(blocks))
    edge_pairs = tuple((a, b) for _, a, _, b, _ in edges)
    layout = layered_positions(node_order, edge_pairs)

    block_w, block_h = 30.0, 20.0
    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    for name in node_order:
        x, y = layout.positions[name]
        corners = [
            [x, y],
            [x + block_w, y],
            [x + block_w, y + block_h],
            [x, y + block_h],
        ]
        for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
            entities.append(SegmentEntity(kind=Kind.segment, **{"from": start}, to=end))
            entity_indices.append(EntityIndice(len(entities) - 1))

    annotations: list[Annotation] = []
    for name in node_order:
        x, y = layout.positions[name]
        annotations.append(
            Annotation(
                text=name,
                anchor=[x + block_w / 2.0, y + block_h / 2.0],
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )
        for j, port in enumerate(sorted(ports.get(name, ()))):
            annotations.append(
                Annotation(
                    text=port,
                    anchor=standoff_ladder([x + block_w, y + block_h / 2.0], j),
                    text_height_mm=3.0,
                    datum_refs=[],
                    per=None,
                )
            )

    # Track how many net labels have already landed on this exact
    # (a_block, b_block) route: two runs between the SAME block pair
    # would otherwise share a midpoint anchor, tripping the drafting
    # audit's no-overlapping-annotations rule (charter 25 sec. 1.7) --
    # the standoff ladder (deliverable 3) breaks the tie deterministically.
    label_index: dict[tuple[str, str], int] = {}
    for run_name, a_block, a_port, b_block, b_port in edges:
        route = layout.routes.get((a_block, b_block))
        if route is None:
            continue
        for start, end in zip(route, route[1:], strict=False):
            entities.append(SegmentEntity(kind=Kind.segment, **{"from": start}, to=end))
            entity_indices.append(EntityIndice(len(entities) - 1))
        midpoint = route[len(route) // 2]
        key = (a_block, b_block)
        index = label_index.get(key, 0)
        label_index[key] = index + 1
        annotations.append(
            Annotation(
                text=f"{run_name}: {a_block}.{a_port} -> {b_block}.{b_port}",
                anchor=standoff_ladder(midpoint, index),
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )

    view = View(
        name="blocks",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="harness"),
        entity_indices=entity_indices,
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} block diagram",
            drawing_number=f"BLK-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=annotations,
        tables=[],
    )
    _log.info(
        "elec block diagram producer: %s -> %d block(s), %d run(s)",
        subject,
        len(node_order),
        len(edges),
    )
    return DrawingModel(subject=subject, sheets=[sheet])


def elec_bom_table(
    subject: str, rows: tuple[tuple[str, str, str, int], ...]
) -> DrawingModel:
    """A BOM schedule sheet (charter/AD-27: schedules are `tables`, not a
    second mechanism) from already-decided `(ref, part_number,
    description, quantity)` rows -- this producer never invents a part
    number (regolith/07 sec. 6, "backends never decide").
    """
    table = Table(
        title="Bill of Materials",
        columns=["ref", "part_number", "description", "quantity"],
        rows=[TableRow(cells=[ref, pn, desc, str(qty)]) for ref, pn, desc, qty in rows],
    )
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title=f"{subject} BOM",
            drawing_number=f"BOM-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[],
        entities=[],
        dimensions=[],
        annotations=[],
        tables=[table],
    )
    return DrawingModel(subject=subject, sheets=[sheet])


def _role_str(
    role: MemberRole1
    | MemberRole2
    | MemberRole3
    | MemberRole4
    | MemberRole5
    | MemberRole6
    | MemberRole7,
) -> str:
    """The display form of a `FrameMember.role` union member: the
    settled-vocabulary variants are `StrEnum`s (`.value`); `MemberRole7`
    (`Other`) carries its verbatim word in `.other`.
    """
    if isinstance(role, MemberRole7):
        return role.other
    return role.value


def civil_plan_section(subject: str, frame: FramePayload) -> DrawingModel:
    """Project a `FramePayload` into a one-sheet civil plan + member
    schedule (calcite/03 sec. 6, WO-50 final slice).

    A net-derived diagram cannot disagree with what was verified
    (charter sec. 1 decision 6, applied here as it was to the fluid
    P&ID): one symbol entity per joint (a generic node glyph,
    `record_digest` citing the frame's own digest -- v1 has no per-joint
    symbol RECORD to cite, same CUT the fluid producer already names)
    laid out on a deterministic grid (joints with a resolved `at` first,
    sorted by id; support-only joints with `at: None` on a second row,
    also sorted by id -- never a fabricated plan position), and one
    segment entity per member connecting its two joints' grid positions.
    A point-anchored footing (`a == b`, calcite/03 sec. 4) contributes no
    segment (it is a reaction point, not a span) -- its joint's own
    symbol entity already marks it.

    One dimension per non-point-anchored member's span length, citing
    the frame's own digest as its `Provenance.Record` (the payload IS
    the record here, exactly like the mech/fluid producers' own source
    IR). A member whose `section`/`material` is the AD-25 `free`
    placeholder gets NO section/material dimension or table cell value
    beyond the honest `"unresolved"` label -- `std.civil` record content
    is not on master this slice (the named residual), and this producer
    never fabricates one.

    The member schedule (calcite/03 sec. 6) rides the SAME sheet as a
    `tables`-only schedule (charter/AD-27: schedules are `tables`, not a
    second mechanism) -- one row per member, `std.civil`-unresolved
    section/material rendered as `"unresolved"` rather than invented.
    """
    source_bytes = frame.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    positioned = sorted(
        (j for j in frame.joints if j.at is not None), key=lambda j: j.id
    )
    unpositioned = sorted((j for j in frame.joints if j.at is None), key=lambda j: j.id)
    positions: dict[str, list[float]] = {}
    for i, joint in enumerate(positioned):
        positions[joint.id] = [float(i) * 40.0, 0.0]
    for i, joint in enumerate(unpositioned):
        positions[joint.id] = [float(i) * 40.0, -40.0]

    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    for joint in sorted(frame.joints, key=lambda j: j.id):
        entities.append(
            SymbolEntity(
                kind=Kind3.symbol,
                record_digest=digest,
                origin=positions[joint.id],
                rotation=0.0,
            )
        )
        entity_indices.append(EntityIndice(len(entities) - 1))

    members: list[FrameMember] = sorted(frame.members, key=lambda m: m.id)
    dims: list[Dimension] = []
    for member in members:
        a_pos = positions.get(member.a, [0.0, 0.0])
        b_pos = positions.get(member.b, [0.0, 0.0])
        point_anchored = member.a == member.b
        if not point_anchored:
            entities.append(
                SegmentEntity(kind=Kind.segment, **{"from": a_pos}, to=b_pos)
            )
            entity_indices.append(EntityIndice(len(entities) - 1))
            midpoint = [
                (a_pos[0] + b_pos[0]) / 2.0,
                (a_pos[1] + b_pos[1]) / 2.0,
            ]
            dims.append(
                Dimension(
                    role=f"member.length:{member.id}",
                    value=member.length.lo,
                    unit=member.length.unit,
                    tolerance=None,
                    anchor=midpoint,
                    view_name="plan",
                    provenance=RecordProvenance(kind=Kind5.record, digest=digest),
                )
            )

    view = View(
        name="plan",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="frame"),
        entity_indices=entity_indices,
    )

    rows = []
    for member in members:
        section = "unresolved" if member.section.name == "free" else member.section.name
        material = (
            "unresolved" if member.material.name == "free" else member.material.name
        )
        rows.append(
            TableRow(
                cells=[
                    member.id,
                    _role_str(member.role),
                    f"{member.length.lo:.3f} {member.length.unit}",
                    section,
                    material,
                ]
            )
        )
    schedule = Table(
        title="Member Schedule",
        columns=["id", "role", "length", "section", "material"],
        rows=rows,
    )

    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} Plan",
            drawing_number=f"PLN-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=dims,
        annotations=[],
        tables=[schedule],
    )
    _log.info(
        "civil plan producer: %s -> %d joint(s), %d member(s), %d dimension(s)",
        subject,
        len(frame.joints),
        len(members),
        len(dims),
    )
    return DrawingModel(subject=subject, sheets=[sheet])
