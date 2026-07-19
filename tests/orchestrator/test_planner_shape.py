"""The planner-model shape (WO-26 D105c): one cause home, plan payloads.

Covers: the single `planner(<what>)` formatter, the retrofit customers
(WO-24 binding, WO-35 pin-mux) producing planner-caused lockfile rows
through it, and plan-artifact publication as a content-addressed
`plan`-kind payload (D96 channel) that resolves back out of the store.
"""

from __future__ import annotations

from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.payload_store import PayloadStore
from regolith.orchestrator.planner import PLAN_PAYLOAD_KIND, planner_cause
from regolith.realizer.elec.binding import Bindings, PlannerPin
from regolith.realizer.elec.pinmux import PinAssignment, PinmuxResult


def _bindings() -> Bindings:
    return Bindings(pins=(PlannerPin.caused("mcu", "mcu/stm32g0@1", "blake3:aa"),))


def _pinmux() -> PinmuxResult:
    return PinmuxResult(
        assignments=(PinAssignment.caused("telemetry", "uart2.tx", "pa2"),)
    )


def test_planner_cause_is_the_one_formatter() -> None:
    assert planner_cause("pinmux uart2.tx") == "planner(pinmux uart2.tx)"


def test_binding_rows_are_planner_caused_through_the_formatter() -> None:
    rows = _bindings().lock_rows()
    assert rows == (
        LockRow(
            slot="bind(mcu)",
            value="mcu/stm32g0@1",
            cause="planner(bind mcu)",
        ),
    )


def test_pinmux_rows_are_planner_caused_through_the_formatter() -> None:
    rows = _pinmux().lock_rows()
    assert rows == (
        LockRow(
            slot="pinmux(uart2.tx)",
            value="pa2",
            cause="planner(pinmux uart2.tx)",
        ),
    )


# frob:tests python/regolith/orchestrator/planner.py::PlannerAdapter.plan_bytes
# frob:tests python/regolith/orchestrator/planner.py::PlannerAdapter.publish
# frob:tests python/regolith/realizer/elec/pinmux.py::PinmuxResult.plan_bytes
# frob:tests python/regolith/realizer/elec/binding.py::Bindings.plan_bytes
def test_plan_artifact_publishes_as_a_plan_kind_payload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """publish() content-addresses the plan bytes; the ref resolves."""
    store = PayloadStore(str(tmp_path))
    plan = _pinmux()
    ref = plan.publish(store)
    assert ref.kind == PLAN_PAYLOAD_KIND
    assert ref.origin == "pinmux"
    resolved = store.resolve(ref.digest)
    assert resolved.is_ok
    assert resolved.danger_ok == plan.plan_bytes()


def test_plan_publication_is_deterministic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The same plan publishes under the same digest (INV-10)."""
    store = PayloadStore(str(tmp_path))
    first = _bindings().publish(store)
    second = _bindings().publish(store)
    assert first.digest == second.digest
