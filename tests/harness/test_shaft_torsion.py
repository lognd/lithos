"""`ShaftTorsionModel` calibration + domain tests (WO-110 deliverable 3).

Calibration pins theta = T L / (G J) against a hand-computed worked
example over published property data: a 25 mm carbon-steel shaft,
G = 79.3 GPa (Shigley's Mechanical Engineering Design, 10th ed.,
table A-5), J = pi d^4 / 32 = 3.8350e-8 m^4 (hand-derived), T = 100
N*m, L = 1 m:

    theta = 100 * 1.0 / (79.3e9 * 3.8350e-8) = 0.032879... rad
"""

from __future__ import annotations

import math

import pytest
from regolith.harness.model import DischargeRequest
from regolith.harness.models.shaft_torsion import CLAIM_KIND, INPUTS, ShaftTorsionModel
from regolith.harness.quantity import Interval

_J_25MM = math.pi * 0.025**4 / 32.0

_STEEL_SHAFT = {
    "torque_nm": 100.0,
    "length_m": 1.0,
    "g_modulus_pa": 79.3e9,
    "j_torsion_m4": _J_25MM,
}


def _request(limit: float = 0.05, **overrides: float) -> DischargeRequest:
    values = {**_STEEL_SHAFT, **overrides}
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={k: Interval(lo=v, hi=v) for k, v in values.items()},
    )


def test_calibration_25mm_steel_shaft() -> None:
    model = ShaftTorsionModel()
    prediction = model.estimate(_request())
    assert prediction.is_ok
    expected = 100.0 * 1.0 / (79.3e9 * _J_25MM)
    assert prediction.danger_ok.value == pytest.approx(expected)
    assert prediction.danger_ok.value == pytest.approx(0.03288, abs=5e-5)
    assert prediction.danger_ok.eps == 0.0


def test_upper_bound_discharges_and_tight_budget_violates() -> None:
    model = ShaftTorsionModel()
    ok = model.discharge(_request(limit=0.05), registry_version="test")
    assert ok.is_ok and ok.danger_ok.status.value == "discharged"
    tight = model.discharge(_request(limit=0.01), registry_version="test")
    assert tight.is_ok and tight.danger_ok.status.value == "violated"


def test_interval_corners_take_the_worst_twist() -> None:
    """An uncertain torque [100, 200] N*m doubles the worst-corner
    twist (INV-9: max over corners)."""
    model = ShaftTorsionModel()
    point = model.estimate(_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=0.05,
        inputs={
            **_request().inputs,
            "torque_nm": Interval(lo=100.0, hi=200.0),
        },
    )
    worst = model.estimate(boxed)
    assert worst.is_ok
    assert worst.danger_ok.value == pytest.approx(2.0 * point)


def test_domain_guards_are_error_values() -> None:
    model = ShaftTorsionModel()
    assert model.estimate(_request(g_modulus_pa=0.0)).is_err
    assert model.estimate(_request(torque_nm=-1.0)).is_err


def test_inputs_export_matches_signature() -> None:
    assert ShaftTorsionModel().signature.inputs == INPUTS
