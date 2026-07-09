"""Per-track `DrawingModel` producers (charter sec. 1 decision 2):
PROJECT realized IRs into the documentation IR -- never author page
description, never compute geometry (AD-27).

Mech and fluid are in scope for this dispatch; the elec BOM table rides
existing netlist/BOM state (kept minimal, a `tables`-only sheet); the
civil plan/section producer is DEFERRED (named residual, gates on
WO-48's `frame` payload -- not built against the unlanded std.civil per
the dispatch instruction).

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
    Kind,
    Kind3,
    Kind5,
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
from regolith.logging_setup import get_logger

_Entity = SegmentEntity | Entity2 | Entity3 | SymbolEntity

_log = get_logger(__name__)


def _digest_of(payload_json: bytes) -> str:
    """A stable blake3 hex digest over already-serialized IR bytes."""
    return blake3.blake3(payload_json).hexdigest()


def mech_part_drawing(subject: str, geometry: RealizedGeometry) -> DrawingModel:
    """Project a `RealizedGeometry` into a one-sheet part drawing.

    Emits ONE view (a bounding-box-derived rectangle stand-in for the
    projected outline -- v1's mechanical, non-aesthetic layout rule,
    charter sec. 1 decision 5) and one dimension per topology axis
    (width/depth/height from the bbox), each carrying `Provenance.Record`
    citing the geometry's own digest (the source IR IS the record).
    """
    source_bytes = geometry.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)
    bbox_min = geometry.topology.bbox_min_mm
    bbox_max = geometry.topology.bbox_max_mm
    width = bbox_max[0] - bbox_min[0]
    depth = bbox_max[1] - bbox_min[1]
    height = bbox_max[2] - bbox_min[2]

    entity = SegmentEntity(kind=Kind.segment, **{"from": [0.0, 0.0]}, to=[width, 0.0])
    view = View(
        name="front",
        plane="XY",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="geometry.realized"),
        entity_indices=[EntityIndice(0)],
    )
    dims = [
        Dimension(
            role="bbox.width",
            value=width,
            unit="mm",
            tolerance=None,
            anchor=[width / 2, 0.0],
            view_name="front",
            provenance=RecordProvenance(kind=Kind5.record, digest=digest),
        ),
        Dimension(
            role="bbox.depth",
            value=depth,
            unit="mm",
            tolerance=None,
            anchor=[0.0, depth / 2],
            view_name="front",
            provenance=RecordProvenance(kind=Kind5.record, digest=digest),
        ),
        Dimension(
            role="bbox.height",
            value=height,
            unit="mm",
            tolerance=None,
            anchor=[0.0, 0.0],
            view_name="front",
            provenance=RecordProvenance(kind=Kind5.record, digest=digest),
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
        entities=[entity],
        dimensions=dims,
        annotations=[],
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
