"""The footing bearing-pressure model pack (cycle 33/D196).

Covers: the discharge verdict (pressure clears the allowable), the
violated verdict (pressure exceeds it), the upper-bound sense (the
conservative corner is max reaction / min area), the domain guards,
registry pickup, and determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.bearing_pressure import CLAIM_KIND, BearingPressureModel


def _request(
    reaction: float | tuple[float, float] = 90000.0,
    area: float | tuple[float, float] = 1.8,
    limit: float = 120000.0,
) -> DischargeRequest:
    r_lo, r_hi = reaction if isinstance(reaction, tuple) else (reaction, reaction)
    a_lo, a_hi = area if isinstance(area, tuple) else (area, area)
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "reaction_n": Interval(lo=r_lo, hi=r_hi),
            "area_m2": Interval(lo=a_lo, hi=a_hi),
        },
    )


def test_pressure_is_reaction_over_area() -> None:
    """The predicted value is exact reaction/area division (eps 0)."""
    prediction = BearingPressureModel().estimate(_request(reaction=90000.0, area=1.8))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == 50000.0
    assert pred.eps == 0.0
    assert pred.in_domain


def test_upper_bound_sense_takes_the_worst_corner() -> None:
    """An interval-valued reaction/area predicts MAX reaction / MIN area
    (the conservative direction for a `<= allowable` claim, INV-9)."""
    prediction = BearingPressureModel().estimate(
        _request(reaction=(80000.0, 100000.0), area=(1.6, 2.0))
    )
    assert prediction.is_ok
    assert prediction.danger_ok.value == 100000.0 / 1.6


def test_signature_is_an_upper_bound_over_reaction_and_area() -> None:
    """The sense is `upper` (larger pressure is worse) over the pair."""
    sig = BearingPressureModel().signature
    assert sig.sense.upper
    assert set(sig.inputs) == {"reaction_n", "area_m2"}
    assert sig.claim_kind == CLAIM_KIND


def test_domain_guards_reject_nonpositive_area_and_negative_reaction() -> None:
    """A zero/negative area is a domain error (no footing has zero
    bearing area), as is a negative reaction."""
    model = BearingPressureModel()
    assert model.estimate(_request(area=0.0)).is_err
    assert model.estimate(_request(area=-1.0)).is_err
    assert model.estimate(_request(reaction=-1.0)).is_err


def test_registry_discharges_and_violates_end_to_end() -> None:
    """The default registry routes `civil.bearing_pressure` here: 50kPa
    predicted vs a 120kPa allowable discharges; the same reaction over a
    much smaller area violates."""
    registry = default_registry()
    ok = registry.discharge(_request(reaction=90000.0, area=1.8, limit=120000.0))
    assert ok.status.value == "discharged", ok
    over = registry.discharge(_request(reaction=90000.0, area=0.3, limit=120000.0))
    assert over.status.value == "violated", over


def test_determinism_same_inputs_same_prediction() -> None:
    """Two identical requests predict identically (INV-10)."""
    a = BearingPressureModel().estimate(_request()).danger_ok
    b = BearingPressureModel().estimate(_request()).danger_ok
    assert (a.value, a.eps, a.coverage) == (b.value, b.eps, b.coverage)
