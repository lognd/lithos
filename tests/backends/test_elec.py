"""Tests for the elec manufacturing backend.

The honest-cut path (tool unavailable) is proven directly, and the
real-tool export path is proven two ways: against a FAKE subprocess
runner (same discipline `tests/realizer/elec/test_kicad.py` uses, so
the wire shape is covered even where no real KiCad install exists),
and -- WHEN `kicad-cli` is genuinely on PATH (cycle 26: it now is,
`make kicad-link` links pcbnew into the venv) -- against the REAL
tool with a minimal hand-built valid `.kicad_pcb` fixture (this
backend re-exports an ALREADY-routed board; a hand-built board plays
the same role a WO-24-produced one would, since WO-24's own
`RealizedLayout`-emitting layout producer has not landed yet -- see
WO-25's Progress ledger).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.elec import AssemblyLine, ElecBackend
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.elec.kicad import real_kicad_available

# A minimal valid KiCad 10 board: no components, just an Edge.Cuts
# outline, so `kicad-cli pcb export {gerbers,drill,pos}` accepts it as
# a real board file rather than exercising a wire-protocol fake.
_MINIMAL_KICAD_PCB = b"""(kicad_pcb
\t(version 20240108)
\t(generator "pcbnew")
\t(general
\t\t(thickness 1.6)
\t)
\t(paper "A4")
\t(layers
\t\t(0 "F.Cu" signal)
\t\t(31 "B.Cu" signal)
\t\t(44 "Edge.Cuts" user)
\t)
\t(setup
\t\t(pad_to_mask_clearance 0)
\t)
\t(net 0 "")
\t(gr_rect
\t\t(start 0 0)
\t\t(end 20 20)
\t\t(stroke (width 0.1) (type default))
\t\t(fill none)
\t\t(layer "Edge.Cuts")
\t\t(uuid "00000000-0000-0000-0000-000000000001")
\t)
)
"""


def test_real_kicad_gate_closed_without_cli():
    # Injected absence: the gate is closed when kicad-cli is missing,
    # regardless of what the host actually has installed.
    assert real_kicad_available(which_fn=lambda name: None) is False


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


def test_elec_backend_honest_cut_teaches_install_guidance(tmp_path):
    """The elec manufacturing package NEEDS kicad-cli (WO-25's tool
    requirement); its absence must be a loud, teaching diagnostic --
    tool name + why + install guidance -- not a bare 'unavailable'."""
    layout = _layout()
    inputs = _inputs(tmp_path, layout, b"(kicad_pcb ...)")
    backend = ElecBackend("board", (), available=lambda: False)
    produced = backend.produce(inputs)
    message = produced.danger_err.message
    assert "kicad-cli" in message
    assert "apt" in message or "conda-forge" in message


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
        out_target = Path(argv[out_index + 1])
        kind = argv[3]
        if kind == "pos":
            # `pos` gets a FILE path in `--output` (real kicad-cli
            # semantics, unlike `gerbers`/`drill`); the fake runner
            # mirrors that shape rather than treating it as a directory.
            out_target.write_bytes(b"fake export bytes")
        else:
            (out_target / f"board.{kind}.txt").write_bytes(b"fake export bytes")
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
    assert "pos/positions.csv" in files
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


@pytest.mark.skipif(
    not real_kicad_available(), reason="kicad-cli not on PATH in this sandbox"
)
def test_elec_backend_real_kicad_cli_export(tmp_path):
    """Real `kicad-cli` end to end: gerbers/drill/pos re-export a genuine
    (hand-built, already-"routed" in the trivial sense of having an
    outline) `.kicad_pcb` -- proves the wire shape this backend drives
    against the ACTUAL tool, not just the fake-runner protocol double.
    Each exported gerber/drill file is well-formed enough for
    `kicad-cli`'s own writer to have produced it without error, which is
    the same signal a reference viewer re-opening it would check.
    """
    layout = _layout()
    inputs = _inputs(tmp_path, layout, _MINIMAL_KICAD_PCB)
    backend = ElecBackend("board", (), available=real_kicad_available)
    produced = backend.produce(inputs)
    assert produced.is_ok, produced.danger_err if produced.is_err else None
    files = {f.relpath: f for f in produced.danger_ok}
    # Edge.Cuts is always plotted; its presence proves a real gerber
    # writer ran (the fake-runner test only proves the argv shape).
    assert any(name.startswith("gerbers/") and "Edge_Cuts" in name for name in files)
    assert "drill/board.drl" in files
    assert "pos/positions.csv" in files
    assert files["pos/positions.csv"].content.startswith(b"Ref,Val,Package")
    assert "bom.csv" in files
    assert "panel.json" in files
