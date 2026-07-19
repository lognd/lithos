"""WO-133 deliverable 3: `elec.power.*` claim routing to the T-0009
built-in models (`regolith.harness.models.power`) via the shared
`_translate_power_claim` wrapper. Each of the seven modeled kinds
routes with real declared inputs (call kwargs, D250.3 -- no "typical
value" fallback anywhere); an undeclared safety-critical input (a
source's `available_fault_current`) defers BY NAME rather than
assuming a value. The five no-model kinds (`withstand`/`coordination`/
`arc_flash`/`grounding`/`harmonics`, D250.4) are deliberately left
unrouted here and checked separately for their honest
`unmatched_call_path` deferral. `working_clearance` (WO-136/D249) is
NOT among either group -- it routes through its OWN D103
general-comparison shape (`_translate_working_clearance`), covered in
`TestWorkingClearance` below, since its inputs cross the elec/calcite
file boundary through entity-DB references rather than inline
literals.
"""

from __future__ import annotations

from regolith._schema.models import Obligation
from regolith.orchestrator.translate import translate


def _power_obligation(
    lhs: str, op: str, rhs: str, refs: list[list[str]] | None = None
) -> Obligation:
    return Obligation.model_validate(
        {
            "claim": {
                "name": "power_check",
                "form": {
                    "form": "comparison",
                    "lhs": lhs,
                    "op": op,
                    "rhs": rhs,
                },
                "forall": [],
                "hints": [],
            },
            "subject_ref": "test-subject",
            "given": {
                "materials": [],
                "loads": [],
                "backing": [],
                "refs": refs or [],
            },
            "hints": [],
            "payloads": [],
        }
    )


class TestDemandLoad:
    # frob:tests python/regolith/orchestrator/translate.py::_translate_power_claim kind="unit"
    def test_routes_with_declared_inputs(self) -> None:
        obligation = _power_obligation(
            "elec.power.demand_load(PanelA, connected_kva=100.0, demand_factor=0.8)",
            "<=",
            "90",
        )
        result = translate(obligation)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.claim_kind == "elec.power.demand_load"
        assert request.inputs["connected_kva"].hi == 100.0
        assert request.inputs["demand_factor"].hi == 0.8

    def test_defers_by_name_when_input_missing(self) -> None:
        obligation = _power_obligation(
            "elec.power.demand_load(PanelA, connected_kva=100.0)",
            "<=",
            "90",
        )
        result = translate(obligation)
        assert not result.is_ok
        deferral = result.danger_err
        assert "demand_factor" in deferral.detail


