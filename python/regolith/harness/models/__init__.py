"""Shipped model packs and the one registration point.

Each pack is a :class:`regolith.harness.model.Model` subclass; new packs
register here so ``harness.registry.default_registry`` picks them up. The
FIRST pack (buck output-voltage ripple) is the reference implementation;
the remaining corpus claims are tracked extension points below.
"""

from __future__ import annotations

from regolith.harness.models.beam_bending import BeamBendingModel
from regolith.harness.models.bolted_joint import BoltedJointModel
from regolith.harness.models.buck_ripple import BuckRippleModel
from regolith.harness.models.conformance import ConformanceRefinementModel
from regolith.harness.models.lame_cylinder import LameCylinderModel
from regolith.harness.models.link_budget import LinkBudgetModel
from regolith.harness.models.sheet_bend import SheetBendModel
from regolith.harness.models.tolerance_stack import ToleranceStackModel
from regolith.harness.registry import ModelRegistry


def register_all(registry: ModelRegistry) -> None:
    """Register every shipped model pack into ``registry``."""
    registry.register(BuckRippleModel())
    registry.register(BoltedJointModel())
    registry.register(BeamBendingModel())
    registry.register(LinkBudgetModel())
    registry.register(LameCylinderModel())
    registry.register(SheetBendModel())
    registry.register(ToleranceStackModel())
    # The conformance-refinement pair (INV-13 discharge half): one model
    # per refinement direction, keyed by its own conformance claim kind.
    registry.register(ConformanceRefinementModel(upper=True))
    registry.register(ConformanceRefinementModel(upper=False))
    # TODO(harness): buck efficiency (eta) + transient (settling) claims --
    #   the other two Regulation/Efficiency claims of buck_converter.cupr.


__all__ = [
    "BeamBendingModel",
    "BoltedJointModel",
    "BuckRippleModel",
    "ConformanceRefinementModel",
    "LameCylinderModel",
    "LinkBudgetModel",
    "SheetBendModel",
    "ToleranceStackModel",
    "register_all",
]
