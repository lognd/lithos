"""Closed-form bolted-joint preload model (VDI 2230 load-sharing).

Discharges the corpus's bolted-joint separation claim -- a preloaded
joint (the ``BoltedFlange`` / ``BoltedPattern`` matings of
``examples/tracks/hematite/torch_igniter.hema``, whose ``require Seal`` depends on
the flange staying clamped, and the stacked ``StackMate`` cards of
``examples/flagships/cubesat``) must keep a residual clamp force above the demanded
minimum under the worst external load, or the joint opens.

Model (VDI 2230 joint-stiffness diagram, concentric axial load):

    phi   = k_bolt / (k_bolt + k_clamp)          (load factor)
    F_KR  = F_M - (1 - phi) * F_A                 (residual clamp force)

``F_KR`` is what still clamps the members after the external axial load
``F_A`` steals part of the preload ``F_M``; the joint separates when it
reaches zero, so the claim is a LOWER bound: ``F_KR >= F_Kreq`` (the
limit -- the clamp a seal / friction grip demands).

Corner conservatism (INV-9): ``F_KR`` shrinks with lower preload, higher
external load, and a lower load factor (softer bolt / stiffer members),
but rather than hand-prove the monotonicity the model evaluates ALL
2**k interval corners in numpy and takes the WORST (min) -- sound for any
interval box. Embedding / preload relaxation (the neglected setting loss)
is charged into ``eps`` as a conservative fraction of the preload.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "mech.bolt.joint_separation"

# Required inputs (SI base units: N, N, N/m, N/m). Public so the
# orchestrator's translate routing can build a matching `inputs` dict
# without duplicating the field-name list (D94-adjacent: one home).
INPUTS = ("f_preload", "f_external", "k_bolt", "k_clamp")
_INPUTS = INPUTS

# Conservative embedding / preload-relaxation loss, as a fraction of the
# worst-corner preload, charged downward against the residual clamp.
_EPS_REL = 0.10


class BoltedJointModel(Model):
    """Closed-form residual clamp force of a preloaded bolted joint."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound residual-clamp claim over the four joint inputs."""
        return ModelSignature(
            name="bolted_joint_separation_vdi2230",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("bolted", "concentric", "vdi2230", "embedding_charged"),
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
        """The module doc's load-sharing source."""
        return "VDI 2230 joint-stiffness diagram, concentric axial load"

    @property
    def input_units(self) -> dict[str, str]:
        """SI base units this model's four inputs carry (module doc line 42)."""
        return {
            "f_preload": "N",
            "f_external": "N",
            "k_bolt": "N/m",
            "k_clamp": "N/m",
        }

    @property
    def output_unit(self) -> str | None:
        """``F_KR``, the residual clamp force, is a force in newtons."""
        return "N"

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Evaluate worst-corner residual clamp over the interval-boxed inputs."""
        f_preload = request.inputs["f_preload"]
        f_external = request.inputs["f_external"]
        k_bolt = request.inputs["k_bolt"]
        k_clamp = request.inputs["k_clamp"]

        # Domain: a real preloaded joint has positive preload and both
        # stiffnesses strictly positive; the external load may be zero.
        if f_preload.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"preload must be strictly positive: "
                        f"f_preload.lo={f_preload.lo}"
                    ),
                )
            )
        if min(k_bolt.lo, k_clamp.lo) <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="k_bolt and k_clamp must be strictly positive",
                )
            )
        if f_external.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"external load must be non-negative: "
                        f"f_external.lo={f_external.lo}"
                    ),
                )
            )

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (f_preload, f_external, k_bolt, k_clamp)
        ]
        worst = np.inf
        for f_m, f_a, kb, kc in itertools.product(*axes):
            phi = kb / (kb + kc)
            f_kr = f_m - (1.0 - phi) * f_a
            worst = min(worst, float(f_kr))

        # Embedding loss is charged against the smallest preload corner.
        eps = _EPS_REL * float(min(axes[0]))
        return Ok(Prediction(value=worst, eps=eps, coverage=1.0, in_domain=True))
