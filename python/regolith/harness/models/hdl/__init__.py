"""std.hdl: the verilator check-mode HDL-verification model-pack family
(WO-82, D189, AD-19/AD-35). Digital-track sibling of std.cam.

`hdl.build` registers for every non-VHDL `examples/hdl/` fixture
(generic verilate/lint); `hdl.sim_assert`/`hdl.equiv_directed` register
only for fixtures with a landed testbench harness
(`fixtures.SIMULATED_FIXTURE_IDS` -- `counter` this dispatch, WO-82
ledger names the rest as a scope cut, not a silent gap). VHDL
(`fsm_traffic`) registers `hdl.build` too -- its `estimate` always
defers with the named "no VHDL frontend" reason, so the model is
present (satisfying "every fixture discharges through the pack, or
defers with a named reason") without special-casing the registry.
"""

from __future__ import annotations

from regolith.harness.models.hdl.fixtures import FIXTURES, SIMULATED_FIXTURE_IDS
from regolith.harness.models.hdl.models import (
    HdlBuildModel,
    HdlEquivDirectedModel,
    HdlSimAssertModel,
)
from regolith.harness.registry import ModelRegistry


def register_hdl_models(registry: ModelRegistry) -> None:
    """Register the std.hdl pack: `hdl.build` x every fixture, plus
    `hdl.sim_assert`/`hdl.equiv_directed` x every SIMULATED fixture."""
    for fixture in FIXTURES:
        registry.register(HdlBuildModel(fixture))
        if fixture.fixture_id in SIMULATED_FIXTURE_IDS:
            registry.register(HdlSimAssertModel(fixture))
            registry.register(HdlEquivDirectedModel(fixture))


__all__ = [
    "HdlBuildModel",
    "HdlEquivDirectedModel",
    "HdlSimAssertModel",
    "register_hdl_models",
]
