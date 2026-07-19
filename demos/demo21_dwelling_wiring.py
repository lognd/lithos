"""Demo 21 -- dwelling/house-wiring program: branch circuits -> panel
siting (cuprite-calcite tandem) -> cable schedule + panel schedule
artifacts (WO-167 deliverable 6, D268 item 4 -- the fourth and final
owner capability target).

Real cuprite/calcite source (`examples/flagships/dwelling_r1/`) proves
the language surface: `circuits.cupr` declares a 240V/120V residential
`power DwellingMain:` net (kitchen small-appliance, bedroom lighting,
bathroom, dryer branch circuits) with `demand_load`/`ampacity`/
`voltage_drop` claims; `panel.cupr` sites `MainPanelBox` into
`dwelling.calx`'s `UtilityCloset` via the WO-136 tandem's
`working_clearance` claim -- `regolith check` on that source is run
here and asserted CLEAN (0 diagnostics), proving the source compiles
through the real toolchain.

SCOPE NOTE (the same honest, named cut demo18/demo19 both take): the
cable schedule + panel schedule artifacts below are driven from an
in-memory `DwellingCircuitPlan` (mirroring the `.cupr` source's own
declared circuit data) through the REAL `regolith.realizer.elec.
dwelling_wiring` realize path -- WO-167's own DFM checks
(`check_ampacity_containment`/`check_voltage_drop_limit`/
`check_working_clearance`) discharge through the REAL WO-135 closed-
form models (`AmpacityModel`/`VoltageDropModel`), not a re-derived
arithmetic -- rather than through a schedule-artifact-emitting
`regolith build`/`ship` stage (no such stage exists yet for the
`power`/panel net kind; see F-WO137-1's sibling finding in
`power.cupr`'s ship spec comment for the identical drawings-producer
gap). The realizer, capability registration, and DFM checks below are
the REAL WO-167 code path, driven end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys

from regolith.backends.capabilities import default_capability_registry
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.logging_setup import get_logger
from regolith.realizer.elec.dwelling_wiring import (
    BranchCircuit,
    DwellingCircuitPlan,
    cable_schedule_for,
    panel_schedule_for,
    realize_dwelling_circuit_plan,
)

from demos.harness import REPO_ROOT, DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo21_dwelling_wiring"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = (
    "dwelling/house-wiring program: branch circuits -> panel siting "
    "(cuprite-calcite tandem) -> cable + panel schedule artifacts (WO-167)"
)
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
PROJECT = REPO_ROOT / "examples" / "flagships" / "dwelling_r1"


def _plan() -> DwellingCircuitPlan:
    """The SAME declared circuit data `circuits.cupr`/`panel.cupr`
    carry (kitchen/bedroom/bathroom/dryer branch circuits off a 200A/
    240V single-phase service, panel sited in the 0.9m-deep
    `UtilityCloset`), mirrored here as the realizer's own input IR."""
    return DwellingCircuitPlan(
        panel_name="MainPanel",
        service_amps=200.0,
        service_voltage=240.0,
        room="UtilityCloset",
        # UtilityCloset.depth (0.9m) - panel.footprint_depth (0.15m)
        # = 0.75m declared working clearance, matching panel.cupr's
        # `front:` obligation exactly.
        working_clearance_mm=750.0,
        min_working_clearance_mm=750.0,
        circuits=(
            BranchCircuit(
                name="kitchen_feed",
                room="Kitchen",
                load_class="receptacle",
                connected_va=2400.0,
                wire_gauge="12 AWG",
                breaker_a=20.0,
                length_m=15.0,
                base_ampacity_a=25.0,
                resistance_ohm_per_m=0.00521,
            ),
            BranchCircuit(
                name="bedroom_feed",
                room="Bedroom",
                load_class="lighting",
                connected_va=1200.0,
                wire_gauge="14 AWG",
                breaker_a=15.0,
                length_m=18.0,
                base_ampacity_a=20.0,
                resistance_ohm_per_m=0.00828,
            ),
            BranchCircuit(
                name="bath_feed",
                room="Bathroom",
                load_class="receptacle",
                connected_va=1800.0,
                wire_gauge="12 AWG",
                breaker_a=20.0,
                length_m=12.0,
                base_ampacity_a=25.0,
                resistance_ohm_per_m=0.00521,
            ),
            BranchCircuit(
                name="dryer_feed",
                room="Laundry",
                load_class="appliance",
                connected_va=5000.0,
                wire_gauge="10 AWG",
                breaker_a=30.0,
                length_m=9.0,
                base_ampacity_a=30.0,
                resistance_ohm_per_m=0.00328,
            ),
        ),
    )


