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

from pathlib import Path

from typani.result import Err, Ok, Result

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
from regolith.realizer.elec.errors import LayoutFailed, ToolUnavailable
from regolith.realizer.elec.extraction import LayoutExtraction, extract_from_pcb
from regolith.realizer.elec.fake_kicad import run_fake_layout
from regolith.realizer.elec.kicad import (
    LayoutArtifact,
    LayoutRequest,
    hash_pcb_file,
    pcbnew_importable,
    real_kicad_available,
    run_real_layout,
)

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


def _fill_identity(
    request: LayoutRequest, netlist_hash: str, board_outline_ref: str
) -> LayoutRequest:
    """Default the silkscreen identity fields the caller left empty
    (WO-124): name from the board's own outline ref, design short-hash
    from ``netlist_hash`` -- each independently, so a caller-supplied
    hash (e.g. the staged loop's payload digest) is never overwritten
    and an empty netlist hash never blanks a supplied one."""
    updates: dict[str, str] = {}
    if not request.board_name:
        updates["board_name"] = board_outline_ref
    if not request.design_hash and netlist_hash:
        updates["design_hash"] = netlist_hash.removeprefix("sha256:")[:12]
    return request.model_copy(update=updates) if updates else request


def realize_elec_board(
    *,
    netlist_hash: str,
    board_outline_ref: str,
    request: LayoutRequest,
) -> Result[RealizedLayout, ToolUnavailable | LayoutFailed]:
    """Run the real-KiCad layout leg end to end and assemble a `RealizedLayout`.

    The staged-build-loop elec leg WO-24's close-out named as a
    distinct future dispatch ("wiring an elec leg into WO-42's staged-
    build loop is a separate future dispatch, mech-only today"): drives
    `run_real_layout` (the honest outline-only/unrouted wrapper,
    `kicad_wrapper.py`'s own documented scope) and folds its result
    into a `RealizedLayout` the same way `test_kicad_real.py`'s
    round-trip test proves by hand, but as a reusable function the
    staged build loop calls per subject.

    Gated on `real_kicad_available()` (WO-35): a KiCad-less host gets
    an honest `Err(ToolUnavailable)` before any subprocess spawns --
    never a faked layout, matching every other elec realizer seam's
    discipline. A route/DRC infrastructure failure propagates as
    `LayoutFailed` (from `run_real_layout`) unchanged.
    """
    if not real_kicad_available():
        _log.info(
            "elec board board_outline_ref=%s: real KiCad gate closed; "
            "staged build honestly skips the layout.realized leg",
            board_outline_ref,
        )
        return Err(
            ToolUnavailable(tool="kicad-cli/pcbnew", message="real KiCad gate closed")
        )

    request = _fill_identity(request, netlist_hash, board_outline_ref)
    layout_result = run_real_layout(request)
    if layout_result.is_err:
        return Err(layout_result.danger_err)
    response = layout_result.danger_ok

    pcb_path = Path(response.pcb_path)
    content_hash = (
        hash_pcb_file(pcb_path)
        if pcb_path.is_file()
        else f"sha256:{response.pcb_sha256.removeprefix('sha256:')}"
    )
    artifact = LayoutArtifact(
        pcb_path=str(pcb_path), content_hash=content_hash, drc=response.drc
    )

    extraction = LayoutExtraction()
    if response.status == "routed" and pcbnew_importable():
        extracted = extract_from_pcb(pcb_path)
        if extracted.is_ok:
            extraction = extracted.danger_ok
        else:
            _log.warning(
                "elec board board_outline_ref=%s: post-route extraction "
                "failed: %r (falling back to an empty summary)",
                board_outline_ref,
                extracted.danger_err,
            )

    layout = build_realized_layout(
        netlist_hash=netlist_hash,
        board_outline_ref=board_outline_ref,
        artifact=artifact,
        extraction=extraction,
    )
    return Ok(layout)


def realize_elec_board_fake(
    *,
    netlist_hash: str,
    board_outline_ref: str,
    request: LayoutRequest,
) -> Result[RealizedLayout, ToolUnavailable | LayoutFailed]:
    """The deterministic, no-KiCad-install counterpart to
    :func:`realize_elec_board` (WO-71 continuation slice 2).

    Never gated on `real_kicad_available()` -- this tier does not
    invoke KiCad at all, it runs `run_fake_layout`'s own
    injectable-runner seam (`regolith.realizer.elec.fake_kicad`,
    the SAME dependency-injection point `run_layout`'s test suite
    already exercises). Opt-in only (`ElecBoardInputs.deterministic`,
    orchestrate.py): the real leg's "never a faked layout" discipline
    stays the default for every board that does not explicitly ask
    for this tier, so a caller can always tell, from the board's own
    spec, which tier produced its `RealizedLayout`. ``request``'s own
    ``outline_w_mm``/``outline_d_mm`` (WO-103) are the ONE source of
    outline geometry -- the same fields `realize_elec_board`'s real
    leg reads, so the two tiers never diverge on the design's size.

    Always reports ``status="unrouted"`` (no netlist bound, no
    footprint placed -- honest, matching the real wrapper's own
    posture) and an empty `DrcReport` (no DRC pass ran in this tier;
    never a claim of DRC-clean, only the honest absence of a check).

    The board-identity silkscreen block (WO-124, charter 41 sec. 3)
    is populated here from this function's own ``board_outline_ref``/
    ``netlist_hash`` (the request's `board_name`/`design_hash` are
    only overridden if the caller left them unset), so every fake-tier
    board carries identity text without every call site having to know
    about it.
    """
    request = _fill_identity(request, netlist_hash, board_outline_ref)
    layout_result = run_fake_layout(request)
    if layout_result.is_err:
        return Err(layout_result.danger_err)
    response = layout_result.danger_ok

    pcb_path = Path(response.pcb_path)
    content_hash = (
        hash_pcb_file(pcb_path)
        if pcb_path.is_file()
        else f"sha256:{response.pcb_sha256.removeprefix('sha256:')}"
    )
    artifact = LayoutArtifact(
        pcb_path=str(pcb_path), content_hash=content_hash, drc=response.drc
    )
    layout = build_realized_layout(
        netlist_hash=netlist_hash,
        board_outline_ref=board_outline_ref,
        artifact=artifact,
        extraction=LayoutExtraction(),
    )
    return Ok(layout)
