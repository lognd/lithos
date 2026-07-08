"""Closed-form thick-walled cylinder (Lame) bore-stress model.

Discharges the corpus's thick-wall pressure claim -- ``require
Structural: hoop: peak(mech.stress.von_mises, during
boundary.chamber_pressure) < material.sigma_y(T_local) / 2.0`` in
``examples/mech/torch_igniter.hema`` (the combustion chamber wall, a
thick-walled cylinder under internal chamber pressure, whose peak
von-Mises stress at the bore must stay below half the local yield).

Model (Lame thick-walled cylinder, internal pressure ``p``, open ends
so the axial stress is neglected -> plane stress at the bore ``r = a``):

    sigma_theta = p * (b**2 + a**2) / (b**2 - a**2)   (hoop, tensile)
    sigma_r     = -p                                  (radial, compressive)
    sigma_vm    = sqrt(sigma_theta**2 - sigma_theta*sigma_r + sigma_r**2)

with inner radius ``a`` and outer radius ``b`` (``sigma_z = 0``). The
peak von-Mises stress is at the bore, so the model evaluates there.

The claim is an UPPER bound: ``sigma_vm <= sigma_limit`` (the limit --
``sigma_y / 2``). The neglected terms (a capped end's axial stress and
bore stress concentration) are charged into ``eps`` as a conservative
relative error, exactly as ``buck_ripple`` charges its ESR term.

Corner conservatism (INV-9): the bore stress grows with higher pressure
and a thinner wall (smaller ``b`` relative to ``a``), but rather than
hand-prove the monotonicity the model evaluates ALL 2**k interval
corners in numpy and takes the WORST (max) -- sound for any interval box.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "mech.cylinder.lame_bore_stress"

# Required inputs (SI base units: Pa, m, m).
_INPUTS = ("pressure", "r_inner", "r_outer")

# Conservative relative error for the neglected axial (capped-end) stress
# and bore stress-concentration terms.
_EPS_REL = 0.05


class LameCylinderModel(Model):
    """Closed-form peak von-Mises bore stress of a thick-walled cylinder."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound bore-stress claim over the three cylinder inputs."""
        return ModelSignature(
            name="lame_cylinder_bore_stress",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("cylinder", "thick_wall", "lame", "open_end", "axial_charged"),
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
        """Evaluate worst-corner bore von-Mises stress over the interval box."""
        pressure = request.inputs["pressure"]
        r_inner = request.inputs["r_inner"]
        r_outer = request.inputs["r_outer"]

        # Domain: a real thick-walled cylinder has strictly positive radii
        # with the whole outer range above the whole inner range (a valid
        # wall at every corner), and a non-negative internal pressure.
        if r_inner.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"inner radius must be strictly positive: "
                        f"r_inner.lo={r_inner.lo}"
                    ),
                )
            )
        if r_outer.lo <= r_inner.hi:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"outer radius must exceed inner radius over the whole box: "
                        f"r_outer.lo={r_outer.lo} <= r_inner.hi={r_inner.hi}"
                    ),
                )
            )
        if pressure.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"pressure must be non-negative: pressure.lo={pressure.lo}",
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (pressure, r_inner, r_outer)
        ]
        worst = 0.0
        for p, a, b in itertools.product(*axes):
            sigma_theta = p * (b**2 + a**2) / (b**2 - a**2)
            sigma_r = -p
            sigma_vm = math.sqrt(sigma_theta**2 - sigma_theta * sigma_r + sigma_r**2)
            worst = max(worst, float(sigma_vm))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
