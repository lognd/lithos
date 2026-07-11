"""`realizer.elec.fake_kicad` (WO-71 continuation slice 2): the
deterministic, no-KiCad-install layout tier that lets a `BoardOutline`
impl body's real `w`/`d` reach a genuine `.kicad_pcb` outline without
requiring `kicad-cli`/`pcbnew` -- the same fake-subprocess-runner
dependency-injection seam `test_kicad.py` already exercises against
`run_layout` directly, promoted here to a reusable non-test module.
"""

from __future__ import annotations

from pathlib import Path

import regolith.orchestrator  # noqa: F401 (import order: avoids the

# pre-existing realized<->orchestrator circular import when a test
# module imports `regolith.realizer.elec.realized` before anything
# has imported `regolith.orchestrator` -- same workaround
# `tests/orchestrator/test_staged_build_elec_kicad.py` sidesteps by
# always importing `regolith.orchestrator` first.
from regolith.realizer.elec.fake_kicad import run_fake_layout
from regolith.realizer.elec.kicad import LayoutRequest
from regolith.realizer.elec.realized import realize_elec_board_fake


def _request(tmp_path: Path) -> LayoutRequest:
    return LayoutRequest(
        netlist_path=str(tmp_path / "board.net"),
        board_outline_path=str(tmp_path / "outline.dxf"),
        output_pcb_path=str(tmp_path / "board.kicad_pcb"),
    )


def test_run_fake_layout_writes_a_real_sized_outline(tmp_path: Path) -> None:
    request = _request(tmp_path)
    result = run_fake_layout(request, w_mm=305.0, d_mm=244.0)
    assert result.is_ok, result.danger_err
    response = result.danger_ok
    # Never claims routed: no netlist bound, no footprint placed.
    assert response.status == "unrouted"
    assert response.drc.violations == ()

    pcb_path = Path(response.pcb_path)
    assert pcb_path.is_file()
    text = pcb_path.read_text()
    assert "Edge.Cuts" in text
    assert "305.0000" in text
    assert "244.0000" in text


def test_run_fake_layout_is_deterministic(tmp_path: Path) -> None:
    """Same w/d in, byte-identical `.kicad_pcb` out (no randomness,
    no timestamps -- a reproducible artifact, WO-71's own requirement).
    """
    r1 = _request(tmp_path / "a")
    (tmp_path / "a").mkdir()
    r2 = _request(tmp_path / "b")
    (tmp_path / "b").mkdir()

    result1 = run_fake_layout(r1, w_mm=100.0, d_mm=70.0)
    result2 = run_fake_layout(r2, w_mm=100.0, d_mm=70.0)
    assert result1.is_ok and result2.is_ok
    assert (
        Path(result1.danger_ok.pcb_path).read_bytes()
        == Path(result2.danger_ok.pcb_path).read_bytes()
    )
    assert result1.danger_ok.pcb_sha256 == result2.danger_ok.pcb_sha256


def test_realize_elec_board_fake_assembles_a_realized_layout(tmp_path: Path) -> None:
    request = _request(tmp_path)
    result = realize_elec_board_fake(
        netlist_hash="blake3:" + "a" * 64,
        board_outline_ref="MainboardMcu.outline",
        request=request,
        w_mm=305.0,
        d_mm=244.0,
    )
    assert result.is_ok, result.danger_err
    layout = result.danger_ok
    assert layout.netlist_hash == "blake3:" + "a" * 64
    assert layout.board_outline_ref == "MainboardMcu.outline"
    assert layout.kicad_pcb_content_hash.startswith("sha256:")
    # Honest: no DRC pass ran in this tier, so nothing is claimed clean
    # beyond the absence of a check -- the copper summary is genuinely
    # empty (nothing routed).
    assert layout.copper.net_lengths_mm == []
    assert layout.copper.copper_areas_mm2 == []
