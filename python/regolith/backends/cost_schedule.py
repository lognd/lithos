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
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    # Type-only: `regolith.realizer.elec.dwelling_wiring` imports THIS
    # module's `cable_schedule_sheet`/`panel_schedule_sheet` (the
    # `Table`/`DrawingModel` schedule machinery, WO-167 deliverable 3),
    # so a runtime import here would be circular -- the same
    # `PayloadResolver`-in-`harness/model.py` precedent.
    from regolith.realizer.elec.dwelling_wiring import RealizedDwellingWiring

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
def cable_schedule_sheet(
    subject: str, realized: RealizedDwellingWiring
) -> DrawingModel:
    """A cable schedule sheet (WO-167 deliverable 3, D268 item 4): one
    row per dwelling branch circuit -- name/room/load class/connected
    VA/wire gauge/breaker size/length/derated ampacity/voltage drop --
    in declaration order, each row's ampacity/voltage-drop verdict
    carried alongside the declared data (never a second silent
    source of truth: the verdict IS this same realize pass's
    `CircuitCheckResult`, projected, not recomputed)."""
    columns = [
        "circuit",
        "room",
        "load_class",
        "connected_va",
        "wire_gauge",
        "breaker_a",
        "length_m",
        "derated_ampacity_a",
        "voltage_drop_pct",
        "verdict",
    ]
    rows: list[TableRow] = []
    checks_by_name = {c.name: c for c in realized.circuit_checks}
    for circuit in realized.plan.circuits:
        check = checks_by_name[circuit.name]
        verdict = (
            "VIOLATED"
            if (check.ampacity_violated or check.voltage_drop_violated)
            else "pass"
        )
        rows.append(
            TableRow(
                cells=[
                    circuit.name,
                    circuit.room,
                    circuit.load_class,
                    f"{circuit.connected_va:g}",
                    circuit.wire_gauge,
                    f"{circuit.breaker_a:g}",
                    f"{circuit.length_m:g}",
                    f"{check.derated_ampacity_a:.3f}",
                    f"{check.voltage_drop_pct:.4f}",
                    verdict,
                ]
            )
        )
    _log.info("cable schedule sheet: %s -> %d row(s)", subject, len(rows))
    return _sheet(
        subject,
        f"{subject} Cable Schedule",
        f"CBL-{subject}",
        Table(title="Cable Schedule", columns=columns, rows=rows),
    )


# frob:doc docs/modules/py-backends.md#backends-cost-schedule
def panel_schedule_sheet(
    subject: str, realized: RealizedDwellingWiring
) -> DrawingModel:
    """A panel schedule sheet (WO-167 deliverable 3): the panel's
    service rating + siting verdict, then one row per branch circuit
    (breaker size + connected load) -- the panel-catalog CONTENT
    (bus ampacity, lugs rating, slot count) is a NAMED REFUSAL (D250
    sec. 3, no `std.power` catalog record for it exists); this sheet
    carries only the author-declared circuits/loads WO-167 permits."""
    plan = realized.plan
    columns = [
        "breaker_slot",
        "circuit",
        "room",
        "load_class",
        "breaker_a",
        "connected_va",
    ]
    rows: list[TableRow] = [
        TableRow(
            cells=[
                str(i + 1),
                circuit.name,
                circuit.room,
                circuit.load_class,
                f"{circuit.breaker_a:g}",
                f"{circuit.connected_va:g}",
            ]
        )
        for i, circuit in enumerate(plan.circuits)
    ]
    clearance_row = TableRow(
        cells=[
            "--",
            "(panel siting)",
            plan.room,
            "working_clearance",
            f"{plan.working_clearance_mm:.1f}mm",
            (
                "VIOLATED"
                if realized.working_clearance_violated
                else f"pass (min {plan.min_working_clearance_mm:.1f}mm)"
            ),
        ]
    )
    rows.append(clearance_row)
    _log.info("panel schedule sheet: %s -> %d row(s)", subject, len(rows))
    return _sheet(
        subject,
        f"{subject} Panel Schedule "
        f"({plan.service_amps:g}A/{plan.service_voltage:g}V service; "
        "breaker/panel bus-ampacity catalog content D250 sec.3 named "
        "refusal, not represented here)",
        f"PNL-{subject}",
        Table(title="Panel Schedule", columns=columns, rows=rows),
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
