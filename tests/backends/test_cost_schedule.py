"""Tests for the cost + schedule sheet producers (WO-101 deliverable 5)."""

from __future__ import annotations

from regolith._schema.models import (
    EstimateLineItem,
    ItemizedEstimate,
    RecordRef,
    ScalarInterval,
)
from regolith.backends.cost_schedule import cost_summary_sheet, member_schedule_sheet


def _estimate() -> ItemizedEstimate:
    return ItemizedEstimate(
        profile="espresso",
        exclusions=["shipping"],
        lines=[
            EstimateLineItem(
                item="boiler",
                qty=ScalarInterval(lo=1.0, hi=1.0, unit="each"),
                unit_cost=ScalarInterval(lo=80.0, hi=80.0, unit="USD"),
                record=RecordRef(digest="sha256:x", name="parts.boiler"),
                extended=ScalarInterval(lo=80.0, hi=80.0, unit="USD"),
            )
        ],
        total=ScalarInterval(lo=80.0, hi=80.0, unit="USD"),
    )


def test_cost_summary_sheet_has_line_exclusion_and_total():
    model = cost_summary_sheet("espresso", {"machine": _estimate()})
    table = model.sheets[0].tables[0]
    assert table.title == "Cost Summary"
    cells = [row.cells for row in table.rows]
    assert any("boiler" in c for c in cells)
    assert any("shipping" in " ".join(c) for c in cells)
    assert any(c[2] == "TOTAL" for c in cells)


def test_cost_summary_sheet_deterministic():
    a = cost_summary_sheet("m", {"b": _estimate(), "a": _estimate()})
    b = cost_summary_sheet("m", {"a": _estimate(), "b": _estimate()})
    assert a.model_dump_json() == b.model_dump_json()


def test_member_schedule_sheet_rows_from_frame():
    from regolith._schema.models import (
        FrameMember,
        FramePayload,
        MemberRole1,
        Releases,
    )
    from regolith._schema.models import (
        RecordRef as RR,
    )

    member = FrameMember(
        id="B1",
        a="J1",
        b="J2",
        role=MemberRole1.beam,
        length=ScalarInterval(lo=3.0, hi=3.0, unit="m"),
        section=RR(digest="sha256:s", name="W200x22"),
        material=RR(digest="sha256:m", name="S355"),
        orientation="+z",
        releases=Releases(a=[], b=[]),
        section_domain=None,
    )
    frame = FramePayload(
        members=[member],
        joints=[],
        loads=[],
        supports=[],
        transfers=[],
        combinations=RR(digest="sha256:c", name="ASCE7"),
    )
    model = member_schedule_sheet("pavilion", frame)
    table = model.sheets[0].tables[0]
    assert table.title == "Member Schedule"
    (row,) = table.rows
    assert row.cells[0] == "B1"
    assert "W200x22" in row.cells
    assert "S355" in row.cells
