"""Ballscrew/leadscrew drive-torque model (motor reflected-load check).

Discharges the mech corpus's `mech.drive_torque` claim --
`cnc_router_r1/axis_module.hema`'s `reserve` claim (`forall ride.pos:
mech.drive_torque(nut, under=boundary.cut_react) <= 0.6 *
motor_a.holding_torque`, the Z-axis leadscrew/motor pairing declared
via `LeadscrewMount`/`vendor(ldo_nema23_3nm)`), waived as `"no
registered harness model for label kind 'reserve' (F126.1 model
gap)"` -- a real harness gap (the sweep is over the machine's config
domain `ride.pos`, not an entity collection, so it does not hit the
D103 entity-derived-bound residual `weldment_frame.hema`'s
`weld_static` waiver names).

Model (vendor/textbook ballscrew driving-torque relation -- Shigley's
Mechanical Engineering Design, 10th ed., ch. 8 sec. 8-1's power-screw
torque-to-thrust form, generalized with a declared mechanical
efficiency in place of the thread-friction-angle term, the same
substitution ballscrew vendor catalogs (e.g. THK/HIWIN "Selection:
Driving Torque") make for a preloaded recirculating-ball nut):

    T_drive = F * lead / (2 * pi * eta) + T_preload_drag

``F`` is the axial thrust the nut must react (the boundary's cutting
reaction), ``lead`` the screw's lead per revolution, ``eta`` the
ballscrew's declared mechanical efficiency (vendor catalog value,
typically 0.85-0.95 for a preloaded double nut -- declared, never
defaulted, D250.3), and ``T_preload_drag`` an optional declared
preload/seal drag torque added directly (defaults to a zero-width
interval so a claim that declares no drag keeps discharging
byte-identically, the same optional-port widening
`fluid_pressure_drop.py`'s WO-140 minor-loss terms use).

Feldspar route (checked, not taken): as of this WO's survey,
feldspar's `crates/feldspar-library/src/mech/` (`frame.rs`,
`sections.rs`, `statics.rs`, `vibration.rs`) carries no leadscrew/
power-screw/drive-sizing module, and no such model is registered
through feldspar's pack seam (`bearing_life.py`'s module doc's own
census of the six feldspar-exposed `regolith.harness` models). The
feldspar-side physics half of WO-111 has not landed for this family
either; this in-tree model is the same honest choice already made
for bearing life and pipe pressure drop.

Corner conservatism (INV-9): the claim is an UPPER bound (`<=`), so
the worst corner is the maximum thrust, maximum lead, MINIMUM
efficiency, and maximum drag torque -- torque grows with each of the
first, third, and fourth and shrinks with efficiency, so no exhaustive
corner search is needed (unlike the fatigue model's non-monotonic
composition); the four-term monotonicity is checked directly.
"""

from __future__ import annotations

import math

from typani.result import Err, Ok, Result

from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.quantity import Interval
from regolith.harness.signature import ClaimSense, ModelSignature

# The registry key this model discharges.
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "mech.drive_torque"

# Required inputs (SI: N, m, --). Public so orchestrator translate
# routing can build a matching `inputs` dict without duplicating the
# field-name list.
# frob:doc docs/modules/py-harness.md#models
INPUTS = ("axial_force_n", "lead_m", "efficiency")
_INPUTS = INPUTS

# Optional preload/seal drag torque (N*m); zero-width when the claim
# declares no drag, so the un-widened case keeps discharging
# byte-identically (same shape as `fluid_pressure_drop.py`'s WO-140
# minor-loss extras).
_ZERO_INTERVAL = Interval(lo=0.0, hi=0.0)


# frob:doc docs/modules/py-harness.md#models
class DriveTorqueModel(Model):
    """Reflected motor torque to drive a ballscrew/leadscrew nut against
    a thrust load."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """Upper-bound drive-torque claim over the three screw inputs."""
        return ModelSignature(
            name="ballscrew_drive_torque",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=_INPUTS,
            domain=("ballscrew_or_leadscrew", "preloaded_nut", "steady_thrust"),
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
        """The module doc's ballscrew driving-torque source."""
        return (
            "Shigley's Mechanical Engineering Design, 10th ed., ch. 8 sec. 8-1 "
            "(power-screw torque), efficiency form"
        )

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the worst-corner (max thrust/lead, min efficiency) drive torque."""
        force = request.inputs["axial_force_n"]
        lead = request.inputs["lead_m"]
        eta = request.inputs["efficiency"]
        drag = request.inputs.get("preload_drag_torque_nm", _ZERO_INTERVAL)

        if force.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"axial_force_n must be non-negative: lo={force.lo}",
                )
            )
        if lead.lo <= 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"lead_m must be strictly positive: lo={lead.lo}",
                )
            )
        if eta.lo <= 0.0 or eta.hi > 1.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"efficiency must lie in (0, 1]: lo={eta.lo}, hi={eta.hi}",
                )
            )
        if drag.lo < 0.0:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"preload_drag_torque_nm must be non-negative: lo={drag.lo}"
                    ),
                )
            )

        torque = force.hi * lead.hi / (2.0 * math.pi * eta.lo) + drag.hi
        return Ok(Prediction(value=torque, eps=0.0, coverage=1.0, in_domain=True))


__all__ = ["CLAIM_KIND", "INPUTS", "DriveTorqueModel"]
