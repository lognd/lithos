"""The thick-walled cylinder (Lame) bore-stress model pack.

Covers: a known-answer numeric check against the hand-derived peak
von-Mises bore stress, the discharge/violated verdicts, corner
conservatism (INV-9, worst = maximum for an upper-bound claim), the
domain guard, and determinism (INV-10).
"""

from __future__ import annotations

import math

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.lame_cylinder import CLAIM_KIND, LameCylinderModel

# A representative combustion-chamber wall point (SI: Pa, m, m).
_P, _A, _B = 3.0e6, 0.01, 0.02
_LIMIT = 1.45e8  # sigma_y/2 for AISI 316 (~290 MPa yield), the hoop limit


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "pressure": Interval.point(_P),
            "r_inner": Interval.point(_A),
            "r_outer": Interval.point(_B),
        },
    )


def _hand_von_mises(p: float, a: float, b: float) -> float:
    """Lame bore von-Mises stress, recomputed independently of the model."""
    sigma_theta = p * (b**2 + a**2) / (b**2 - a**2)
    sigma_r = -p
    return math.sqrt(sigma_theta**2 - sigma_theta * sigma_r + sigma_r**2)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = LameCylinderModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_von_mises(_P, _A, _B)
    # sigma_theta = 3e6*(5e-4/3e-4) = 5e6; sigma_r = -3e6; sigma_z = 0.
    # vm = sqrt(5e6^2 - 5e6*(-3e6) + 3e6^2) = sqrt(49e12) = 7e6 Pa.
    assert abs(prediction.danger_ok.value - expected) < 1e-3
    assert abs(expected - 7.0e6) < 1e-3


def test_discharged_with_healthy_margin() -> None:
    """7 MPa bore stress + 5% eps is well under the 145 MPa limit."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "lame_cylinder_bore_stress@1"


def test_violated_when_limit_below_stress() -> None:
    """A limit below the bore stress is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=5.0e6))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the reported stress (INV-9)."""
    point = LameCylinderModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst stress: max pressure, max inner radius, min outer radius
            # (the thinnest, most-pressurised wall).
            "pressure": Interval(lo=_P, hi=4.0e6),
            "r_inner": Interval(lo=_A, hi=0.012),
            "r_outer": Interval(lo=_B, hi=0.025),
        },
    )
    worst = LameCylinderModel().estimate(boxed).danger_ok.value
    assert worst >= point
    assert abs(worst - _hand_von_mises(4.0e6, 0.012, _B)) < 1e-3


def test_out_of_domain_wall_not_thick() -> None:
    """An outer radius not above the inner radius is degenerate -> indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "pressure": Interval.point(_P),
                "r_inner": Interval.point(_A),
                "r_outer": Interval.point(_A),
            }
        }
    )
    assert LameCylinderModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
