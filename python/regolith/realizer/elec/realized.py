"""`RealizedLayout` assembly (WO-42 deliverable 4's remainder, WO-24's own
gap): the realizer-side emission seam that builds the generated
`regolith._schema.models.RealizedLayout` payload from a completed
`run_layout`/`extract_from_pcb` pass and `put`s it into the WO-30
payload store (`kind: layout.realized`).

Mirrors `regolith.orchestrator.orchestrate.put_realized_geometry`'s
precedent exactly: like a standalone `RealizedGeometry`, a
`RealizedLayout` has no upstream Rust-computed AD-18 digest to pin at
assembly time (nothing has compiled against it yet), so this seam uses
`PayloadStore.put` (a fresh blake3 digest of the payload's canonical
JSON bytes), not `put_at`.
"""

from __future__ import annotations

from regolith._schema.models import (
    CopperArea,
    CopperSummary,
    NetLength,
    Placement,
    RealizedLayout,
    RoutedSegment,
)
from regolith.logging_setup import get_logger
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.elec.extraction import LayoutExtraction
from regolith.realizer.elec.kicad import LayoutArtifact

_log = get_logger(__name__)


def build_realized_layout(
    *,
    netlist_hash: str,
    board_outline_ref: str,
    artifact: LayoutArtifact,
    placements: tuple[Placement, ...] = (),
    routed_segments: tuple[RoutedSegment, ...] = (),
    extraction: LayoutExtraction | None = None,
) -> RealizedLayout:
    """Assemble the generated `RealizedLayout` payload from realizer parts.

    ``placements``/``routed_segments`` are the caller's own realizer-
    sorted (AD-6) sequences -- this function does not order them, only
    packages them. ``extraction`` (net lengths / copper areas, from
    :func:`regolith.realizer.elec.extraction.extract_from_pcb`) folds
    into the schema's `CopperSummary`; an absent extraction (the tool
    was unavailable, or the board is unrouted with nothing to measure)
    is legitimately an empty summary, not an error -- an unrouted board
    genuinely has zero routed length and zero filled copper.
    """
    extraction = extraction or LayoutExtraction()
    copper = CopperSummary(
        net_lengths_mm=[
            NetLength(net=net, length_mm=length)
            for net, length in sorted(extraction.net_lengths_mm.items())
        ],
        copper_areas_mm2=[
            CopperArea(region=region, area_mm2=area)
            for region, area in sorted(extraction.copper_areas_mm2.items())
        ],
    )
    layout = RealizedLayout(
        netlist_hash=netlist_hash,
        board_outline_ref=board_outline_ref,
        kicad_pcb_content_hash=artifact.content_hash,
        placements=list(placements),
        routed_segments=list(routed_segments),
        copper=copper,
        parasitics=[],
    )
    _log.info(
        "assembled RealizedLayout: netlist_hash=%s placements=%d segments=%d",
        netlist_hash,
        len(placements),
        len(routed_segments),
    )
    return layout


def put_realized_layout(store: PayloadStore, layout: RealizedLayout) -> str:
    """Store ``layout`` (kind `layout.realized`) into the WO-30 payload
    store, returning its content digest.

    Same shape as `regolith.orchestrator.orchestrate.
    put_realized_geometry`: `PayloadStore.put` (fresh digest), not
    `put_at` -- the returned digest is what a later staged build would
    supply as a `RealizedInput` key.
    """
    data = layout.model_dump_json().encode("utf-8")
    digest = store.put(data)
    _log.debug(
        "payload store: put layout.realized for netlist_hash=%s digest=%s",
        layout.netlist_hash,
        digest,
    )
    return digest
