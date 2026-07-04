"""Closed-form RF link-budget model (Kestrel downlink margin).

Discharges the corpus's link-budget claim -- ``require Link: margin:
comms.pa_out + antenna.gain - path_loss(...) >= gs.sensitivity + 6dB``
in ``examples/cubesat/kestrel.cupr`` (the UHF downlink must close with at
least 6 dB of margin over the ground station's sensitivity). The spec
notes this stays honestly indeterminate until flatsat range-test
evidence; this pack computes the numeric budget so it CAN discharge once
the orchestrator resolves the dB terms (see the tracked gap below).

Model (decibel power balance, all terms already unit-reconciled to
dBm / dBi / dB by the core qty crate, AD-9):

    P_rx   = pa_out + gain - path_loss           (received power, dBm)
    margin = P_rx - sensitivity                  (link margin, dB)

The claim is a LOWER bound: ``margin >= margin_req`` (the limit -- the
6 dB the mission demands). The neglected implementation, pointing, and
polarization losses are charged into ``eps`` as a conservative fixed dB
budget, exactly as ``buck_ripple`` charges its ESR term.

Corner conservatism (INV-9): the margin shrinks with lower transmit
power / antenna gain, higher path loss, and higher (less sensitive)
receiver threshold, but rather than hand-prove the monotonicity the model
evaluates ALL 2**k interval corners in numpy and takes the WORST (min) --
sound for any interval box.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Ok, Result

from rockhead.harness.errors import HarnessError
from rockhead.harness.model import DischargeRequest, Model, Prediction
from rockhead.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string.
CLAIM_KIND = "elec.link.margin"

# Required inputs (dB-domain: dBm, dBi, dB, dBm).
_INPUTS = ("pa_out", "gain", "path_loss", "sensitivity")

# Conservative fixed dB budget for the neglected implementation /
# pointing / polarization losses, charged downward against the margin.
_EPS_DB = 2.0


class LinkBudgetModel(Model):
    """Closed-form decibel link margin of an RF downlink."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound link-margin claim over the four dB-domain inputs."""
        return ModelSignature(
            name="link_budget_margin_db",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("rf", "link_budget", "decibel", "impl_loss_charged"),
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
        """Evaluate worst-corner link margin over the interval-boxed inputs.

        The dB terms are unbounded reals (no positivity domain), so every
        request is in-domain; the corner sweep alone drives conservatism.
        """
        pa_out = request.inputs["pa_out"]
        gain = request.inputs["gain"]
        path_loss = request.inputs["path_loss"]
        sensitivity = request.inputs["sensitivity"]

        # Cartesian product of the (deduplicated) corners, evaluated in
        # numpy: sound worst-case over the interval box (INV-9).
        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (pa_out, gain, path_loss, sensitivity)
        ]
        worst = np.inf
        for pa, g, pl, sens in itertools.product(*axes):
            p_rx = pa + g - pl
            margin = p_rx - sens
            worst = min(worst, float(margin))

        return Ok(Prediction(value=worst, eps=_EPS_DB, coverage=1.0, in_domain=True))
