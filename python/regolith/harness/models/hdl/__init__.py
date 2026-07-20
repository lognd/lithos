"""std.hdl: the verilator check-mode HDL-verification model-pack family
(WO-82, D189, AD-19/AD-35; D202 cycle 33 source-generic `hdl.build`).
Digital-track sibling of std.cam.

`hdl.build` registers EXACTLY ONCE (D202): source-generic, it
discharges every non-VHDL request regardless of which extern edge it
came from, with VHDL requests deferring through that same single
instance (no fixture identity to enumerate, no collision to avoid).
`hdl.sim_assert`/`hdl.equiv_directed` still register only for fixtures
with a landed testbench harness (`fixtures.SIMULATED_FIXTURE_IDS` --
`counter` this dispatch, WO-82 ledger names the rest as a scope cut,
not a silent gap).
"""

from __future__ import annotations

from regolith.harness.models.hdl.fixtures import FIXTURES, SIMULATED_FIXTURE_IDS
from regolith.harness.models.hdl.models import (
    HdlBuildModel,
    HdlEquivDirectedModel,
    HdlSimAssertGenericModel,
    HdlSimAssertModel,
)
from regolith.harness.registry import ModelRegistry


# frob:doc docs/modules/py-harness.md#models-hdl-init
# frob:waive TEST001 reason="registration fn, tested via registry build (transitive)"
def register_hdl_models(registry: ModelRegistry) -> None:
    """Register the std.hdl pack: the ONE source-generic `hdl.build`
    model (D202), the ONE source-generic `hdl.sim_assert` model
    (WO-155/D264 -- discharges any request naming a `sim_stimulus`
    payload), plus `hdl.sim_assert`/`hdl.equiv_directed` x every
    SIMULATED fixture (WO-82, unchanged -- the fixture path stays
    real coverage, not retired by the generic model's arrival)."""
    registry.register(HdlBuildModel())
    registry.register(HdlSimAssertGenericModel())
    for fixture in FIXTURES:
        if fixture.fixture_id in SIMULATED_FIXTURE_IDS:
            registry.register(HdlSimAssertModel(fixture))
            registry.register(HdlEquivDirectedModel(fixture))


__all__ = [
    "HdlBuildModel",
    "HdlEquivDirectedModel",
    "HdlSimAssertGenericModel",
    "HdlSimAssertModel",
    "register_hdl_models",
]
