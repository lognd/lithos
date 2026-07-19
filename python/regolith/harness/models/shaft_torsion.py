"""Closed-form uniform-shaft torsion (angle of twist) model (WO-110
deliverable 3).

Discharges the corpus's torsional-stiffness claim -- ``twist:
mech.twist(stock.body, under=...) <= <angle>`` (cnc_router_r1
`gantry_beam.hema`: a box-section gantry beam whose mid-span torsion
under the survey-corner cutting force must stay inside the machine's
kinematic budget).

Model (Shigley's Mechanical Engineering Design, Budynas & Nisbett,
10th ed., ch. 4, torsional deflection of a uniform shaft):

    theta = T * L / (G * J)        (radians)

``T`` is the applied torque (N*m), ``L`` the twisted length (m), ``G``
the shear modulus (Pa, a material-record datum), ``J`` the section's
torsion constant (m^4; the polar second moment for a circular section
-- for thin-wall/open sections the author supplies the section's own
torsion constant, a handbook datum). Every input is DECLARED data, so
``eps`` is zero.

UNIT NOTE (the house `_parse_float` posture): the prediction is in
RADIANS (SI, like every model in this package); a claim bound spelled
in sub-radian units (`0.10 mrad`) parses unitless at translate today
-- the bound-unit resolution gap is escalated in the WO-110 close-out
rather than silently absorbed here (this model never sees such a
claim discharge: the fleet's `twist:` rows defer inputs-missing until
WO-113 declares T/L/G/J).

The claim is an UPPER bound: ``theta <= <limit>``. Corner conservatism
(INV-9): twist grows with higher torque and length and lower modulus
and torsion constant; rather than hand-prove the monotonicity the
model evaluates ALL 2**k interval corners in numpy and takes the WORST
(max), the `beam_bending` posture exactly.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges (the source call name itself,
# `mech.twist(...)`). One home for the string.
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "mech.twist"

# Required inputs (SI base units: N*m, m, Pa, m**4). Public: the
# translate router names these in an honest
# `mech.twist_inputs_missing` deferral, the house convention.
# frob:doc docs/modules/py-harness.md#models
INPUTS = ("torque_nm", "length_m", "g_modulus_pa", "j_torsion_m4")
_INPUTS = INPUTS


# frob:doc docs/modules/py-harness.md#models
class ShaftTorsionModel(Model):
    """Closed-form angle of twist of a uniform shaft (upper bound)."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound twist claim over the four torsion inputs."""
        return ModelSignature(
            name="mech_shaft_twist_uniform",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("shaft", "uniform_section", "linear_elastic"),
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
        """The module doc's torsional-deflection source."""
        return (
            "Shigley's Mechanical Engineering Design (Budynas & Nisbett), "
            "10th ed., ch. 4, theta = TL/(GJ)"
        )

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner twist angle over the interval box."""
        torque = request.inputs["torque_nm"]
        length = request.inputs["length_m"]
        g_modulus = request.inputs["g_modulus_pa"]
        j_torsion = request.inputs["j_torsion_m4"]

        # Domain: stiffness terms are strictly positive; length and
        # torque are non-negative (the twist sense is the claim's).
        if min(g_modulus.lo, j_torsion.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="g_modulus_pa and j_torsion_m4 must be strictly positive",
                )
            )
        if torque.lo < 0.0 or length.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="torque_nm and length_m must be non-negative",
                )
            )

        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (torque, length, g_modulus, j_torsion)
        ]
        worst = 0.0
        for t, ell, g, j in itertools.product(*axes):
            theta = t * ell / (g * j)
            worst = max(worst, float(theta))
        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "INPUTS", "ShaftTorsionModel"]
