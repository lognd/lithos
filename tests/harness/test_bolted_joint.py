"""The bolted-joint preload model pack (VDI 2230 load-sharing).

Covers: a known-answer numeric check against the hand-derived residual
clamp force, the discharge/violated verdicts, corner conservatism
(INV-9, worst = minimum for a lower-bound claim), the domain guard, and
determinism (INV-10).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.bolted_joint import CLAIM_KIND, BoltedJointModel

# A representative M-bolt flange point (SI: N, N, N/m, N/m).
_FM, _FA, _KB, _KC = 10_000.0, 4_000.0, 1.0e8, 4.0e8
_LIMIT = 2_000.0  # required residual clamp force F_Kreq (N)


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "f_preload": Interval.point(_FM),
            "f_external": Interval.point(_FA),
            "k_bolt": Interval.point(_KB),
            "k_clamp": Interval.point(_KC),
        },
    )


def _hand_residual(f_m: float, f_a: float, kb: float, kc: float) -> float:
    """VDI 2230 residual clamp force, recomputed independently of the model."""
    phi = kb / (kb + kc)
    return f_m - (1.0 - phi) * f_a


def test_known_answer_value() -> None:
    """Model value matches the hand-derived residual clamp to f64 precision."""
    prediction = BoltedJointModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_residual(_FM, _FA, _KB, _KC)
    # phi = 0.2 -> F_KR = 10000 - 0.8*4000 = 6800 N.
    assert abs(prediction.danger_ok.value - expected) < 1e-9
    assert abs(expected - 6800.0) < 1e-9


def test_discharged_with_healthy_margin() -> None:
    """6800 N residual less 10% embedding eps still clears the 2 kN demand."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "bolted_joint_separation_vdi2230@1"


def test_violated_when_demand_exceeds_residual() -> None:
    """A clamp demand above the residual is a violation, not indeterminate."""
    evidence = default_registry().discharge(_point_request(limit=7_000.0))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening inputs never raises the reported residual clamp (INV-9)."""
    point = BoltedJointModel().estimate(_point_request()).danger_ok.value
    boxed = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_LIMIT,
        inputs={
            # Worst residual: min preload, max external load.
            "f_preload": Interval(lo=8_000.0, hi=_FM),
            "f_external": Interval(lo=_FA, hi=6_000.0),
            "k_bolt": Interval.point(_KB),
            "k_clamp": Interval.point(_KC),
        },
    )
    worst = BoltedJointModel().estimate(boxed).danger_ok.value
    assert worst <= point
    # Independently: the worst corner is min preload, max external load.
    assert abs(worst - _hand_residual(8_000.0, 6_000.0, _KB, _KC)) < 1e-9


def test_out_of_domain_non_positive_preload() -> None:
    """Zero preload is not a clamped joint -> domain error / indeterminate."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                "f_preload": Interval.point(0.0),
                "f_external": Interval.point(_FA),
                "k_bolt": Interval.point(_KB),
                "k_clamp": Interval.point(_KC),
            }
        }
    )
    assert BoltedJointModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
