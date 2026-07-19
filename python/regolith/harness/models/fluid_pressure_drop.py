"""Closed-form Darcy-Weisbach pipe pressure-drop model (WO-94/D196.1).

Discharges the fluorite corpus's `fluids.dp(<edge or edge span>) <=
<limit>` claim (fluorite/02 sec. 6; espresso_machine's `thermosiphon.
fluo` `dp:` line and `brew_water.fluo`'s `supply_dp:` line -- the
WO-92 close-out's `push_fluid_obligation` structural fix already
lowers this call form to a real scalar comparator, leaving it
`no_model` for want of a registered discharge -- this model fills
exactly that gap).

The formula is the single-segment Darcy-Weisbach pressure loss

    dp = f * (L / D) * (rho * v**2 / 2)

textbook-standard (White, Fluid Mechanics, 8th ed., sec. 6.6) and
IDENTICAL to feldspar's own `fluids.dp.pipe` direction
(`feldspar.library.fluids.incompressible.darcy_dp`, wired straight
to `crates/feldspar-library/src/fluids/`, the same citation) -- this
module does NOT import feldspar (the harness has no feldspar
dependency, AD-19: packs are a separate, optional plugin channel) but
its arithmetic is checked byte-for-byte against feldspar's compiled
Rust implementation in this model's own test (`test_fluid_pressure_
drop.py`), the "citable closed-form" bar WO-94 sets: the corpus's
declared friction factor is a design input (Moody-chart/laminar
estimate, folded upstream of this claim, honest and out of this
model's scope -- the same "declared, not derived" posture `civil.
bearing_pressure`'s reaction/area inputs take), not re-derived here.

Corner conservatism (INV-9): the claim is an UPPER bound (`<=`), so
every input multiplies dp UPWARD -- the conservative corner takes the
MAXIMUM of each input's interval (`f.hi`, `L.hi`, `rho.hi`, `v.hi`)
and the MINIMUM diameter (`D.lo`, since dp ~ 1/D); `eps` is zero
because every input is a declared datum, not a model-side estimate.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges (the fluorite call name
# itself -- `fluids.dp(...)` -- matched via `_match_call_lhs`/
# `_split_named_call_predicate` in `orchestrator/translate.py`, the
# same non-frame call-form dispatch `mech.bolt.joint_separation` and
# `mech.bearing.l10_hours` use).
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "fluids.dp"

# Required inputs (SI base units: dimensionless, m, m, kg/m**3, m/s).
# frob:doc docs/modules/py-harness.md#models
INPUTS = ("friction_factor", "length_m", "diameter_m", "density_kgm3", "velocity_ms")
_INPUTS = INPUTS


# frob:doc docs/modules/py-harness.md#models
class FluidPressureDropModel(Model):
    """Single-segment Darcy-Weisbach pressure drop vs a declared limit."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound dp claim (`<= <limit>`) over the five Darcy inputs."""
        return ModelSignature(
            name="fluid_darcy_weisbach_dp",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("incompressible", "single_segment", "fully_developed"),
        )

    @property
    # frob:doc docs/modules/py-harness.md#models
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    @property
    # frob:doc docs/modules/py-harness.md#models
    def citation(self) -> str | None:
        """The module doc's Darcy-Weisbach source."""
        return "White, Fluid Mechanics, 8th ed., sec. 6.6, Darcy-Weisbach"

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the conservative (max-numerator/min-diameter) dp."""
        f = request.inputs["friction_factor"]
        length = request.inputs["length_m"]
        diameter = request.inputs["diameter_m"]
        density = request.inputs["density_kgm3"]
        velocity = request.inputs["velocity_ms"]

        if diameter.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"diameter_m must be strictly positive: lo={diameter.lo}",
                )
            )
        if f.lo < 0.0 or length.lo < 0.0 or density.lo < 0.0 or velocity.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="friction_factor/length_m/density_kgm3/velocity_ms "
                    "must be non-negative",
                )
            )

        # Upper-bound sense: dp grows with f, L, rho, v (all HI) and
        # shrinks with D (LO) -- the worst corner for a `<= limit` claim.
        dp = f.hi * (length.hi / diameter.lo) * (density.hi * velocity.hi**2 / 2.0)
        return Ok(Prediction(value=dp, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "FluidPressureDropModel"]
