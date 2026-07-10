"""WO-74 ship-artifact residual, sheets/schedule leg: the plan/section
sheet + member schedule for `examples/flagships/timber_pavilion/`, via
the WO-50 `civil_plan_section` producer directly over the REAL
`FramePayload` off `compiler.check(...)`'s own build payload
(`payload["frames"]["PavilionFrame"]`) -- the same direct-producer
idiom `tests/backends/test_drawings.py`'s own `civil_plan_section`
unit tests exercise over a hand-built fixture, and the same "pull the
real payload, don't build a synthetic one" idiom `tests/
test_flagship_printer_sheets.py` establishes for the harness block
diagram.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from regolith import compiler
from regolith._schema.models import FramePayload
from regolith.backends.drawings.producers import civil_plan_section
from regolith.backends.drawings.renderer import render_svg


def _pavilion_frame() -> FramePayload:
    result = compiler.check(("examples/flagships/timber_pavilion",))
    assert result.is_ok, f"timber_pavilion: check itself failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    frames = payload.get("frames") or {}
    assert "PavilionFrame" in frames, sorted(frames)
    return FramePayload.model_validate(frames["PavilionFrame"])


class TestTimberPavilionPlanSection:
    def test_produces_a_sheet_with_member_schedule(self) -> None:
        frame = _pavilion_frame()
        model = civil_plan_section("PavilionFrame", frame)
        assert model.sheets, "expected at least one sheet"
        table = model.sheets[0].tables[0]
        assert table.title == "Member Schedule"
        # G1, G2, Purlin, and both posts (P_A/P_B) all carry a
        # nonzero length off this project's frame elaboration.
        assert len(table.rows) >= 3

    def test_svg_is_valid_and_deterministic(self) -> None:
        frame = _pavilion_frame()
        m1 = civil_plan_section("PavilionFrame", frame)
        m2 = civil_plan_section("PavilionFrame", frame)
        assert m1.model_dump_json(by_alias=True) == m2.model_dump_json(by_alias=True)
        svg1 = render_svg(m1)
        svg2 = render_svg(m2)
        assert svg1 == svg2
        ET.fromstring(svg1)
        svg1.decode("ascii")

    def test_every_dimension_carries_provenance(self) -> None:
        frame = _pavilion_frame()
        model = civil_plan_section("PavilionFrame", frame)
        for sheet in model.sheets:
            for dim in sheet.dimensions:
                assert dim.provenance is not None
