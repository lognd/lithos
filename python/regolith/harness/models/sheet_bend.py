"""Closed-form sheet-metal minimum-bend-radius DFM model.

Discharges the corpus's sheet-metal manufacturability rule -- the
``dfm(min_bend_radius)`` check on ``examples/mech/sheet_bracket.hem``'s
``flange = Bend(edge=..., angle=90deg, radius=free)``, whose ``radius``
must resolve to (or exceed) the press pack's minimum inside bend radius
for the sheet gauge, or the bend cracks / over-thins the outer fibre.

Model (press-pack min-bend-radius rule, an eager DFM check):

    r_min = ratio * thickness                       (minimum inside radius)

where ``ratio`` is the material/process minimum inside-radius-to-thickness
factor the press pack supplies (e.g. ~1.6 for 1.5 mm laser-cut stock, so
r_min = 2.4 mm -- the corpus's resolved value).

The design's specified bend radius is the ``limit``; the claim is an
UPPER bound on the required minimum: ``r_min <= r_specified`` (a bend
whose specified radius is at least the manufacturable minimum passes).
Springback and grain-direction allowance (which can raise the minimum)
are the neglected term, charged into ``eps`` as a conservative relative
error, exactly as ``buck_ripple`` charges its ESR term.

Corner conservatism (INV-9): the required minimum grows with a larger
ratio and a thicker gauge, but rather than hand-prove the monotonicity
the model evaluates ALL 2**k interval corners in numpy and takes the
WORST (max) -- sound for any interval box.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "mech.sheet.min_bend_radius"

# Required inputs (SI base units: m, dimensionless).
_INPUTS = ("thickness", "ratio")

# Conservative relative error for the neglected springback / grain-
# direction allowance, which can raise the manufacturable minimum.
_EPS_REL = 0.10


class SheetBendModel(Model):
    """Closed-form minimum inside bend radius of a sheet-metal bend."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound min-bend-radius claim over the two sheet inputs."""
        return ModelSignature(
            name="sheet_min_bend_radius",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("sheet_metal", "bend", "dfm", "springback_charged"),
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
        """Evaluate worst-corner minimum bend radius over the interval box."""
        thickness = request.inputs["thickness"]
        ratio = request.inputs["ratio"]

        # Domain: a real gauge has strictly positive thickness and the
        # process minimum-radius ratio is strictly positive.
        if thickness.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"thickness must be strictly positive: "
                        f"thickness.lo={thickness.lo}"
                    ),
                )
            )
        if ratio.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"min-radius ratio must be strictly positive: "
                        f"ratio.lo={ratio.lo}"
                    ),
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (thickness, ratio)
        ]
        worst = 0.0
        for t, k in itertools.product(*axes):
            r_min = k * t
            worst = max(worst, float(r_min))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
