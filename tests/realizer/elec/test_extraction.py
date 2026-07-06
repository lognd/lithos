"""Post-route extraction surface (WO-24 deliverable 4)."""

from __future__ import annotations

from pathlib import Path

from regolith.realizer.elec.errors import ToolUnavailable
from regolith.realizer.elec.extraction import (
    LayoutExtraction,
    extract_from_pcb,
    to_discharge_inputs,
)


def test_extract_from_pcb_is_honest_tool_unavailable(tmp_path: Path) -> None:
    """No fake numbers: pcbnew is absent, so this is a documented cut."""
    result = extract_from_pcb(tmp_path / "board.kicad_pcb")
    assert result.is_err
    assert isinstance(result.danger_err, ToolUnavailable)
    assert result.danger_err.tool == "pcbnew"


def test_to_discharge_inputs_shapes_a_net_length() -> None:
    extraction = LayoutExtraction(net_lengths_mm={"VDD": 42.5})
    inputs = to_discharge_inputs(extraction, "VDD")
    assert inputs["net_length_mm"].lo == 42.5
    assert inputs["net_length_mm"].hi == 42.5


def test_to_discharge_inputs_defaults_unknown_net_to_zero() -> None:
    extraction = LayoutExtraction()
    inputs = to_discharge_inputs(extraction, "UNKNOWN")
    assert inputs["net_length_mm"].lo == 0.0
