"""The beam demand/capacity utilization model pack (WO-48 slice C).

Covers: a known-answer numeric check against the hand-derived
interaction ratio, the discharge/violated verdicts, corner
conservatism (INV-9), the domain guard, and determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.beam_utilization import CLAIM_KIND, BeamUtilizationModel

# A representative W-shape steel member (SI: N*m, N, m**3, m**2, Pa).
_M, _P, _Z, _A, _FY = 40_000.0, 5_000.0, 8.0e-4, 1.0e-2, 345.0e6
_LIMIT = 1.0


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "moment_demand": Interval.point(_M),
            "axial_demand": Interval.point(_P),
            "section_modulus": Interval.point(_Z),
            "area": Interval.point(_A),
            "fy": Interval.point(_FY),
        },
    )


def _hand_utilization(m: float, p: float, z: float, a: float, fy: float) -> float:
    """Combined bending + axial utilization, recomputed independently."""
    return abs(m) / (z * fy) + abs(p) / (a * fy)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = BeamUtilizationModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_utilization(_M, _P, _Z, _A, _FY)
    assert abs(prediction.danger_ok.value - expected) < 1e-12


def test_discharged_with_healthy_margin() -> None:
    """~0.16 utilization + 8% eps is well under the 1.0 limit."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "beam_utilization_interaction@1"


def test_violated_when_limit_below_utilization() -> None:
    """A tighter-than-utilization limit is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=0.05))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the reported utilization (INV-9)."""
    point = BeamUtilizationModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst utilization: max demand, min section/material capacity.
            "moment_demand": Interval(lo=_M, hi=60_000.0),
            "axial_demand": Interval(lo=_P, hi=8_000.0),
            "section_modulus": Interval(lo=6.0e-4, hi=_Z),
            "area": Interval(lo=8.0e-3, hi=_A),
            "fy": Interval(lo=250.0e6, hi=_FY),
        },
    )
    worst = BeamUtilizationModel().estimate(boxed).danger_ok.value
    assert worst >= point
    expected_worst = _hand_utilization(60_000.0, 8_000.0, 6.0e-4, 8.0e-3, 250.0e6)
    assert abs(worst - expected_worst) < 1e-12


def test_out_of_domain_non_positive_section() -> None:
    """A zero section modulus is degenerate -> domain / indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "moment_demand": Interval.point(_M),
                "axial_demand": Interval.point(_P),
                "section_modulus": Interval.point(0.0),
                "area": Interval.point(_A),
                "fy": Interval.point(_FY),
            }
        }
    )
    assert BeamUtilizationModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
