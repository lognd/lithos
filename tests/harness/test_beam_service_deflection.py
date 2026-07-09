"""The simple-span beam service-deflection model pack (WO-48 slice C).

Covers: a known-answer numeric check against the hand-derived midspan
deflection, the discharge/violated verdicts, corner conservatism
(INV-9), the domain guard, and determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.beam_service_deflection import (
    CLAIM_KIND,
    BeamServiceDeflectionModel,
)

# A representative steel girder under uniform load (SI: N/m, m, Pa, m**4).
_W, _L, _E, _I = 5_000.0, 12.0, 200e9, 5.0e-4
_LIMIT = _L / 360  # the corpus's span/360 serviceability form


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "w_load": Interval.point(_W),
            "length": Interval.point(_L),
            "e_modulus": Interval.point(_E),
            "i_area": Interval.point(_I),
        },
    )


def _hand_deflection(w: float, ell: float, e_mod: float, inertia: float) -> float:
    """Simple-span uniform-load midspan deflection, recomputed independently."""
    return 5.0 * w * ell**4 / (384.0 * e_mod * inertia)


def test_known_answer_value() -> None:
    """Model value matches the hand-derived closed form to f64 precision."""
    prediction = BeamServiceDeflectionModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_deflection(_W, _L, _E, _I)
    assert abs(prediction.danger_ok.value - expected) < 1e-15


def test_discharged_with_healthy_margin() -> None:
    """The reference case comfortably clears its span/360 limit."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "beam_simple_span_deflection_udl@1"


def test_violated_when_limit_below_deflection() -> None:
    """A tighter-than-deflection limit is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=1.0e-6))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs to a box never lowers the reported deflection (INV-9)."""
    point = BeamServiceDeflectionModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            "w_load": Interval(lo=_W, hi=8_000.0),
            "length": Interval(lo=_L, hi=14.0),
            "e_modulus": Interval(lo=_E, hi=210e9),
            "i_area": Interval(lo=4.0e-4, hi=_I),
        },
    )
    worst = BeamServiceDeflectionModel().estimate(boxed).danger_ok.value
    assert worst >= point
    assert abs(worst - _hand_deflection(8_000.0, 14.0, _E, 4.0e-4)) < 1e-12


def test_out_of_domain_non_positive_geometry() -> None:
    """A zero second moment of area is degenerate -> domain / indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "w_load": Interval.point(_W),
                "length": Interval.point(_L),
                "e_modulus": Interval.point(_E),
                "i_area": Interval.point(0.0),
            }
        }
    )
    assert BeamServiceDeflectionModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
