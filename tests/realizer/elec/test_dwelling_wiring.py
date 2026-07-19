"""Tests for the dwelling/house-wiring realizer (WO-167, D268 item 4):
`realize_dwelling_circuit_plan` discharges every branch circuit's
ampacity/voltage-drop claim through the real WO-135 `AmpacityModel`/
`VoltageDropModel`, gates each with the real WO-170 DFM checks, and
`cable_schedule_for`/`panel_schedule_for` project the result into the
`Table`/`DrawingModel` schedule machinery."""

from __future__ import annotations

from typing import NotRequired, TypedDict, Unpack

from regolith.realizer.elec.dwelling_wiring import (
    BranchCircuit,
    DwellingCircuitPlan,
    cable_schedule_for,
    panel_schedule_for,
    realize_dwelling_circuit_plan,
)


class _CircuitOverrides(TypedDict, total=False):
    """Mirrors `BranchCircuit`'s field set precisely (not
    `dict[str, object]`) so `**overrides` type-checks against the
    model's real per-field types instead of losing them to `object`."""

    name: str
    room: str
    load_class: str
    connected_va: float
    wire_gauge: str
    breaker_a: float
    length_m: float
    base_ampacity_a: float
    resistance_ohm_per_m: float
    reactance_ohm_per_m: float
    power_factor: float
    phase_multiplier: float
    voltage_v: float
    temperature_correction_factor: float
    fill_adjustment_factor: float
    max_voltage_drop_pct: float


# frob:ticket T-0047
def _circuit(**overrides: Unpack[_CircuitOverrides]) -> BranchCircuit:
    defaults: _CircuitOverrides = dict(
        name="kitchen_feed",
        room="Kitchen",
        load_class="receptacle",
        connected_va=2400.0,
        wire_gauge="12 AWG",
        breaker_a=20.0,
        length_m=15.0,
        base_ampacity_a=25.0,
        resistance_ohm_per_m=0.00521,
    )
    defaults.update(overrides)
    return BranchCircuit(**defaults)


class _PlanOverrides(TypedDict, total=False):
    """Mirrors `DwellingCircuitPlan`'s field set precisely (not
    `dict[str, object]`); `circuits` is filled in below `_plan`'s own
    default from its `*circuits` varargs, never passed as an override
    directly."""

    panel_name: str
    service_amps: float
    service_voltage: float
    circuits: NotRequired[tuple[BranchCircuit, ...]]
    room: str
    working_clearance_mm: float
    min_working_clearance_mm: float


# frob:ticket T-0047
def _plan(
    *circuits: BranchCircuit, **overrides: Unpack[_PlanOverrides]
) -> DwellingCircuitPlan:
    defaults: _PlanOverrides = dict(
        panel_name="MainPanel",
        service_amps=200.0,
        service_voltage=240.0,
        room="UtilityCloset",
        working_clearance_mm=750.0,
        min_working_clearance_mm=750.0,
        circuits=circuits or (_circuit(),),
    )
    defaults.update(overrides)
    return DwellingCircuitPlan(**defaults)


# frob:ticket T-0047
def test_realize_dwelling_circuit_plan():
    """The bare `realize_dwelling_circuit_plan` name-matched unit test
    (frob TEST001): a clean plan realizes with every circuit and the
    panel siting check passing."""
    result = realize_dwelling_circuit_plan(_plan())
    assert result.is_ok
    assert result.danger_ok.all_clean


# frob:ticket T-0047
def test_realize_a_clean_plan_discharges_every_circuit():
    result = realize_dwelling_circuit_plan(_plan())
    assert result.is_ok
    realized = result.danger_ok
    assert realized.all_clean
    (check,) = realized.circuit_checks
    assert check.derated_ampacity_a == 25.0
    assert not check.ampacity_violated
    assert not check.voltage_drop_violated
    assert not realized.working_clearance_violated


# frob:ticket T-0047
def test_realize_an_ampacity_violation_is_named_not_papered_over():
    overloaded = _circuit(base_ampacity_a=15.0)  # below the 20A declared breaker
    result = realize_dwelling_circuit_plan(_plan(overloaded))
    realized = result.danger_ok
    assert not realized.all_clean
    (check,) = realized.circuit_checks
    assert check.ampacity_violated
    assert "exceeds" in check.ampacity_note


# frob:ticket T-0047
def test_realize_a_voltage_drop_violation_is_named():
    long_run = _circuit(length_m=500.0)  # a run long enough to exceed 3%
    result = realize_dwelling_circuit_plan(_plan(long_run))
    realized = result.danger_ok
    assert not realized.all_clean
    (check,) = realized.circuit_checks
    assert check.voltage_drop_violated


# frob:ticket T-0047
def test_realize_a_working_clearance_violation_is_named():
    result = realize_dwelling_circuit_plan(
        _plan(working_clearance_mm=100.0, min_working_clearance_mm=750.0)
    )
    realized = result.danger_ok
    assert realized.working_clearance_violated
    assert not realized.all_clean


# frob:ticket T-0047
def test_all_clean():
    """The bare `all_clean` name-matched unit test (frob TEST001)."""
    clean = realize_dwelling_circuit_plan(_plan()).danger_ok
    assert clean.all_clean
    dirty = realize_dwelling_circuit_plan(
        _plan(working_clearance_mm=0.0, min_working_clearance_mm=750.0)
    ).danger_ok
    assert not dirty.all_clean


# frob:ticket T-0047
def test_cable_schedule_for_and_panel_schedule_for_are_real_producers():
    realized = realize_dwelling_circuit_plan(_plan()).danger_ok
    cable_model = cable_schedule_for(realized)
    panel_model = panel_schedule_for(realized)
    assert cable_model.sheets[0].tables[0].title == "Cable Schedule"
    assert panel_model.sheets[0].tables[0].title == "Panel Schedule"


# frob:ticket T-0047
def test_realize_is_deterministic():
    plan = _plan()
    a = realize_dwelling_circuit_plan(plan).danger_ok
    b = realize_dwelling_circuit_plan(plan).danger_ok
    assert a.model_dump_json() == b.model_dump_json()
