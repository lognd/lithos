"""The lithos closed-form power-model pack (WO-135/D248.3/AD-42).

Covers: each closed-form model's worst-corner physics, domain guards,
citation presence (D250.1), registry pickup + discharge/violated
verdicts, the D250.3 named-absence refusal (a required safety input
simply absent from the request -> InputError, never a synthesized
default), and the D250.4 boundary proof that ``elec.power.arc_flash``
(and its certified-tier siblings) cannot be discharged by any built-in
registered here -- the most important test in WO-135's acceptance list.
"""

from __future__ import annotations

import pytest
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.errors import InputError
from regolith.harness.models.power import (
    AMPACITY_KIND,
    DEMAND_LOAD_KIND,
    FAULT_CURRENT_KIND,
    MOTOR_START_DIP_KIND,
    POWER_FACTOR_KIND,
    TRANSFORMER_LOADING_KIND,
    VOLTAGE_DROP_KIND,
    WORKING_CLEARANCE_KIND,
    AmpacityModel,
    DemandLoadModel,
    MotorStartDipModel,
    PowerFactorModel,
    TransformerFaultCurrentScreeningModel,
    TransformerLoadingModel,
    VoltageDropModel,
    WorkingClearanceModel,
)


def _iv(x: float | tuple[float, float]) -> Interval:
    lo, hi = x if isinstance(x, tuple) else (x, x)
    return Interval(lo=lo, hi=hi)


# ---------------------------------------------------------------------------
# 1. Demand load.
# ---------------------------------------------------------------------------


