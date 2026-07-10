"""Shipped model packs and the one registration point.

Each pack is a :class:`regolith.harness.model.Model` subclass; new packs
register here so ``harness.registry.default_registry`` picks them up. The
FIRST pack (buck output-voltage ripple) is the reference implementation;
the remaining corpus claims are tracked extension points below.
"""

from __future__ import annotations

from regolith.harness.models.beam_bending import BeamBendingModel
from regolith.harness.models.beam_service_deflection import BeamServiceDeflectionModel
from regolith.harness.models.beam_utilization import BeamUtilizationModel
from regolith.harness.models.bearing_life import BearingL10HoursModel
from regolith.harness.models.bolted_joint import BoltedJointModel
from regolith.harness.models.buck_efficiency import BuckEfficiencyModel
from regolith.harness.models.buck_ripple import BuckRippleModel
from regolith.harness.models.buck_transient import BuckTransientModel
from regolith.harness.models.cam import register_cam_models
from regolith.harness.models.conformance import ConformanceRefinementModel
from regolith.harness.models.cost_estimators import (
    CostCivilTakeoffModel,
    CostElecBomModel,
    CostFluidBomModel,
)
from regolith.harness.models.lame_cylinder import LameCylinderModel
from regolith.harness.models.link_budget import LinkBudgetModel
from regolith.harness.models.lumped_thermal import LumpedThermalModel
from regolith.harness.models.sheet_bend import SheetBendModel
from regolith.harness.models.tolerance_stack import ToleranceStackModel
from regolith.harness.models.workload_realization import WorkloadRealizationModel
from regolith.harness.registry import ModelRegistry


def register_all(registry: ModelRegistry) -> None:
    """Register every shipped model pack into ``registry``."""
    registry.register(BuckRippleModel())
    registry.register(BoltedJointModel())
    # Thin in-tree ISO 281:2007 basic-L10 model (coordinator wiring
    # dispatch, WO-72 close-out): feldspar's own bearing_life route is
    # not exposed through the plugin seam today (see the model's own
    # module doc for the checked-and-not-taken feldspar route).
    registry.register(BearingL10HoursModel())
    registry.register(BeamBendingModel())
    # WO-48 slice C: civil frame-member closed-form models (utilization
    # + service deflection) -- enough for the calcite corpus's non-FEA
    # claims; feldspar's direct-stiffness `mech.struct` consumption of
    # the frame IR is separate, feldspar-side follow-up.
    registry.register(BeamUtilizationModel())
    registry.register(BeamServiceDeflectionModel())
    registry.register(LinkBudgetModel())
    registry.register(LameCylinderModel())
    registry.register(SheetBendModel())
    registry.register(ToleranceStackModel())
    # The conformance-refinement pair (INV-13 discharge half): one model
    # per refinement direction, keyed by its own conformance claim kind.
    registry.register(ConformanceRefinementModel(upper=True))
    registry.register(ConformanceRefinementModel(upper=False))
    # EOPEN-15 rule 3 / INV-26 derived-workloads default: the identity
    # discharge for a derived realization edge (declared edges defer
    # honestly -- see regolith.harness.models.workload_realization).
    registry.register(WorkloadRealizationModel())
    # The WO-26 D105a/D102 unblocks: the remaining tracked buck claims
    # (Efficiency.eta over its load sweep; Regulation.transient's
    # settles() containment) plus the D105b reduced-tier reference.
    registry.register(BuckEfficiencyModel())
    registry.register(BuckTransientModel())
    registry.register(LumpedThermalModel())
    # WO-54 deliverable 5 (D147, toolchain/27 sec. 1.4): the std.cost
    # reference estimators -- three models competing under the ONE
    # `mfg.cost` claim kind, disambiguated by the per-basis payload
    # ports the orchestrator's cost staging publishes.
    registry.register(CostElecBomModel())
    registry.register(CostFluidBomModel())
    registry.register(CostCivilTakeoffModel())
    # WO-67 (AD-35, D175): std.cam CAM-verification check-mode pack --
    # five models x two dialects (gcode_fanuc, gcode_marlin).
    register_cam_models(registry)


__all__ = [
    "BeamBendingModel",
    "BeamServiceDeflectionModel",
    "BeamUtilizationModel",
    "BearingL10HoursModel",
    "BoltedJointModel",
    "BuckEfficiencyModel",
    "BuckRippleModel",
    "BuckTransientModel",
    "ConformanceRefinementModel",
    "CostCivilTakeoffModel",
    "CostElecBomModel",
    "CostFluidBomModel",
    "LameCylinderModel",
    "LinkBudgetModel",
    "LumpedThermalModel",
    "SheetBendModel",
    "ToleranceStackModel",
    "WorkloadRealizationModel",
    "register_all",
]
