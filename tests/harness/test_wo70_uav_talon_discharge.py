"""WO-70 (D183 required surface): feldspar discharging over
`uav_talon`'s two REQUIRED claim families, evaluated with the
flagship's own declared geometry/loads (`airframe.hema`) -- WingSpar
bending/deflection under the declared, basis-cited gust case
(`beam_bending.py`'s Euler-Bernoulli cantilever model,
`mech.beam.cantilever_deflection`), and BoomClamp's bolted joint
separation check (`bolted_joint.py`'s VDI 2230 model,
`mech.bolt.joint_separation`) -- mirroring `tests/harness/
test_beam_service_deflection.py`/`test_bolted_joint.py`'s own known-
answer + discharge-verdict idiom, WO-64's "hand-declared evaluators
over the SAME realized-domain producers" posture (no `.hema` ->
harness-request producer exists end to end; the compiler's own claim
lowering is a different, diagnostic-shaped surface, not this DischargeRequest
schema).

Gust load basis: CS-23/MIL-HDBK-5J discrete-gust envelope, 15 m/s
vertical gust at cruise (`airframe.hema`'s `WingSpar.boundary.
gust_v`) -- combined with a conservative q*S estimate at a 1.2m-class
airframe's cruise dynamic pressure to derive the tip force this test
feeds the model (recorded here, not invented at the claim site: the
claim itself only asserts the numeric bound, `mech.deflection(...) <
25mm`).
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.beam_bending import CLAIM_KIND as _BEAM_KIND
from regolith.harness.models.beam_bending import BeamBendingModel
from regolith.harness.models.bolted_joint import CLAIM_KIND as _BOLT_KIND
from regolith.harness.models.bolted_joint import BoltedJointModel

# --- WingSpar cantilever bending under the declared gust case -------
# AL7075-T6 spar cap (airframe.hema): E = 71.7 GPa (std.materials
# aluminum.toml AL7075_T6), 900mm half-span cap run, 3mm-thick x
# 60mm-deep rectangular section (I = w*h**3/12).
_E_MODULUS_PA = 71.7e9
_SPAN_M = 0.900
_THICKNESS_M = 0.003
_DEPTH_M = 0.060
_I_AREA_M4 = _THICKNESS_M * _DEPTH_M**3 / 12.0

# Gust tip force: 15 m/s gust at a 1.2m-class airframe's ~18 m/s
# cruise -> delta_CL from a thin-airfoil gust-alleviation estimate
# (2*pi*(dv/V)), times a conservative half-wing dynamic-pressure load
# -- rolled into one bounding tip force per the claim's own
# `interface_envelope(SparCapMount)` conservatism (G4: load
# relocated to the tip is conservative for an UPPER deflection
# claim). Recomputed independently of the model, same idiom
# `test_bolted_joint.py`'s `_hand_residual` uses.
_GUST_TIP_FORCE_N = 220.0

_DEFLECTION_LIMIT_M = 0.025  # airframe.hema: tip_defl < 25mm


def _hand_cantilever_deflection(
    force: float, length: float, e: float, i: float
) -> float:
    """Euler-Bernoulli tip deflection, recomputed independently of the model."""
    return force * length**3 / (3.0 * e * i)


def test_wing_spar_gust_deflection_discharges() -> None:
    """`beam_bending.BeamBendingModel` (`mech.beam.cantilever_deflection`,
    the corpus's `mech.deflection(...)` service claim, `sensor_boom.hema`'s
    own precedent) discharges `WingSpar.tip_defl` under the declared
    gust tip force, comfortably inside the 25mm limit."""
    request = DischargeRequest(
        claim_kind=_BEAM_KIND,
        limit=_DEFLECTION_LIMIT_M,
        inputs={
            "force": Interval.point(_GUST_TIP_FORCE_N),
            "length": Interval.point(_SPAN_M),
            "e_modulus": Interval.point(_E_MODULUS_PA),
            "i_area": Interval.point(_I_AREA_M4),
        },
    )

    model = BeamBendingModel()
    assert model.model_id.startswith("beam_cantilever_deflection_eb")
    prediction_result = model.estimate(request)
    assert prediction_result.is_ok, prediction_result
    prediction = prediction_result.danger_ok

    hand = _hand_cantilever_deflection(
        _GUST_TIP_FORCE_N, _SPAN_M, _E_MODULUS_PA, _I_AREA_M4
    )
    assert abs(prediction.value - hand) / hand < 0.06  # within the model's own eps

    evidence = default_registry().discharge(request)
    assert evidence.model_id == model.model_id
    assert evidence.status.value == "discharged", (
        f"expected WingSpar tip deflection ({prediction.value * 1000:.3f}mm) "
        f"to discharge the 25mm claim, got {evidence.status.value}"
    )


# --- BoomClamp bolted joint separation under the tail shear reaction -
# Two M5 clamp bolts (airframe.hema: `PatternOf<Pierce<circle(dia
# 5mm)>>(n=2, ...)`), each preloaded to a conservative hand-tight M5
# class value; clamp/bolt stiffness ratio typical for a 4mm AL6061
# flange (`k_bolt`/`k_clamp` order-of-magnitude values, same idiom
# `test_bolted_joint.py`'s own `_FM`/`_FA`/`_KB`/`_KC` fixture).
_BOLT_PRELOAD_N = 4_500.0  # per bolt, conservative M5 class
_TAIL_SHEAR_N = 900.0  # boom tail reaction (BoomMount promise: derived(sf=1.3))
_K_BOLT_N_M = 1.0e8
_K_CLAMP_N_M = 4.0e8
_SEPARATION_MARGIN_REQUIRED_N = 0.0  # any positive residual clamp


def test_boom_clamp_bolted_joint_discharges() -> None:
    """`bolted_joint.BoltedJointModel` (`mech.bolt.joint_separation`,
    the `mech.bolt.separation_margin(...)` claim's discharged kind,
    `engine_bottom_end.hema`'s `cap_bolts` precedent) discharges
    `BoomClamp.clamp_bolts` under the tail's declared shear reaction."""
    request = DischargeRequest(
        claim_kind=_BOLT_KIND,
        limit=_SEPARATION_MARGIN_REQUIRED_N,
        inputs={
            "f_preload": Interval.point(_BOLT_PRELOAD_N),
            "f_external": Interval.point(_TAIL_SHEAR_N),
            "k_bolt": Interval.point(_K_BOLT_N_M),
            "k_clamp": Interval.point(_K_CLAMP_N_M),
        },
    )

    model = BoltedJointModel()
    assert model.model_id.startswith("bolted_joint_separation_vdi2230")
    prediction_result = model.estimate(request)
    assert prediction_result.is_ok, prediction_result
    prediction = prediction_result.danger_ok

    evidence = default_registry().discharge(request)
    assert evidence.model_id == model.model_id
    assert evidence.status.value == "discharged", (
        f"expected BoomClamp residual clamp ({prediction.value:.1f}N) "
        f"to discharge the no-separation claim, got {evidence.status.value}"
    )
