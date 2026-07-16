"""The fluorite friction-factor model pack (WO-139/D258.3/F158 GAP a1).

Covers: byte-for-byte calibration against feldspar's OWN compiled
`fluids_laminar_friction_factor`/`fluids_haaland_friction_factor`
(the WO-94 "citable closed-form" bar this model must also clear), the
upper-bound worst-corner sense, the domain guards, the honest
INDETERMINATE transition band (D258 ruling 3 -- no numeric `f` is ever
returned there), the Haaland-vs-Colebrook `eps` charge, registry
pickup, and determinism (INV-10).

The feldspar import is TEST-ONLY (calibration evidence), matching
`test_fluid_pressure_drop.py`'s posture -- the model itself has zero
feldspar import (AD-19). Skipped if feldspar is not installed.
"""

from __future__ import annotations

import pytest
from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.friction_factor import CLAIM_KIND, FrictionFactorModel

feldspar = pytest.importorskip("feldspar")


def _request(
    reynolds: float | tuple[float, float],
    relative_roughness: float | tuple[float, float] = 0.0,
    limit: float = 1.0,
) -> DischargeRequest:
    def _iv(x: float | tuple[float, float]) -> Interval:
        lo, hi = x if isinstance(x, tuple) else (x, x)
        return Interval(lo=lo, hi=hi)

    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "reynolds_number": _iv(reynolds),
            "relative_roughness": _iv(relative_roughness),
        },
    )


def test_laminar_calibrated_against_feldspars_64_over_re() -> None:
    """Laminar branch (Re < 2300) matches feldspar's compiled
    `fluids_laminar_friction_factor` exactly (White 8e sec. 6.4)."""
    from feldspar import _feldspar

    reynolds = 1500.0
    reference = _feldspar.fluids_laminar_friction_factor(reynolds)

    prediction = FrictionFactorModel().estimate(_request(reynolds))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == pytest.approx(reference, rel=1e-12)
    assert pred.eps == 0.0
    assert pred.in_domain


def test_turbulent_calibrated_against_feldspars_haaland() -> None:
    """Turbulent branch (Re > 4000) matches feldspar's compiled
    `fluids_haaland_friction_factor` exactly (Haaland 1983) -- the
    model's `eps` is a SEPARATE Haaland-vs-Colebrook charge, not part
    of the value comparison."""
    from feldspar import _feldspar

    reynolds, relative_roughness = 50_000.0, 0.0005
    reference = _feldspar.fluids_haaland_friction_factor(reynolds, relative_roughness)

    prediction = FrictionFactorModel().estimate(_request(reynolds, relative_roughness))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == pytest.approx(reference, rel=1e-12)
    assert pred.eps == pytest.approx(reference * 0.015, rel=1e-12)
    assert pred.in_domain


@pytest.mark.parametrize(
    ("reynolds", "relative_roughness"),
    [
        (1000.0, 0.0),
        (2000.0, 0.001),
        (10_000.0, 0.0002),
        (200_000.0, 0.00005),
    ],
)
def test_calibrated_over_a_shared_re_eps_over_d_fixture(
    reynolds: float, relative_roughness: float
) -> None:
    """A shared `(Re, eps/D)` fixture (the recon's own pairing) matches
    feldspar's laminar/Haaland split branch-for-branch (WO-94
    precedent for `fluid_pressure_drop.py`, applied here)."""
    from feldspar import _feldspar

    if reynolds < 2300.0:
        reference = _feldspar.fluids_laminar_friction_factor(reynolds)
        expected_eps = 0.0
    else:
        reference = _feldspar.fluids_haaland_friction_factor(
            reynolds, relative_roughness
        )
        expected_eps = reference * 0.015

    prediction = FrictionFactorModel().estimate(_request(reynolds, relative_roughness))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.value == pytest.approx(reference, rel=1e-12)
    assert pred.eps == pytest.approx(expected_eps, rel=1e-12)
    assert pred.in_domain


