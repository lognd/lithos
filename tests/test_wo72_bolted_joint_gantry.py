"""WO-72 (D183 demo 2, bolted-joint half): VDI 2230 discharge of
`examples/flagships/cnc_router_r1/contracts.hema`'s `BeamJoint` mating
(the gantry shoulder-to-beam-end joint: 6 x M8, `preload: 12 kN,
scatter=[0.75, 1.25]`), fed with the corpus's OWN declared numbers
directly into `BoltedJointModel.estimate()`.

This is the "direct producer/realizer path" precedent WO-64 phase C
established (`tests/orchestrator/test_wo64_phase_c_bed_carriage.py`'s own
header note): `python/regolith/orchestrator/translate.py` has no DSL
dispatch entry routing ANY hematite `require` form to
`mech.bolt.joint_separation` yet (escalated this dispatch, see the WO-72
ledger) -- both `crates/` and `python/regolith/orchestrator/` are outside
this WO's file surface (examples/ + tests/ + the WO file), so the model
is exercised directly against the corpus's real declared preload rather
than through `regolith check`.

Inputs, all traced to the corpus source:
  - f_preload: `BeamJoint`'s own `preload: 12 kN, scatter=[0.75, 1.25]`
    (contracts.hema) -> interval [9000, 15000] N.
  - f_external: `machine.hema`'s `boundary: cutting: [0, 800 N]` survey-
    corner cutting-force envelope, taken directly as the worst-case axial
    pull-apart load on the joint (a conservative simplification recorded
    here, not a derived free-body reaction -- deriving the true axial
    component of an 800N general cutting force through the shoulder
    geometry is a separate, unbudgeted free-body-diagram exercise; using
    the full envelope value is the SOUND-BY-construction over-conservative
    substitute, per INV-9's own "evaluate the worst corner" discipline).
  - k_bolt / k_clamp: no vendor stiffness record exists in this corpus
    for M8-through-20mm-steel (AD-22: never fabricate catalog data), so
    these use the SAME order-of-magnitude engineering estimates the
    model's own unit test (`tests/harness/test_bolted_joint.py`) uses for
    a representative M-bolt flange point -- an explicit, named assumption,
    not a corpus-cited value.
"""

from __future__ import annotations

from regolith.harness import DischargeRequest, Interval, default_registry
from regolith.harness.models.bolted_joint import CLAIM_KIND

# BeamJoint mating, contracts.hema: `preload: 12 kN, scatter=[0.75, 1.25]`
_F_PRELOAD = Interval(lo=12_000.0 * 0.75, hi=12_000.0 * 1.25)
# machine.hema `boundary: cutting: [0, 800 N]`
_F_EXTERNAL = Interval(lo=0.0, hi=800.0)
# Engineering-estimated M8-through-20mm-steel stiffnesses (order of
# magnitude only; same values `tests/harness/test_bolted_joint.py` uses).
_K_BOLT = Interval.point(1.0e8)
_K_CLAMP = Interval.point(4.0e8)
# Required residual clamp: enough to keep the 6-bolt flange from
# separating under worst axial pull with a modest margin over the
# external load's own upper corner (a named, conservative choice, not a
# corpus-cited value -- no `F_Kreq` figure is declared in contracts.hema
# today).
_F_KREQ = 2_000.0


def _beam_joint_request(limit: float = _F_KREQ) -> DischargeRequest:
    return DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=limit,
        inputs={
            "f_preload": _F_PRELOAD,
            "f_external": _F_EXTERNAL,
            "k_bolt": _K_BOLT,
            "k_clamp": _K_CLAMP,
        },
    )


def test_beam_joint_discharges_with_real_corpus_preload() -> None:
    """The gantry's 6xM8 BeamJoint clears its residual-clamp floor."""
    evidence = default_registry().discharge(_beam_joint_request())
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "bolted_joint_separation_vdi2230@1"


def test_beam_joint_violates_if_preload_relaxes_below_scatter_floor() -> None:
    """Sanity: a preload well below the mating's declared scatter floor
    (a fastener under-torqued far outside the [0.75, 1.25] scatter this
    corpus declares) separates -- the model is sensitive to the real
    corpus numbers, not vacuously discharging."""
    starved = DischargeRequest(
        claim_kind=CLAIM_KIND,
        limit=_F_KREQ,
        inputs={
            "f_preload": Interval.point(1_500.0),
            "f_external": _F_EXTERNAL,
            "k_bolt": _K_BOLT,
            "k_clamp": _K_CLAMP,
        },
    )
    evidence = default_registry().discharge(starved)
    assert evidence.status.value == "violated"
