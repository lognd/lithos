"""Post-route extraction surface (WO-24 deliverable 4)."""

from __future__ import annotations

from pathlib import Path

from regolith.realizer.elec.errors import LayoutFailed, ToolUnavailable
from regolith.realizer.elec.extraction import (
    LayoutExtraction,
    extract_from_pcb,
    to_discharge_inputs,
)
from regolith.realizer.elec.kicad import pcbnew_importable


# frob:tests python/regolith/realizer/elec/kicad.py::pcbnew_importable kind="unit"
# frob:waive TEST005 reason="test-file fixture/helper with environment-gated branches (tool-absent paths unreachable in a kicad-less env); TEST005 measuring test code is a tool quirk (TEST001 skips test files, TEST005 does not) -- FROBLEMS 2026-07-19"
def test_extract_from_pcb_is_honest_tool_unavailable(tmp_path: Path) -> None:
    """No fake numbers on a pcbnew-less host: a documented, gated cut.

    On a host where `make install`'s `kicad-link` succeeded (this
    repo's own dev environment), `pcbnew` IS importable -- the honest
    outcome for a MISSING file there is `LayoutFailed`, asserted by
    `test_extract_from_pcb_missing_file_is_honest_layout_failed` below,
    not this ToolUnavailable case.
    """
    if pcbnew_importable():
        import pytest

        pytest.skip("pcbnew importable on this host; see the LayoutFailed test")
    result = extract_from_pcb(tmp_path / "board.kicad_pcb")
    assert result.is_err
    assert isinstance(result.danger_err, ToolUnavailable)
    assert result.danger_err.tool == "pcbnew"


def test_extract_from_pcb_missing_file_is_honest_layout_failed(
    tmp_path: Path,
) -> None:
    """On a pcbnew-having host, a missing file is `LayoutFailed`, not a crash."""
    if not pcbnew_importable():
        import pytest

        pytest.skip("pcbnew not importable on this host; see the ToolUnavailable test")
    result = extract_from_pcb(tmp_path / "does_not_exist.kicad_pcb")
    assert result.is_err
    assert isinstance(result.danger_err, LayoutFailed)


def test_to_discharge_inputs_shapes_a_net_length() -> None:
    extraction = LayoutExtraction(net_lengths_mm={"VDD": 42.5})
    inputs = to_discharge_inputs(extraction, "VDD")
    assert inputs["net_length_mm"].lo == 42.5
    assert inputs["net_length_mm"].hi == 42.5


def test_to_discharge_inputs_defaults_unknown_net_to_zero() -> None:
    extraction = LayoutExtraction()
    inputs = to_discharge_inputs(extraction, "UNKNOWN")
    assert inputs["net_length_mm"].lo == 0.0
