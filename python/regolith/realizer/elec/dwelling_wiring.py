"""The dwelling/house-wiring realizer program (WO-167, D268 item 4 --
the fourth and final owner capability target).

An application of the WO-132..137 power track's landed cuprite power
vocabulary + WO-136 cuprite-calcite tandem to residential branch-
circuit/panel/service scope, NOT a new language (WO-167's own framing:
"this program does not introduce a new language split, it extends the
landed power track's"). This module is this program's own minimal
capability IR (:class:`DwellingCircuitPlan`, mirroring
`PerfboardNetlist`/`WireEdmProfile`'s "new capability, own small IR"
precedent, WO-165/166), plus the realize step that discharges every
branch circuit's ampacity/voltage-drop claims through the REAL
WO-135 closed-form models (`regolith.harness.models.power`) -- never
re-deriving the arithmetic those models already own (NO DUPLICATION) --
and projects the declared circuit data into the two artifact families
this program brings (`cable_schedule`, `panel_schedule`, WO-167
deliverable 3) via the existing `Table`/`DrawingModel` schedule
machinery (`regolith.backends.cost_schedule`).

Licensing posture (D250/D268, verbatim, this module's own binding):
every circuit's load/wire-gauge/breaker-size/length/base-ampacity/
conductor-resistance figure is AUTHOR-DECLARED (a residential design's
own read of its own conductors), never a transcribed NEC table row.
Panel bus-ampacity/breaker-catalog content stays a NAMED REFUSAL (D250
sec. 3) -- this module never claims or checks it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.backends.cost_schedule import cable_schedule_sheet, panel_schedule_sheet
from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest
from regolith.harness.models.dfm.checks import (
    check_ampacity_containment,
    check_voltage_drop_limit,
    check_working_clearance,
)
from regolith.harness.models.power import AmpacityModel, VoltageDropModel
from regolith.harness.quantity import Interval
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# frob:doc docs/modules/py-harness.md#models-dfm-process
#: The `put_realized_*` payload-store kind this domain's realizer emits
#: (AD-25 discipline), named once here so `capabilities.py`'s
#: registration and any future orchestrator wiring share one string
#: (the tripwire rule applied to a realized-kind literal).
DWELLING_WIRING_DOMAIN_TAG = "dwelling_wiring.realized"


# frob:doc docs/modules/py-harness.md#models-dfm-process
class BranchCircuit(BaseModel):
    """One author-declared residential branch circuit: the load it
    serves, its conductor, and the run it takes -- every field a
    design fact this circuit's author supplies, never a table lookup
    (D250.3: an unverifiable input is a named absence, never a
    default)."""

    model_config = ConfigDict(frozen=True)

    name: str
    room: str
    load_class: str  # "receptacle" | "lighting" | "appliance" | "motor"
    connected_va: float
    wire_gauge: str  # e.g. "12 AWG"
    breaker_a: float
    length_m: float
    base_ampacity_a: float
    resistance_ohm_per_m: float
    reactance_ohm_per_m: float = 0.0002
    power_factor: float = 0.95
    phase_multiplier: float = 2.0  # single-phase round-trip (IEEE 141 ch.3)
    voltage_v: float = 240.0
    temperature_correction_factor: float = 1.0
    fill_adjustment_factor: float = 1.0
    max_voltage_drop_pct: float = (
        3.0  # this design's own dwelling branch-circuit budget
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
class DwellingCircuitPlan(BaseModel):
    """One dwelling's panel + its branch circuits -- this program's
    own input IR (the `PerfboardNetlist`/`WireEdmProfile` precedent:
    a new capability program gets its own minimal IR rather than
    forcing an existing one to fit)."""

    model_config = ConfigDict(frozen=True)

    panel_name: str
    service_amps: float
    service_voltage: float
    circuits: tuple[BranchCircuit, ...]
    room: str
    working_clearance_mm: float
    min_working_clearance_mm: float


# frob:doc docs/modules/py-harness.md#models-dfm-process
class CircuitCheckResult(BaseModel):
    """One circuit's ampacity + voltage-drop verdicts (the two DFM
    checks WO-167 deliverable 4 names)."""

    model_config = ConfigDict(frozen=True)

    name: str
    derated_ampacity_a: float
    ampacity_violated: bool
    ampacity_note: str
    voltage_drop_pct: float
    voltage_drop_violated: bool
    voltage_drop_note: str


# frob:doc docs/modules/py-harness.md#models-dfm-process
class RealizedDwellingWiring(BaseModel):
    """The realized dwelling-wiring program: per-circuit check verdicts
    plus the panel's working-clearance verdict -- everything the
    `cable_schedule`/`panel_schedule` artifact families and the demo
    proof pack need."""

    model_config = ConfigDict(frozen=True)

    plan: DwellingCircuitPlan
    circuit_checks: tuple[CircuitCheckResult, ...]
    working_clearance_violated: bool
    working_clearance_note: str

    @property
    # frob:doc docs/modules/py-harness.md#models-dfm-process
    def all_clean(self) -> bool:
        """True iff every circuit check and the panel siting check pass."""
        return not self.working_clearance_violated and all(
            not c.ampacity_violated and not c.voltage_drop_violated
            for c in self.circuit_checks
        )


def _discharge_ampacity(circuit: BranchCircuit) -> Result[float, HarnessError]:
    """Derated ampacity via the REAL `AmpacityModel` (WO-135, NEC
    310.15 cited there) -- this function never re-derives the
    derating arithmetic."""
    request = DischargeRequest(
        claim_kind=AmpacityModel().signature.claim_kind,
        limit=circuit.breaker_a,
        inputs={
            "base_ampacity_a": Interval.point(circuit.base_ampacity_a),
            "temperature_correction_factor": Interval.point(
                circuit.temperature_correction_factor
            ),
            "fill_adjustment_factor": Interval.point(circuit.fill_adjustment_factor),
        },
    )
    result = AmpacityModel().estimate(request)
    if result.is_err:
        return Err(result.danger_err)
    return Ok(result.danger_ok.value)


def _discharge_voltage_drop(circuit: BranchCircuit) -> Result[float, HarnessError]:
    """Voltage drop (volts) via the REAL `VoltageDropModel` (WO-135,
    IEEE Std 141-1993 cited there); converted to percent-of-nominal
    here (the check's own declared units, never re-derived physics)."""
    current_a = circuit.breaker_a
    request = DischargeRequest(
        claim_kind=VoltageDropModel().signature.claim_kind,
        limit=circuit.voltage_v * circuit.max_voltage_drop_pct / 100.0,
        inputs={
            "current_a": Interval.point(current_a),
            "length_m": Interval.point(circuit.length_m),
            "resistance_ohm_per_m": Interval.point(circuit.resistance_ohm_per_m),
            "reactance_ohm_per_m": Interval.point(circuit.reactance_ohm_per_m),
            "power_factor": Interval.point(circuit.power_factor),
            "phase_multiplier": Interval.point(circuit.phase_multiplier),
        },
    )
    result = VoltageDropModel().estimate(request)
    if result.is_err:
        return Err(result.danger_err)
    volts = result.danger_ok.value
    return Ok(100.0 * volts / circuit.voltage_v)


# frob:doc docs/modules/py-harness.md#models-dfm-process
def realize_dwelling_circuit_plan(
    plan: DwellingCircuitPlan,
) -> Result[RealizedDwellingWiring, HarnessError]:
    """Realize a dwelling circuit plan: discharge every circuit's
    ampacity/voltage-drop claim through the real WO-135 models, gate
    each with the WO-170 `check_ampacity_containment`/
    `check_voltage_drop_limit` predicates, and gate the panel's siting
    with `check_working_clearance` (WO-136 tandem's own check, the
    same predicate `panel.cupr`'s `front:` obligation discharges
    against in the cuprite/calcite source)."""
    circuit_results: list[CircuitCheckResult] = []
    for circuit in plan.circuits:
        ampacity_result = _discharge_ampacity(circuit)
        if ampacity_result.is_err:
            return Err(ampacity_result.danger_err)
        derated = ampacity_result.danger_ok
        ampacity_outcome = check_ampacity_containment(derated, circuit.breaker_a)

        vdrop_result = _discharge_voltage_drop(circuit)
        if vdrop_result.is_err:
            return Err(vdrop_result.danger_err)
        vdrop_pct = vdrop_result.danger_ok
        vdrop_outcome = check_voltage_drop_limit(
            vdrop_pct, circuit.max_voltage_drop_pct
        )

        _log.info(
            "dwelling_wiring: circuit=%s derated_ampacity=%.3fA vdrop=%.4f%%",
            circuit.name,
            derated,
            vdrop_pct,
        )
        circuit_results.append(
            CircuitCheckResult(
                name=circuit.name,
                derated_ampacity_a=derated,
                ampacity_violated=ampacity_outcome.violated,
                ampacity_note=ampacity_outcome.note,
                voltage_drop_pct=vdrop_pct,
                voltage_drop_violated=vdrop_outcome.violated,
                voltage_drop_note=vdrop_outcome.note,
            )
        )

    clearance_outcome = check_working_clearance(
        plan.working_clearance_mm, plan.min_working_clearance_mm
    )
    _log.info(
        "dwelling_wiring: panel=%s working_clearance=%.2fmm min=%.2fmm violated=%s",
        plan.panel_name,
        plan.working_clearance_mm,
        plan.min_working_clearance_mm,
        clearance_outcome.violated,
    )
    return Ok(
        RealizedDwellingWiring(
            plan=plan,
            circuit_checks=tuple(circuit_results),
            working_clearance_violated=clearance_outcome.violated,
            working_clearance_note=clearance_outcome.note,
        )
    )


# frob:doc docs/modules/py-harness.md#models-dfm-process
def cable_schedule_for(realized: RealizedDwellingWiring):
    """The `cable_schedule` artifact: reuse
    `regolith.backends.cost_schedule.cable_schedule_sheet` (WO-167
    deliverable 3 -- no new schedule-rendering mechanism, the SAME
    `Table`/`DrawingModel` machinery `cost_summary_sheet`/
    `member_schedule_sheet` already use)."""
    return cable_schedule_sheet(realized.plan.panel_name, realized)


# frob:doc docs/modules/py-harness.md#models-dfm-process
def panel_schedule_for(realized: RealizedDwellingWiring):
    """The `panel_schedule` artifact (WO-167 deliverable 3)."""
    return panel_schedule_sheet(realized.plan.panel_name, realized)


__all__ = [
    "DWELLING_WIRING_DOMAIN_TAG",
    "BranchCircuit",
    "CircuitCheckResult",
    "DwellingCircuitPlan",
    "RealizedDwellingWiring",
    "cable_schedule_for",
    "panel_schedule_for",
    "realize_dwelling_circuit_plan",
]
