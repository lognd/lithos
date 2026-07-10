"""Closed-form footing bearing-pressure model (cycle 33/D196 close-out).

Discharges the corpus's `civil.bearing_pressure(<footing>) <= <soil
allowable>` claim (calcite/03 sec. 5 -- every calcite-track corpus
design's `bearing:` row) with the reaction-based closed-form pattern
`civil.embedment`/`post_embedment.py` already set (D194/WO-85): the
claimed quantity is the footing's resolved support REACTION (the
gravity load-path reaction the frame's incoming `Pinned`/`Moment`/
`BasePlate` transfers deliver into the footing joint -- the same
reaction machinery `frame_resolve._axial_demand` folds for columns,
generalized in `frame_resolve.support_reaction_n` to any transfer
TARGET, not only column-role members) divided by the footing's
declared bearing AREA, compared against the allowable pressure from
the claim's own comparator (`site.soil.bearing` / `<structure>.soil.
bearing`, a std.civil soil record's declared allowable interval).

Two inputs this v1 model demands genuinely do not resolve in the
current corpus (named here, not fabricated -- the translator defers
by name rather than passing a fake value through):

- The comparator bound: `civil.embedment`'s `site.<datum>` bound
  literalizes at the RUST lowering layer (`claims.rs`'s
  `resolve_embedment_site_bound`, embedment-only); `civil.
  bearing_pressure`'s bound never goes through that substitution, so
  `site.soil.bearing`/`<structure>.soil.bearing` stays symbolic text
  at this (Python, orchestrator) layer -- `_translate_civil_bearing`
  defers `unresolved_limit` when the bound is not already a literal.
- The footing's bearing area: `FramePayload.transfers` carries a
  generic `tributary: area` field (`FrameTransfer.tributary`,
  SCHEMA_VERSION 27) but calcite's `std.civil` connection-class
  vocabulary declares it ONLY on `Bearing<tributary: area>`
  (`stdlib/std.civil/transfers.hema`) -- the column-to-footing
  connection every corpus design uses is `BasePlate<anchors: string>`,
  which the pack does not (yet) let carry a bearing-area parameter.
  This model still reads any `tributary` value an incoming transfer
  DOES carry (forward-compatible, zero-risk: it costs nothing to
  honor the field if a future design/pack revision populates it), but
  when none does, the translator defers `footing_area_undeclared`
  naming exactly that gap -- NOT a schema/grammar change (out of this
  slice's Python-only, no-SCHEMA_VERSION-bump scope; escalate to a
  future WO widening `std.civil`'s `BasePlate` mating class).

Corner conservatism (INV-9): pressure grows with a LARGER reaction and
a SMALLER area, so the worst corner is `reaction.hi / area.lo`; `eps`
is zero because both inputs are exact reads (a resolved reaction sum,
a declared area), with any upstream approximation folded into the
reaction/area resolution itself (the `post_embedment` precedent).
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges.
CLAIM_KIND = "civil.bearing_pressure"

# Required inputs (SI base units: N, m**2).
_INPUTS = ("reaction_n", "area_m2")


class BearingPressureModel(Model):
    """Footing reaction divided by declared bearing area vs allowable."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound pressure claim (`<= <allowable>`) over two inputs."""
        return ModelSignature(
            name="footing_bearing_pressure",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("footing", "bearing_reaction", "gravity_only_demand"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form: the cheapest tier."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the conservative (max-reaction/min-area) bearing pressure."""
        reaction = request.inputs["reaction_n"]
        area = request.inputs["area_m2"]

        if area.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"area_m2 must be strictly positive: lo={area.lo}",
                )
            )
        if reaction.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"reaction_n must be non-negative: lo={reaction.lo}",
                )
            )

        # Upper-bound sense: the conservative corner is the LARGEST
        # reaction over the SMALLEST area (INV-9); eps = 0 -- both
        # inputs are exact reads, not model-side estimates.
        pressure = reaction.hi / area.lo
        return Ok(Prediction(value=pressure, eps=0.0, coverage=1.0, in_domain=True))
