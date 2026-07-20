"""The Marin/Goodman/Basquin single-block Miner fatigue-damage model.

Covers: a known-answer numeric check against a hand-derived damage
fraction, discharge/violated verdicts, corner conservatism (INV-9,
worst = maximum damage for an upper-bound claim), the Goodman-line
domain guard, and determinism (INV-10) -- same shape as
`test_bearing_life.py`.
"""

from __future__ import annotations

import math

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.fatigue_damage import CLAIM_KIND, FatigueDamageModel

# A representative steel-shaft point (SI: Pa, Pa, --, Pa, Pa, six Marin
# factors --, --, --).
_SIGMA_A, _SIGMA_M = 120.0e6, 40.0e6
_KF_NOTCH = 1.6
_SUT, _SE_PRIME = 700.0e6, 350.0e6
_KA, _KB, _KC, _KD, _KE, _KF_MARIN = 0.80, 0.90, 1.0, 1.0, 0.90, 1.0
_F_FRAC = 0.85
_CYCLES_APPLIED = 5.0e5
_LIMIT = 1.0


def _point_request(limit: float = _LIMIT) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "sigma_a_pa": Interval.point(_SIGMA_A),
            "sigma_m_pa": Interval.point(_SIGMA_M),
            "kf_notch": Interval.point(_KF_NOTCH),
            "sut_pa": Interval.point(_SUT),
            "se_prime_pa": Interval.point(_SE_PRIME),
            "marin_ka": Interval.point(_KA),
            "marin_kb": Interval.point(_KB),
            "marin_kc": Interval.point(_KC),
            "marin_kd": Interval.point(_KD),
            "marin_ke": Interval.point(_KE),
            "marin_kf": Interval.point(_KF_MARIN),
            "basquin_f": Interval.point(_F_FRAC),
            "cycles_applied": Interval.point(_CYCLES_APPLIED),
        },
    )


def _hand_damage(
    sigma_a: float,
    sigma_m: float,
    kf_notch: float,
    sut: float,
    se_prime: float,
    ka: float,
    kb: float,
    kc: float,
    kd: float,
    ke: float,
    kf_marin: float,
    f_frac: float,
    cycles_applied: float,
) -> float:
    """Marin/Goodman/Basquin single-block Miner damage, hand-derived independently."""
    se = ka * kb * kc * kd * ke * kf_marin * se_prime
    sigma_ar = (kf_notch * sigma_a) / (1.0 - sigma_m / sut)
    a_coef = (f_frac * sut) ** 2 / se
    b_coef = -math.log10(f_frac * sut / se) / 3.0
    n_cycles = (sigma_ar / a_coef) ** (1.0 / b_coef)
    return cycles_applied / n_cycles


def test_known_answer_value() -> None:
    """Model value matches the hand-derived Miner damage to f64 precision."""
    prediction = FatigueDamageModel().estimate(_point_request())
    assert prediction.is_ok
    expected = _hand_damage(
        _SIGMA_A,
        _SIGMA_M,
        _KF_NOTCH,
        _SUT,
        _SE_PRIME,
        _KA,
        _KB,
        _KC,
        _KD,
        _KE,
        _KF_MARIN,
        _F_FRAC,
        _CYCLES_APPLIED,
    )
    assert abs(prediction.danger_ok.value - expected) < 1e-6
    assert 0.0 < expected < 1.0  # sanity: a real, sub-unity damage fraction


def test_discharged_with_healthy_margin() -> None:
    """Damage well under 1.0 discharges against the sf=4 style comparator."""
    evidence = default_registry().discharge(_point_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "fatigue_goodman_marin_basquin_damage@1"


def test_violated_when_limit_tightened_below_damage() -> None:
    """A damage cap below the computed fraction is a violation, not indeterminate."""
    point = FatigueDamageModel().estimate(_point_request()).danger_ok.value
    evidence = default_registry().discharge(_point_request(limit=point * 0.5))
    assert evidence.status.value == "violated"


def test_corner_conservatism_takes_worst_corner() -> None:
    """Widening sigma_a/sigma_m/cycles never lowers the reported damage (INV-9)."""
    point = FatigueDamageModel().estimate(_point_request()).danger_ok.value
    boxed = _point_request().model_copy(
        update={
            "inputs": {
                **_point_request().inputs,
                "sigma_a_pa": Interval(lo=_SIGMA_A, hi=140.0e6),
                "sigma_m_pa": Interval(lo=_SIGMA_M, hi=60.0e6),
                "cycles_applied": Interval(lo=_CYCLES_APPLIED, hi=8.0e5),
            }
        }
    )
    worst = FatigueDamageModel().estimate(boxed).danger_ok.value
    assert worst >= point


def test_out_of_domain_mean_stress_at_ultimate() -> None:
    """Mean stress at/above Sut breaks the Goodman line -> domain error."""
    req = _point_request().model_copy(
        update={
            "inputs": {
                **_point_request().inputs,
                "sigma_m_pa": Interval.point(_SUT),
            }
        }
    )
    assert FatigueDamageModel().estimate(req).is_err
    assert default_registry().discharge(req).status.value == "indeterminate"


def test_determinism_same_inputs_same_hash() -> None:
    """Identical inputs give a byte-identical evidence hash (INV-10)."""
    first = default_registry().discharge(_point_request())
    second = default_registry().discharge(_point_request())
    assert first.hash == second.hash
