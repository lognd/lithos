"""Closed-form beam demand/capacity utilization model.

Discharges the corpus's `civil.utilization(member, under=combo)` claim
(calcite/03 sec. 5) -- ``require Structure: strength:
civil.utilization(Bridge.members.all, under=combo) <= 1.0`` in every
calcite-track corpus design (footbridge/pole_barn/retaining_wall/
bus_shelter/small_office). v1 is the simple beam-column interaction
subset: combined bending + axial utilization against an allowable
stress, per the AISC/NDS allowable-stress format the corpus's
`std.civil.aisc.strength`/`std.civil.nds.strength` combination sets
already assume (`stdlib/std.civil/records/combinations.toml`).

Model (elastic beam-column interaction, no second-order amplification):

    utilization = |M| / (Z * Fy) + |P| / (A * Fy)

``M`` is the factored bending demand, ``P`` the factored axial demand,
``Z`` the section modulus, ``A`` the section area, ``Fy`` the material
yield/reference stress -- the frame IR's per-member ``section``/
``material`` refs resolve to these scalars upstream (orchestrator/
registry territory, not this model's; see the WO-48 close-out note on
frame-payload-to-scalar extraction being deferred integration work).

Corner conservatism (INV-9): utilization grows with larger demand and
smaller section/material capacity -- rather than hand-prove the
monotonicity the model evaluates every interval corner and takes the
WORST (max), the ``beam_bending`` precedent.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges.
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "civil.utilization"

# Required inputs (SI base units: N*m, N, m**3, m**2, Pa).
_INPUTS = ("moment_demand", "axial_demand", "section_modulus", "area", "fy")

# Conservative relative error: the neglected second-order (P-delta)
# amplification and shear-interaction terms.
_EPS_REL = 0.08


# frob:doc docs/modules/py-harness.md#models
class BeamUtilizationModel(Model):
    """Closed-form combined bending + axial demand/capacity ratio."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound utilization claim (`<= 1.0`) over five scalar inputs."""
        return ModelSignature(
            name="beam_utilization_interaction",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("beam", "beam_column", "elastic", "no_second_order"),
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

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner interaction utilization over the interval box."""
        moment = request.inputs["moment_demand"]
        axial = request.inputs["axial_demand"]
        z_mod = request.inputs["section_modulus"]
        area = request.inputs["area"]
        f_y = request.inputs["fy"]

        # Domain: section/material capacities are strictly positive.
        if min(z_mod.lo, area.lo, f_y.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="section_modulus, area, and fy must be strictly positive",
                )
            )

        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (moment, axial, z_mod, area, f_y)
        ]
        worst = 0.0
        for m_demand, p_demand, z, a, fy in itertools.product(*axes):
            utilization = abs(m_demand) / (z * fy) + abs(p_demand) / (a * fy)
            worst = max(worst, float(utilization))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
