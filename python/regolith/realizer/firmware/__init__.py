"""Firmware realizer: pinned lockfile rows -> generated BSP + contract header (WO-37).

Spec: design-log `2026-07-07-cycle-21.md` sec. E (F108/D109, NORMATIVE
for this WO); cuprite/05 sec. 3-5 (image as realized artifact,
`partitions:`, prebuilt `extern` images); cuprite/04 sec. 1 step 2
(pin-mux, `locked: pinmux`); cuprite/06 lowering table (firmware image
row); regolith/07 sec. 6 (backends serialize evidence, they never
decide); regolith/13 INV-10/21/22; AD-22 (consume only schema-versioned
output + lockfile).

D109: the realizer GENERATES the design-determined code layer -- a
hardware contract header (symbolic constants for pins/nets/peripherals/
clocks/events, each carrying its lockfile cause), BSP pin/clock/ISR-stub
sources translated through an MCU-FAMILY PACK, and a linker memory map
+ build fragment. It decides nothing: every generated symbol traces to
an upstream planner decision (pin-mux, WO-35; event ledger, WO-36;
`partitions:`, cuprite/05 sec. 4). Application logic is never generated.

Submodules: :mod:`contract` (typed design input + contract header
codegen), :mod:`packs` (the MCU-family pack seam, AD-19-shaped),
:mod:`bsp` (pin/clock/ISR C sources via a pack), :mod:`linker` (memory
map + build fragment), :mod:`bindings` (cross-language bindings
generated from the contract header), :mod:`realize` (the top-level
orchestration + content-addressed output tree), :mod:`errors` (AD-7
error values).

RESOLVED (WO-37 close-out follow-up, `TODO.md`): WO-36 landed the
typed `on <event>:` surface (`OnBlock`, `regolith-lower::converter`).
:mod:`contract`'s :func:`~contract.events_from_on_blocks` now builds
the `EventDecl` ledger by reading `compiler.on_events` (the
`regolith-py` binding over `regolith_api::on_events`, thin marshalling
per AD-2), which parses the real CST rather than a caller
hand-assembling event names. `EventDecl` itself stays -- WO-35 pin-mux
facts (`pin`, `interrupt_capable`) are not CST data and are supplied
by the caller -- but its `name`/`event_id` fields are no longer a
forward-authored placeholder (AD-22's promotion path, now taken).
"""

from __future__ import annotations
