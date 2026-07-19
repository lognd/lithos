"""Pin-mux matcher: flow demands -> function instances -> package pins.

Spec: cuprite/04 sec. 1 step 2 (NORMATIVE: "pin-mux is a monomorphized
matching problem": the component record declares alternate-function
tables; flows demand bus/timer/ADC/DMA resources; the solver assigns
function instances to ports to pins, subject to ERC ledgers and
routing-quality policy; every assignment is lockfile-caused
(``cause: planner(pinmux <instance>)``); a failed match is a
constructive error naming the contended resource); cuprite/02 sec. 5
(allocation feasibility screens: capability arithmetic is the cheap
search tier). Closes F101.

Scope note (mirrors WO-24's `binding.py` precedent -- see that
module's docstring): this engine operates on the explicit
:class:`AlternateFunctionTable` / :class:`FlowDemand` input model, the
typed shape deliverable 1 asks the registry record parsing to expose,
not on a raw `.cupr` AST or a live registry record's opaque body
directly (the Rust front-end does not parse package pin tables into
`regolith.magnetite.records.Record` yet -- that translation is a future
bridge, same shape as `realizer/elec/bridge.py`'s note for `binding.py`
demands). A fixture missing a table is a fixture to write against
these typed models (the WO's own instruction), not a format to invent.

GENERALITY RULE (WO-35 deliverable 2): every allocatable resource and
capability is RECORD-DECLARED DATA. `assign_pinmux` hardcodes no
vendor shape and no fixed resource taxonomy: a `FunctionInstance`'s
``kind`` is an opaque matching key (a record author's convention, e.g.
"uart.tx" or "sercom.i2c.sda") and its ``capabilities`` are opaque
flags (e.g. "dma_capable"); the matcher only compares these against a
:class:`FlowDemand`. A finite pool where N demands compete for K slots
in a shared group (e.g. only one DMA-capable SPI) falls out of the
same instance/capability screen -- no separate "resource group" concept
is needed because a shared pool IS a `kind`+`capabilities` slice of
`instances` that multiple demands can request.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.planner import PlannerAdapter, planner_cause
from regolith.realizer.elec.errors import LockedPinInfeasible, NoFeasiblePinmux

_log = get_logger(__name__)


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class FunctionInstance(BaseModel):
    """One assignable peripheral function instance (e.g. ``"uart2.tx"``).

    ``kind`` is the record author's demand-matching key (a
    :class:`FlowDemand` asks for a ``kind``, never for a specific
    instance id); ``capabilities`` are opaque flags a demand may
    require (e.g. ``"dma_capable"``). Both are record-declared data --
    the matcher never inspects vendor-specific names.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    capabilities: frozenset[str] = frozenset()


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class PinOption(BaseModel):
    """One package pin and the function-instance ids it can carry."""

    model_config = ConfigDict(frozen=True)

    pin: str
    functions: tuple[str, ...] = ()


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class AlternateFunctionTable(BaseModel):
    """A package's full pin-mux table: record-declared, deliverable 1's shape.

    ``pins`` is the flat pin -> function-instance-ids table
    (`examples/registry/stm32g0.cupr` `packages:` shape); ``instances``
    is the function-instance catalog (kind + capability flags) those
    ids resolve against. A caller builds this once per component
    record (or per fixture, per the module docstring's scope note).
    """

    model_config = ConfigDict(frozen=True)

    package: str
    pins: tuple[PinOption, ...] = ()
    instances: tuple[FunctionInstance, ...] = ()

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def instance(self, instance_id: str) -> FunctionInstance | None:
        """The catalog entry for ``instance_id``, or ``None`` if undeclared."""
        for inst in self.instances:
            if inst.id == instance_id:
                return inst
        return None

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def pins_for(self, instance_id: str) -> tuple[str, ...]:
        """Every pin whose function list carries ``instance_id`` (sorted)."""
        return tuple(
            sorted(opt.pin for opt in self.pins if instance_id in opt.functions)
        )


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class FlowDemand(BaseModel):
    """One flow's resource demand: an instance ``kind`` plus required flags.

    ``flow`` is the design-facing demand identifier (e.g.
    ``"u_mcu.uart2.tx"``, the same spelling the `locked: pinmux(...)`
    escape names); ``locked_pin`` mirrors that escape's fixed
    pre-assignment when the design source pins it.
    """

    model_config = ConfigDict(frozen=True)

    flow: str
    kind: str
    required_capabilities: frozenset[str] = frozenset()
    locked_pin: str | None = None


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class PinAssignment(BaseModel):
    """One resolved assignment: the lockfile row shape, planner-caused."""

    model_config = ConfigDict(frozen=True)

    flow: str
    instance: str
    pin: str
    cause: str

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    @staticmethod
    def caused(flow: str, instance: str, pin: str) -> PinAssignment:
        """Build the assignment with its INV-21 planner cause attached."""
        return PinAssignment(
            flow=flow,
            instance=instance,
            pin=pin,
            # The ONE planner-cause formatter (WO-26 D105c).
            cause=planner_cause(f"pinmux {instance}"),
        )


