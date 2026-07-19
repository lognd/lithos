"""WO-140 (D258.2/F158): the `fluids.dp` minor-loss (fitting/component)
chain widening on `FluidPressureDropModel`.

Covers: the two new OPTIONAL inputs (`minor_loss_k_sum`, `component_
crack_dp_pa`) are byte-checked against feldspar's own compiled
`fluids_minor_loss_dp` K-factor form (`feldspar:crates/feldspar-
library/src/fluids/incompressible.rs`, the same WO-94 both-sides
precedent WO-139's friction-factor model uses), the chain WIDENS
(a claim declaring neither term keeps discharging byte-identically to
the pre-WO-140 five-input model), the upper-bound corner (`.hi` on
both terms), and the domain guard (negative K-sum/crack-dp is a
domain error, same posture as the five Darcy inputs).

Skipped if feldspar is not installed (test-only calibration
dependency, same posture `test_fluid_pressure_drop.py` takes -- the
model itself has zero feldspar import).
"""

from __future__ import annotations

import pytest
from regolith.harness import DischargeRequest, Interval
from regolith.harness.models.fluid_pressure_drop import (
    CLAIM_KIND,
    FluidPressureDropModel,
)

feldspar = pytest.importorskip("feldspar")

_F, _LENGTH, _DIAMETER, _DENSITY, _VELOCITY = 0.03, 0.05, 0.008, 965.0, 0.05


def _base_inputs() -> dict[str, Interval]:
    return {
        "friction_factor": Interval(lo=_F, hi=_F),
        "length_m": Interval(lo=_LENGTH, hi=_LENGTH),
        "diameter_m": Interval(lo=_DIAMETER, hi=_DIAMETER),
        "density_kgm3": Interval(lo=_DENSITY, hi=_DENSITY),
        "velocity_ms": Interval(lo=_VELOCITY, hi=_VELOCITY),
    }


def _darcy_only() -> float:
    return _F * (_LENGTH / _DIAMETER) * (_DENSITY * _VELOCITY**2 / 2.0)


def test_no_fittings_declared_is_byte_identical_to_pre_wo140() -> None:
    """A claim declaring neither minor-loss term predicts EXACTLY the
    five-input Darcy-only dp -- the chain WIDENING must not perturb the
    unwidened case (WO-140 acceptance)."""
    prediction = FluidPressureDropModel().estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=2.0, inputs=_base_inputs())
    )
    assert prediction.is_ok
    assert prediction.danger_ok.value == pytest.approx(_darcy_only(), rel=1e-12)


def test_minor_loss_k_sum_matches_feldspars_minor_loss_dp() -> None:
    """`minor_loss_k_sum * rho * v^2 / 2` byte-checks against feldspar's
    own compiled `fluids_minor_loss_dp(k_factor, density, velocity)`."""
    from feldspar import _feldspar

    k_sum = 2.4  # e.g. two elbows + an entrance, summed
    reference_minor = _feldspar.fluids_minor_loss_dp(k_sum, _DENSITY, _VELOCITY)

    inputs = _base_inputs()
    inputs["minor_loss_k_sum"] = Interval(lo=k_sum, hi=k_sum)
    prediction = FluidPressureDropModel().estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=100.0, inputs=inputs)
    )
    assert prediction.is_ok
    expected = _darcy_only() + reference_minor
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_component_crack_dp_adds_directly() -> None:
    """`component_crack_dp_pa` adds to the total unconverted (it is
    itself a pressure drop, not a K-factor)."""
    inputs = _base_inputs()
    inputs["component_crack_dp_pa"] = Interval(lo=20_000.0, hi=20_000.0)
    prediction = FluidPressureDropModel().estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=100_000.0, inputs=inputs)
    )
    assert prediction.is_ok
    assert prediction.danger_ok.value == pytest.approx(
        _darcy_only() + 20_000.0, rel=1e-12
    )


def test_upper_bound_sense_takes_the_hi_corner_on_both_new_terms() -> None:
    """An interval K-sum/crack-dp predicts the `.hi` corner (INV-9),
    matching the five-Darcy-input worst-corner posture."""
    inputs = _base_inputs()
    inputs["minor_loss_k_sum"] = Interval(lo=1.0, hi=2.0)
    inputs["component_crack_dp_pa"] = Interval(lo=1000.0, hi=5000.0)
    prediction = FluidPressureDropModel().estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=100_000.0, inputs=inputs)
    )
    assert prediction.is_ok
    expected = _darcy_only() + 2.0 * (_DENSITY * _VELOCITY**2 / 2.0) + 5000.0
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_domain_guard_rejects_negative_minor_loss_terms() -> None:
    """A negative K-sum or crack-dp is a domain error, never silently
    clamped (same posture the five Darcy inputs already take)."""
    model = FluidPressureDropModel()
    bad_k = _base_inputs()
    bad_k["minor_loss_k_sum"] = Interval(lo=-1.0, hi=-1.0)
    assert model.estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=1.0, inputs=bad_k)
    ).is_err

    bad_crack = _base_inputs()
    bad_crack["component_crack_dp_pa"] = Interval(lo=-1.0, hi=-1.0)
    assert model.estimate(
        DischargeRequest(claim_kind=CLAIM_KIND, limit=1.0, inputs=bad_crack)
    ).is_err
