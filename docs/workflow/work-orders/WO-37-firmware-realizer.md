# WO-37: Firmware realizer (design-determined BSP codegen + extern contract)

Status: done (see scope note below on WO-36's dependency gap)
Depends: WO-35 (pin-mux assignments + pinout table -- the primary
input), WO-24 engine half (binding/lockfile rows), WO-36 (typed
`on`-event surface for ISR signatures), WO-16 (registry records for
MCU-family packs). Independent of the fluorite chain and WO-29/30.
Language: Python (`regolith.realizer.firmware`); no schema changes
expected (consumes lockfile + BuildPayload; emits content-addressed
artifacts)
Spec: design-log `2026-07-07-cycle-21.md` sec. E (F108/D109 --
NORMATIVE for this WO); cuprite/05 sec. 3-4 (image as realized
measured artifact, `partitions:`, prebuilt `extern` images) and
sec. 5; cuprite/04 sec. 1 step 2 (pin-mux, `locked: pinmux`);
cuprite/06 lowering table (firmware image row); regolith/07 sec. 6
(backends serialize evidence, they never decide); regolith/13
INV-10/21/22; AD-22 (consume only schema-versioned output +
lockfile).

## Goal

The design-determined layer of firmware becomes a GENERATED,
content-addressed artifact: pin configuration, peripheral init,
clock setup, ISR vectors, the linker memory map, and -- the
load-bearing piece -- a hardware contract header that application
code (any language) references symbolically, so a re-planned pin or
peripheral BREAKS COMPILATION instead of silently misbehaving.
Application logic is never generated (D109).

## Deliverables

1. **The hardware contract header** (`<design>_contract.h`):
   symbolic constants for every pin assignment (from WO-35 pinout),
   net, peripheral instance, clock frequency, and event id; each
   symbol carries a provenance comment naming its lockfile cause and
   the generating lockfile hash. `extern "C"`-safe, ASCII, stable
   ordering (deterministic).
2. **BSP sources** (C): pin configuration and peripheral init
   translated from the pin-mux/binding lockfile rows through an
   MCU-FAMILY PACK (deliverable 4); clock tree setup from declared
   constraints; ISR vector stubs whose signatures come from the
   typed event ledger (`on <event>` handlers, WO-36) -- stub bodies
   call user-provided hooks, never contain logic.
3. **Linker memory map + build fragment**: the image's declared
   `partitions:` (cuprite/05 sec. 4) emit the linker script; a
   CMake/Make fragment builds BSP + user sources into the image.
   The built image re-enters via the EXISTING `image`/`extern`
   hash-pin machinery; fit/stack/WCET/boot claims verify it
   unchanged (this WO adds zero claim vocabulary).
4. **MCU-family pack seam**: vendor HAL/register idiom mapping is
   registry/pack content (template set keyed by family record),
   NOT regolith code -- ship ONE reference family pack (pick the
   family the Kestrel fixture's MCU record models, stm32g0 lineage)
   proving the seam; the pack is signable like any record content
   (trust tiers apply). A design whose MCU family has no pack is
   honest indeterminate on the codegen step, never a guess.
5. **Cross-language bindings**: generated FROM the contract header
   as the single source of truth -- v1 ships the C header (the
   contract) + a Rust `-sys`-shaped binding generator behind a flag
   (or documented bindgen invocation if a generator would duplicate
   it -- decide by NO DUPLICATION, record which). Other languages
   are follow-on demand, same one-source rule.
6. **Determinism + provenance tests**: same lockfile -> byte
   identical generated tree (INV-10 shape); every generated symbol
   traces to a lockfile cause (INV-21); changing one pin-mux lock
   regenerates exactly the affected symbols (test with a `locked:
   pinmux` flip); generated tree hash-recorded in the ship manifest
   (WO-25 backend rules -- generation runs at realize time, ship
   serializes it).
7. **Docs**: cuprite/05 gains the codegen section (D109 condensed);
   cuprite/06 lowering table row; guide chapter stub in
   docs/guide/ if the guide set exists at dispatch time; TODO.md
   ledger flip.

## Acceptance criteria

- Kestrel-shaped fixture end-to-end: bound board + pin-mux results
  generate a contract header + BSP tree; a trivial user `main.c`
  referencing only contract symbols compiles against it (host-cc
  smoke compile is enough; cross-toolchain presence is gated like
  KiCad in WO-35 -- skip-with-reason, never fake).
- Flipping one `locked: pinmux(...)` and rebuilding changes exactly
  the affected generated symbols; the stale user code referencing
  the old symbol FAILS to compile (the anti-staleness property,
  asserted in a test).
- ISR stub signatures match the declared `on`-event types; an event
  with no interrupt-capable pin assignment is a constructive
  diagnostic naming the pin and the record fact (interrupt
  capability comes from the component record, WO-35's model).
- No family pack installed -> honest indeterminate naming the
  family; with the reference pack, deterministic output twice.
- Zero application logic in any generated file (reviewer criterion:
  stubs call hooks only); regolith core contains no vendor register
  strings (grep criterion -- they live in the pack).
- `make check` green.

## Close-out note (implementation)

Implemented as `python/regolith/realizer/firmware/` (`contract.py`
deliverable 1, `bsp.py`+`packs.py` deliverables 2+4, `linker.py`
deliverable 3, `bindings.py` deliverable 5, `realize.py` deliverable
6's orchestration + content addressing); tests in
`tests/realizer/firmware/test_realize.py` cover determinism (INV-10
shape), per-symbol provenance (INV-21 shape), the pin-flip
anti-staleness property, the honest-indeterminate paths (unknown
family, missing interrupt capability, overlapping partitions), the
zero-application-logic reviewer criterion, and a gated host-cc smoke
compile of a trivial `main.c` against the generated header.

**Escalated gap**: WO-36 (typed `on`-event surface) was `Status: todo`
at this WO's dispatch time -- there is no Rust-emitted event ledger to
consume. Per AD-22 (a consumer's forward-authored contract type is a
SPEC for what the producer must eventually carry), `contract.EventDecl`
is that forward contract; the module docstring records the promotion
path. This is the same shape as `pinmux.py`'s precedent for its own
upstream gap and is not a design decision this WO invented.

## Non-goals

- Application/control logic synthesis (`by spec` bodies stay the
  existing deferral); RTOS/scheduler selection or configuration.
- WCET/stack/map ANALYSIS models (already speced as harness models
  over the compiled image, cuprite/05 sec. 4).
- FPGA bitstream generation (`hosted_on` synthesis targets --
  future, alongside WO-35's FPGA non-goal).
- Generating code for non-MCU hosts (a desktop daemon binding is
  just the contract header + bindings; nothing MCU-shaped applies).
