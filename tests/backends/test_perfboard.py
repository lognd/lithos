"""Tests for the perf-board manufacturing backend (WO-165): wiring map
+ cut list, both `tier="deterministic"` (no external tool -- the
Manhattan jumper assignment runs entirely in-process, WO-160/AD-45)."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs
from regolith.backends.perfboard import PerfboardBackend
from regolith.orchestrator.lockfile import Lockfile
from regolith.realizer.elec.board_assignment import ComponentAssignment
from regolith.realizer.elec.perfboard import (
    PerfboardNet,
    PerfboardNetlist,
    PerfboardSubstrate,
    realize_perfboard,
)


def _inputs(tmp_path: Path, subject: str = "perfboard_demo") -> BackendInputs:
    netlist = PerfboardNetlist(
        netlist_hash="sha256:test",
        board_outline_ref="demo:perfboard_led_blink",
        substrate=PerfboardSubstrate(rows=8, cols=12),
        components=(
            ComponentAssignment(
                reference="LED1", footprint="LED_3mm", anchor_hole="2,2"
            ),
            ComponentAssignment(reference="R1", footprint="R0805", anchor_hole="2,4"),
            ComponentAssignment(reference="SW1", footprint="SW_PTH", anchor_hole="5,2"),
        ),
        nets=(
            PerfboardNet(name="vcc", pin_holes=("0,0", "2,2")),
            PerfboardNet(name="sig", pin_holes=("2,2", "2,4")),
            PerfboardNet(name="gnd", pin_holes=("2,4", "5,2", "7,0")),
        ),
    )
    assignment = realize_perfboard(netlist).danger_ok
    return BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(str(tmp_path)),
        board_assignments={subject: assignment},
    )


def test_missing_board_assignment_refuses(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, subject="other_subject")
    backend = PerfboardBackend("perfboard_demo")
    result = backend.produce(inputs)
    assert result.is_err
    assert result.danger_err.kind == "board_assignment_ir_unavailable"


def test_produce_emits_wiring_map_and_cutlist(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    backend = PerfboardBackend("perfboard_demo")
    result = backend.produce(inputs)
    assert result.is_ok
    files = {f.relpath: f for f in result.danger_ok}
    assert "wiring_map/wiring_map.svg" in files
    assert "wiring_map/wiring_map.json" in files
    assert "cutlist/cutlist.csv" in files
    assert "cutlist/board_dimensions.json" in files
    for f in files.values():
        assert f.provenance is not None
        assert f.provenance.tier == "deterministic"
        assert f.provenance.tool is None


def test_cutlist_csv_has_a_row_per_wire_plus_total(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    backend = PerfboardBackend("perfboard_demo")
    files = {f.relpath: f for f in backend.produce(inputs).danger_ok}
    rows = list(csv.reader(io.StringIO(files["cutlist/cutlist.csv"].content.decode())))
    header, *body = rows
    assert header == ["net", "from_hole", "to_hole", "length_mm", "gauge_awg"]
    assert body[-1][0] == "TOTAL"
    # 3 nets producing 4 wire segments total (vcc:1, sig:1, gnd:2) + totals row.
    assert len(body) == 4 + 1


def test_produce_is_deterministic_byte_identical(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    backend = PerfboardBackend("perfboard_demo")
    first = {f.relpath: f.content for f in backend.produce(inputs).danger_ok}
    second = {f.relpath: f.content for f in backend.produce(inputs).danger_ok}
    assert first == second
