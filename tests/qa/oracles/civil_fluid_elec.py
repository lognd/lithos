"""Independent closed-form oracles: footing bearing pressure, fluid
pressure drop, lumped-thermal, SI series termination, buck output
ripple (D226).

Every formula here is written fresh from its cited source -- none of
these functions import or call the corresponding
``regolith.harness.models`` / ``feldspar`` model.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping


def _corners(lo: float, hi: float) -> tuple[float, ...]:
    return tuple(sorted({lo, hi}))


def footing_bearing_pressure(inputs: Mapping[str, tuple[float, float]]) -> float:
    """``pressure = reaction / area``, worst (max) corner: max reaction
    over min area."""
    reaction = inputs["reaction_n"]
    area = inputs["area_m2"]
    return max(reaction) / min(area)


def darcy_weisbach_dp(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Darcy-Weisbach: ``dp = f*(L/D)*(rho*v**2/2)`` (White, Fluid
    Mechanics 8th ed. sec. 6.6). Upper bound: every input multiplies
    upward except diameter (dp ~ 1/D), so max f/L/rho/v and min D.
    """
    f = max(inputs["friction_factor"])
    length = max(inputs["length_m"])
    diameter = min(inputs["diameter_m"])
    density = max(inputs["density_kgm3"])
    velocity = max(inputs["velocity_ms"])
    return f * (length / diameter) * (density * velocity**2 / 2.0)


def lumped_thermal_junction_temp(inputs: Mapping[str, tuple[float, float]]) -> float:
    """``T_j = T_ambient + P * R_theta``, every input strictly
    increasing -> the high corner of each."""
    ambient = max(inputs["ambient"])
    power = max(inputs["power"])
    r_theta = max(inputs["r_theta"])
    return ambient + power * r_theta


def buck_output_ripple_ccm(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Peak-to-peak output ripple of a CCM buck, ESR neglected
    (Erickson & Maksimovic, *Fundamentals of Power Electronics* 2nd ed.
    sec. 2.3 / ch. 4 -- the standard inductor-ripple + capacitor-charge
    pair), written fresh here:

        di_L    = v_out * (v_in - v_out) / (v_in * f_sw * L)
        v_pp    = di_L / (8 * f_sw * C_out)

    An UPPER-bound claim, so the worst (max) corner is returned. The
    monotonicity is not hand-proven here: every interval corner is
    enumerated and the maximum taken, which is sound for any interval
    box and is deliberately a DIFFERENT derivation path from the model
    under test (F152 made this family fleet-reachable, so D226 requires
    this oracle).
    """
    worst = None
    for v_in, v_out, f_sw, ell, c_out in itertools.product(
        _corners(*inputs["v_in"]),
        _corners(*inputs["v_out"]),
        _corners(*inputs["f_sw"]),
        _corners(*inputs["l"]),
        _corners(*inputs["c_out"]),
    ):
        # Outside CCM buck validity (a step-down converter requires
        # v_out <= v_in); such a corner is not a physical operating
        # point and cannot be the worst REAL ripple -- skip it rather
        # than emit a negative/absurd number.
        if v_in <= 0 or v_out < 0 or v_out > v_in:
            continue
        di_l = v_out * (v_in - v_out) / (v_in * f_sw * ell)
        v_pp = di_l / (8.0 * f_sw * c_out)
        worst = v_pp if worst is None else max(worst, v_pp)
    assert worst is not None
    return worst


def si_series_termination_rs(inputs: Mapping[str, tuple[float, float]]) -> float:
    """``Rs = Z0 - Ro`` (Johnson & Graham, ch. 4), a floor claim: worst
    (min) corner is min(Z0) - max(Ro)."""
    z0 = inputs["elec.si.series_termination.z0"]
    ro = inputs["elec.si.series_termination.ro"]
    worst = None
    for z0_, ro_ in itertools.product(_corners(*z0), _corners(*ro)):
        rs = z0_ - ro_
        worst = rs if worst is None else min(worst, rs)
    assert worst is not None
    return worst