# frob:doc docs/modules/py-realizer.md#elec-pinmux
class PinmuxResult(BaseModel, PlannerAdapter):
    """The total feasible pin-mux: one assignment per demand, in order.

    A :class:`~regolith.orchestrator.planner.PlannerAdapter` (WO-26
    D105c): the whole assignment is one content-addressable plan
    artifact, and each assignment pins one planner-caused lockfile row.
    """

    model_config = ConfigDict(frozen=True)

    assignments: tuple[PinAssignment, ...]

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    @property
    def what(self) -> str:
        """The plan identity: what this planner decided."""
        return "pinmux"

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def plan_bytes(self) -> bytes:
        """Canonical plan artifact bytes (deterministic field order)."""
        return self.model_dump_json().encode("utf-8")

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def lock_rows(self) -> tuple[LockRow, ...]:
        """One `pinmux(<instance>) = <pin>` row per assignment (INV-21)."""
        return tuple(
            LockRow(
                slot=f"pinmux({a.instance})",
                value=a.pin,
                cause=a.cause,
            )
            for a in self.assignments
        )

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def pinout(self) -> dict[str, str]:
        """The deliverable-4 pinout table: pin -> function instance id."""
        return {a.pin: a.instance for a in self.assignments}

    # frob:doc docs/modules/py-realizer.md#elec-pinmux
    def instance_to_pin(self) -> dict[str, str]:
        """The reverse of :meth:`pinout`: function instance id -> pin.

        The lookup a netlist emitter (`realizer.elec.netlist`) needs:
        a component port already named by its function-instance id
        resolves to the real package pin the assignment picked
        (deliverable 4: "the netlist gains real pin numbers where it
        previously carried port names").
        """
        return {a.instance: a.pin for a in self.assignments}


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def _candidates(
    demand: FlowDemand, table: AlternateFunctionTable
) -> list[tuple[str, str]]:
    """Every ``(pin, instance_id)`` pair legal for ``demand`` (sorted).

    A pair is legal iff the instance's ``kind`` matches the demand and
    the instance carries every capability the demand requires; when
    the demand is locked to a pin, only that pin's options are
    considered.
    """
    pairs: list[tuple[str, str]] = []
    for inst in table.instances:
        if inst.kind != demand.kind:
            continue
        if not demand.required_capabilities <= inst.capabilities:
            continue
        for pin in table.pins_for(inst.id):
            if demand.locked_pin is not None and pin != demand.locked_pin:
                continue
            pairs.append((pin, inst.id))
    return sorted(pairs)


def _contention(
    demands: Sequence[FlowDemand], table: AlternateFunctionTable
) -> tuple[str, str, str] | None:
    """The first pair of demands whose combined candidate pool cannot
    cover both of them, or ``None``.

    Named after the acceptance criterion's shape ("both flows need the
    only DMA-capable SPI"): if two demands' candidate instance ids,
    taken together, number fewer than two distinct instances, no
    assignment of both can succeed regardless of search order -- the
    constructive contention error names both flows and the shared kind.
    """
    cand_instances = {
        d.flow: {inst_id for _pin, inst_id in _candidates(d, table)} for d in demands
    }
    for i, d1 in enumerate(demands):
        for d2 in demands[i + 1 :]:
            union = cand_instances[d1.flow] | cand_instances[d2.flow]
            if len(union) < 2 and (cand_instances[d1.flow] or cand_instances[d2.flow]):
                return d1.flow, d2.flow, d1.kind
    return None


