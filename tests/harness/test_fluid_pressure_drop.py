"""The fluorite Darcy-Weisbach pressure-drop model pack (WO-94/D196.1).

Covers: the closed-form calibration against feldspar's OWN compiled
`fluids.dp.pipe` direction (the "citable closed-form" bar WO-94's
dispatch sets -- an uncitable model is cut, this one is checked
byte-for-byte against the reference implementation), the discharge/
violated verdicts, the upper-bound sense (max numerator / min
diameter is the conservative corner), the domain guards, registry
pickup, and determinism (INV-10).

The feldspar import is a TEST-ONLY dependency (calibration evidence),
never a runtime one -- `fluid_pressure_drop.py` itself has zero
feldspar import, matching harness/AD-19's "packs are a separate,
optional plugin channel" posture. Skipped if feldspar is not
installed in this environment (the harness must not hard-depend on
it), same posture the repo's other feldspar-adjacent tests take.
"""

from __future__ import annotations

import pytest
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.fluid_pressure_drop import (
    CLAIM_KIND,
    FluidPressureDropModel,
)

feldspar = pytest.importorskip("feldspar")


def _request(
    f: float | tuple[float, float] = 0.03,
    length: float | tuple[float, float] = 0.05,
    diameter: float | tuple[float, float] = 0.008,
    density: float | tuple[float, float] = 965.0,
    velocity: float | tuple[float, float] = 0.05,
    limit: float = 2.0,
) -> DischargeRequest:
    def _iv(x: float | tuple[float, float]) -> Interval:
        lo, hi = x if isinstance(x, tuple) else (x, x)
        return Interval(lo=lo, hi=hi)

    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "friction_factor": _iv(f),
            "length_m": _iv(length),
            "diameter_m": _iv(diameter),
            "density_kgm3": _iv(density),
            "velocity_ms": _iv(velocity),
        },
    )


def test_calibrated_against_feldspars_darcy_dp() -> None:
    """Pinned-interval inputs predict EXACTLY feldspar's own compiled
    `fluids_darcy_dp` (White, Fluid Mechanics 8th ed. sec. 6.6) -- the
    citable-reference bar WO-94's dispatch requires of any new fluid
    harness model."""
    from feldspar import _feldspar

    f, length, diameter, density, velocity = 0.03, 0.05, 0.008, 965.0, 0.05
    reference = _feldspar.fluids_darcy_dp(f, length, diameter, density, velocity)

    prediction = FluidPressureDropModel().estimate(
        _request(
            f=f, length=length, diameter=diameter, density=density, velocity=velocity
        )
    )
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == pytest.approx(reference, rel=1e-12)
    assert pred.eps == 0.0
    assert pred.in_domain


def test_upper_bound_sense_takes_the_worst_corner() -> None:
    """An interval-valued input set predicts MAX f/L/rho/v over MIN
    diameter (the conservative direction for a `<= limit` claim, INV-9)."""
    prediction = FluidPressureDropModel().estimate(
        _request(
            f=(0.02, 0.03),
            length=(0.04, 0.05),
            diameter=(0.008, 0.010),
            density=(960.0, 965.0),
            velocity=(0.04, 0.05),
        )
    )
    assert prediction.is_ok
    expected = 0.03 * (0.05 / 0.008) * (965.0 * 0.05**2 / 2.0)
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_signature_is_an_upper_bound_over_the_five_darcy_inputs() -> None:
    """The sense is `upper` (larger dp is worse) over the five inputs."""
    sig = FluidPressureDropModel().signature
    assert sig.sense.upper
    assert set(sig.inputs) == {
        "friction_factor",
        "length_m",
        "diameter_m",
        "density_kgm3",
        "velocity_ms",
    }
    assert sig.claim_kind == CLAIM_KIND


def test_domain_guards_reject_nonpositive_diameter_and_negative_inputs() -> None:
    """A zero/negative diameter is a domain error (no pipe has zero
    bore), as is a negative friction factor/length/density/velocity."""
    model = FluidPressureDropModel()
    assert model.estimate(_request(diameter=0.0)).is_err
    assert model.estimate(_request(diameter=-0.001)).is_err
    assert model.estimate(_request(f=-0.01)).is_err
    assert model.estimate(_request(length=-1.0)).is_err
    assert model.estimate(_request(density=-1.0)).is_err
    assert model.estimate(_request(velocity=-1.0)).is_err


def test_registry_discharges_and_violates_end_to_end() -> None:
    """The default registry routes `fluids.dp` here: ~0.23 Pa predicted
    vs a 2Pa limit discharges; the same geometry over a much longer run
    violates."""
    registry = default_registry()
    ok = registry.discharge(_request(length=0.05, limit=2.0))
    assert ok.status.value == "discharged", ok
    over = registry.discharge(_request(length=50.0, limit=2.0))
    assert over.status.value == "violated", over


def test_determinism_same_inputs_same_prediction() -> None:
    """Two identical requests predict identically (INV-10)."""
    a = FluidPressureDropModel().estimate(_request()).danger_ok
    b = FluidPressureDropModel().estimate(_request()).danger_ok
    assert (a.value, a.eps, a.coverage) == (b.value, b.eps, b.coverage)
