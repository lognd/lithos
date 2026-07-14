"""Closed-form buck-converter efficiency model (WO-26 D105a unblock).

Discharges the corpus's ``require Efficiency: eta`` claim shape
(``examples/tracks/cuprite/buck_converter.cupr``): a sweep-domain claim
(``forall i(out) in [0.2A, i_max]:``, lowered into ``Obligation.sweep``
by D105a) demanding a LOWER bound on efficiency over the whole load
range. This pack was the "buck efficiency" entry on the WO-26 tracked
pack list, blocked until D105a exposed sweep-domain claim lines.

Model (loss bookkeeping, the standard first-order buck budget):

    P_out  = v_out * i_out
    P_cond = r_series * i_out**2      (conduction: FET R_dson + DCR)
    eta    = P_out / (P_out + P_cond + p_fixed)

``p_fixed`` lumps the load-independent losses (switching, gate drive,
controller). Efficiency is quasiconcave in ``i_out`` (fixed losses
dominate at light load, conduction at heavy load), so its minimum over
an interval is NOT provably at a corner by declaration -- ``i_out``
rides the numeric base's grid sweep, honestly recorded per-axis, while
the three provably monotone inputs each contribute their worst corner.
"""

from __future__ import annotations

from collections.abc import Mapping

from regolith.harness.numeric import DECREASING, INCREASING, NumericReducedTierModel
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string. The
# kind names WHAT is claimed (D94): converter power efficiency.
CLAIM_KIND = "elec.converter.efficiency"

# Required inputs (SI: V, A, ohm, W). Public alias (`INPUTS`) so
# `orchestrator.translate`'s call-form route reads the model's own
# input names, one home (F152, the `fluid_pressure_drop` convention).
INPUTS = ("v_out", "i_out", "r_series", "p_fixed")
_INPUTS = INPUTS

# Conservative absolute efficiency error for the neglected switching-
# loss load dependence and AC conduction terms.
_EPS_ETA = 0.02


class BuckEfficiencyModel(NumericReducedTierModel):
    """First-order loss-budget efficiency of a buck converter."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound efficiency claim over the four budget inputs."""
        return ModelSignature(
            name="buck_efficiency_loss_budget",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("buck", "ccm", "loss_budget"),
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
        """Efficiency falls with losses, rises with output voltage.

        ``i_out`` is deliberately ABSENT (quasiconcave, not monotone):
        the base sweeps it on a grid and says so in the coverage.
        """
        return {
            "v_out": INCREASING,
            "r_series": DECREASING,
            "p_fixed": DECREASING,
        }

    @property
    def eps(self) -> float:
        """Fixed conservative absolute efficiency error."""
        return _EPS_ETA

    def evaluate_point(self, inputs: Mapping[str, float]) -> float:
        """The loss-budget efficiency at one pinned operating point."""
        p_out = inputs["v_out"] * inputs["i_out"]
        p_cond = inputs["r_series"] * inputs["i_out"] ** 2
        total = p_out + p_cond + inputs["p_fixed"]
        if total <= 0.0:
            return 0.0
        return p_out / total
