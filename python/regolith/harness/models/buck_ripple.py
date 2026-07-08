"""Closed-form buck-converter output-voltage-ripple model (reference pack).

Discharges the corpus claim ``require Regulation: ripple`` in
``examples/tracks/cuprite/buck_converter.cupr`` -- the peak-to-peak output ripple of
a synchronous/CCM buck must stay below a limit. This is the FIRST
closed-form pack and the reference for every later one: signature ->
worst-corner numpy evaluation -> ``Prediction`` -> the shared discharge
rule.

Model (textbook CCM buck, ESR neglected):

    D          = v_out / v_in                      (duty cycle)
    delta_i_L  = v_out * (v_in - v_out) / (v_in * f_sw * L)   (inductor ripple)
    v_ripple   = delta_i_L / (8 * f_sw * C_out)    (capacitor charge ripple)

Corner conservatism (INV-9): ripple grows as f_sw, L, and C_out shrink
and (for fixed v_out) as v_in grows, but rather than hand-prove the
monotonicity the model evaluates ALL 2**k interval corners in numpy and
takes the worst (max) -- sound for any interval box. The ESR term this
neglects is folded into ``eps`` as a conservative relative error.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "elec.buck.output_voltage_ripple"

# Required inputs (SI base units: V, V, Hz, H, F).
_INPUTS = ("v_in", "v_out", "f_sw", "l", "c_out")

# Conservative relative error for the neglected ESR / higher-order terms.
_EPS_REL = 0.05


class BuckRippleModel(Model):
    """Closed-form peak-to-peak output ripple of a CCM buck converter."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound ripple claim over the five converter inputs."""
        return ModelSignature(
            name="buck_output_ripple_ccm",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("buck", "ccm", "esr_neglected"),
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
        """Evaluate worst-corner ripple over the interval-boxed inputs."""
        v_in = request.inputs["v_in"]
        v_out = request.inputs["v_out"]
        f_sw = request.inputs["f_sw"]
        ind = request.inputs["l"]
        c_out = request.inputs["c_out"]

        # Domain: a buck steps DOWN, so v_out must be below the whole v_in
        # range, and every reactive value must be strictly positive.
        if v_out.hi >= v_in.lo:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"not a buck operating point: v_out.hi={v_out.hi} "
                        f">= v_in.lo={v_in.lo}"
                    ),
                )
            )
        if min(f_sw.lo, ind.lo, c_out.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="f_sw, L, and C_out must be strictly positive",
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (v_in, v_out, f_sw, ind, c_out)
        ]
        worst = 0.0
        for vin, vout, fsw, lh, cout in itertools.product(*axes):
            delta_i_l = vout * (vin - vout) / (vin * fsw * lh)
            v_ripple = delta_i_l / (8.0 * fsw * cout)
            worst = max(worst, float(v_ripple))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