# frob:doc docs/modules/py-realizer.md#elec-pinmux
def assign_pinmux(
    demands: Sequence[FlowDemand],
    table: AlternateFunctionTable,
) -> Result[PinmuxResult, LockedPinInfeasible | NoFeasiblePinmux]:
    """Deterministic constraint search: flow demands -> pins (cuprite/04 sec. 1).

    Reuses the WO-24 `binding.bind_all` allocation-search/backjump
    skeleton (sorted candidates, chronological backtracking, D75
    nogoods as search-only state): each demand is assigned in the
    given order to the lexicographically-first legal ``(pin,
    instance)`` pair not already claimed by an earlier demand; a
    demand's candidate pool is exhausted before backjumping to the
    previous one. A `locked_pin` restricts a demand to its own pin
    up front -- if that pin carries no legal instance, the failure
    names the lock and the demand it blocks (never folded into the
    generic exhaustion path). Every emitted assignment carries the
    INV-21 `planner(pinmux <instance>)` cause (deliverable 2).
    """
    # Locked-pin infeasibility is checked first and named distinctly
    # (the human's lock, the machine's counterexample -- deliverable 3).
    for demand in demands:
        if demand.locked_pin is None:
            continue
        if not _candidates(demand, table):
            _log.warning(
                "locked pin %s infeasible for flow %s (kind=%s)",
                demand.locked_pin,
                demand.flow,
                demand.kind,
            )
            return Err(
                LockedPinInfeasible(
                    flow=demand.flow,
                    pin=demand.locked_pin,
                    kind=demand.kind,
                    message=(
                        f"locked pin {demand.locked_pin} for {demand.flow} carries "
                        f"no instance of kind {demand.kind!r}"
                    ),
                )
            )

    order = [d.flow for d in demands]
    by_flow = {d.flow: d for d in demands}
    pools = {d.flow: _candidates(d, table) for d in demands}
    cursor = [0] * len(order)
    chosen: list[tuple[str, str] | None] = [None] * len(order)

    i = 0
    while 0 <= i < len(order):
        flow = order[i]
        pool = pools[flow]
        used_pins = {p for c in chosen[:i] if c is not None for p in (c[0],)}
        used_instances = {c[1] for c in chosen[:i] if c is not None}
        placed = False
        while cursor[i] < len(pool):
            pin, inst = pool[cursor[i]]
            cursor[i] += 1
            if pin in used_pins or inst in used_instances:
                continue
            chosen[i] = (pin, inst)
            placed = True
            break
        if placed:
            i += 1
            continue
        cursor[i] = 0
        chosen[i] = None
        i -= 1
        if i >= 0:
            _log.info("pinmux backjumping to %s after exhausting %s", order[i], flow)

    if i < 0:
        contended = _contention(demands, table)
        if contended is not None:
            flow_a, flow_b, kind = contended
            message = (
                f"both {flow_a} and {flow_b} need the only kind={kind!r} instance "
                "satisfying their required capabilities"
            )
            _log.warning("pinmux contention: %s", message)
            return Err(
                NoFeasiblePinmux(
                    flows=(flow_a, flow_b),
                    kind=kind,
                    message=message,
                )
            )
        failed_flow = order[0] if order else ""
        return Err(
            NoFeasiblePinmux(
                flows=(failed_flow,),
                kind=by_flow[failed_flow].kind if failed_flow else "",
                message=(
                    "pin-mux search exhausted every candidate combination "
                    f"starting at {failed_flow!r}"
                ),
            )
        )

    assignments = tuple(
        PinAssignment.caused(flow=order[idx], instance=pair[1], pin=pair[0])
        for idx, pair in enumerate(chosen)
        if pair is not None
    )
    _log.info("pinmux assigned %d flows deterministically", len(assignments))
    return Ok(PinmuxResult(assignments=assignments))
