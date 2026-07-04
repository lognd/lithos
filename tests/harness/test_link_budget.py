"""The RF link-budget model pack (Kestrel downlink margin).

Covers: a known-answer numeric check against the hand-derived dB margin,
the discharge/violated verdicts, corner conservatism (INV-9, worst =
minimum for a lower-bound claim), and determinism (INV-10).
"""

from __future__ import annotations

from rockhead.harness import DischargeRequest, Interval, default_registry
from rockhead.harness.models.link_budget import CLAIM_KIND, LinkBudgetModel

# A representative UHF downlink point (dB domain: dBm, dBi, dB, dBm).
_PA, _GAIN, _PL, _SENS = 30.0, 12.0, 140.0, -110.0
_LIMIT = 6.0  # the mission's demanded 6 dB link margin (kestrel require Link)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "pa_out": Interval.point(_PA),
            "gain": Interval.point(_GAIN),
            "path_loss": Interval.point(_PL),
            "sensitivity": Interval.point(_SENS),
        },
    )


def _hand_margin(pa: float, g: float, pl: float, sens: float) -> float:
    """Decibel link margin, recomputed independently of the model."""
    return (pa + g - pl) - sens


def test_known_answer_value() -> None:
    """Model value matches the hand-derived dB margin to f64 precision."""
    prediction = LinkBudgetModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_margin(_PA, _GAIN, _PL, _SENS)
    # P_rx = 30 + 12 - 140 = -98 dBm; margin = -98 - (-110) = 12 dB.
    assert abs(prediction.danger_ok.value - expected) < 1e-12
    assert abs(expected - 12.0) < 1e-12


def test_discharged_with_healthy_margin() -> None:
    """12 dB margin less the 2 dB impl-loss eps still clears the 6 dB demand."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "link_budget_margin_db@1"


def test_violated_when_demand_exceeds_margin() -> None:
    """A demand above the eps-charged margin is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=11.0))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs never raises the reported link margin (INV-9)."""
    point = LinkBudgetModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst margin: min power/gain, max path loss and threshold.
            "pa_out": Interval(lo=28.0, hi=_PA),
            "gain": Interval(lo=10.0, hi=_GAIN),
            "path_loss": Interval(lo=_PL, hi=150.0),
            "sensitivity": Interval(lo=_SENS, hi=-105.0),
        },
    )
    worst = LinkBudgetModel().estimate(boxed).danger_ok.value
    assert worst <= point
    assert abs(worst - _hand_margin(28.0, 10.0, 150.0, -105.0)) < 1e-12


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
