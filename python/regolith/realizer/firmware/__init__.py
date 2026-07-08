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

SCOPE NOTE (mirrors `realizer/elec/pinmux.py`'s precedent): WO-37's
stated dependency WO-36 (typed `on`-event surface) is `Status: todo`
at this WO's dispatch time -- there is no Rust-emitted typed event
ledger to consume yet. Per AD-22 (a consumer's forward-authored
contract type is a SPEC for what the producer must eventually carry,
not a permanent parallel type), :mod:`contract`'s :class:`EventDecl`
is that forward contract: this WO operates on it directly rather than
inventing a private read path into `regolith-sem`'s `ConverterGraph`.
When WO-36 lands the real typed surface, `EventDecl` promotes to (or
is regenerated from) the Rust-sourced schema and this note retires.
"""

from __future__ import annotations
