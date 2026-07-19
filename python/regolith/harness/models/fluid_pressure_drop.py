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

WO-140 widening (D258.2/F158): a path's total dp may ALSO include
minor (fitting/component) losses -- elbows, tees, valves, entrances,
exits, expansions, contractions -- on top of the Darcy segment term
above. Two OPTIONAL extra inputs carry this, both defaulting to a
zero-width `[0, 0]` interval when absent so every existing
single-segment `fluids.dp` fixture that declares no fittings keeps
discharging byte-identically (a chain WIDENING, never a behavior
change for the unwidened case):

- `minor_loss_k_sum`: the summed K of every declared fitting on the
  path (`stdlib/std.fluid/records/fittings.toml`'s geometry-law rows,
  resolved by `orchestrator.translate._translate_fluid_dp`), applied
  as `K_sum * rho * v**2 / 2` -- the same `K*rho*v^2/2` minor-loss
  form feldspar's own library already carries
  (`feldspar:crates/feldspar-library/src/fluids/incompressible.rs:108`),
  byte-checked against it in this model's own test.
- `component_crack_dp_pa`: a declared component's own crack/rated dp
  (e.g. a valve's Cv-derived dp at the path's flow, `components.toml`),
  added directly -- it is not a K-factor term, it is itself a pressure
  drop at a stated flow, so it adds to the total unconverted.

Both terms are UPPER-bound inputs like the five Darcy terms above:
the worst corner takes each interval's `.hi`.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.quantity import Interval
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

# WO-140: optional minor-loss extras (see module doc); absent from
# `_INPUTS`/`signature.inputs` on purpose -- they are NOT required, a
# claim declaring neither keeps discharging via the five Darcy inputs
# alone, byte-identical to pre-WO-140 behavior.
_ZERO_INTERVAL = Interval(lo=0.0, hi=0.0)


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

        # WO-140 widening: optional minor-loss terms, zero when the
        # claim declares no fittings/components (see module doc).
        k_sum = request.inputs.get("minor_loss_k_sum", _ZERO_INTERVAL)
        crack_dp = request.inputs.get("component_crack_dp_pa", _ZERO_INTERVAL)
        if k_sum.lo < 0.0 or crack_dp.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="minor_loss_k_sum/component_crack_dp_pa must be "
                    "non-negative",
                )
            )
        dp += k_sum.hi * (density.hi * velocity.hi**2 / 2.0)
        dp += crack_dp.hi
        return Ok(Prediction(value=dp, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "FluidPressureDropModel"]
