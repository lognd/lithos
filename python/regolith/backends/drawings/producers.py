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

import math

import blake3
from pydantic import BaseModel, ConfigDict

from regolith._schema.models import (
    Annotation,
    Branch,
    BranchParams1,
    BranchParams2,
    BranchParams3,
    BranchParams4,
    Bus,
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
    Load,
    MemberRole1,
    MemberRole2,
    MemberRole3,
    MemberRole4,
    MemberRole5,
    MemberRole6,
    MemberRole7,
    OptimizationTrace,
    Point,
    PowerNetPayload,
    RealizedGeometry,
    ScalarInterval,
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
from regolith.backends.quantity import DimensionedValue

# NO DUPLICATION (WO-143): the laminar/Haaland closed forms this
# producer plots are WO-139's own model formulas, reused verbatim
# rather than re-derived here -- "never an inline fitted curve this
# producer invents" (WO-143 deliverable 1).
from regolith.harness.models.friction_factor import _haaland, _laminar
from regolith.logging_setup import get_logger
from regolith.magnetite.waveform import AuthoredProvenance as _WaveformAuthored
from regolith.magnetite.waveform import WaveformMaskRecord
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
def _scalar_label(interval: ScalarInterval) -> str:
    """A `ScalarInterval` rendered as one label token (INV-34/D262: the
    magnitude never reaches text without going through
    `DimensionedValue`, so a bare numeral is never representable here,
    matching the D265 "unit rides attached to the value's own text"
    call `perfboard.py`/`calc.py` already made). A degenerate interval
    (``lo == hi``, the common case for a declared nameplate value)
    renders as one number; a genuine range renders `lo-hi`."""
    lo = DimensionedValue.of(f"{interval.lo:g}", interval.unit)
    if interval.hi == interval.lo:
        return f"{lo.magnitude} {lo.unit}"
    hi = DimensionedValue.of(f"{interval.hi:g}", interval.unit)
    return f"{lo.magnitude}-{hi.magnitude} {lo.unit}"


def _bus_label(bus: Bus) -> str:
    """A bus bar's label: id, nominal voltage, phase count (charter 43
    sec. 1's bus vocabulary) -- the one-line diagram's node identity."""
    return f"{bus.id}  {_scalar_label(bus.nominal_voltage)}  {bus.phases}ph"


def _branch_label(branch: Branch) -> str:
    """A branch edge's label: apparatus kind + its standard family + the
    key nameplate ratings the params variant declares (charter 43 sec.
    2's four `BranchParams` shapes -- source/transformer/feeder/
    protective-device); an optional field absent from the declaration
    is honestly omitted rather than fabricated (the AD-25 GeomExtract
    idiom this drawing track already follows elsewhere in this
    module)."""
    params = branch.params
    parts: list[str] = [f"apparatus={params.apparatus.value}"]
    if isinstance(params, BranchParams1):
        if params.voltage is not None:
            parts.append(f"V={_scalar_label(params.voltage)}")
        if params.available_fault_current is not None:
            parts.append(f"Isc={_scalar_label(params.available_fault_current)}")
        if params.x_over_r is not None:
            parts.append(f"X/R={_scalar_label(params.x_over_r)}")
    elif isinstance(params, BranchParams2):
        parts.append(f"kVA={_scalar_label(params.kva)}")
        if params.pct_z is not None:
            parts.append(f"%Z={_scalar_label(params.pct_z)}")
        if params.vector_group is not None:
            parts.append(f"vector={params.vector_group}")
        if params.standard_family is not None:
            parts.append(f"std={params.standard_family.value}")
    elif isinstance(params, BranchParams3):
        parts.append(f"L={_scalar_label(params.length)}")
        if params.standard_family is not None:
            parts.append(f"std={params.standard_family.value}")
    elif isinstance(params, BranchParams4):
        parts.append(f"frame={_scalar_label(params.frame)}")
        if params.trip is not None:
            parts.append(f"trip={_scalar_label(params.trip)}")
        if params.standard_family is not None:
            parts.append(f"std={params.standard_family.value}")
    return f"{branch.id} ({branch.kind.value}): " + " ".join(parts)


def _load_label(load: Load) -> str:
    """A load terminal's label: id, connected kVA, declared class, and a
    motor marker (`M(<hp/kW>)`) when the load declares motor nameplate
    fields (charter 43 sec. 2's motor vocabulary)."""
    parts = [load.id, _scalar_label(load.connected_kva)]
    if load.class_ is not None:
        parts.append(load.class_)
    if load.motor is not None:
        parts.append(f"M({_scalar_label(load.motor.hp_kw)})")
    return " ".join(parts)


# frob:doc docs/modules/py-backends.md#drawings-producers
# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def power_oneline(subject: str, power: PowerNetPayload) -> DrawingModel:
    """Project a `PowerNetPayload` into a one-line diagram (charter 43,
    F-WO137-1): buses as horizontal bars, branches as vertical labeled
    edges between bars, loads as terminal symbols hanging off their bus.

    A net-derived diagram cannot disagree with what was verified
    (charter sec. 1 decision 6, the same reading the fluid P&ID/civil
    plan producers already apply): bus/branch/load POSITIONS are a pure
    function of the payload's own declared graph (`layered_positions`,
    D165's "mechanical, not aesthetic" layout rule -- never a solver),
    and every rendered magnitude reaches text only through
    `_scalar_label`'s `DimensionedValue` construction (INV-34). Load
    terminal symbols cite `record_digest=digest` (this payload's own
    digest) -- v1 has no per-load symbol RECORD to cite, the same CUT
    the fluid/civil producers already name.
    """
    source_bytes = power.model_dump_json(by_alias=True).encode("utf-8")
    digest = _digest_of(source_bytes)

    buses = sorted(power.buses, key=lambda b: b.id)
    bus_ids = tuple(b.id for b in buses)
    branches = sorted(power.branches, key=lambda br: br.id)
    branch_edges = tuple((br.a, br.b) for br in branches)
    layout = layered_positions(bus_ids, branch_edges)

    bar_half_width = 25.0
    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    annotations: list[Annotation] = []

    for bus in buses:
        x, y = layout.positions[bus.id]
        entities.append(
            SegmentEntity(
                kind=Kind.segment,
                **{"from": [x - bar_half_width, y]},
                to=[x + bar_half_width, y],
            )
        )
        entity_indices.append(EntityIndice(len(entities) - 1))
        annotations.append(
            Annotation(
                text=_bus_label(bus),
                anchor=[x - bar_half_width, y],
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )

    # WO-123-style de-overlap: two branch labels sharing a route midpoint
    # (two branches between the same bus pair) ladder apart, mirroring
    # `fluid_pid`/`elec_blocks`'s own collision-key discipline.
    branch_label_index: dict[tuple[float, float], int] = {}
    for branch in branches:
        route = layout.routes.get((branch.a, branch.b))
        if route is None:
            _log.warning(
                "power_oneline: branch %r cites an unresolved bus (%r -> %r)",
                branch.id,
                branch.a,
                branch.b,
            )
            continue
        for start, end in zip(route, route[1:], strict=False):
            entities.append(SegmentEntity(kind=Kind.segment, **{"from": start}, to=end))
            entity_indices.append(EntityIndice(len(entities) - 1))
        mid = route[len(route) // 2]
        midpoint: tuple[float, float] = (mid[0], mid[1])
        index = branch_label_index.get(midpoint, 0)
        branch_label_index[midpoint] = index + 1
        annotations.append(
            Annotation(
                text=_branch_label(branch),
                anchor=standoff_ladder(list(midpoint), index),
                text_height_mm=3.0,
                datum_refs=[],
                per=None,
            )
        )

    loads_by_bus: dict[str, list[Load]] = {}
    for load in sorted(power.loads, key=lambda ld: ld.id):
        loads_by_bus.setdefault(load.bus, []).append(load)

    stub_step_mm = 12.0
    stub_drop_mm = 15.0
    for bus_name in sorted(loads_by_bus):
        base = layout.positions.get(bus_name)
        if base is None:
            _log.warning("power_oneline: load(s) on unresolved bus %r", bus_name)
            continue
        bx, by = base
        for i, load in enumerate(loads_by_bus[bus_name]):
            lx = bx + (i + 1) * stub_step_mm
            ly = by + stub_drop_mm
            entities.append(
                SegmentEntity(kind=Kind.segment, **{"from": [lx, by]}, to=[lx, ly])
            )
            entity_indices.append(EntityIndice(len(entities) - 1))
            entities.append(
                SymbolEntity(
                    kind=Kind3.symbol,
                    record_digest=digest,
                    origin=[lx, ly],
                    rotation=0.0,
                )
            )
            entity_indices.append(EntityIndice(len(entities) - 1))
            annotations.append(
                Annotation(
                    text=_load_label(load),
                    anchor=[lx, ly + 4.0],
                    text_height_mm=3.0,
                    datum_refs=[],
                    per=None,
                )
            )

    view = View(
        name="oneline",
        plane="schematic",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="power_net"),
        entity_indices=entity_indices,
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} one-line diagram",
            drawing_number=f"PWR-{subject}",
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
        "power one-line producer: %s -> %d bus(es), %d branch(es), %d load(s)",
        subject,
        len(buses),
        len(branches),
        len(power.loads),
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


def _waveform_authored_annotation(
    record: WaveformMaskRecord, *, anchor: list[float], role: str
) -> Annotation | None:
    """The `AUTHORED (design intent)` chart annotation for `record`, or
    `None` when its provenance is not `authored` (WO-152 deliverable 2 /
    D260 ruling 3): the badge is driven strictly by the record's own
    `provenance.posture` field, never assumed from context (D263.1
    provenance honesty, AD-45) -- a `measured`/`model_derived` record
    gets no badge at all, never a differently-worded one."""
    if not isinstance(record.provenance, _WaveformAuthored):
        return None
    return Annotation(
        text=f"AUTHORED (design intent) [{role}: {record.package}/{record.key}]",
        anchor=anchor,
        text_height_mm=3.0,
        datum_refs=[],
        per=None,
    )


# frob:doc docs/modules/py-backends.md#drawings-producers
def waveform_chart(
    subject: str,
    record: WaveformMaskRecord,
    *,
    overlay: WaveformMaskRecord | None = None,
) -> DrawingModel:
    """Project a `waveform`/`mask` record (WO-151's record class) into a
    real axes-with-ticks chart (WO-152 deliverable 1, charter 41 rule
    6): the record's own `segments` plot against its declared `axes`/
    `quantity`, through the SAME chart code path `opt_trace` uses (a
    `waveform.record` view, `_CHART_SOURCE_KINDS` in `renderer.py` --
    no second renderer, AD-7).

    `overlay` (WO-152 deliverable 3, e.g. a mask a claim's own signal
    must `stays_within`) renders as a SECOND series on the SAME axes,
    not a separate figure: its segments form a second, disjoint
    `SegmentEntity` chain in the same view (`_chart_polylines` in
    `renderer.py` splits disjoint chains back into separate strokes).

    An `authored`-posture `record` OR `overlay` gets its own unmistakable
    `AUTHORED (design intent)` chart annotation (deliverable 2); a
    `measured`/`model_derived` record gets none, per its own provenance
    field -- never assumed.
    """
    source_bytes = record.model_dump_json(by_alias=True).encode("utf-8")
    digest = record.content_hash

    entities: list[_Entity] = []
    entity_indices: list[EntityIndice] = []
    signal_points = [(s.t, s.v) for s in record.segments]
    for start, end in zip(signal_points, signal_points[1:], strict=False):
        entities.append(
            SegmentEntity(kind=Kind.segment, **{"from": list(start)}, to=list(end))
        )
        entity_indices.append(EntityIndice(len(entities) - 1))

    if overlay is not None:
        mask_points = [(s.t, s.v) for s in overlay.segments]
        for start, end in zip(mask_points, mask_points[1:], strict=False):
            entities.append(
                SegmentEntity(kind=Kind.segment, **{"from": list(start)}, to=list(end))
            )
            entity_indices.append(EntityIndice(len(entities) - 1))

    x_label = f"t [{record.axes.t}]"
    y_label = f"{record.quantity} [{record.axes.value}]"
    view = View(
        name=f"{record.record_class}:{record.package}/{record.key}",
        # WO-152: `plane` carries the chart's axis-label pair
        # (`renderer._chart_labels`'s convention for `waveform.record`
        # views) -- the field's own docstring already calls it a free
        # "axis label" string, so this is not a schema repurposing.
        plane=f"{x_label}|{y_label}",
        scale=1.0,
        source=ViewSource(source_digest=digest, source_kind="waveform.record"),
        entity_indices=entity_indices,
    )

    annotations: list[Annotation] = []
    signal_anchor = list(signal_points[0]) if signal_points else [0.0, 0.0]
    signal_badge = _waveform_authored_annotation(
        record, anchor=signal_anchor, role="signal"
    )
    if signal_badge is not None:
        annotations.append(signal_badge)
    if overlay is not None:
        overlay_badge = _waveform_authored_annotation(
            overlay,
            anchor=list(mask_points[0]) if mask_points else [0.0, 0.0],
            role="mask",
        )
        if overlay_badge is not None:
            annotations.append(overlay_badge)

    rows = [
        TableRow(cells=["package", record.package]),
        TableRow(cells=["key", record.key]),
        TableRow(cells=["class", record.record_class]),
        TableRow(cells=["quantity", record.quantity]),
        TableRow(cells=["kind", record.kind]),
        TableRow(cells=["interp", record.interp]),
        TableRow(cells=["posture", record.provenance.posture]),
        TableRow(cells=["content hash", record.content_hash]),
    ]
    if overlay is not None:
        rows.append(TableRow(cells=["mask key", f"{overlay.package}/{overlay.key}"]))
        rows.append(TableRow(cells=["mask posture", overlay.provenance.posture]))
    table = Table(
        title=f"Waveform/Mask Record ({record.package}/{record.key}, digest {digest})",
        columns=["field", "value"],
        rows=rows,
    )

    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject}: {record.package}/{record.key}",
            drawing_number=f"WAVE-{record.key}",
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
        "waveform chart producer: %s -> %s/%s (%d segment(s), overlay=%s)",
        subject,
        record.package,
        record.key,
        len(record.segments),
        f"{overlay.package}/{overlay.key}" if overlay is not None else "none",
    )
    _log.debug("waveform chart producer source bytes: %d", len(source_bytes))
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


