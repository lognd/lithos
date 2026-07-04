"""The sheet-metal minimum-bend-radius DFM model pack.

Covers: a known-answer numeric check against the hand-derived minimum
inside bend radius, the discharge/violated verdicts, corner conservatism
(INV-9, worst = maximum for an upper-bound claim), the domain guard, and
determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.sheet_bend import CLAIM_KIND, SheetBendModel

# A representative 1.5 mm laser-cut sheet point (SI: m, dimensionless).
_T, _RATIO = 0.0015, 1.6
# The design's specified bend radius (the limit): 3.0 mm clears the min.
_LIMIT = 0.003


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "thickness": Interval.point(_T),
            "ratio": Interval.point(_RATIO),
        },
    )


def _hand_min_radius(t: float, k: float) -> float:
    """Minimum inside bend radius, recomputed independently of the model."""
    return k * t


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = SheetBendModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_min_radius(_T, _RATIO)
    # 1.6 * 1.5 mm = 2.4 mm -- the corpus's resolved min_bend_radius.
    assert abs(prediction.danger_ok.value - expected) < 1e-15
    assert abs(expected - 0.0024) < 1e-15


def test_discharged_when_specified_radius_clears_min() -> None:
    """2.4 mm min + 10% eps is under the 3.0 mm specified radius."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "sheet_min_bend_radius@1"


def test_violated_when_specified_radius_below_min() -> None:
    """A specified radius below the manufacturable min is a violation."""
    evidence = default_registry().discharge(_point_request(limit=0.002))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the required min (INV-9)."""
    point = SheetBendModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst (largest) min radius: max gauge and max ratio.
            "thickness": Interval(lo=_T, hi=0.002),
            "ratio": Interval(lo=_RATIO, hi=2.0),
        },
    )
    worst = SheetBendModel().estimate(boxed).danger_ok.value
    assert worst >= point
    assert abs(worst - _hand_min_radius(0.002, 2.0)) < 1e-15


def test_out_of_domain_non_positive_thickness() -> None:
    """A zero gauge is degenerate -> domain error / indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "thickness": Interval.point(0.0),
                "ratio": Interval.point(_RATIO),
            }
        }
    )
    assert SheetBendModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
