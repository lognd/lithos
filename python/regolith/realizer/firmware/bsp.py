"""BSP source generation (deliverable 2): pin config + clock + ISR stubs.

Translates the pin-mux/binding lockfile rows through an MCU-family
pack (deliverable 4) into C sources. ISR stub signatures come from the
typed event ledger (WO-36's forward contract, see this package's
`__init__` docstring); stub BODIES call user-provided hooks by name
and contain no logic (D109, WO-37 acceptance criterion 5).
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.logging_setup import get_logger
from regolith.realizer.firmware.contract import (
    FirmwareDesign,
    check_event_interrupt_capability,
)
from regolith.realizer.firmware.errors import InterruptCapabilityMissing, UnknownFamily
from regolith.realizer.firmware.packs import FamilyPack, get_pack

_log = get_logger(__name__)

_BANNER = (
    "/* GENERATED FILE -- DO NOT EDIT. Produced by regolith.realizer.firmware\n"
    " * (WO-37). Pin/clock init only; ISR stubs call user hooks, no logic. */\n"
)


# frob:doc docs/modules/py-realizer.md#firmware-bsp
def generate_bsp_init(design: FirmwareDesign, pack: FamilyPack) -> str:
    """`<design>_bsp.c`: pin configuration + clock tree setup, in declared order."""
    lines: list[str] = [
        _BANNER,
        f'#include "{design.name}_contract.h"',
        "",
        f"void {design.name}_bsp_init(void)",
        "{",
    ]
    for a in sorted(design.pinmux.assignments, key=lambda a: a.flow):
        lines.extend(pack.pin_init_lines(a))
    for c in sorted(design.clocks, key=lambda c: c.name):
        lines.extend(pack.clock_init_lines(c))
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# frob:doc docs/modules/py-realizer.md#firmware-bsp
def generate_isr_stubs(design: FirmwareDesign, pack: FamilyPack) -> str:
    """`<design>_isr.c`: one stub per declared event, sorted by event name."""
    lines: list[str] = [
        _BANNER,
        f'#include "{design.name}_contract.h"',
        "",
    ]
    for e in sorted(design.events, key=lambda e: e.name):
        lines.extend(pack.isr_stub(e))
        lines.append("")
    return "\n".join(lines)


# frob:doc docs/modules/py-realizer.md#firmware-bsp
def generate_bsp(
    design: FirmwareDesign,
) -> Result[dict[str, str], UnknownFamily | InterruptCapabilityMissing]:
    """The full BSP file set for ``design``: `{filename: content}`.

    Fails honest-indeterminate (never a guess) when the family has no
    pack, or when an event's interrupt-capability fact is missing
    (acceptance criteria 3/4).
    """
    cap = check_event_interrupt_capability(design.events)
    if cap.is_err:
        return Err(cap.danger_err)

    pack_result = get_pack(design.family)
    if pack_result.is_err:
        return Err(pack_result.danger_err)
    pack = pack_result.danger_ok

    files = {
        f"{design.name}_bsp.c": generate_bsp_init(design, pack),
        f"{design.name}_isr.c": generate_isr_stubs(design, pack),
    }
    _log.info(
        "generated BSP for %s (family=%s): %d files",
        design.name,
        design.family,
        len(files),
    )
    return Ok(files)
