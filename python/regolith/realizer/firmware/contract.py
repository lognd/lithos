"""The typed firmware design input + the hardware contract header (deliverable 1).

Spec: cuprite/04 sec. 1 step 2 (pin-mux); cuprite/05 sec. 4
(`partitions:`); design-log `2026-07-07-cycle-21.md` sec. E (D109 --
the contract header is the load-bearing anti-staleness artifact: a
re-planned pin/peripheral/event BREAKS COMPILATION instead of
silently misbehaving because application code references only these
symbolic constants). regolith/13 INV-10 (byte-identical from the same
lockfile) and INV-21 (every symbol traces to a lockfile cause).

:class:`FirmwareDesign` aggregates the realized decisions this WO
consumes: WO-35's :class:`~regolith.realizer.elec.pinmux.PinmuxResult`
(pin assignments), the forward-authored :class:`EventDecl` ledger (see
this package's docstring for the WO-36 scope note), declared clocks,
and declared `partitions:`. Nothing here decides anything -- every
value is copied from an upstream cause.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith import compiler
from regolith.errors import CoreFailure
from regolith.logging_setup import get_logger
from regolith.realizer.elec.pinmux import PinmuxResult
from regolith.realizer.firmware.errors import InterruptCapabilityMissing

_log = get_logger(__name__)

_NO_STRINGS: Mapping[str, str] = MappingProxyType({})
_NO_BOOLS: Mapping[str, bool] = MappingProxyType({})

#: Header guard / generated-file banner, identical on every regeneration.
_BANNER = (
    "/* GENERATED FILE -- DO NOT EDIT.\n"
    " * Produced by regolith.realizer.firmware (WO-37) from a pinned\n"
    " * lockfile. Every symbol below carries the lockfile cause that\n"
    " * produced it; re-run the build after any design change instead\n"
    " * of hand-editing this file. */\n"
)

_IDENT_RE = re.compile(r"[^A-Za-z0-9]+")


def c_identifier(name: str) -> str:
    """Uppercase, underscore-joined C identifier for a flow/event/clock name.

    Deterministic and total: non-alnum runs collapse to one `_`, and a
    leading digit gets a `_` prefix (C identifiers cannot start with a
    digit).
    """
    ident = _IDENT_RE.sub("_", name).strip("_").upper()
    if not ident:
        ident = "SYM"
    if ident[0].isdigit():
        ident = "_" + ident
    return ident


class ClockDecl(BaseModel):
    """One declared clock (cuprite/05 sec. 4 "clock tree setup from
    the declared constraints")."""

    model_config = ConfigDict(frozen=True)

    name: str
    freq_hz: int
    cause: str


class EventDecl(BaseModel):
    """One `on <event>` handler's typed signature (WO-36 forward contract).

    ``pin`` is the interrupt-capable pin assignment feeding the event
    (``None`` when the event has no pin trigger, e.g. a timer tick);
    ``interrupt_capable`` is the component-record fact WO-35's model
    already carries (a pin can be assigned without being interrupt
    capable -- that combination is the acceptance-criterion-3 error).
    """

    model_config = ConfigDict(frozen=True)

    event_id: int
    name: str
    pin: str | None
    interrupt_capable: bool
    cause: str


def events_from_on_blocks(
    paths: Sequence[str],
    *,
    pins: Mapping[str, str | None] = _NO_STRINGS,
    interrupt_capable: Mapping[str, bool] = _NO_BOOLS,
    causes: Mapping[str, str] = _NO_STRINGS,
) -> Result[tuple[EventDecl, ...], CoreFailure]:
    """Build the typed event ledger from the real `on <event>:` CST.

    WO-37 close-out follow-up (`TODO.md`): promotes `EventDecl` off its
    forward-authored placeholder (AD-22) by reading
    `compiler.on_events` -- the Rust-typed `OnBlock` surface
    (`regolith_lower::converter::collect_on_events`) -- instead of a
    caller hand-assembling event names. `event_id` is the event's
    index in the deterministic (sorted) pair order `on_events`
    returns (INV-10 shape: the same sources produce the same ids).
    `pins`/`interrupt_capable` are WO-35 pin-mux facts keyed by event
    name (this module does not decide them, only looks them up);
    `causes` overrides the default lockfile-cause string per event,
    keyed by event name.
    """
    result = compiler.on_events(tuple(paths))
    if result.is_err:
        return Err(result.danger_err)
    pairs = result.danger_ok
    events = tuple(
        EventDecl(
            event_id=event_id,
            name=event,
            pin=pins.get(event),
            interrupt_capable=interrupt_capable.get(event, False),
            cause=causes.get(event, f"lower(on {decl}.{event})"),
        )
        for event_id, (decl, event) in enumerate(pairs)
    )
    _log.info(
        "built %d event decls from typed on-block CST across %d path(s)",
        len(events),
        len(paths),
    )
    return Ok(events)


class PartitionDecl(BaseModel):
    """One declared `partitions:` region (cuprite/05 sec. 4)."""

    model_config = ConfigDict(frozen=True)

    name: str
    region: str
    start: int
    size: int
    cause: str

    @property
    def end(self) -> int:
        """Exclusive end address of this partition."""
        return self.start + self.size


class FirmwareDesign(BaseModel):
    """The full realized input this WO's codegen consumes -- nothing else."""

    model_config = ConfigDict(frozen=True)

    name: str
    family: str
    pinmux: PinmuxResult
    events: tuple[EventDecl, ...] = ()
    clocks: tuple[ClockDecl, ...] = ()
    partitions: tuple[PartitionDecl, ...] = ()


def check_event_interrupt_capability(
    events: Sequence[EventDecl],
) -> Result[None, InterruptCapabilityMissing]:
    """First event with no interrupt-capable pin assignment, as a constructive error.

    Acceptance criterion 3: "an event with no interrupt-capable pin
    assignment is a constructive diagnostic naming the pin and the
    record fact."
    """
    for event in events:
        if event.pin is not None and event.interrupt_capable:
            continue
        _log.warning(
            "event %s has no interrupt-capable pin assignment (pin=%s)",
            event.name,
            event.pin,
        )
        return Err(
            InterruptCapabilityMissing(
                event=event.name,
                pin=event.pin,
                message=(
                    f"event {event.name!r} has no interrupt-capable pin "
                    f"assignment (pin={event.pin!r}, interrupt_capable="
                    f"{event.interrupt_capable})"
                ),
            )
        )
    return Ok(None)


def generate_contract_header(design: FirmwareDesign) -> str:
    """The hardware contract header: symbolic constants, one per realized fact.

    Deterministic ordering (INV-10): pins by flow name, clocks by
    name, events by name, partitions by name -- never emission/insert
    order, which a caller could vary accidentally. Every symbol's
    comment names its lockfile cause (INV-21).
    """
    guard = f"REGOLITH_{c_identifier(design.name)}_CONTRACT_H"
    lines: list[str] = [
        _BANNER,
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
    ]

    pins = sorted(design.pinmux.assignments, key=lambda a: a.flow)
    if pins:
        lines.append("/* Pin assignments (cuprite/04 sec. 1 step 2) */")
        for a in pins:
            ident = c_identifier(a.flow)
            lines.append(f"/* cause: {a.cause} */")
            lines.append(f'#define PIN_{ident} "{a.pin}"')
            lines.append(f'#define INSTANCE_{ident} "{a.instance}"')
        lines.append("")

    clocks = sorted(design.clocks, key=lambda c: c.name)
    if clocks:
        lines.append("/* Clocks (cuprite/05 sec. 4) */")
        for c in clocks:
            ident = c_identifier(c.name)
            lines.append(f"/* cause: {c.cause} */")
            lines.append(f"#define CLOCK_{ident}_HZ {c.freq_hz}u")
        lines.append("")

    events = sorted(design.events, key=lambda e: e.name)
    if events:
        lines.append("/* Events (WO-36 typed on-event surface) */")
        for e in events:
            ident = c_identifier(e.name)
            lines.append(f"/* cause: {e.cause} */")
            lines.append(f"#define EVENT_{ident}_ID {e.event_id}u")
            if e.pin is not None:
                lines.append(f'#define EVENT_{ident}_PIN "{e.pin}"')
        lines.append("")

    partitions = sorted(design.partitions, key=lambda p: p.name)
    if partitions:
        lines.append("/* Memory partitions (cuprite/05 sec. 4) */")
        for p in partitions:
            ident = c_identifier(p.name)
            lines.append(f"/* cause: {p.cause} */")
            lines.append(f'#define PARTITION_{ident}_REGION "{p.region}"')
            lines.append(f"#define PARTITION_{ident}_START {p.start}u")
            lines.append(f"#define PARTITION_{ident}_SIZE {p.size}u")
        lines.append("")

    lines += [
        "#ifdef __cplusplus",
        "}",
        "#endif",
        "",
        f"#endif /* {guard} */",
        "",
    ]
    _log.info(
        "generated contract header for %s: %d pins, %d clocks, %d events, "
        "%d partitions",
        design.name,
        len(pins),
        len(clocks),
        len(events),
        len(partitions),
    )
    return "\n".join(lines)