def test_demand_load_worst_corner_and_citation() -> None:
    model = DemandLoadModel()
    request = DischargeRequest(
        claim_kind=DEMAND_LOAD_KIND,
        limit=1000.0,
        inputs={
            "connected_kva": _iv((80.0, 100.0)),
            "demand_factor": _iv((0.6, 0.8)),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(100.0 * 0.8)
    assert model.citation is not None
    assert "NEC" in model.citation
    assert "220" in model.citation


def test_demand_load_rejects_out_of_range_factor() -> None:
    model = DemandLoadModel()
    bad = DischargeRequest(
        claim_kind=DEMAND_LOAD_KIND,
        limit=1000.0,
        inputs={"connected_kva": _iv(100.0), "demand_factor": _iv(1.5)},
    )
    assert model.estimate(bad).is_err


def test_demand_load_named_absence_refuses_without_default() -> None:
    """A request missing ``demand_factor`` REFUSES by name (D250.3) --
    the shared discharge path never substitutes a typical factor."""
    model = DemandLoadModel()
    request = DischargeRequest(
        claim_kind=DEMAND_LOAD_KIND,
        limit=1000.0,
        inputs={"connected_kva": _iv(100.0)},
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_err
    err = outcome.danger_err
    assert isinstance(err, InputError)
    assert err.missing == ("demand_factor",)


# ---------------------------------------------------------------------------
# 2. Voltage drop.
# ---------------------------------------------------------------------------


def test_voltage_drop_matches_closed_form_at_pinned_point() -> None:
    model = VoltageDropModel()
    request = DischargeRequest(
        claim_kind=VOLTAGE_DROP_KIND,
        limit=10.0,
        inputs={
            "current_a": _iv(100.0),
            "length_m": _iv(50.0),
            "resistance_ohm_per_m": _iv(0.0005),
            "reactance_ohm_per_m": _iv(0.0002),
            "power_factor": _iv(0.9),
            "phase_multiplier": _iv(1.7320508075688772),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    import math

    sin_phi = math.sqrt(1.0 - 0.9**2)
    expected = 1.7320508075688772 * 100.0 * 50.0 * (0.0005 * 0.9 + 0.0002 * sin_phi)
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_voltage_drop_rejects_bad_domain() -> None:
    model = VoltageDropModel()

    def _req(**overrides: Interval) -> DischargeRequest:
        base = {
            "current_a": _iv(10.0),
            "length_m": _iv(10.0),
            "resistance_ohm_per_m": _iv(0.001),
            "reactance_ohm_per_m": _iv(0.001),
            "power_factor": _iv(0.9),
            "phase_multiplier": _iv(2.0),
        }
        base.update(overrides)
        return DischargeRequest(claim_kind=VOLTAGE_DROP_KIND, limit=1.0, inputs=base)

    assert model.estimate(_req(power_factor=_iv(1.2))).is_err
    assert model.estimate(_req(power_factor=_iv(0.0))).is_err
    assert model.estimate(_req(phase_multiplier=_iv(0.0))).is_err
    assert model.estimate(_req(current_a=_iv(-1.0))).is_err


# ---------------------------------------------------------------------------
# 3. Ampacity.
# ---------------------------------------------------------------------------


def test_ampacity_lower_bound_takes_minimum_corner() -> None:
    model = AmpacityModel()
    request = DischargeRequest(
        claim_kind=AMPACITY_KIND,
        limit=50.0,
        inputs={
            "base_ampacity_a": _iv((90.0, 100.0)),
            "temperature_correction_factor": _iv((0.87, 0.91)),
            "fill_adjustment_factor": _iv((0.8, 1.0)),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(90.0 * 0.87 * 0.8)
    assert not model.signature.sense.upper


def test_ampacity_named_absence_refuses_without_default() -> None:
    """No table row (``base_ampacity_a``) declared -> named refusal."""
    model = AmpacityModel()
    request = DischargeRequest(
        claim_kind=AMPACITY_KIND,
        limit=50.0,
        inputs={
            "temperature_correction_factor": _iv(0.9),
            "fill_adjustment_factor": _iv(0.8),
        },
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_err
    err = outcome.danger_err
    assert isinstance(err, InputError)
    assert err.missing == ("base_ampacity_a",)


# ---------------------------------------------------------------------------
# 4. Transformer fault-current screening.
# ---------------------------------------------------------------------------


def test_fault_current_screening_matches_closed_form() -> None:
    model = TransformerFaultCurrentScreeningModel()
    request = DischargeRequest(
        claim_kind=FAULT_CURRENT_KIND,
        limit=1.0e6,
        inputs={
            "transformer_kva": _iv(500.0),
            "pct_z": _iv(5.75),
            "secondary_voltage_v": _iv(480.0),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    import math

    full_load = (500.0 * 1000.0) / (math.sqrt(3.0) * 480.0)
    expected = full_load / (5.75 / 100.0)
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_fault_current_pct_z_named_absence_refuses() -> None:
    """No nameplate %Z declared -> D250.3 named refusal, never a
    'typical' 5.75% substituted."""
    model = TransformerFaultCurrentScreeningModel()
    request = DischargeRequest(
        claim_kind=FAULT_CURRENT_KIND,
        limit=1.0e6,
        inputs={
            "transformer_kva": _iv(500.0),
            "secondary_voltage_v": _iv(480.0),
        },
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_err
    err = outcome.danger_err
    assert isinstance(err, InputError)
    assert err.missing == ("pct_z",)


def test_fault_current_citation_names_screening_not_certified_study() -> None:
    citation = TransformerFaultCurrentScreeningModel().citation
    assert citation is not None
    assert "SCREENING" in citation
    assert "IEEE Std 242" in citation


# ---------------------------------------------------------------------------
# 5. Motor starting voltage dip.
# ---------------------------------------------------------------------------


def test_motor_start_dip_worst_corner() -> None:
    model = MotorStartDipModel()
    request = DischargeRequest(
        claim_kind=MOTOR_START_DIP_KIND,
        limit=15.0,
        inputs={
            "motor_locked_rotor_kva": _iv((200.0, 220.0)),
            "source_available_kva": _iv((1000.0, 1200.0)),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    expected = 100.0 * 220.0 / (220.0 + 1000.0)
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_motor_start_dip_named_absence_refuses_without_code_letter_default() -> None:
    """No declared locked-rotor kVA (no code letter on the nameplate) ->
    named refusal, never a 'typical' code-letter substitution."""
    model = MotorStartDipModel()
    request = DischargeRequest(
        claim_kind=MOTOR_START_DIP_KIND,
        limit=15.0,
        inputs={"source_available_kva": _iv(1000.0)},
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_err
    err = outcome.danger_err
    assert isinstance(err, InputError)
    assert err.missing == ("motor_locked_rotor_kva",)


# ---------------------------------------------------------------------------
# 6. Transformer loading + power factor.
# ---------------------------------------------------------------------------


def test_transformer_loading_worst_corner() -> None:
    model = TransformerLoadingModel()
    request = DischargeRequest(
        claim_kind=TRANSFORMER_LOADING_KIND,
        limit=100.0,
        inputs={"actual_kva": _iv((400.0, 420.0)), "rated_kva": _iv((490.0, 500.0))},
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(100.0 * 420.0 / 490.0)


def test_power_factor_worst_corner_and_lower_bound_sense() -> None:
    model = PowerFactorModel()
    request = DischargeRequest(
        claim_kind=POWER_FACTOR_KIND,
        limit=0.9,
        inputs={
            "real_power_kw": _iv((80.0, 90.0)),
            "apparent_power_kva": _iv((95.0, 100.0)),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(80.0 / 100.0)
    assert not model.signature.sense.upper


# ---------------------------------------------------------------------------
# Registry pickup + discharge/violated verdicts.
# ---------------------------------------------------------------------------


def test_registry_discharges_and_violates_demand_load() -> None:
    registry = default_registry()
    request = DischargeRequest(
        claim_kind=DEMAND_LOAD_KIND,
        limit=100.0,
        inputs={"connected_kva": _iv(100.0), "demand_factor": _iv(0.7)},
    )
    ok = registry.discharge(request)
    assert ok.status.value == "discharged", ok

    over = DischargeRequest(
        claim_kind=DEMAND_LOAD_KIND,
        limit=50.0,
        inputs={"connected_kva": _iv(100.0), "demand_factor": _iv(0.7)},
    )
    violated = registry.discharge(over)
    assert violated.status.value == "violated", violated


def test_every_power_model_has_a_real_citation() -> None:
    """D250.1: an uncited power model may not ship -- every model in
    this pack renders a non-``None`` citation through the registry's
    citation accessor (the calc book's rendering channel, D221)."""
    registry = default_registry()
    citations = registry.citations()
    power_models = (
        DemandLoadModel(),
        VoltageDropModel(),
        AmpacityModel(),
        TransformerFaultCurrentScreeningModel(),
        MotorStartDipModel(),
        TransformerLoadingModel(),
        PowerFactorModel(),
        WorkingClearanceModel(),
    )
    for model in power_models:
        assert citations.get(model.model_id) == model.citation
        assert model.citation, f"{model.model_id} has no citation"


# ---------------------------------------------------------------------------
# 7. Working clearance (WO-136/D249/AD-42): the calcite tandem's new
# claim kind -- the first whose SUBJECT is electrical and whose
# EVIDENCE is architectural.
# ---------------------------------------------------------------------------


def test_working_clearance_available_equals_room_minus_footprint() -> None:
    model = WorkingClearanceModel()
    request = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(3.0), "footprint_dim_m": _iv(1.2)},
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(1.8)
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_ok
    assert outcome.danger_ok.status.value == "discharged"


def test_working_clearance_worst_corner_is_min_room_max_footprint() -> None:
    """INV-9: available clearance shrinks with a SMALLER room dimension
    and a LARGER footprint, so the worst corner is ``room.lo -
    footprint.hi`` even when both inputs are given as intervals."""
    model = WorkingClearanceModel()
    request = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={
            "room_dim_m": _iv((2.8, 3.2)),
            "footprint_dim_m": _iv((1.0, 1.2)),
        },
    )
    prediction = model.estimate(request)
    assert prediction.is_ok, prediction
    assert prediction.danger_ok.value == pytest.approx(2.8 - 1.2)


def test_working_clearance_violates_when_room_is_undersized() -> None:
    model = WorkingClearanceModel()
    request = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(1.5), "footprint_dim_m": _iv(1.2)},
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_ok
    assert outcome.danger_ok.status.value == "violated"


def test_working_clearance_rejects_bad_domain() -> None:
    model = WorkingClearanceModel()
    non_positive_room = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(0.0), "footprint_dim_m": _iv(0.5)},
    )
    assert model.estimate(non_positive_room).is_err

    negative_footprint = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(3.0), "footprint_dim_m": _iv(-0.1)},
    )
    assert model.estimate(negative_footprint).is_err


def test_working_clearance_named_absence_refuses_without_default() -> None:
    """D250.3: a request missing ``footprint_dim_m`` refuses by name --
    never a synthesized "typical" apparatus footprint."""
    model = WorkingClearanceModel()
    request = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(3.0)},
    )
    outcome = model.discharge(request, registry_version="test")
    assert outcome.is_err
    err = outcome.danger_err
    assert isinstance(err, InputError)
    assert err.missing == ("footprint_dim_m",)


def test_working_clearance_citation_is_nec_110_26() -> None:
    model = WorkingClearanceModel()
    assert model.citation is not None
    assert "110.26" in model.citation
    assert "NEC" in model.citation


def test_working_clearance_registered_in_default_registry() -> None:
    registry = default_registry()
    request = DischargeRequest(
        claim_kind=WORKING_CLEARANCE_KIND,
        limit=1.0,
        inputs={"room_dim_m": _iv(3.0), "footprint_dim_m": _iv(1.2)},
    )
    outcome = registry.discharge(request)
    assert outcome.status.value == "discharged", outcome


# ---------------------------------------------------------------------------
# D250.4: arc flash (and the rest of the certified tier) cannot reach
# release trust through a lithos built-in -- this is the WO's most
# important test.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "certified_tier_kind",
    [
        "elec.power.arc_flash",
        "elec.power.coordination",
        "elec.power.harmonics",
        "elec.power.fault_current_certified",
    ],
)
def test_certified_tier_claims_have_no_lithos_built_in(
    certified_tier_kind: str,
) -> None:
    """No model registered by this pack (or anywhere in the default
    built-in registry) discharges arc-flash/coordination/harmonics --
    those are feldspar's certified-solver claims (AD-42, charter 43
    sec. 3). A claim of this kind against the default registry yields
    the honest ``harness.no_model`` indeterminate, never a built-in
    screening estimate wearing a certified study's clothes (D250.4)."""
    registry = default_registry()
    request = DischargeRequest(
        claim_kind=certified_tier_kind,
        limit=1.0,
        inputs={},
    )
    outcome = registry.discharge(request)
    assert outcome.status.value == "indeterminate", outcome
    assert outcome.model_id == "harness.no_model"


def test_arc_flash_kind_is_not_among_any_registered_power_model_kind() -> None:
    """Belt-and-suspenders: enumerate every registered model's claim
    kind and assert none of them is the arc-flash (or coordination/
    harmonics) kind -- the boundary rule (AD-37/AD-42) holds by
    construction, not merely by an empty-registry accident."""
    registry = default_registry()
    kinds = {model.signature.claim_kind for model in registry.all_models()}
    assert "elec.power.arc_flash" not in kinds
    assert "elec.power.coordination" not in kinds
    assert "elec.power.harmonics" not in kinds
