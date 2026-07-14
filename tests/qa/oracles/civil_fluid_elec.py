"""Independent closed-form oracles: footing bearing pressure, fluid
pressure drop, lumped-thermal, SI series termination (D226).

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