def _regolith_check(*paths: str) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "regolith.cli", "check", *paths]
    _log.info("demo21: running %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    return result.returncode == 0, result.stdout + result.stderr


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the dwelling-wiring proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)

    # --- slice a: real cuprite/calcite source compiles clean --------------
    ok, rendered = _regolith_check(str(PROJECT))
    if not ok:
        raise RuntimeError(
            f"regolith check on {PROJECT} reported diagnostics:\n{rendered}"
        )
    writer.emit("source_check/check_output.txt", rendered.encode("ascii", "replace"))

    # --- slice b: realize the declared circuit plan through the real -----
    #             WO-135 models + WO-170 DFM checks
    plan = _plan()
    realized_result = realize_dwelling_circuit_plan(plan)
    if realized_result.is_err:
        raise RuntimeError(f"realize failed: {realized_result.danger_err}")
    realized = realized_result.danger_ok
    if not realized.all_clean:
        raise RuntimeError("dwelling circuit plan failed its own DFM gates")

    # --- slice c: cable schedule + panel schedule artifacts ---------------
    cable_sheet = cable_schedule_for(realized)
    panel_sheet = panel_schedule_for(realized)
    writer.emit("cable_schedule/cable_schedule.pdf", render_pdf(cable_sheet))
    writer.emit("cable_schedule/cable_schedule.svg", render_svg(cable_sheet))
    writer.emit("panel_schedule/panel_schedule.pdf", render_pdf(panel_sheet))
    writer.emit("panel_schedule/panel_schedule.svg", render_svg(panel_sheet))

    checks_report = {
        "circuit_checks": [
            {
                "name": c.name,
                "derated_ampacity_a": c.derated_ampacity_a,
                "ampacity_violated": c.ampacity_violated,
                "voltage_drop_pct": c.voltage_drop_pct,
                "voltage_drop_violated": c.voltage_drop_violated,
            }
            for c in realized.circuit_checks
        ],
        "working_clearance_mm": plan.working_clearance_mm,
        "working_clearance_violated": realized.working_clearance_violated,
        "working_clearance_note": realized.working_clearance_note,
        "panel_catalog_content": {
            "status": "named_refusal",
            "detail": "panel bus ampacity / breaker-lugs rating / branch "
            "slot count require breaker/panel manufacturer catalog "
            "content not landed in std.power beyond WO-134/134B's "
            "transformer catalogue (D250 sec. 3) -- not represented in "
            "the panel schedule above",
        },
    }
    checks_bytes = (
        json.dumps(checks_report, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    ).encode("ascii")
    writer.emit("dwelling/checks_report.json", checks_bytes, deterministic=True)

    # --- slice d: capability registration ----------------------------------
    registry = default_capability_registry()
    dwelling_cap = registry.get("dwelling_wiring")
    if dwelling_cap is None:
        raise RuntimeError("dwelling_wiring capability failed to register")

    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- pipeline path: real cuprite/calcite source "
            "(`examples/flagships/dwelling_r1/circuits.cupr` + "
            "`panel.cupr` + `dwelling.calx`) checked clean via "
            "`regolith check` (slice a) -> `DwellingCircuitPlan` "
            "(slice b, the SAME declared circuit data as the source) -> "
            "`regolith.realizer.elec.dwelling_wiring."
            "realize_dwelling_circuit_plan` discharging every branch "
            "circuit's ampacity/voltage-drop claim through the real "
            "WO-135 `AmpacityModel`/`VoltageDropModel` and gating with "
            "the real WO-170 `check_ampacity_containment`/"
            "`check_voltage_drop_limit`/`check_working_clearance` "
            "predicates -> `cable_schedule`/`panel_schedule` artifacts "
            "(slice c) via the existing `Table`/`DrawingModel` schedule "
            "machinery (`regolith.backends.cost_schedule`).",
            "- feature proven: a 200A/240V single-phase residential "
            "service with four author-declared branch circuits (kitchen "
            "small-appliance 20A/12AWG, bedroom lighting 15A/14AWG, "
            "bathroom 20A/12AWG, dryer 30A/10AWG) all pass their "
            "declared derated-ampacity and 3%-voltage-drop budgets; the "
            "panel's 0.75m declared working clearance (`UtilityCloset."
            "depth - panel.footprint_depth - 0.75m` in `panel.cupr`, "
            "this design's own read of NEC Table 110.26(A)(1) Condition "
            "1) meets its own declared minimum exactly.",
            "- capability registration: `dwelling_wiring` domain "
            "registered via `regolith.backends.capabilities."
            "register_capability` (all seven `RealizerCapability` "
            f"fields populated: `program_kind`=`DwellingCircuitPlan`, "
            f"`realized_kind`={dwelling_cap.realized_kind!r}, "
            f"`artifact_families`={dwelling_cap.artifact_families!r}, "
            "one `deterministic` tool-adapter tier -- no external tool "
            "is invoked -- `process_records` referencing the three "
            "EXISTING WO-170 `std.process` elec-install records only, "
            "three real `dfm_checks`, and three EXISTING "
            "`elec.power.*` claim kinds, no new claim vocabulary).",
            "- honesty labels: panel bus-ampacity/breaker-lugs rating/"
            "branch-slot-count is a NAMED REFUSAL (D250 sec. 3, see "
            "`dwelling/checks_report.json`'s `panel_catalog_content` "
            "entry) -- no breaker/panel manufacturer catalog record "
            "exists in `std.power` beyond WO-134/134B's landed "
            "transformer catalogue, and none is fabricated here.",
            "- SCOPE NOTE (see this script's module docstring): the "
            "schedule artifacts are driven from an in-memory "
            "`DwellingCircuitPlan` mirroring the `.cupr` source's own "
            "declared data, rather than through a schedule-emitting "
            "`regolith build`/`ship` stage -- no such stage exists yet "
            "for the `power`/panel net kind (the same F-WO137-1 "
            "drawings-producer gap `power.cupr`'s ship spec already "
            "names); the cuprite/calcite source itself, the realizer, "
            "the DFM checks, and the capability registration are the "
            "REAL WO-167 code path, driven end to end above.",
            "",
            "## Re-run",
            "",
            "```",
            "uv run python -m demos.demo21_dwelling_wiring",
            "```",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="n/a (dwelling-wiring program, not an optimizer surface)",
        domain=(
            "residential branch-circuit/panel wiring program: 200A/240V "
            "service, four branch circuits, one sited panel"
        ),
        winner="n/a",
        cause_row="n/a",
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
