"""Closed-form embedded-post depth adequacy model (WO-85/D194).

Discharges the corpus's `civil.embedment(<post>) >= <depth bound>`
claim (calcite/03 sec. 5; pole_barn.calx's `frost:` line) -- the
`civil.bearing_pressure` reaction-based closed-form PATTERN: the
claimed quantity is the post's DECLARED embedment depth (the
`EmbeddedPost(depth=...)` transfer argument, `FrameTransfer.depth`,
SCHEMA 27), and the limit the harness charges it against is the
GOVERNING lower bound -- the claim's own written bound (frost depth)
folded with the code-required depth from lateral/moment demand at
grade (nonconstrained-earth closed form, the IBC 1807.3-family
formula `d = A/2 * (1 + sqrt(1 + 4.36*h/A))`), whichever is deeper.
The fold happens in `orchestrator/translate.py` (`_translate_civil_
embedment`, the same translator-does-the-arithmetic posture
`_translate_civil_utilization` uses); the `required_depth` input is
carried here so the evidence record shows BOTH numbers, not just the
folded limit.

v1 demand honesty: the calcite load vocabulary is gravity-only
(`FrameLoad.direction` is `"gravity"` in every lowered payload), so
the resolvable lateral demand at grade is exactly zero and the
required-from-demand term degenerates to 0 -- the model's domain tags
say so. When a lateral load vocabulary lands, the translator's
closed form picks it up without touching this model.

Corner conservatism (INV-9): the claim is a LOWER bound (deeper is
safer), so the conservative prediction is the MINIMUM declared-depth
corner; `eps` is zero because the declared depth is a datum read off
the design, not a computed estimate (the required-depth side's
conservatism lives in the limit fold, upstream).
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges.
CLAIM_KIND = "civil.embedment"

# Required inputs (SI base units: m, m).
_INPUTS = ("declared_depth", "required_depth")


class PostEmbedmentModel(Model):
    """Declared embedment depth vs the governing required depth."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound depth claim (`>= <bound>`) over the two depths."""
        return ModelSignature(
            name="post_embedment_declared_vs_required",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("embedded_post", "nonconstrained_earth", "gravity_only_demand"),
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
        """Predict the conservative (minimum-corner) declared depth."""
        declared = request.inputs["declared_depth"]
        required = request.inputs["required_depth"]

        if declared.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"declared_depth must be strictly positive: "
                        f"lo={declared.lo}"
                    ),
                )
            )
        if required.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"required_depth must be non-negative: lo={required.lo}",
                )
            )

        # Lower-bound sense: the conservative corner is the SHALLOWEST
        # declared depth (INV-9); eps = 0 -- a declared datum carries
        # no model error (the demand-side conservatism is folded into
        # the limit by the translator).
        return Ok(Prediction(value=declared.lo, eps=0.0, coverage=1.0, in_domain=True))
