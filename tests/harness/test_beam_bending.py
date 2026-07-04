"""The Euler-Bernoulli cantilever beam-bending model pack.

Covers: a known-answer numeric check against the hand-derived tip
deflection, the discharge/violated verdicts, corner conservatism
(INV-9), the domain guard, and determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.beam_bending import CLAIM_KIND, BeamBendingModel

# A representative steel cantilever point (SI: N, m, Pa, m**4).
_F, _L, _E, _I = 200.0, 0.05, 200e9, 1.0e-8
_LIMIT = 2.0e-4  # 0.2 mm tip deflection limit (sheet_bracket sag claim)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "force": Interval.point(_F),
            "length": Interval.point(_L),
            "e_modulus": Interval.point(_E),
            "i_area": Interval.point(_I),
        },
    )


def _hand_deflection(f: float, ell: float, e_mod: float, inertia: float) -> float:
    """Cantilever end-load tip deflection, recomputed independently."""
    return f * ell**3 / (3.0 * e_mod * inertia)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = BeamBendingModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_deflection(_F, _L, _E, _I)
    # 200*(0.05**3)/(3*200e9*1e-8) = 4.1666...e-6 m.
    assert abs(prediction.danger_ok.value - expected) < 1e-18
    assert abs(expected - 4.166666666666667e-6) < 1e-18


def test_discharged_with_healthy_margin() -> None:
    """~4.2 um deflection + 5% eps is well under the 0.2 mm limit."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "beam_cantilever_deflection_eb@1"


def test_violated_when_limit_below_deflection() -> None:
    """A tighter-than-deflection limit is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=1.0e-6))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the reported deflection (INV-9)."""
    point = BeamBendingModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst deflection: max force and length, min E and I.
            "force": Interval(lo=_F, hi=400.0),
            "length": Interval(lo=_L, hi=0.08),
            "e_modulus": Interval(lo=_E, hi=210e9),
            "i_area": Interval(lo=_I, hi=2.0e-8),
        },
    )
    worst = BeamBendingModel().estimate(boxed).danger_ok.value
    assert worst >= point
    assert abs(worst - _hand_deflection(400.0, 0.08, _E, _I)) < 1e-18


def test_out_of_domain_non_positive_geometry() -> None:
    """A zero second moment of area is degenerate -> domain / indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "force": Interval.point(_F),
                "length": Interval.point(_L),
                "e_modulus": Interval.point(_E),
                "i_area": Interval.point(0.0),
            }
        }
    )
    assert BeamBendingModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
