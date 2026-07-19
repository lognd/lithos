"""`NpshMarginModel` calibration + domain tests (WO-110 deliverable 4).

Calibration pins the NPSH energy balance against a hand-computed
worked example over PUBLISHED property data (water at 20 C: vapor
pressure 2339 Pa, density 998 kg/m3 -- White, Fluid Mechanics, 8th
ed., property table A.5's 20 C row; supply at standard atmosphere
101325 Pa; standard gravity 9.80665 m/s^2 exact):

    NPSHa  = (101325 - 2339) / (998 * 9.80665) - 3.0 - 0.8
           = 98986 / 9787.04 - 3.8
           = 10.1140... - 3.8 = 6.3140... m
    margin = NPSHa - 4.0 = 2.3140... m
"""

from __future__ import annotations

import pytest
from regolith.harness.errors import DomainError
from regolith.harness.model import DischargeRequest
from regolith.harness.models.npsh_margin import CLAIM_KIND, INPUTS, NpshMarginModel
from regolith.harness.quantity import Interval, bits_to_f64

_WATER_20C = {
    "p_supply_pa": 101325.0,
    "p_vapor_pa": 2339.0,
    "density_kgm3": 998.0,
    "z_static_m": -3.0,
    "h_friction_m": 0.8,
    "npshr_m": 4.0,
}


def _request(limit: float = 1.5, **overrides: float) -> DischargeRequest:
    values = {**_WATER_20C, **overrides}
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={k: Interval(lo=v, hi=v) for k, v in values.items()},
    )


def test_calibration_water_20c_suction_lift() -> None:
    """The worked example above: margin = 2.3140 m (4 significant
    figures by hand)."""
    model = NpshMarginModel()
    prediction = model.estimate(_request())
    assert prediction.is_ok
    expected = (101325.0 - 2339.0) / (998.0 * 9.80665) - 3.0 - 0.8 - 4.0
    assert prediction.danger_ok.value == pytest.approx(expected)
    assert prediction.danger_ok.value == pytest.approx(2.314, abs=5e-4)
    assert prediction.danger_ok.eps == 0.0


def test_lower_bound_discharges_and_starved_violates() -> None:
    """margin 2.314 m > 1.5 m discharges; a 7 m lift flips it to
    -1.686 m, a genuine violation."""
    model = NpshMarginModel()
    good = model.discharge(_request(), registry_version="test")
    assert good.is_ok and good.danger_ok.status.value == "discharged"
    starved = model.discharge(_request(z_static_m=-7.0), registry_version="test")
    assert starved.is_ok and starved.danger_ok.status.value == "violated"
    assert bits_to_f64(starved.danger_ok.value_bits) == pytest.approx(
        2.314 - 4.0, abs=5e-4
    )


def test_interval_corners_take_the_worst_margin() -> None:
    """An uncertain friction loss [0.8, 1.8] m charges the WORST corner
    (INV-9): margin drops by exactly the extra metre."""
    model = NpshMarginModel()
    point = model.estimate(_request()).danger_ok.value
    boxed = _request()
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=1.5,
        inputs={
            **boxed.inputs,
            "h_friction_m": Interval(lo=0.8, hi=1.8),
        },
    )
    worst = model.estimate(boxed)
    assert worst.is_ok
    assert worst.danger_ok.value == pytest.approx(point - 1.0)


def test_domain_guards_are_error_values() -> None:
    model = NpshMarginModel()
    bad_density = model.estimate(_request(density_kgm3=0.0))
    assert bad_density.is_err
    gauge_pressure = model.estimate(_request(p_supply_pa=0.0))
    assert gauge_pressure.is_err
    assert isinstance(gauge_pressure.danger_err, DomainError)
    assert "ABSOLUTE" in gauge_pressure.danger_err.message


def test_inputs_export_matches_signature() -> None:
    """The public INPUTS tuple (the translate router's deferral naming)
    is the signature's own inputs, verbatim."""
    assert NpshMarginModel().signature.inputs == INPUTS