class TestFaultCurrent:
    def test_undeclared_fault_current_input_defers_never_assumes(self) -> None:
        # D250.3: a transformer with no declared pct_z must defer by
        # name, never assume a "typical" nameplate percent impedance.
        obligation = _power_obligation(
            "elec.power.fault_current(MainBus, transformer_kva=1000.0, "
            "secondary_voltage_v=480.0)",
            "<=",
            "65000",
        )
        result = translate(obligation)
        assert not result.is_ok
        assert "pct_z" in result.danger_err.detail

    def test_routes_with_every_declared_input(self) -> None:
        obligation = _power_obligation(
            "elec.power.fault_current(MainBus, transformer_kva=1000.0, "
            "pct_z=5.75, secondary_voltage_v=480.0)",
            "<=",
            "65000",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.fault_current"


class TestVoltageDropAmpacityMotorLoadingFactor:
    def test_voltage_drop_routes(self) -> None:
        obligation = _power_obligation(
            "elec.power.voltage_drop(PanelA -> LightingLoad, current_a=40.0, "
            "length_m=20.0, resistance_ohm_per_m=0.0008, "
            "reactance_ohm_per_m=0.0002, power_factor=0.9, "
            "phase_multiplier=1.732)",
            "<=",
            "9.6",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.voltage_drop"

    def test_ampacity_routes(self) -> None:
        obligation = _power_obligation(
            "elec.power.ampacity(f2, base_ampacity_a=145.0, "
            "temperature_correction_factor=0.87, "
            "fill_adjustment_factor=1.0)",
            ">=",
            "100",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.ampacity"

    def test_motor_start_dip_routes(self) -> None:
        obligation = _power_obligation(
            "elec.power.motor_start_dip(PressMotor, "
            "motor_locked_rotor_kva=250.0, source_available_kva=5000.0)",
            "<=",
            "10",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.motor_start_dip"

    def test_transformer_loading_routes(self) -> None:
        obligation = _power_obligation(
            "elec.power.transformer_loading(xfmr, actual_kva=800.0, rated_kva=1000.0)",
            "<=",
            "100",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.transformer_loading"

    def test_power_factor_routes(self) -> None:
        obligation = _power_obligation(
            "elec.power.power_factor(MainBus, real_power_kw=720.0, "
            "apparent_power_kva=800.0)",
            ">=",
            "0.85",
        )
        result = translate(obligation)
        assert result.is_ok, result
        assert result.danger_ok.claim_kind == "elec.power.power_factor"


class TestWorkingClearance:
    """WO-136 (D249/AD-42): `elec.power.working_clearance(<apparatus>)`,
    the calcite tandem's new claim kind -- routed through
    `_translate_working_clearance`, not `_translate_power_claim`
    (its rhs carries cross-file entity-field references, not inline
    literals)."""

    # frob:tests python/regolith/orchestrator/translate.py::_translate_working_clearance
    def test_routes_and_resolves_refs_via_given_refs(self) -> None:
        obligation = _power_obligation(
            "elec.power.working_clearance(xfmr)",
            ">=",
            "ElectricalRoom.depth - xfmr.footprint_depth - 1.0",
            refs=[
                ["ElectricalRoom.depth", "3.0m"],
                ["xfmr.footprint_depth", "1.2m"],
            ],
        )
        result = translate(obligation)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.claim_kind == "elec.power.working_clearance"
        assert request.limit == 1.0
        assert request.inputs["room_dim_m"].hi == 3.0
        assert request.inputs["footprint_dim_m"].hi == 1.2

    def test_unresolved_reference_defers_naming_it(self) -> None:
        obligation = _power_obligation(
            "elec.power.working_clearance(xfmr)",
            ">=",
            "ElectricalRoom.depth - xfmr.footprint_depth - 1.0",
            refs=[["xfmr.footprint_depth", "1.2m"]],
        )
        result = translate(obligation)
        assert result.is_err
        deferral = result.danger_err
        assert deferral.reason == "given_unresolved"
        assert "ElectricalRoom.depth" in deferral.detail

    def test_shape_mismatch_when_rhs_has_no_literal(self) -> None:
        obligation = _power_obligation(
            "elec.power.working_clearance(xfmr)",
            ">=",
            "ElectricalRoom.depth - xfmr.footprint_depth",
        )
        result = translate(obligation)
        assert result.is_err
        assert result.danger_err.reason == "working_clearance_shape_mismatch"

    def test_shape_mismatch_when_the_literal_is_added_not_subtracted(self) -> None:
        obligation = _power_obligation(
            "elec.power.working_clearance(xfmr)",
            ">=",
            "ElectricalRoom.depth - xfmr.footprint_depth + 1.0",
        )
        result = translate(obligation)
        assert result.is_err
        assert result.danger_err.reason == "working_clearance_shape_mismatch"


class TestNoModelKindsStayUnrouted:
    # D250.4: arc_flash/coordination/harmonics/grounding/
    # withstand register NO built-in model -- deliberately absent from
    # `_POWER_CLAIM_INPUTS`/the FORM_NAMES dispatch tables above, so a
    # claim of one of these kinds takes the SAME generic scalar-claim
    # path any other unregistered kind takes (never routed through
    # `_translate_power_claim`, which would otherwise report a
    # misleading "missing inputs" deferral for ports no model reads).
    # The harness's own model-registry lookup at discharge time is
    # what ultimately refuses it (see
    # `tests/harness/test_power_models.py`'s no-model proof).
    def test_arc_flash_is_not_routed_through_the_power_wrapper(self) -> None:
        obligation = _power_obligation("elec.power.arc_flash(MainSwgr)", "<=", "8")
        result = translate(obligation)
        assert result.is_ok, result
        request = result.danger_ok
        assert request.claim_kind == "elec.power.arc_flash"
        # No `_POWER_CLAIM_INPUTS` port names were pulled onto this
        # request -- it carries only whatever the generic path found.
        assert "pct_z" not in request.inputs
        assert "available_fault_current" not in request.inputs
