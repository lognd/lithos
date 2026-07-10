"""Lumped-parameter steady-state thermal model (the D105b reference).

The FIRST customer of the reduced-tier numeric base
(:class:`regolith.harness.numeric.NumericReducedTierModel`, WO-26
D105b): a single thermal resistance from a dissipating junction to its
ambient, ``T_junction = T_ambient + P * R_theta`` -- the textbook lumped
steady state every datasheet quotes. The subclass carries ONLY the
point physics and its monotonicity declarations; corners, coverage, and
the margin rule live in the base (NO DUPLICATION).

The claim is an UPPER bound (`thermo.temperature(x) < limit`); the
value grows with all three inputs, so each is declared ``INCREASING``
and contributes exactly its high corner (INV-9 conservatism by
declaration, recorded per-axis as `monotone` coverage).
"""

from __future__ import annotations

from collections.abc import Mapping

from regolith.harness.numeric import INCREASING, NumericReducedTierModel
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this pack discharges. One home for the string. The
# kind names WHAT is claimed (D94): a steady junction temperature.
CLAIM_KIND = "thermo.junction_temperature"

# Required inputs (SI: K, W, K/W). Public so translate.py's call-form
# lowering (thermo.temperature(...) claims) can read the model's own
# input names without duplicating them (NO DUPLICATION).
INPUTS = ("ambient", "power", "r_theta")
_INPUTS = INPUTS

# Conservative fixed error (K) for the neglected radiation/convection
# nonlinearity and interface-resistance scatter.
_EPS_K = 5.0


class LumpedThermalModel(NumericReducedTierModel):
    """Steady lumped junction temperature over one thermal resistance."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound junction-temperature claim over three inputs."""
        return ModelSignature(
            name="thermo_lumped_steady",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("thermal", "lumped", "steady_state"),
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
        """Junction temperature grows with every input."""
        return {name: INCREASING for name in _INPUTS}

    @property
    def eps(self) -> float:
        """Fixed conservative error budget, kelvin."""
        return _EPS_K

    def evaluate_point(self, inputs: Mapping[str, float]) -> float:
        """``T_j = T_amb + P * R_theta`` at one pinned point."""
        return inputs["ambient"] + inputs["power"] * inputs["r_theta"]
