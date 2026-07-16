"""Darcy friction-factor model: laminar exact / Haaland turbulent / an
honestly INDETERMINATE transition band (WO-139, D258.3/F158 GAP a1).

Two closed forms, chosen exactly per the recon and D258 ruling 3:

- **Laminar** (`Re < 2300`): `f = 64 / Re`, the exact Hagen-Poiseuille
  result for fully developed laminar pipe flow (White, *Fluid
  Mechanics*, 8th ed., sec. 6.4). `eps = 0` -- this is not an
  approximation, it IS the closed form.
- **Turbulent** (`Re > 4000`): Haaland's explicit approximation to
  Colebrook (Haaland, S. E., "Simple and Explicit Formulas for the
  Friction Factor in Turbulent Pipe Flow", J. Fluids Eng. 105(1):89-90,
  1983), chosen as the primary explicit correlation because feldspar's
  own Colebrook Newton iteration is SEEDED from this exact formula
  (`feldspar:crates/feldspar-library/src/fluids/incompressible.rs:49-89`),
  giving this model's byte-check test a natural cross-check partner --
  the same WO-94 precedent `fluid_pressure_drop.py` already sets. The
  model's `eps` folds in the documented Haaland-vs-Colebrook deviation
  (~1.5% max on `f` over the Moody range, White 8e sec. 6.8): an honest
  way to ship an explicit approximation of an implicit law, never a
  claim of exactness.
- **Transition** (`2300 <= Re <= 4000`, D97/D258 ruling 3): the
  laminar-turbulent transition is NOT interpolated through. Any
  Reynolds-number INTERVAL that touches this band at all (even at one
  endpoint) reports `in_domain=False` -- an honest, conservative
  bracketing (INV-9): no numeric `f` is ever asserted for an interval
  that could straddle the transition.

Corner conservatism (INV-9): this is registered as an UPPER-BOUND claim
(`fluids.friction_factor(...) <= limit`, e.g. a design check that a
pipe's roughness/Re combination does not exceed an assumed `f`) -- a
LARGER `f` is the worse corner. Both closed forms are monotonically
DEcreasing in `Re` and INcreasing in relative roughness, so the worst
corner takes `reynolds_number.lo` (the smallest Re in the interval) and
`relative_roughness.hi` (the roughest bound) -- the same "widen
outward, never narrow" posture `fluid_pressure_drop.py`'s dp claim
takes over its own five inputs.

`fluids.dp`'s input chain (`fluid_pressure_drop.py`/`translate.py`)
consumes this model to DERIVE a missing `friction_factor` input from a
resolved Reynolds number + relative roughness, when no inline
declaration overrides it (AD-22) -- see `orchestrator/translate.py`'s
`_translate_fluid_dp` and `orchestrator/fluid_resolve.py`'s roughness
resolution.
"""

from __future__ import annotations

import math

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges.
CLAIM_KIND = "fluids.friction_factor"

# Required inputs: both dimensionless.
INPUTS = ("reynolds_number", "relative_roughness")
_INPUTS = INPUTS

# D258 ruling 3 / the recon's stated transition band (2300, laminar
# ceiling; 4000, turbulent floor -- White 8e sec. 6.8's Moody-chart
# convention).
_RE_LAMINAR_CEILING = 2300.0
_RE_TURBULENT_FLOOR = 4000.0

# Haaland-vs-Colebrook max deviation over the Moody range (the recon's
# cited figure, White 8e sec. 6.8 commentary): folded into `eps` as a
# fractional charge on the turbulent branch's predicted `f`, never
# hidden.
_HAALAND_VS_COLEBROOK_FRACTION = 0.015


def _laminar(reynolds: float) -> float:
    """Hagen-Poiseuille: `f = 64 / Re` (exact, White 8e sec. 6.4)."""
    return 64.0 / reynolds


def _haaland(reynolds: float, relative_roughness: float) -> float:
    """Haaland 1983 explicit turbulent approximation to Colebrook.

    `1/sqrt(f) = -1.8 * log10( (eps/D/3.7)^1.11 + 6.9/Re )` --
    byte-identical formula to feldspar's own
    `fluids_haaland_friction_factor` (the WO-94 cross-check precedent).
    """
    inner = (relative_roughness / 3.7) ** 1.11 + 6.9 / reynolds
    inv_sqrt_f = -1.8 * math.log10(inner)
    return 1.0 / (inv_sqrt_f * inv_sqrt_f)


class FrictionFactorModel(Model):
    """Darcy friction factor: 64/Re laminar, Haaland turbulent, honest
    INDETERMINATE transition (D258 ruling 3)."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound `f` claim over Reynolds number + relative roughness."""
        return ModelSignature(
            name="fluids_friction_factor",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("incompressible", "single_segment", "fully_developed"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    @property
    def citation(self) -> str | None:
        """The two closed forms' sources (D221 calc-book citation)."""
        return (
            "Haaland, S. E., 'Simple and Explicit Formulas for the Friction "
            "Factor in Turbulent Pipe Flow', J. Fluids Eng. 105(1):89-90, "
            "1983 (turbulent branch); White, F. M., Fluid Mechanics, 8th "
            "ed., McGraw-Hill, sec. 6.4 (laminar 64/Re, exact)"
        )

    @property
    def input_units(self) -> dict[str, str]:
        """Both ports are dimensionless (WO-123 D238.4)."""
        return {"reynolds_number": "1", "relative_roughness": "1"}

    @property
    def output_unit(self) -> str | None:
        """The Darcy friction factor is dimensionless."""
        return "1"

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the conservative (min-Re/max-roughness) friction factor.

        Returns `in_domain=False` (D258 ruling 3, D97 regime-tag
        posture) for any Reynolds-number interval that touches the
        [2300, 4000] transition band at either endpoint -- no
        numeric `f` is ever asserted there, never interpolated.
        """
        reynolds = request.inputs["reynolds_number"]
        relative_roughness = request.inputs["relative_roughness"]

        if reynolds.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"reynolds_number must be strictly positive: lo={reynolds.lo}"
                    ),
                )
            )
        if relative_roughness.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="relative_roughness must be non-negative: "
                    f"lo={relative_roughness.lo}",
                )
            )

        # Honest transition band (D258 ruling 3): ANY part of the
        # interval touching [2300, 4000] makes the regime ambiguous --
        # conservative bracketing (INV-9) never picks a side.
        touches_transition = (
            reynolds.hi >= _RE_LAMINAR_CEILING and reynolds.lo <= _RE_TURBULENT_FLOOR
        )
        if touches_transition:
            return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0, in_domain=False))

        # Worst corner (INV-9): f decreases with Re and increases with
        # relative roughness in both closed forms, so the conservative
        # (largest) f comes from the SMALLEST Re and LARGEST roughness.
        re_worst = reynolds.lo
        rr_worst = relative_roughness.hi

        if reynolds.hi < _RE_LAMINAR_CEILING:
            f = _laminar(re_worst)
            eps = 0.0
        else:
            f = _haaland(re_worst, rr_worst)
            eps = f * _HAALAND_VS_COLEBROOK_FRACTION

        return Ok(Prediction(value=f, eps=eps, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "FrictionFactorModel"]