# WO-143 (charter 41 rule 6/AD-39): the Moody calc-sheet figure --
# log-log f-vs-Re curves for a pinned eps/D family, the laminar line,
# the honestly-shaded transition band (D97/D258 ruling 3), and the
# discharging obligation's own operating point marked on the chart.
#
# Coordinate frame: a fixed 180mm x 120mm plot box (ANSI A sheet body),
# log10-mapped on both axes over the fixed decade ranges below -- WIDE
# enough to cover every fixture this repo's fluid claims exercise
# (laminar down to Re=100 through fully rough turbulent up to Re=1e8).
# Re/f are dimensionless (charter 41 rule 6's "unit-labeled titles"
# requirement is satisfied by an EXPLICIT "[-]" unit marker, the same
# UNIT_UNREACHABLE-adjacent honesty the calc sheet's `_quantity_cell`
# gives a dimensionless value elsewhere in this package).
_MOODY_RE_MIN = 1.0e2
_MOODY_RE_MAX = 1.0e8
_MOODY_F_MIN = 6.0e-3
_MOODY_F_MAX = 1.0e0
_MOODY_PLOT_W_MM = 180.0
_MOODY_PLOT_H_MM = 120.0
_MOODY_RE_LAMINAR_CEILING = 2300.0
_MOODY_RE_TURBULENT_FLOOR = 4000.0


