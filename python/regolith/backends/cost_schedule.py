"""Cost + schedule sheet producers (WO-101 deliverable 5; charter 38
sec. 1.8, AD-27).

Costing evidence and schedules become SHIPPED sheets -- every one an
ordinary `DrawingModel` table through the ordinary table/sheet IR
(charter/AD-27: schedules are `tables` in the same IR, never a second
mechanism), so they render through the same registry as every drawing:

- :func:`cost_summary_sheet` projects a build's persisted itemized
  estimates (`ItemizedEstimate`, toolchain/27 sec. 1.5) into a cost
  summary table (one line item per row + the profile-cited total);
- :func:`member_schedule_sheet` projects a calcite frame's members into
  a member schedule (calcite/03 sec. 4).

The CAM plan summary schedule is a follow-up (its plan payload has no
backend-facing surface yet -- recorded as a WO-101 residual).

Every value is already-decided (regolith/07 sec. 6): these functions
PROJECT the realized IRs, they never compute a cost or a takeoff.
"""

from __future__ import annotations

from collections.abc import Mapping

from regolith._schema.models import (
    DrawingModel,
    FramePayload,
    ItemizedEstimate,
    Sheet,
    SheetSize1,
    Table,
    TableRow,
    TitleBlock,
)
from regolith.logging_setup import get_logger

_log = get_logger(__name__)


def _sheet(subject: str, title: str, drawing_number: str, table: Table) -> DrawingModel:
    """Wrap one table in a single-sheet `DrawingModel` (shared boilerplate)."""
    sheet = Sheet(
        size=SheetSize1.ansi_a,
        title_block=TitleBlock(
            title=title,
            drawing_number=drawing_number,
            revision="A",
            scale_label="NTS",
            subject=subject,
        ),
        views=[],
        entities=[],
        dimensions=[],
        annotations=[],
        tables=[table],
    )
    return DrawingModel(subject=subject, sheets=[sheet])


# frob:doc docs/modules/py-backends.md#backends-cost-schedule
def cost_summary_sheet(
    subject: str, estimates: Mapping[str, ItemizedEstimate]
) -> DrawingModel:
    """A cost summary sheet: one row per estimate line item across every
    subject/profile, then a per-estimate total row citing its profile.

    Deterministic: subjects sorted, then line items in estimator-emission
    order (the estimate payload's own order)."""
    columns = ["subject", "profile", "item", "qty", "unit_cost", "extended", "record"]
    rows: list[TableRow] = []
    for est_subject in sorted(estimates):
        estimate = estimates[est_subject]
        for line in estimate.lines:
            rows.append(
                TableRow(
                    cells=[
                        est_subject,
                        estimate.profile,
                        line.item,
                        f"{line.qty.lo:g}",
                        f"{line.unit_cost.lo:g} {line.unit_cost.unit}",
                        f"{line.extended.lo:g} {line.extended.unit}",
                        line.record.name,
                    ]
                )
            )
        for exclusion in estimate.exclusions:
            rows.append(
                TableRow(
                    cells=[
                        est_subject,
                        estimate.profile,
                        f"(excluded: {exclusion})",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            )
        total = estimate.total
        rows.append(
            TableRow(
                cells=[
                    est_subject,
                    estimate.profile,
                    "TOTAL",
                    "",
                    "",
                    f"{total.lo:g} {total.unit}",
                    "",
                ]
            )
        )
    _log.info("cost summary sheet: %s -> %d row(s)", subject, len(rows))
    return _sheet(
        subject,
        f"{subject} Cost Summary",
        f"COST-{subject}",
        Table(title="Cost Summary", columns=columns, rows=rows),
    )


# frob:doc docs/modules/py-backends.md#backends-cost-schedule
def member_schedule_sheet(subject: str, frame: FramePayload) -> DrawingModel:
    """A member schedule sheet (calcite/03 sec. 4): one row per frame
    member -- id / role / section / material / length -- in source order.

    An unresolved section/material name is left blank (the AD-25
    GeomExtract idiom: an unresolved value is never a fabricated cell)."""
    columns = ["mark", "role", "section", "material", "length"]
    rows: list[TableRow] = []
    for member in frame.members:
        role = getattr(member.role, "value", member.role)
        length = member.length
        rows.append(
            TableRow(
                cells=[
                    member.id,
                    str(role),
                    member.section.name,
                    member.material.name,
                    f"{length.lo:g} {length.unit}",
                ]
            )
        )
    _log.info("member schedule sheet: %s -> %d member(s)", subject, len(rows))
    return _sheet(
        subject,
        f"{subject} Member Schedule",
        f"SCHED-{subject}",
        Table(title="Member Schedule", columns=columns, rows=rows),
    )
