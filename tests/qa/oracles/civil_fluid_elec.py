"""Independent closed-form oracles: footing bearing pressure, fluid
pressure drop, lumped-thermal, SI series termination, buck output
ripple, and the WO-135/136 facility power-distribution family (D226).

Every formula here is written fresh from its cited source -- none of
these functions import or call the corresponding
``regolith.harness.models`` / ``feldspar`` model.
"""

from __future__ import annotations

import itertools
import math
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


# ---------------------------------------------------------------------------
# WO-135/136 facility power-distribution family (D226; F154/F155 made the
# 8 elec_power_* families fleet-reachable via factory_p1 with no oracle).
# Each formula below is hand-transcribed fresh from the model docstring's
# own cited standard (NEC 220/310.15/110.26, IEEE 141, IEEE 242,
# IEEE C57.91) -- never by calling ``regolith.harness.models.power``.
# ---------------------------------------------------------------------------


def demand_load_kva(inputs: Mapping[str, tuple[float, float]]) -> float:
    """NEC Art. 220: ``demand_kva = connected_kva * demand_factor``.

    Upper bound, both factors increasing -> the high corner of each
    (connected_kva.hi * demand_factor.hi).
    """
    connected = inputs["connected_kva"]
    factor = inputs["demand_factor"]
    return max(connected) * max(factor)


def voltage_drop_v(inputs: Mapping[str, tuple[float, float]]) -> float:
    """IEEE Std 141-1993 ch. 3 conductor voltage drop:

        vd = phase_multiplier * I * L * (R * pf + X * sqrt(1 - pf**2))

    Upper bound: I/L/R/X/multiplier all push the drop up (their HI
    corner); power_factor is not monotone over its interval, so both
    endpoints are evaluated and the larger drop kept.
    """
    current = max(inputs["current_a"])
    length = max(inputs["length_m"])
    resistance = max(inputs["resistance_ohm_per_m"])
    reactance = max(inputs["reactance_ohm_per_m"])
    multiplier = max(inputs["phase_multiplier"])
    pf_lo, pf_hi = inputs["power_factor"]
    worst = None
    for pf in (pf_lo, pf_hi):
        sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
        drop = multiplier * current * length * (resistance * pf + reactance * sin_phi)
        worst = drop if worst is None else max(worst, drop)
    assert worst is not None
    return worst


def ampacity_derated_a(inputs: Mapping[str, tuple[float, float]]) -> float:
    """NEC 310.15(B)/(C) derated ampacity:

        derated = base_ampacity_a * temperature_correction_factor *
                  fill_adjustment_factor

    Lower bound (available capacity vs a required load current):
    derating only ever reduces capacity, so the worst corner is the
    MIN of all three factors.
    """
    base = min(inputs["base_ampacity_a"])
    temp_factor = min(inputs["temperature_correction_factor"])
    fill_factor = min(inputs["fill_adjustment_factor"])
    return base * temp_factor * fill_factor


def fault_current_screening_a(inputs: Mapping[str, tuple[float, float]]) -> float:
    """IEEE Std 242-2001 sec. 4 single-source transformer %Z screening:

        I_full_load = (kva * 1000) / (sqrt(3) * v_secondary)
        I_fault     = I_full_load / (pct_z / 100)

    Upper bound: worst corner is max kVA, MIN %Z (a stiffer
    transformer trips higher fault current), MIN secondary voltage.
    """
    kva = max(inputs["transformer_kva"])
    pct_z = min(inputs["pct_z"])
    voltage = min(inputs["secondary_voltage_v"])
    full_load_current = (kva * 1000.0) / (math.sqrt(3.0) * voltage)
    return full_load_current / (pct_z / 100.0)


def motor_start_dip_pct(inputs: Mapping[str, tuple[float, float]]) -> float:
    """IEEE Std 141-1993 ch. 5 motor-starting voltage-dip divider:

        dip_pct = 100 * lra_kva / (lra_kva + source_available_kva)

    Upper bound: dip grows with LRA (its HI corner) and shrinks with
    more available source capacity (its LO corner).
    """
    lra = max(inputs["motor_locked_rotor_kva"])
    source = min(inputs["source_available_kva"])
    return 100.0 * lra / (lra + source)


def transformer_loading_pct(inputs: Mapping[str, tuple[float, float]]) -> float:
    """IEEE Std C57.91-2011 sec. 1 percent-of-nameplate loading:

        loading_pct = 100 * actual_kva / rated_kva

    Upper bound: worst corner is max actual_kva over min rated_kva.
    """
    actual = max(inputs["actual_kva"])
    rated = min(inputs["rated_kva"])
    return 100.0 * actual / rated


def power_factor_ratio(inputs: Mapping[str, tuple[float, float]]) -> float:
    """IEEE Std 141-1993 ch. 2: ``pf = real_power_kw / apparent_power_kva``.

    Lower bound (pf vs a minimum tariff threshold): worst corner is
    min real_power_kw over max apparent_power_kva.
    """
    real = min(inputs["real_power_kw"])
    apparent = max(inputs["apparent_power_kva"])
    return real / apparent


def working_clearance_available_m(inputs: Mapping[str, tuple[float, float]]) -> float:
    """NEC 110.26 available working clearance:

        available_m = room_dim_m - footprint_dim_m

    Lower bound (available vs a required minimum): worst corner is
    min room_dim_m minus max footprint_dim_m.
    """
    room = min(inputs["room_dim_m"])
    footprint = max(inputs["footprint_dim_m"])
    return room - footprint
