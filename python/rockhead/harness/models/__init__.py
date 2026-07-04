"""Shipped model packs and the one registration point.

Each pack is a :class:`rockhead.harness.model.Model` subclass; new packs
register here so ``harness.registry.default_registry`` picks them up. The
FIRST pack (buck output-voltage ripple) is the reference implementation;
the remaining corpus claims are tracked extension points below.
"""

from __future__ import annotations

from rockhead.harness.models.buck_ripple import BuckRippleModel
from rockhead.harness.registry import ModelRegistry


def register_all(registry: ModelRegistry) -> None:
    """Register every shipped model pack into ``registry``."""
    registry.register(BuckRippleModel())
    # TODO(harness): bolted-joint preload diagram (VDI 2230) -- discharges
    #   mech joint-separation / bolt-stress claims (Phase D, roadmap 12).
    # TODO(harness): Euler-Bernoulli beam -- deflection/first-mode claims.
    # TODO(harness): thick-wall Lame -- press-fit/pressure-vessel stress.
    # TODO(harness): sheet-metal DFM rule pack -- min bend radius, hole
    #   spacing (Phase C, roadmap 10); planner-evidence shaped.
    # TODO(harness): link budget -- elec dB power/margin claims (uses the
    #   rockhead-qty dB log views, FE-1); lower-bound sense.
    # TODO(harness): buck efficiency (eta) + transient (settling) claims --
    #   the other two Regulation/Efficiency claims of buck_converter.cupr.


__all__ = ["BuckRippleModel", "register_all"]
