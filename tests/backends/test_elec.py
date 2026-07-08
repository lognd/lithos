"""Tests for the elec manufacturing backend.

Real KiCad tooling is unavailable in this sandbox (same cut WO-24/35
recorded: no `kicad-cli` on PATH, `pcbnew` not importable) -- the
honest-cut path is proven directly, and the real-tool export path is
proven against a FAKE subprocess runner (same discipline
`tests/realizer/elec/test_kicad.py` uses).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.elec import AssemblyLine, ElecBackend
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.elec.kicad import real_kicad_available


def test_real_kicad_unavailable_in_sandbox():
    assert real_kicad_available() is False


def _layout(board_outline_ref="board", pcb_hash="ff" * 32, netlist_hash="ee" * 32):
    from regolith._schema.models import CopperSummary, RealizedLayout

    return RealizedLayout(
        board_outline_ref=board_outline_ref,
        copper=CopperSummary(copper_areas_mm2=[], net_lengths_mm=[]),
        kicad_pcb_content_hash=pcb_hash,
        netlist_hash=netlist_hash,
        parasitics=[],
        placements=[],
        routed_segments=[],
    )


def _inputs(tmp_path, layout, pcb_bytes):
    native = NativeArtifactStore(str(tmp_path))
    native.put_at(layout.kicad_pcb_content_hash, pcb_bytes)
    return BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={"board": layout},
        native=native,
    )


def test_elec_backend_honest_cut_when_tool_unavailable(tmp_path):
    layout = _layout()
    inputs = _inputs(tmp_path, layout, b"(kicad_pcb ...)")
    backend = ElecBackend("board", (), available=lambda: False)
    produced = backend.produce(inputs)
    assert produced.is_err
    assert produced.danger_err.kind == "tool_unavailable"


def test_elec_backend_missing_layout_is_honest_error(tmp_path):
    native = NativeArtifactStore(str(tmp_path))
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=native,
    )
    backend = ElecBackend("missing_board", (), available=lambda: True)
    produced = backend.produce(inputs)
    assert produced.is_err
    assert produced.danger_err.kind == "layout_ir_unavailable"


def _fake_export_runner():
    def runner(argv, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        out_index = argv.index("--output")
        out_dir = Path(argv[out_index + 1])
        kind = argv[3]
        (out_dir / f"board.{kind}.txt").write_bytes(b"fake export bytes")
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=b"", stderr=b""
        )

    return runner


def test_elec_backend_real_tier_with_fake_subprocess(tmp_path):
    layout = _layout()
    inputs = _inputs(tmp_path, layout, b"(kicad_pcb ...)")
    assembly = (
        AssemblyLine(
            reference="U1",
            part_number="STM32G0",
            description="MCU",
            vendor_ref="lcsc:C123",
            quantity=1,
        ),
    )
    backend = ElecBackend(
        "board", assembly, runner=_fake_export_runner(), available=lambda: True
    )
    produced = backend.produce(inputs)
    assert produced.is_ok
    files = {f.relpath: f for f in produced.danger_ok}
    assert "gerbers/board.gerbers.txt" in files
    assert "drill/board.drill.txt" in files
    assert "pos/board.pos.txt" in files
    assert "bom.csv" in files
    assert b"lcsc:C123" in files["bom.csv"].content
    assert "panel.json" in files
    assert b'"board"' in files["panel.json"].content


def test_elec_backend_export_failure_is_honest_error(tmp_path):
    layout = _layout()
    inputs = _inputs(tmp_path, layout, b"(kicad_pcb ...)")

    def failing_runner(argv, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=argv, returncode=1, stdout=b"", stderr=b"boom"
        )

    backend = ElecBackend("board", (), runner=failing_runner, available=lambda: True)
    produced = backend.produce(inputs)
    assert produced.is_err
    assert produced.danger_err.kind == "export_failed"
