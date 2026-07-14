"""Tests for the fake-KiCad fab-set exporter and the charter 41 sec. 3
completeness checker (WO-124, D238.2/AD-39)."""

from __future__ import annotations

from regolith._codes import FAB_SET_INCOMPLETE
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
    assert result.danger_err.kind == FAB_SET_INCOMPLETE
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


# ---------------------------------------------------------------------------
# WO-124 D238.3 visual-pass regressions: the identity block must be
# strictly inside the board outline with real margin, at a legible
# height, and must carry name + design short-hash + REV -- proven by
# PARSING the plotted/emitted gerber, on both legs.
# ---------------------------------------------------------------------------

_IDENTITY_MARGIN_BAR_MM = 2.0  # the coordinator's inspection floor (ink)


def _assert_inside_with_margin(silk_bounds, edge_bounds, margin_mm):
    sx0, sy0, sx1, sy1 = silk_bounds
    ex0, ey0, ex1, ey1 = edge_bounds
    assert sx0 >= ex0 + margin_mm, f"left: {sx0} vs {ex0}"
    assert sy0 >= ey0 + margin_mm, f"bottom: {sy0} vs {ey0}"
    assert sx1 <= ex1 - margin_mm, f"right: {sx1} vs {ex1}"
    assert sy1 <= ey1 - margin_mm, f"top: {sy1} vs {ey1}"


def test_fake_tier_identity_inside_outline_with_margin_and_content():
    """D238.3 regression, fake leg: parse the emitted silkscreen and
    Edge.Cuts gerbers -- identity ink strictly inside the outline with
    margin, at/above the charter minimum height, and byte-identical to
    a reference rendering of 'name + short-hash / REV: N/A' (the
    content check: the strokes ARE the identity text, not arbitrary
    marks)."""
    from regolith.realizer.elec.identity import (
        MIN_TEXT_HEIGHT_MM,
        identity_block_layout,
    )

    layout = _layout()
    name_line, rev_line = elec_fabset.identity_lines("test_board", layout)
    assert "abab" in name_line, "short-hash missing from the name line"
    assert rev_line == "REV: N/A"
    pcb_text = _kicad_pcb_text(100.0, 80.0, identity_lines=(name_line, rev_line))
    files = {
        f.relpath: f
        for f in elec_fabset.build_fake_fab_set("test_board", layout, pcb_text)
    }
    silk = files["gerbers/board-F_Silkscreen.gto"].content
    edge = files["gerbers/board-Edge_Cuts.gm1"].content
    silk_bounds = elec_fabset.gerber_bounds(silk)
    edge_bounds = elec_fabset.gerber_bounds(edge)
    assert silk_bounds is not None and edge_bounds is not None
    _assert_inside_with_margin(silk_bounds, edge_bounds, _IDENTITY_MARGIN_BAR_MM)
    # Height: the drawn block spans at least one full line of ink at
    # the charter minimum (per-line ink height is 0.8h in the stick
    # font, so a 2.5mm floor draws >= 2mm-tall glyphs).
    assert silk_bounds[3] - silk_bounds[1] >= 0.8 * MIN_TEXT_HEIGHT_MM
    # Content: re-render the exact identity block through the same
    # writer; every one of its draw commands must appear verbatim in
    # the emitted silkscreen (the emitted file draws identity first).
    height_mm, anchors = identity_block_layout(100.0, 80.0, name_line, rev_line)
    reference = elec_fabset._GerberWriter("Legend,Top")
    for text, x, y_down in anchors:
        reference.text(text, x, 80.0 - y_down, height_mm=height_mm)
    ref_draws = [
        line
        for line in reference.render().decode("ascii").splitlines()
        if line.endswith(("D01*", "D02*"))
    ]
    silk_text = silk.decode("ascii")
    assert ref_draws, "reference rendering drew nothing"
    for line in ref_draws:
        assert line in silk_text


def test_real_kicad_identity_inside_outline_with_margin():
    """D238.3 regression, real leg: author the board through the SAME
    text the fake tier writes (the demo11 path), plot silkscreen +
    edge cuts with REAL kicad-cli, and parse the plotted `.gto` --
    identity ink strictly inside the outline with margin, and the
    authored source carries name + short-hash + REV (the plotted
    strokes are KiCad's own rendering of exactly those strings, so
    a non-trivial stroke count pins that the text was plotted)."""
    import subprocess
    import tempfile
    from pathlib import Path

    import pytest
    from regolith.realizer.elec.kicad import real_kicad_available

    if not real_kicad_available():
        pytest.skip("kicad-cli/pcbnew not resolvable on this host")

    name_line = "test_board ababababab12"
    rev_line = "REV: N/A"
    pcb_text = _kicad_pcb_text(305.0, 244.0, identity_lines=(name_line, rev_line))
    # Content at the authored seam: all three identity elements.
    assert "test_board" in pcb_text
    assert "ababababab12" in pcb_text
    assert "REV: N/A" in pcb_text
    with tempfile.TemporaryDirectory() as tmp:
        pcb = Path(tmp) / "board.kicad_pcb"
        pcb.write_text(pcb_text, encoding="ascii")
        out = Path(tmp) / "g"
        completed = subprocess.run(
            [
                "kicad-cli",
                "pcb",
                "export",
                "gerbers",
                "--layers",
                "F.SilkS,Edge.Cuts",
                "--output",
                str(out),
                str(pcb),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        silk = (out / "board-F_Silkscreen.gto").read_bytes()
        edge = (out / "board-Edge_Cuts.gm1").read_bytes()
    silk_bounds = elec_fabset.gerber_bounds(silk)
    edge_bounds = elec_fabset.gerber_bounds(edge)
    assert silk_bounds is not None and edge_bounds is not None
    _assert_inside_with_margin(silk_bounds, edge_bounds, _IDENTITY_MARGIN_BAR_MM)
    # 22 name chars + 8 rev chars of stroke text: far more segments
    # than the outline-only board's zero silk strokes.
    assert silk.count(b"D01*") > 100