def _moody_x(re: float) -> float:
    """Map a Reynolds number to plot-box x (mm), log10 scale."""
    lo, hi = math.log10(_MOODY_RE_MIN), math.log10(_MOODY_RE_MAX)
    return _MOODY_PLOT_W_MM * (math.log10(re) - lo) / (hi - lo)


def _moody_y(f: float) -> float:
    """Map a friction factor to plot-box y (mm), log10 scale."""
    lo, hi = math.log10(_MOODY_F_MIN), math.log10(_MOODY_F_MAX)
    return _MOODY_PLOT_H_MM * (math.log10(f) - lo) / (hi - lo)


def _moody_axis_box_and_ticks() -> tuple[list[SegmentEntity], list[Annotation]]:
    """The plot border + decade tick marks/labels on both axes (charter
    41 rule 6: "axes with ticks and unit-labeled titles ... a bare
    polyline is not a chart")."""
    entities: list[SegmentEntity] = [
        SegmentEntity(
            kind=Kind.segment, **{"from": [0.0, 0.0]}, to=[_MOODY_PLOT_W_MM, 0.0]
        ),
        SegmentEntity(
            kind=Kind.segment,
            **{"from": [_MOODY_PLOT_W_MM, 0.0]},
            to=[_MOODY_PLOT_W_MM, _MOODY_PLOT_H_MM],
        ),
        SegmentEntity(
            kind=Kind.segment,
            **{"from": [_MOODY_PLOT_W_MM, _MOODY_PLOT_H_MM]},
            to=[0.0, _MOODY_PLOT_H_MM],
        ),
        SegmentEntity(
            kind=Kind.segment, **{"from": [0.0, _MOODY_PLOT_H_MM]}, to=[0.0, 0.0]
        ),
    ]
    annotations: list[Annotation] = [
        Annotation(
            text="Reynolds number Re [-] (log scale)",
            anchor=[_MOODY_PLOT_W_MM / 2.0, -24.0],
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        ),
        Annotation(
            text="Darcy friction factor f [-] (log scale)",
            anchor=[-40.0, _MOODY_PLOT_H_MM + 10.0],
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        ),
    ]
    re_decade = int(math.log10(_MOODY_RE_MIN))
    while 10.0**re_decade <= _MOODY_RE_MAX:
        re = 10.0**re_decade
        x = _moody_x(re)
        entities.append(
            SegmentEntity(kind=Kind.segment, **{"from": [x, 0.0]}, to=[x, -2.0])
        )
        annotations.append(
            Annotation(
                text=f"1e{re_decade}",
                anchor=[x, -6.0],
                text_height_mm=2.5,
                datum_refs=[],
                per=None,
            )
        )
        re_decade += 1
    f_decade = int(math.log10(_MOODY_F_MIN))
    while 10.0**f_decade <= _MOODY_F_MAX:
        f = 10.0**f_decade
        y = _moody_y(f)
        entities.append(
            SegmentEntity(kind=Kind.segment, **{"from": [0.0, y]}, to=[-2.0, y])
        )
        annotations.append(
            Annotation(
                text=f"{f:g}",
                anchor=[-8.0, y],
                text_height_mm=2.5,
                datum_refs=[],
                per=None,
            )
        )
        f_decade += 1
    return entities, annotations


