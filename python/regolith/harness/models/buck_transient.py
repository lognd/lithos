"""Closed-form converter settling-time model (WO-26 D102/D105 unblock).

Discharges the corpus's ``require Regulation: transient`` claim shape
(``settles(v(out), to=+-2%, within 500us after load_step)`` in
``examples/tracks/cuprite/buck_converter.cupr``): the D102 CONTAINMENT
form whose acceptance is its own window -- the orchestrator lowers it
to an UPPER bound on settling time (limit = the window duration,
seconds) with the ``to=`` tolerance as an input. This pack was the
"transient" entry on the WO-26 tracked pack list, blocked until D102
gave the claim a typed lowering.

Model (dominant-pole control-loop envelope):

    t_settle = ln(1 / tol) / (2 * pi * f_c)

where ``f_c`` is the loop crossover frequency and ``tol`` the settling
band as a fraction. Settling time shrinks as either grows, so both are
declared monotone-decreasing and contribute their LOW corner (INV-9).
The single-pole idealization under-counts slew/ringing; a conservative
relative eps is charged for it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Prediction
from regolith.harness.numeric import DECREASING, NumericReducedTierModel
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string. The
# kind names WHAT is claimed (D94): output settling time.
CLAIM_KIND = "elec.converter.settling_time"

# Required inputs (Hz, fraction). Public alias (`INPUTS`) so
# `orchestrator.translate`'s call-form route reads the model's own
# input names, one home (F152, the `fluid_pressure_drop` convention).
INPUTS = ("f_c", "tol")
_INPUTS = INPUTS

# Conservative relative error for the single-pole idealization
# (slew limiting, ringing beyond the dominant pole), charged as a
# fraction of the predicted settling time.
_EPS_REL = 0.5


class BuckTransientModel(NumericReducedTierModel):
    """Dominant-pole settling time of a regulated converter output."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound settling-time claim over crossover + tolerance."""
        return ModelSignature(
            name="converter_settling_dominant_pole",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("converter", "control_loop", "dominant_pole"),
        )

    @property
    def version(self) -> str:
        """Model version (bump on any formula/eps change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Closed-form point physics under the numeric sweep: cheap."""
        return 1

    @property
    def monotonicity(self) -> Mapping[str, str]:
        """Settling time falls as bandwidth or the tolerance band grows."""
        return {name: DECREASING for name in _INPUTS}

    @property
    def eps(self) -> float:
        """Relative eps is resolved at estimate time; see `estimate`."""
        return 0.0

    def evaluate_point(self, inputs: Mapping[str, float]) -> float:
        """``t_settle = ln(1/tol) / (2 pi f_c)`` at one pinned point.

        A non-positive crossover or an out-of-(0,1) tolerance has no
        settling time; it evaluates to infinity, which the `estimate`
        override maps to an honest domain error (never a guess and
        never a non-finite float in evidence).
        """
        f_c = inputs["f_c"]
        tol = inputs["tol"]
        if f_c <= 0.0 or tol <= 0.0 or tol >= 1.0:
            return math.inf
        return math.log(1.0 / tol) / (2.0 * math.pi * f_c)

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Charge the relative eps against the base's worst-corner value.

        A non-finite sweep result means some corner fell outside the
        model's meaningful domain: an explicit :class:`DomainError`
        (the registry maps it to indeterminate evidence), never a
        non-finite value entering the content-addressed evidence.
        """
        estimated = super().estimate(request)
        if estimated.is_err:
            return estimated
        prediction = estimated.danger_ok
        if not math.isfinite(prediction.value):
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "settling time is unbounded at a swept corner "
                        "(non-positive crossover or tolerance outside (0, 1))"
                    ),
                )
            )
        return Ok(prediction.model_copy(update={"eps": prediction.value * _EPS_REL}))
