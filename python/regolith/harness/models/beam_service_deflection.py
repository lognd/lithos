"""Closed-form simply-supported beam service deflection model.

Discharges the corpus's general `mech.deflection(member, under=case)`
service claim over a frame member (calcite/03 sec. 5) -- distinct from
``beam_bending``'s cantilever-tip model (a sheet-metal flange, not a
framed member): ``deflect: mech.deflection(G1, under=std.civil.aisc.
service) <= G1.span / 360`` in footbridge.calx/small_office/frame.calx;
``deflect: mech.deflection(T1, under=std.civil.nds.service) <= T1.span
/ 240`` in pole_barn.calx.

Model (simply-supported beam, uniformly distributed load ``w`` over
span ``L``, midspan deflection):

    delta = 5 * w * L**4 / (384 * E * I)

Point-load and continuous-span cases are NOT modeled here (a future
pack extension per member end-condition; recorded as a gap, not
faked) -- v1 covers the corpus's uniformly-loaded girder/truss/purlin
claims, the dominant serviceability shape for the five-design corpus.

Corner conservatism (INV-9): deflection grows with larger load and
span and smaller modulus/inertia -- the ``beam_bending`` precedent's
worst-corner evaluation over the interval box.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges.
CLAIM_KIND = "mech.beam.service_deflection"

# Required inputs (SI base units: N/m, m, Pa, m**4).
_INPUTS = ("w_load", "length", "e_modulus", "i_area")

# Conservative relative error for the neglected shear-deflection term
# (same floor as the cantilever model -- valid for a slender beam).
_EPS_REL = 0.05


class BeamServiceDeflectionModel(Model):
    """Closed-form midspan deflection of a uniformly-loaded simple beam."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound deflection claim over the four beam inputs."""
        return ModelSignature(
            name="beam_simple_span_deflection_udl",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("beam", "simple_span", "uniform_load", "shear_neglected"),
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
        """Evaluate worst-corner midspan deflection over the interval box."""
        w_load = request.inputs["w_load"]
        length = request.inputs["length"]
        e_modulus = request.inputs["e_modulus"]
        i_area = request.inputs["i_area"]

        if min(length.lo, e_modulus.lo, i_area.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="length, E, and I must be strictly positive",
                )
            )
        if w_load.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"w_load must be non-negative: w_load.lo={w_load.lo}",
                )
            )

        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (w_load, length, e_modulus, i_area)
        ]
        worst = 0.0
        for w, ell, e_mod, inertia in itertools.product(*axes):
            delta = 5.0 * w * ell**4 / (384.0 * e_mod * inertia)
            worst = max(worst, float(delta))

        eps = _EPS_REL * worst
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
