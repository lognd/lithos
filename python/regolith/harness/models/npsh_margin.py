"""Closed-form pump NPSH margin model (WO-110 deliverable 4).

Discharges the fluid corpus's cavitation-headroom claim --
``npsh: fluids.npsh_margin(pump) > 1.5m`` (cnc_router_r1 `coolant.fluo`,
espresso_machine `brew_water.fluo`, small_office `hydronics.fluo`,
dune_buggy `cooling.fluo`, the fluorite tracks corpus): the net
positive suction head AVAILABLE at the pump inlet must exceed the
pump's REQUIRED NPSH by the claimed margin, or the impeller cavitates.

Model (White, Fluid Mechanics, 8th ed., ch. 11 Turbomachinery, the
standard NPSH energy balance from the supply free surface to the pump
inlet):

    NPSHa   = (p_supply - p_vapor) / (rho * g) + z_static - h_friction
    margin  = NPSHa - NPSHr

``p_supply`` is the ABSOLUTE pressure on the supply free surface (Pa),
``p_vapor`` the liquid's vapor pressure at the working temperature
(Pa, a steam-table/property-record datum), ``z_static`` the height of
the supply surface ABOVE the pump inlet (m; negative = suction lift),
``h_friction`` the suction-line head loss (m), and ``NPSHr`` the
pump's required NPSH at the operating point (m, a manufacturer-curve
datum). ``g`` is standard gravity, 9.80665 m/s^2 (exact by
definition). Every input is DECLARED data (property records, pump
curve, suction-line hydraulics folded upstream, the same "declared,
not derived" posture `fluids.dp` takes), so ``eps`` is zero.

The claim is a LOWER bound: ``margin >= <limit>``. Corner conservatism
(INV-9): margin falls with lower supply pressure, higher vapor
pressure, lower static head, higher friction loss, higher NPSHr, and
moves non-monotonically with density only through the pressure term --
rather than hand-prove monotonicity the model evaluates ALL 2**k
interval corners in numpy and takes the WORST (min), exactly the
`bearing_life` posture.
"""

from __future__ import annotations

import itertools

import numpy as np
from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges (the fluorite call name
# itself, `fluids.npsh_margin(...)` -- matched via the same non-frame
# call-form dispatch `fluids.dp` uses). One home for the string.
CLAIM_KIND = "fluids.npsh_margin"

# Required inputs (SI base units: Pa, Pa, kg/m**3, m, m, m). Public:
# the translate router names these in an honest
# `fluids.npsh_margin_inputs_missing` deferral, the house convention.
INPUTS = (
    "p_supply_pa",
    "p_vapor_pa",
    "density_kgm3",
    "z_static_m",
    "h_friction_m",
    "npshr_m",
)
_INPUTS = INPUTS

# Standard gravity (m/s^2), exact by definition (CGPM 1901).
_G = 9.80665


class NpshMarginModel(Model):
    """Closed-form NPSH available-minus-required margin (lower bound)."""

    @property
    def signature(self) -> ModelSignature:
        """Lower-bound margin claim over the six suction-side inputs."""
        return ModelSignature(
            name="fluids_npsh_margin_energy_balance",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.lower_bound(),
            inputs=_INPUTS,
            domain=("pump", "suction", "incompressible", "steady"),
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
        """Evaluate worst-corner NPSH margin over the interval box."""
        p_supply = request.inputs["p_supply_pa"]
        p_vapor = request.inputs["p_vapor_pa"]
        density = request.inputs["density_kgm3"]
        z_static = request.inputs["z_static_m"]
        h_friction = request.inputs["h_friction_m"]
        npshr = request.inputs["npshr_m"]

        # Domain: a liquid has strictly positive density and a
        # non-negative vapor pressure; supply pressure is absolute
        # (strictly positive); friction loss and NPSHr are non-negative.
        if density.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"density must be strictly positive: lo={density.lo}",
                )
            )
        if p_supply.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        "p_supply_pa is ABSOLUTE and must be strictly "
                        f"positive: lo={p_supply.lo}"
                    ),
                )
            )
        if p_vapor.lo < 0.0 or h_friction.lo < 0.0 or npshr.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=("p_vapor_pa/h_friction_m/npshr_m must be non-negative"),
                )
            )

        axes = [
            np.array(sorted(set(iv.corners())), dtype=np.float64)
            for iv in (p_supply, p_vapor, density, z_static, h_friction, npshr)
        ]
        worst = np.inf
        for ps, pv, rho, z, hf, req in itertools.product(*axes):
            npsha = (ps - pv) / (rho * _G) + z - hf
            worst = min(worst, float(npsha - req))
        return Ok(Prediction(value=worst, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "INPUTS", "NpshMarginModel"]
