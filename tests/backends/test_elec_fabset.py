"""Tests for the fake-KiCad fab-set exporter and the charter 41 sec. 3
completeness checker (WO-124, D238.2/AD-39)."""

from __future__ import annotations

from regolith._schema.models import CopperSummary, Placement, RealizedLayout
from regolith.backends import elec_fabset
from regolith.backends.framework import OutputFile
from regolith.realizer.elec.fake_kicad import _kicad_pcb_text


def _layout(placements: tuple[Placement, ...] = ()) -> RealizedLayout:
    return RealizedLayout(
        board_outline_ref="test_board",
        copper=CopperSummary(copper_areas_mm2=[], net_lengths_mm=[]),
        kicad_pcb_content_hash="ff" * 32,
        netlist_hash="sha256:" + "ab" * 32,
        parasitics=[],
        placements=list(placements),
        routed_segments=[],
    )


def test_check_fab_set_completeness_passes_on_full_manifest():
    files = tuple(
        OutputFile.of(f"boards/{name}", b"x") for name in elec_fabset.REQUIRED_FAB_SET
    )
    result = elec_fabset.check_fab_set_completeness(files, prefix="boards/")
    assert result.is_ok


def test_check_fab_set_completeness_fails_on_todays_four_layer_output():
    """The negative fixture the WO acceptance criteria names: today's
    shipped set (copper/courtyard/edge/margin only) must fail."""
    todays_set = (
        "boards/gerbers/board-F_Cu.gtl",
        "boards/gerbers/board-B_Cu.gbl",
        "boards/gerbers/board-Edge_Cuts.gm1",
        "boards/gerbers/board-Margin.gbr",
        "boards/gerbers/board-F_Courtyard.gbr",
        "boards/gerbers/board-B_Courtyard.gbr",
    )
    files = tuple(OutputFile.of(name, b"x") for name in todays_set)
    result = elec_fabset.check_fab_set_completeness(files, prefix="boards/")
    assert result.is_err
    assert result.danger_err.kind == "fab_set_incomplete"
    assert "F_Silkscreen" in result.danger_err.message or "silk" in (
        result.danger_err.message.lower()
    )


def test_build_fake_fab_set_manifest_matches_required_set():
    layout = _layout()
    pcb_text = _kicad_pcb_text(
        50.0, 40.0, identity_lines=("test_board abcdef123456", "REV: N/A")
    )
    files = elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    names = {f.relpath for f in files}
    assert names == set(elec_fabset.REQUIRED_FAB_SET)


def test_build_fake_fab_set_silkscreen_carries_identity_strokes():
    layout = _layout()
    pcb_text = _kicad_pcb_text(
        50.0, 40.0, identity_lines=("test_board abcdef123456", "REV: N/A")
    )
    files = {
        f.relpath: f
        for f in elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    }
    silk = files["gerbers/board-F_Silkscreen.gto"].content
    # Real strokes, not an empty shell: many D01/D02 draw pairs from the
    # 3x5 stick font (two identity lines, ~20 characters total).
    assert silk.count(b"D01*") > 20


def test_build_fake_fab_set_silkscreen_carries_placement_refdes():
    placement = Placement(
        footprint="R_0402",
        position_mm=[10.0, 10.0],
        reference="R1",
        rotation_deg=0.0,
        side="top",
    )
    layout = _layout(placements=(placement,))
    pcb_text = _kicad_pcb_text(50.0, 40.0)
    before = elec_fabset.build_fake_fab_set("test_board", _layout(), pcb_text)
    after = elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    silk_before = {f.relpath: f for f in before}[
        "gerbers/board-F_Silkscreen.gto"
    ].content
    silk_after = {f.relpath: f for f in after}["gerbers/board-F_Silkscreen.gto"].content
    assert len(silk_after) > len(silk_before)


def test_build_fake_fab_set_mask_paste_are_honestly_empty():
    """No pad-stack geometry exists in `Placement` yet (the WO-124
    close-out finding): mask/paste apertures are legitimately empty
    gerbers, never a fabricated pad."""
    layout = _layout()
    pcb_text = _kicad_pcb_text(50.0, 40.0)
    files = {
        f.relpath: f
        for f in elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    }
    for name in (
        "gerbers/board-F_Mask.gts",
        "gerbers/board-B_Mask.gbs",
        "gerbers/board-F_Paste.gtp",
        "gerbers/board-B_Paste.gbp",
    ):
        assert b"D01*" not in files[name].content
        assert b"M02*" in files[name].content  # still a valid, terminated gerber


def test_build_fake_fab_set_edge_cuts_matches_outline_size():
    layout = _layout()
    pcb_text = _kicad_pcb_text(50.0, 40.0)
    files = {
        f.relpath: f
        for f in elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    }
    edge = files["gerbers/board-Edge_Cuts.gm1"].content
    # 50mm -> 50_000_000 (4.6 fixed point, micrometer resolution)
    assert b"X50000000" in edge


def test_build_fake_fab_set_is_deterministic():
    layout = _layout()
    pcb_text = _kicad_pcb_text(
        50.0, 40.0, identity_lines=("test_board abc", "REV: N/A")
    )
    a = elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    b = elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    assert tuple((f.relpath, f.sha256) for f in a) == tuple(
        (f.relpath, f.sha256) for f in b
    )
