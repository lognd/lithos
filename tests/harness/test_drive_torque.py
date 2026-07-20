"""The ballscrew/leadscrew drive-torque model (motor reflected-load check).

Covers: a known-answer numeric check against a hand-derived torque,
discharge/violated verdicts, corner conservatism (INV-9, worst =
maximum torque for an upper-bound claim), the domain guards, and
determinism (INV-10) -- same shape as `test_bearing_life.py`.
"""

from __future__ import annotations

import math

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.drive_torque import CLAIM_KIND, DriveTorqueModel

# A representative preloaded-ballscrew point (SI: N, m, --).
_FORCE, _LEAD, _ETA = 800.0, 0.005, 0.90
_LIMIT = 1.2  # required N*m headroom (0.6 * a 2.0 N*m motor's holding torque)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "axial_force_n": Interval.point(_FORCE),
            "lead_m": Interval.point(_LEAD),
            "efficiency": Interval.point(_ETA),
        },
    )


def _hand_torque(force: float, lead: float, eta: float, drag: float = 0.0) -> float:
    """Ballscrew driving torque, recomputed independently of the model."""
    return force * lead / (2.0 * math.pi * eta) + drag


def test_known_answer_value() -> None:
    """Model value matches the hand-derived drive torque to f64 precision."""
    prediction = DriveTorqueModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_torque(_FORCE, _LEAD, _ETA)
    assert abs(prediction.danger_ok.value - expected) < 1e-9
    assert expected < _LIMIT  # sanity: comfortably under the demand


def test_discharged_with_healthy_margin() -> None:
    """Torque well under the 0.6x holding-torque demand discharges."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "ballscrew_drive_torque@1"


def test_violated_when_demand_below_torque() -> None:
    """A torque cap below the computed drive torque is a violation."""
    point = DriveTorqueModel().estimate(_point_request()).danger_ok.value
    evidence = default_registry().discharge(_point_request(limit=point * 0.5))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening force/lead upward and efficiency downward never lowers torque (INV-9)."""
    point = DriveTorqueModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            "axial_force_n": Interval(lo=_FORCE, hi=1_000.0),
            "lead_m": Interval(lo=_LEAD, hi=0.006),
            "efficiency": Interval(lo=0.85, hi=_ETA),
        },
    )
    worst = DriveTorqueModel().estimate(boxed).danger_ok.value
    assert worst >= point
    assert abs(worst - _hand_torque(1_000.0, 0.006, 0.85)) < 1e-9


def test_preload_drag_torque_adds_directly() -> None:
    """An optional declared preload drag torque adds on top of the screw term."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                **_point_request().inputs,
                "preload_drag_torque_nm": Interval.point(0.05),
            }
        }
    )
    prediction = DriveTorqueModel().estimate(req)
    assert prediction.is_ok
    expected = _hand_torque(_FORCE, _LEAD, _ETA, drag=0.05)
    assert abs(prediction.danger_ok.value - expected) < 1e-9


def test_out_of_domain_zero_efficiency() -> None:
    """A zero (or out-of-range) efficiency is not a real screw -> domain error."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                **_point_request().inputs,
                "efficiency": Interval.point(0.0),
            }
        }
    )
    assert DriveTorqueModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
