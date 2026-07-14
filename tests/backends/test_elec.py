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
from regolith.backends import elec_fabset
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.elec import AssemblyLine, ElecBackend
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.elec.kicad import real_kicad_available

# A minimal valid KiCad 10 board: no components, just an Edge.Cuts
# outline, so `kicad-cli pcb export {gerbers,drill,pos}` accepts it as
# a real board file rather than exercising a wire-protocol fake. The
# FULL standard layer table (WO-124) is required: kicad-cli silently
# drops any `--layers` entry the board's own `(layers ...)` table does
# not declare (verified on-host against kicad-cli 10.0.4), so a board
# lacking F.SilkS/F.Mask/etc. would plot an incomplete fab set.
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
\t\t(32 "B.Adhes" user "B.Adhesive")
\t\t(33 "F.Adhes" user "F.Adhesive")
\t\t(34 "B.Paste" user)
\t\t(35 "F.Paste" user)
\t\t(36 "B.SilkS" user "B.Silkscreen")
\t\t(37 "F.SilkS" user "F.Silkscreen")
\t\t(38 "B.Mask" user)
\t\t(39 "F.Mask" user)
\t\t(44 "Edge.Cuts" user)
\t\t(45 "Margin" user)
\t\t(46 "B.CrtYd" user "B.Courtyard")
\t\t(47 "F.CrtYd" user "F.Courtyard")
\t\t(48 "B.Fab" user)
\t\t(49 "F.Fab" user)
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
\t(gr_text "TEST_BOARD abc123def456"
\t\t(at 2 2)
\t\t(layer "F.SilkS")
\t\t(uuid "00000000-0000-0000-0000-000000000002")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(gr_text "REV: N/A"
\t\t(at 2 4)
\t\t(layer "F.SilkS")
\t\t(uuid "00000000-0000-0000-0000-000000000003")
\t\t(effects (font (size 1 1) (thickness 0.15)))
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


def test_elec_backend_fake_tier_when_tool_unavailable(tmp_path):
    """WO-124 (charter 41 sec. 3, D238.2): kicad-cli/pcbnew unavailable
    is no longer an honest cut -- the fake-KiCad fab-set exporter emits
    the complete, deterministic manifest by hand, and the completeness
    checker (run over its own output) is satisfied."""
    from regolith.realizer.elec.fake_kicad import _kicad_pcb_text

    pcb_text = _kicad_pcb_text(
        50.0, 40.0, identity_lines=("test_board abc123def456", "REV: N/A")
    )
    layout = _layout()
    inputs = _inputs(tmp_path, layout, pcb_text.encode("ascii"))
    backend = ElecBackend("board", (), available=lambda: False)
    produced = backend.produce(inputs)
    assert produced.is_ok, produced.danger_err if produced.is_err else None
    files = {f.relpath: f for f in produced.danger_ok}
    for name in elec_fabset.REQUIRED_FAB_SET:
        assert name in files, f"missing required fab-set file: {name}"
    # Board identity text made it onto the silkscreen (hand-rolled
    # stick-font strokes -- proven at the pixel level by
    # `test_elec_fabset.py`; here we only prove the CONTENT is
    # threaded through, via the non-empty gerber body).
    silk = files["gerbers/board-F_Silkscreen.gto"].content
    assert len(silk) > 200  # header + real stroke draws, not an empty shell
    assert "board_status.json" in files


def test_elec_backend_fake_tier_teaches_install_guidance(tmp_path, caplog):
    """The elec manufacturing package prefers kicad-cli (WO-25's tool
    requirement); its absence is still a loud, teaching LOG line --
    tool name + why + install guidance -- even though it no longer
    blocks the ship (WO-124's fake tier covers the gap)."""
    import logging

    layout = _layout()
    inputs = _inputs(tmp_path, layout, b"(kicad_pcb (layers))\n")
    backend = ElecBackend("board", (), available=lambda: False)
    with caplog.at_level(logging.INFO, logger="regolith.backends.elec"):
        produced = backend.produce(inputs)
    assert produced.is_ok
    message = " ".join(r.message for r in caplog.records)
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
    """A fake `kicad-cli` subprocess double: writes the FULL charter 41
    sec. 3 file names for `gerbers`/`drill` (WO-124's completeness
    checker gates every `produce()` call, so this fixture must satisfy
    it exactly like a real export would) and the single `pos` file."""

    def runner(argv, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        out_index = argv.index("--output")
        out_target = Path(argv[out_index + 1])
        kind = argv[3]
        if kind == "pos":
            # `pos` gets a FILE path in `--output` (real kicad-cli
            # semantics, unlike `gerbers`/`drill`); the fake runner
            # mirrors that shape rather than treating it as a directory.
            out_target.write_bytes(b"fake export bytes")
        elif kind == "gerbers":
            for path in elec_fabset.GERBER_LAYER_FILES:
                (out_target / Path(path).name).write_bytes(b"fake export bytes")
        elif kind == "drill":
            for path in elec_fabset.DRILL_FILES:
                (out_target / Path(path).name).write_bytes(b"fake export bytes")
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
    for name in elec_fabset.REQUIRED_FAB_SET:
        assert name in files, f"missing required fab-set file: {name}"
    assert "pos/positions.csv" in files
    assert "bom.csv" in files
    assert b"lcsc:C123" in files["bom.csv"].content
    assert "panel.json" in files
    assert b'"board"' in files["panel.json"].content
    # WO-103: the pinned board file ships beside its exports, with an
    # honest derived status (no routed segments -> "unrouted").
    assert "board.kicad_pcb" in files
    assert files["board.kicad_pcb"].content == b"(kicad_pcb ...)"
    assert "board_status.json" in files
    assert b'"unrouted' in files["board_status.json"].content
    assert b"fab-shape evidence" in files["board_status.json"].content


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
    for name in elec_fabset.REQUIRED_FAB_SET:
        assert name in files, f"missing required fab-set file: {name}"
    silk = files["gerbers/board-F_Silkscreen.gto"].content
    assert b"D02" in silk or b"D01" in silk  # real vector strokes plotted
    assert "pos/positions.csv" in files
    assert files["pos/positions.csv"].content.startswith(b"Ref,Val,Package")
    assert "bom.csv" in files
    assert "panel.json" in files
    # WO-103: the pinned board file rides along, honestly stamped.
    assert "board.kicad_pcb" in files
    assert files["board.kicad_pcb"].content == _MINIMAL_KICAD_PCB
    assert "board_status.json" in files


def test_package_index_labels_unrouted_boards_as_fab_shape_evidence() -> None:
    """WO-103 deliverable 3: the package index's boards-family line
    carries the backend's own honest status label (never invented by
    the index; absent when there is no `board_status.json`)."""
    from regolith.backends.framework import OutputFile
    from regolith.backends.package import build_index
    from regolith.orchestrator.orchestrate import GateCounts, GateSummary

    gate = GateSummary(
        tier="RELEASE",
        ok=True,
        release_ok=True,
        counts=GateCounts(violated=0, indeterminate=0, below_trust_floor=0),
    )
    status = (
        b'{"label":"unrouted -- fab-shape evidence: real board outline, '
        b'no routing performed","status":"unrouted"}'
    )
    labeled = build_index(
        "proj",
        gate,
        (
            OutputFile.of("boards/board.kicad_pcb", b"(kicad_pcb ...)"),
            OutputFile.of("boards/board_status.json", status),
        ),
    ).decode("ascii")
    assert "boards/: present (unrouted -- fab-shape evidence" in labeled

    unlabeled = build_index(
        "proj",
        gate,
        (OutputFile.of("boards/board.kicad_pcb", b"(kicad_pcb ...)"),),
    ).decode("ascii")
    assert "boards/: present\n" in unlabeled
