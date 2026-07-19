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
recompute/verify it independently.

WO-99 D6 / charter 38 sec. 1.4 amendment: to keep the canonical Rust
content address and a locally-computed digest NEVER confusable, a local
digest is PREFIX-TAGGED `local-blake3:<hex>` (`_digest_of`). Every
realized IR these producers project is a STANDALONE IR with no upstream
Rust content address exposed across the FFI (the only canonical address
Python can obtain is `compiler.obligation_content_hashes`, over
`Obligation`s -- not over `RealizedGeometry`/`FlownetPayload`/... which
`PayloadStore.put` keys with a fresh local blake3, WO-98 note). So every
producer here is the "no upstream address" case and its `source_digest`
carries the `local-blake3:` tag; a producer that GAINS an upstream Rust
address later uses that canonical address verbatim (no tag) instead.
"""

from __future__ import annotations

import blake3
from pydantic import BaseModel, ConfigDict

from regolith._schema.models import (
    Annotation,
    ContractGraphPayload,
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
    Kind1,
    Kind2,
    Kind3,
    Kind5,
    MemberRole1,
    MemberRole2,
    MemberRole3,
    MemberRole4,
    MemberRole5,
    MemberRole6,
    MemberRole7,
    OptimizationTrace,
    Point,
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
from regolith.realizer.elec.board_assignment import RealizedBoardAssignment

_Entity = SegmentEntity | Entity2 | Entity3 | SymbolEntity

_log = get_logger(__name__)


# WO-99 D6 / charter 38 sec. 1.4: the tag that marks a locally-computed
# digest as distinct from a canonical Rust content address, so the two are
# never confusable in a shipped `source_digest`.
_LOCAL_DIGEST_PREFIX = "local-blake3:"


def _digest_of(payload_json: bytes) -> str:
    """A stable, PREFIX-TAGGED local digest over already-serialized IR bytes.

    Returns ``local-blake3:<hex>`` (WO-99 D6): the tag distinguishes this
    locally-computed address from a canonical Rust `content_address`, which
    a producer with an upstream address would carry verbatim (untagged).
    """
    return _LOCAL_DIGEST_PREFIX + blake3.blake3(payload_json).hexdigest()


# frob:doc docs/modules/py-backends.md#drawings-producers
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
    # WO-123 D238.3 defect 7: height has no projection in this single-
    # view v1 stand-in -- it used to render as a floating annotation
    # attached to nothing (F135.1-class orphan text); it renders as a
    # row in a small DIMENSIONS notes table instead (the mech producer's
    # own honesty rule stays: never fabricate a second view to hang it
    # on, but a table row is not an orphan the way loose sheet-space
    # text is).
    notes_table = Table(
        title="Dimensions (not projected)",
        columns=["dimension", "value", "note"],
        rows=[
            TableRow(
                cells=["height", f"{height:.2f} mm", "no projection in this view"]
            ),
        ],
    )
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
        annotations=[],
        tables=[notes_table],
    )
    _log.info(
        "mech drawing producer: %s -> 1 sheet, %d dimension(s)", subject, len(dims)
    )
    return DrawingModel(subject=subject, sheets=[sheet])


# frob:doc docs/modules/py-backends.md#drawings-producers
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
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
    # WO-123 (INV-31): two edge labels could previously share an anchor
    # exactly -- either two edges leaving the SAME node, or a real
    # node's position colliding with the [0,0] fallback an off-net
    # endpoint (e.g. `ambient`) resolves to -- tripping the (now-
    # gating) no-overlapping-annotations rule. Ladder labels by their
    # RESOLVED anchor point (the same deterministic standoff-step
    # de-overlap rule elec_blocks uses), so any two labels landing on
    # the same spot separate regardless of why they collided.
    label_count: dict[tuple[float, float], int] = {}
    annotations = []
    for edge in edges:
        base = positions.get(edge.a, [0.0, 0.0])
        key = (base[0], base[1])
        index = label_count.get(key, 0)
        label_count[key] = index + 1
        annotations.append(
            Annotation(
                text=f"{edge.id}: {edge.kind}",
                anchor=standoff_ladder(base, index),
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )
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


# frob:doc docs/modules/py-backends.md#drawings-producers
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
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


# frob:doc docs/modules/py-backends.md#drawings-producers
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


# frob:doc docs/modules/py-backends.md#drawings-producers
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
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


# frob:doc docs/modules/py-backends.md#drawings-producers
def contract_graph(subject: str, graph: ContractGraphPayload) -> DrawingModel:
    """Project a `ContractGraphPayload` (WO-61 deliverable 2, D165/D167)
    into a node-and-edge L2 contract-graph sheet: one symbol entity per
    node (interface or artifact, named by annotation, with its
    promise-slot count for an interface node), one orthogonally-routed
    polyline per mating edge (WO-58 deliverable 3's shared
    `layered_positions` helper), and one annotation per edge citing its
    name and connection-kind label.

    Net-derived diagrams cannot disagree with what was verified (charter
    sec. 1 decision 6, the same rule the fluid P&ID/civil plan producers
    already apply): every node/edge here is read straight off the
    `ContractGraphPayload` the compiler itself emitted, never
    recomputed or re-derived.
    """
    source_bytes = graph.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    node_order = tuple(n.name for n in graph.nodes)
    node_by_name = {n.name: n for n in graph.nodes}
    edge_pairs = tuple((e.a, e.b) for e in graph.edges)
    layout = layered_positions(node_order, edge_pairs)

    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    annotations: list[Annotation] = []
    for name in node_order:
        origin = layout.positions[name]
        entities.append(
            SymbolEntity(
                kind=Kind3.symbol,
                record_digest=digest,
                origin=origin,
                rotation=0.0,
            )
        )
        entity_indices.append(EntityIndice(len(entities) - 1))
        node = node_by_name[name]
        label = f"{name} ({node.kind}"
        label += f", {node.promise_slots} slot(s))" if node.kind == "interface" else ")"
        annotations.append(
            Annotation(
                text=label,
                anchor=[origin[0], origin[1] - 6.0],
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )

    label_index: dict[tuple[str, str], int] = {}
    for edge in sorted(graph.edges, key=lambda e: e.name):
        route = layout.routes.get((edge.a, edge.b))
        if route is None:
            continue
        for start, end in zip(route, route[1:], strict=False):
            entities.append(SegmentEntity(kind=Kind.segment, **{"from": start}, to=end))
            entity_indices.append(EntityIndice(len(entities) - 1))
        midpoint = route[len(route) // 2]
        key = (edge.a, edge.b)
        index = label_index.get(key, 0)
        label_index[key] = index + 1
        annotations.append(
            Annotation(
                text=f"{edge.name}: {edge.kind}",
                anchor=standoff_ladder(midpoint, index),
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )

    view = View(
        name="contract_graph",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="contract_graph"),
        entity_indices=entity_indices,
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} contract graph",
            drawing_number=f"CGR-{subject}",
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
        "contract graph producer: %s -> %d node(s), %d edge(s)",
        subject,
        len(node_order),
        len(graph.edges),
    )
    return DrawingModel(subject=subject, sheets=[sheet])


# frob:doc docs/modules/py-backends.md#drawings-producers
def opt_trace(subject: str, trace: OptimizationTrace) -> DrawingModel:
    """Project an `OptimizationTrace` (WO-58 deliverable 4, gated on
    WO-55) into a candidate-table + convergence-polyline sheet: one
    `tables` row per evaluated candidate (schedule-style, AD-27:
    schedules are `tables`, not a second mechanism), one polyline
    segment per consecutive evaluation-index pair plotting the FIRST
    objective-vector component (the lexicographically primary
    objective, regolith/12 sec. 4) against its evaluation index, and
    one winner annotation. Every number on this sheet cites the
    trace's own content digest (charter-25 provenance rule) -- there is
    no other source of truth for a search trail.
    """
    source_bytes = trace.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    rows = [
        TableRow(
            cells=[
                str(i),
                "; ".join(f"{item.root[0]}={item.root[1]}" for item in c.assignment),
                ", ".join(f"{v:.6g}" for v in c.objective_vector),
                str(c.feasible),
                c.verdict_summary,
            ]
        )
        for i, c in enumerate(trace.candidates)
    ]
    # The FULL trace digest lives here, in the off-chart caption region
    # (D238.3 defect 11: short-hash on the plot, full hash in the sheet
    # caption/footer region -- this table title IS that region).
    table = Table(
        title=(
            f"Optimization Trace ({trace.strategy_id}, seed={trace.seed}, "
            f"trace {digest})"
        ),
        columns=["index", "assignment", "objective", "feasible", "verdict"],
        rows=rows,
    )

    points: list[list[float]] = [
        [float(i), c.objective_vector[0] if c.objective_vector else 0.0]
        for i, c in enumerate(trace.candidates)
    ]
    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    for start, end in zip(points, points[1:], strict=False):
        entities.append(SegmentEntity(kind=Kind.segment, **{"from": start}, to=end))
        entity_indices.append(EntityIndice(len(entities) - 1))

    view = View(
        name="convergence",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="optimize.trace"),
        entity_indices=entity_indices,
    )

    annotations: list[Annotation] = []
    if trace.winner is not None and 0 <= trace.winner < len(points):
        # WO-123 D238.3 defect 11: a SHORT label on the chart ("winner:
        # #2"), never the full blake3 string inline on the plot -- the
        # full digest still cites the trace, in the off-chart caption
        # below (charter 41 sec. 2: "short-hash in plot captions, full
        # hash in the sheet footer/caption region").
        annotations.append(
            Annotation(
                text=f"winner: #{trace.winner}",
                anchor=points[trace.winner],
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )
    annotations.append(
        Annotation(
            text=f"termination: {trace.termination.value} "
            f"({trace.budget_spent}/{trace.budget_declared} evals, "
            f"trace {digest[:19]})",
            anchor=[0.0, -8.0],
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        )
    )

    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} optimization trace",
            drawing_number=f"OPT-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=annotations,
        tables=[table],
    )
    _log.info(
        "opt trace producer: %s -> %d candidate(s), termination=%s",
        subject,
        len(trace.candidates),
        trace.termination.value,
    )
    return DrawingModel(subject=subject, sheets=[sheet])


# frob:doc docs/modules/py-backends.md#drawings-producers
class SiSheetRow(BaseModel):
    """One SI table row (WO-78; charter 35 sec. 1.5): a net's impedance
    or termination claim with its calculated value and full provenance
    -- an unattributable number on a sheet is unrepresentable (AD-27),
    so ``model_id``/``cause`` are required fields, never blank labels.
    """

    model_config = ConfigDict(frozen=True)

    claim: str
    net: str
    target: str
    stackup: str
    layer: str
    geometry: str
    computed: str
    margin: str
    status: str
    model_id: str
    cause: str


# frob:doc docs/modules/py-backends.md#drawings-producers
def si_table(subject: str, rows: tuple[SiSheetRow, ...]) -> DrawingModel:
    """The per-board SI table sheet (WO-78 deliverable 5; charter 35
    sec. 1.5): net / target / chosen stackup + layer / width-gap
    geometry / computed value / margin / model id / cause, one row per
    SI obligation, from already-decided values (regolith/07 sec. 6:
    "backends never decide" -- the rows arrive derived from the
    build's own obligations + evidence, `ship.si_rows_from_report`).
    """
    table = Table(
        title="Signal Integrity",
        columns=[
            "claim",
            "net",
            "target",
            "stackup",
            "layer",
            "geometry",
            "computed",
            "margin",
            "status",
            "model",
            "cause",
        ],
        rows=[
            TableRow(
                cells=[
                    row.claim,
                    row.net,
                    row.target,
                    row.stackup,
                    row.layer,
                    row.geometry,
                    row.computed,
                    row.margin,
                    row.status,
                    row.model_id,
                    row.cause,
                ]
            )
            for row in rows
        ],
    )
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title=f"{subject} Signal Integrity",
            drawing_number=f"SI-{subject}",
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
    _log.info("SI table producer: %s -> %d row(s)", subject, len(rows))
    return DrawingModel(subject=subject, sheets=[sheet])


# frob:doc docs/modules/py-backends.md#drawings-producers
def perfboard_wiring_map(
    subject: str, assignment: RealizedBoardAssignment
) -> DrawingModel:
    """Project a `RealizedBoardAssignment` (WO-163/165, perf-board
    substrate) into a human-followable wiring-map sheet: one small
    circle per component anchor hole (a real through-hole, not a
    schematic symbol -- the perf-board grid itself IS the layout), a
    reference-designator annotation beside each, and one straight
    segment per jumper/wire run, labeled with its net name at the
    segment midpoint.

    Reuses the SAME `DrawingModel` -> svg/dxf/pdf renderer machinery
    every other track's producer feeds (WO-165 deliverable 4: "reuse
    the existing drawing/rendering backend machinery ... rather than
    inventing a new renderer") -- this function only projects, it
    never draws bytes itself.
    """
    source_bytes = assignment.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    hole_radius_mm = 0.5  # a real perf-board plated-hole radius, honest v1 constant
    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    annotations: list[Annotation] = []

    for comp in assignment.components:
        row_s, _, col_s = comp.anchor_hole.partition(",")
        x, y = float(col_s), float(row_s)
        entities.append(
            Entity2(
                kind=Kind1.arc,
                center=[x, y],
                radius=hole_radius_mm,
                start_angle=0.0,
                end_angle=6.283185307179586,
            )
        )
        entity_indices.append(EntityIndice(len(entities) - 1))
        annotations.append(
            Annotation(
                text=comp.reference,
                anchor=[x + hole_radius_mm, y + hole_radius_mm],
                text_height_mm=2.0,
                datum_refs=[],
                per=None,
            )
        )

    for wire in assignment.wires:
        from_row_s, _, from_col_s = wire.from_hole.partition(",")
        to_row_s, _, to_col_s = wire.to_hole.partition(",")
        from_pt = [float(from_col_s), float(from_row_s)]
        to_pt = [float(to_col_s), float(to_row_s)]
        entities.append(
            Entity3(kind=Kind2.polyline, points=[Point(from_pt), Point(to_pt)])
        )
        entity_indices.append(EntityIndice(len(entities) - 1))
        midpoint = [(from_pt[0] + to_pt[0]) / 2.0, (from_pt[1] + to_pt[1]) / 2.0]
        annotations.append(
            Annotation(
                text=f"{wire.net} ({wire.length_mm:.2f} mm)",
                anchor=midpoint,
                text_height_mm=2.0,
                datum_refs=[],
                per=None,
            )
        )

    view = View(
        name="wiring_map",
        plane="schematic",
        scale=1.0,
        source=ViewSource(
            source_digest=digest, source_kind="board_assignment.realized"
        ),
        entity_indices=entity_indices,
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} perf-board wiring map",
            drawing_number=f"WMAP-{subject}",
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
        "perfboard wiring map producer: %s -> %d component(s), %d wire(s)",
        subject,
        len(assignment.components),
        len(assignment.wires),
    )
    return DrawingModel(subject=subject, sheets=[sheet])
