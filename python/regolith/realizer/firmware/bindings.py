"""Cross-language bindings generated FROM the contract header (deliverable 5).

D109 / NO DUPLICATION: the C contract header is the single source of
truth; a Rust `-sys`-shaped binding generator (v1's follow-on
language, per demand) re-emits the same symbols as Rust `pub const`
items rather than hand-authoring a second symbol table that could
desync. This module reads :class:`FirmwareDesign` directly (the same
input the C header used) instead of parsing generated C text back --
one producer-side pass, two emitted artifacts, never a parse-the-
generated-output step (that would be a second, fragile source of
truth).

Emission is opt-in (``emit_rust_sys`` flag on
:func:`regolith.realizer.firmware.realize.realize_firmware`): v1 ships
the C header unconditionally and the Rust binding on demand, per the
WO's "decide by NO DUPLICATION, record which" instruction -- recorded
here: generating straight from `FirmwareDesign` was chosen over
documenting a `bindgen <design>_contract.h` invocation because pin/
event string constants (`#define PIN_X "PA9"`) are not `bindgen`-
representable as compile-time constants the way integer defines are;
a textual re-emission from the same typed input avoids a second
partial C-parser.
"""

from __future__ import annotations

from regolith.logging_setup import get_logger
from regolith.realizer.firmware.contract import FirmwareDesign, c_identifier

_log = get_logger(__name__)

_BANNER = (
    "// GENERATED FILE -- DO NOT EDIT. Produced by regolith.realizer.firmware\n"
    "// (WO-37) from the same lockfile as the C contract header. `-sys`-shaped:\n"
    "// raw symbolic constants only, no safe wrapper.\n"
)


def generate_rust_sys_binding(design: FirmwareDesign) -> str:
    """`<design>_contract_sys.rs`: `pub const` items mirroring the C header."""
    lines: list[str] = [_BANNER, "#![allow(dead_code)]", ""]

    for a in sorted(design.pinmux.assignments, key=lambda a: a.flow):
        ident = c_identifier(a.flow)
        lines.append(f"// cause: {a.cause}")
        lines.append(f'pub const PIN_{ident}: &str = "{a.pin}";')
        lines.append(f'pub const INSTANCE_{ident}: &str = "{a.instance}";')

    for c in sorted(design.clocks, key=lambda c: c.name):
        ident = c_identifier(c.name)
        lines.append(f"// cause: {c.cause}")
        lines.append(f"pub const CLOCK_{ident}_HZ: u32 = {c.freq_hz};")

    for e in sorted(design.events, key=lambda e: e.name):
        ident = c_identifier(e.name)
        lines.append(f"// cause: {e.cause}")
        lines.append(f"pub const EVENT_{ident}_ID: u32 = {e.event_id};")
        if e.pin is not None:
            lines.append(f'pub const EVENT_{ident}_PIN: &str = "{e.pin}";')

    for p in sorted(design.partitions, key=lambda p: p.name):
        ident = c_identifier(p.name)
        lines.append(f"// cause: {p.cause}")
        lines.append(f'pub const PARTITION_{ident}_REGION: &str = "{p.region}";')
        lines.append(f"pub const PARTITION_{ident}_START: u32 = {p.start};")
        lines.append(f"pub const PARTITION_{ident}_SIZE: u32 = {p.size};")

    lines.append("")
    _log.info("generated rust-sys binding for %s", design.name)
    return "\n".join(lines)