def _moody_curve_polyline(points: list[tuple[float, float]]) -> Entity3:
    """One log-log (Re, f) polyline, plot-box mapped."""
    return Entity3(
        kind=Kind2.polyline,
        points=[Point([_moody_x(re), _moody_y(f)]) for re, f in points],
    )


# frob:doc docs/modules/py-backends.md#drawings-producers
def diagram_moody(
    subject: str,
    *,
    eps_d_family: tuple[float, ...],
    operating_re: float,
    operating_f: float,
    obligation_id: str,
    samples_per_decade: int = 12,
) -> DrawingModel:
    """The `diagram.moody` calc-sheet figure (WO-143/charter 41 rule 6).

    Renders from CALLER-SUPPLIED `eps_d_family`/operating point only
    (D224: every plotted number traces to a real payload/record) --
    this producer never resolves a roughness record itself (`std.fluid`
    roughness data is presently withdrawn pending counsel review, D266;
    a caller with no real eps/D family to supply names that gap rather
    than calling this producer with a fabricated one -- see
    `backends/calc.py`'s wiring comment for the exact refusal path).

    - the laminar line (`f = 64/Re`, `Re < 2300`, WO-139's own closed
      form, `_laminar`).
    - one curve per `eps_d_family` member (`Re` in
      `[4000, 1e8]`), via WO-139's own Haaland closed form (`_haaland`)
      -- never a fitted curve this producer invents.
    - the transition band (`2300 <= Re <= 4000`) hatched (a dense set
      of vertical polylines -- the schema carries no filled-region
      entity, so a hatch IS this producer's "shaded" primitive) and
      labeled INDETERMINATE (D97/D258 ruling 3: never interpolated).
    - the discharging obligation's operating point, marked with a
      cross-hair symbol pair and labeled with its `obligation_id`
      verbatim (the winner-mark precedent, `opt_trace`'s own
      `producers.py:795` convention).
    - a legend table (AD-27: schedules are tables, not a second
      mechanism) when more than one eps/D curve is drawn.
    """
    entities: list[_Entity] = []
    annotations: list[Annotation] = []

    axis_entities, axis_annotations = _moody_axis_box_and_ticks()
    entities.extend(axis_entities)
    annotations.extend(axis_annotations)

    # Laminar line.
    laminar_points = []
    re = _MOODY_RE_MIN
    step = 10.0 ** (1.0 / samples_per_decade)
    while re <= _MOODY_RE_LAMINAR_CEILING:
        laminar_points.append((re, _laminar(re)))
        re *= step
    laminar_points.append(
        (_MOODY_RE_LAMINAR_CEILING, _laminar(_MOODY_RE_LAMINAR_CEILING))
    )
    entities.append(_moody_curve_polyline(laminar_points))
    annotations.append(
        Annotation(
            text="laminar (f = 64/Re)",
            anchor=[
                _moody_x(laminar_points[0][0]),
                _moody_y(laminar_points[0][1]) + 4.0,
            ],
            text_height_mm=2.5,
            datum_refs=[],
            per=None,
        )
    )

    # Transition band: hatched, labeled indeterminate -- never
    # interpolated across (D97/D258 ruling 3).
    x_lo = _moody_x(_MOODY_RE_LAMINAR_CEILING)
    x_hi = _moody_x(_MOODY_RE_TURBULENT_FLOOR)
    n_hatch = 6
    for i in range(n_hatch + 1):
        x = x_lo + (x_hi - x_lo) * i / n_hatch
        entities.append(
            SegmentEntity(
                kind=Kind.segment, **{"from": [x, 0.0]}, to=[x, _MOODY_PLOT_H_MM]
            )
        )
    annotations.append(
        Annotation(
            text="transition (Re 2300-4000, INDETERMINATE)",
            anchor=[(x_lo + x_hi) / 2.0, _MOODY_PLOT_H_MM * 0.9],
            text_height_mm=2.5,
            datum_refs=[],
            per=None,
        )
    )

    # One turbulent Haaland curve per eps/D family member.
    legend_rows: list[TableRow] = []
    for eps_d in eps_d_family:
        points = []
        re = _MOODY_RE_TURBULENT_FLOOR
        while re <= _MOODY_RE_MAX:
            points.append((re, _haaland(re, eps_d)))
            re *= step
        points.append((_MOODY_RE_MAX, _haaland(_MOODY_RE_MAX, eps_d)))
        entities.append(_moody_curve_polyline(points))
        legend_rows.append(TableRow(cells=[f"eps/D = {eps_d:.2e}"]))

    # Operating point: cross-hair + obligation-id label (winner-mark
    # precedent, `opt_trace` producer).
    ox, oy = _moody_x(operating_re), _moody_y(operating_f)
    entities.append(
        SegmentEntity(kind=Kind.segment, **{"from": [ox - 3.0, oy]}, to=[ox + 3.0, oy])
    )
    entities.append(
        SegmentEntity(kind=Kind.segment, **{"from": [ox, oy - 3.0]}, to=[ox, oy + 3.0])
    )
    annotations.append(
        Annotation(
            text=obligation_id,
            anchor=[ox + 4.0, oy + 4.0],
            text_height_mm=3.0,
            datum_refs=[],
            per=None,
        )
    )

    entity_indices = [EntityIndice(i) for i in range(len(entities))]
    tables = (
        [Table(title="eps/D family", columns=["series"], rows=legend_rows)]
        if len(eps_d_family) > 1
        else []
    )
    view = View(
        name="moody",
        plane="schematic",
        scale=1.0,
        source=ViewSource(
            source_digest=_digest_of(
                f"{subject}|{eps_d_family}|{operating_re}|{operating_f}|"
                f"{obligation_id}".encode()
            ),
            source_kind="diagram_moody",
        ),
        entity_indices=entity_indices,
    )
    sheet = Sheet(
        size=SheetSize2.ansi_b,
        title_block=TitleBlock(
            title=f"{subject} Moody diagram",
            drawing_number=f"MOODY-{subject}",
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[view],
        entities=entities,
        dimensions=[],
        annotations=annotations,
        tables=tables,
    )
    _log.info(
        "diagram.moody producer: %s -> %d eps/D curve(s), operating point %s",
        subject,
        len(eps_d_family),
        obligation_id,
    )
    return DrawingModel(subject=subject, sheets=[sheet])
