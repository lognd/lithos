"""Closed-form Euler-Bernoulli cantilever bending model.

Discharges the corpus's beam deflection claim -- ``require Structural:
sag: mech.deflection(formed.flange.tip, ...) < 0.2mm`` in
``examples/tracks/hematite/sheet_bracket.hema`` (a sensor pad on a cantilevered
sheet-metal flange whose tip must not sag beyond the limit under the
interface load).

Model (Euler-Bernoulli cantilever, end point load ``F``):

    delta = F * L**3 / (3 * E * I)                (tip deflection)

The claim is an UPPER bound: ``delta <= delta_max`` (the limit). Shear
(Timoshenko) deflection is neglected -- valid for a slender beam -- and
that neglected term is charged into ``eps`` as a conservative relative
error, exactly as ``buck_ripple`` charges its ESR term.

Corner conservatism (INV-9): deflection grows with larger force and
length and smaller modulus and second moment of area, but rather than
hand-prove the monotonicity the model evaluates ALL 2**k interval
corners in numpy and takes the WORST (max) -- sound for any interval box.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "mech.beam.cantilever_deflection"

# Required inputs (SI base units: N, m, Pa, m**4).
_INPUTS = ("force", "length", "e_modulus", "i_area")

# Conservative relative error for the neglected shear-deflection term.
_EPS_REL = 0.05


class BeamBendingModel(Model):
    """Closed-form tip deflection of an end-loaded cantilever beam."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound deflection claim over the four beam inputs."""
        return ModelSignature(
            name="beam_cantilever_deflection_eb",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("beam", "cantilever", "euler_bernoulli", "shear_neglected"),
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
        """Evaluate worst-corner tip deflection over the interval-boxed inputs."""
        force = request.inputs["force"]
        length = request.inputs["length"]
        e_modulus = request.inputs["e_modulus"]
        i_area = request.inputs["i_area"]

        # Domain: geometry and stiffness are strictly positive; a
        # non-negative load is required (the beam pushes one way).
        if min(length.lo, e_modulus.lo, i_area.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="length, E, and I must be strictly positive",
                )
            )
        if force.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"force must be non-negative: force.lo={force.lo}",
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (force, length, e_modulus, i_area)
        ]
        worst = 0.0
        for f, ell, e_mod, inertia in itertools.product(*axes):
            delta = f * ell**3 / (3.0 * e_mod * inertia)
            worst = max(worst, float(delta))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
