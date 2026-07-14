"""Independent closed-form oracles: bearing life, bolted joints, beams,
shaft critical speed (mechanical families, D226).

Every formula here is written fresh from its cited source -- none of
these functions import or call the corresponding
``regolith.harness.models`` / ``feldspar`` model.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping


def _corners(lo: float, hi: float) -> tuple[float, ...]:
    """The (deduplicated) endpoints of one input's interval."""
    return tuple(sorted({lo, hi}))


def bearing_l10h(inputs: Mapping[str, tuple[float, float]]) -> float:
    """ISO 281:2007 sec. 6.2 basic L10/L10h rating life, worst (min) corner.

    ``L10 = (C/P)**p`` (millions of rev), ``L10h = L10 * 1e6 / (60*n)``.
    """
    c = inputs["c_rating"]
    p = inputs["p_load"]
    n = inputs["speed_rpm"]
    pexp = inputs["p_exponent"]
    worst = math.inf
    for c_, p_, n_, pe_ in itertools.product(
        _corners(*c), _corners(*p), _corners(*n), _corners(*pexp)
    ):
        l10 = (c_ / p_) ** pe_
        l10h = l10 * 1.0e6 / (60.0 * n_)
        worst = min(worst, l10h)
    return worst


def bolted_joint_residual_clamp(inputs: Mapping[str, tuple[float, float]]) -> float:
    """VDI 2230 joint-stiffness diagram: ``F_KR = F_M - (1-phi)*F_A``,
    ``phi = k_bolt / (k_bolt + k_clamp)``, worst (min) corner.
    """
    f_m = inputs["f_preload"]
    f_a = inputs["f_external"]
    k_b = inputs["k_bolt"]
    k_c = inputs["k_clamp"]
    worst = math.inf
    for fm, fa, kb, kc in itertools.product(
        _corners(*f_m), _corners(*f_a), _corners(*k_b), _corners(*k_c)
    ):
        phi = kb / (kb + kc)
        f_kr = fm - (1.0 - phi) * fa
        worst = min(worst, f_kr)
    return worst


def cantilever_tip_deflection(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Euler-Bernoulli end-loaded cantilever: ``delta = F*L**3/(3*E*I)``,
    worst (max) corner.
    """
    f = inputs["force"]
    ell = inputs["length"]
    e = inputs["e_modulus"]
    i_ = inputs["i_area"]
    worst = 0.0
    for f_, l_, e_, i in itertools.product(
        _corners(*f), _corners(*ell), _corners(*e), _corners(*i_)
    ):
        delta = f_ * l_**3 / (3.0 * e_ * i)
        worst = max(worst, delta)
    return worst


def simple_span_udl_deflection(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Simply-supported UDL midspan deflection: ``5*w*L**4/(384*E*I)``,
    worst (max) corner.
    """
    w = inputs["w_load"]
    ell = inputs["length"]
    e = inputs["e_modulus"]
    i_ = inputs["i_area"]
    worst = 0.0
    for w_, l_, e_, i in itertools.product(
        _corners(*w), _corners(*ell), _corners(*e), _corners(*i_)
    ):
        delta = 5.0 * w_ * l_**4 / (384.0 * e_ * i)
        worst = max(worst, delta)
    return worst


def beam_utilization(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Elastic beam-column interaction:
    ``|M|/(Z*Fy) + |P|/(A*Fy)``, worst (max) corner.
    """
    m = inputs["moment_demand"]
    p = inputs["axial_demand"]
    z = inputs["section_modulus"]
    a = inputs["area"]
    fy = inputs["fy"]
    worst = 0.0
    for m_, p_, z_, a_, fy_ in itertools.product(
        _corners(*m), _corners(*p), _corners(*z), _corners(*a), _corners(*fy)
    ):
        util = abs(m_) / (z_ * fy_) + abs(p_) / (a_ * fy_)
        worst = max(worst, util)
    return worst


def shaft_critical_speed_rpm(inputs: Mapping[str, tuple[float, float]]) -> float:
    """Shigley 11e eq. 7-22: ``n_c = (60/(2*pi)) * sqrt(k/m)`` rpm,
    worst (min) corner (a floor claim: must clear the operating speed).
    """
    k = inputs["mech.critical_speed.stiffness"]
    m = inputs["mech.critical_speed.mass"]
    worst = math.inf
    for k_, m_ in itertools.product(_corners(*k), _corners(*m)):
        omega = math.sqrt(k_ / m_)
        n_c = omega * 60.0 / (2.0 * math.pi)
        worst = min(worst, n_c)
    return worst