@pytest.mark.parametrize("reynolds", [2300.0, 2500.0, 3000.0, 3999.9999, 4000.0])
def test_transition_band_is_indeterminate_never_interpolated(reynolds: float) -> None:
    """A Reynolds number in [2300, 4000] (D258 ruling 3) produces
    `in_domain=False` -- no numeric `f` is ever asserted there, and
    the value carried is the honest zero placeholder, never a
    smoothed/interpolated figure."""
    prediction = FrictionFactorModel().estimate(_request(reynolds))
    assert prediction.is_ok, prediction
    pred = prediction.danger_ok
    assert pred.in_domain is False
    assert pred.value == 0.0
    assert pred.eps == 0.0


def test_an_interval_touching_the_transition_band_is_also_indeterminate() -> None:
    """An interval whose bounds straddle the boundary from either side
    (e.g. [2000, 2400] or [3900, 4500]) is ALSO indeterminate -- the
    conservative bracketing never picks a side for a Re range that
    could fall in the transition (INV-9)."""
    below_into_transition = FrictionFactorModel().estimate(_request((2000.0, 2400.0)))
    assert below_into_transition.is_ok
    assert below_into_transition.danger_ok.in_domain is False

    transition_into_above = FrictionFactorModel().estimate(_request((3900.0, 4500.0)))
    assert transition_into_above.is_ok
    assert transition_into_above.danger_ok.in_domain is False


def test_strictly_laminar_and_strictly_turbulent_intervals_stay_in_domain() -> None:
    """An interval fully below 2300 or fully above 4000 discharges
    normally -- only the band itself is indeterminate."""
    laminar = FrictionFactorModel().estimate(_request((500.0, 2000.0)))
    assert laminar.is_ok
    assert laminar.danger_ok.in_domain is True

    turbulent = FrictionFactorModel().estimate(_request((4001.0, 100_000.0), 0.0001))
    assert turbulent.is_ok
    assert turbulent.danger_ok.in_domain is True


def test_upper_bound_sense_takes_min_re_max_roughness() -> None:
    """The conservative corner for an interval box: smallest Re (both
    closed forms decrease with Re) and largest relative roughness
    (Haaland increases with roughness), INV-9."""
    from feldspar import _feldspar

    prediction = FrictionFactorModel().estimate(
        _request((10_000.0, 20_000.0), (0.0001, 0.0005))
    )
    assert prediction.is_ok
    expected = _feldspar.fluids_haaland_friction_factor(10_000.0, 0.0005)
    assert prediction.danger_ok.value == pytest.approx(expected, rel=1e-12)


def test_signature_is_an_upper_bound_over_reynolds_and_roughness() -> None:
    """The sense is `upper` (larger f is worse) over the two inputs."""
    sig = FrictionFactorModel().signature
    assert sig.sense.upper
    assert set(sig.inputs) == {"reynolds_number", "relative_roughness"}
    assert sig.claim_kind == CLAIM_KIND


def test_domain_guards_reject_nonpositive_reynolds_and_negative_roughness() -> None:
    """A zero/negative Reynolds number is a domain error (no flow has
    zero/negative Re), as is a negative relative roughness."""
    model = FrictionFactorModel()
    assert model.estimate(_request(0.0)).is_err
    assert model.estimate(_request(-100.0)).is_err
    assert model.estimate(_request(1000.0, -0.001)).is_err


def test_registry_discharges_and_violates_end_to_end() -> None:
    """The default registry routes `fluids.friction_factor` here."""
    registry = default_registry()
    ok = registry.discharge(_request(50_000.0, 0.0005, limit=1.0))
    assert ok.status.value == "discharged", ok
    over = registry.discharge(_request(50_000.0, 0.0005, limit=0.001))
    assert over.status.value == "violated", over


def test_transition_band_discharges_indeterminate_through_the_registry() -> None:
    """The registry's shared margin rule turns `in_domain=False` into
    the honest `indeterminate` status -- never a silent pass or a
    fabricated value (D258 ruling 3)."""
    registry = default_registry()
    result = registry.discharge(_request(3000.0, limit=1.0))
    assert result.status.value == "indeterminate", result


def test_determinism_same_inputs_same_prediction() -> None:
    """Two identical requests predict identically (INV-10)."""
    a = FrictionFactorModel().estimate(_request(50_000.0, 0.0005)).danger_ok
    b = FrictionFactorModel().estimate(_request(50_000.0, 0.0005)).danger_ok
    assert (a.value, a.eps, a.coverage, a.in_domain) == (
        b.value,
        b.eps,
        b.coverage,
        b.in_domain,
    )
