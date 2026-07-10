"""The rolling-bearing basic-L10 rating-life model (ISO 281:2007).

Covers: a known-answer numeric check against the hand-derived L10h, the
discharge/violated verdicts, corner conservatism (INV-9, worst =
minimum for a lower-bound claim), the domain guard, and determinism
(INV-10) -- same shape as `test_bolted_joint.py`.
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.bearing_life import CLAIM_KIND, BearingL10HoursModel

# A representative deep-groove ball bearing point (SI: N, N, rpm, --).
_C, _P, _N, _P_EXP = 60_000.0, 6_200.0, 800.0, 3.0
_LIMIT = 4_000.0  # required L10h (hours)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "c_rating": Interval.point(_C),
            "p_load": Interval.point(_P),
            "speed_rpm": Interval.point(_N),
            "p_exponent": Interval.point(_P_EXP),
        },
    )


def _hand_l10h(c: float, p: float, n: float, p_exp: float) -> float:
    """ISO 281:2007 basic L10/L10h, recomputed independently of the model."""
    l10_million_revs = (c / p) ** p_exp
    return l10_million_revs * 1.0e6 / (60.0 * n)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived L10h to f64 precision."""
    prediction = BearingL10HoursModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_l10h(_C, _P, _N, _P_EXP)
    assert abs(prediction.danger_ok.value - expected) < 1e-6
    assert expected > 18_000.0  # sanity: comfortably above the 4000h demand


def test_discharged_with_healthy_margin() -> None:
    """L10h less the 50% a_iso-standin eps still clears the 4000h demand."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "bearing_basic_rating_life_l10h@1"


def test_violated_when_demand_exceeds_life() -> None:
    """A life demand above the (haircut) L10h is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=100_000.0))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs never raises the reported L10h (INV-9)."""
    point = BearingL10HoursModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst L10h: min C, max P, max speed.
            "c_rating": Interval(lo=50_000.0, hi=_C),
            "p_load": Interval(lo=_P, hi=7_000.0),
            "speed_rpm": Interval(lo=_N, hi=900.0),
            "p_exponent": Interval.point(_P_EXP),
        },
    )
    worst = BearingL10HoursModel().estimate(boxed).danger_ok.value
    assert worst <= point
    assert abs(worst - _hand_l10h(50_000.0, 7_000.0, 900.0, _P_EXP)) < 1e-6


def test_out_of_domain_non_positive_rating() -> None:
    """Zero dynamic load rating is not a real bearing -> domain error."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "c_rating": Interval.point(0.0),
                "p_load": Interval.point(_P),
                "speed_rpm": Interval.point(_N),
                "p_exponent": Interval.point(_P_EXP),
            }
        }
    )
    assert BearingL10HoursModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
