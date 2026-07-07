# WO-35: Elec assignment completion (pin-mux solver + real-KiCad gate)

Status: todo
Depends: WO-24 engine half (binding/netlist/KiCad seam -- done),
WO-16 (registry records). Complements the WO-29 remainder (the
lowering->binding bridge) but does not depend on it: pin-mux
operates on bound blocks, proven against the same explicit input
model WO-24 used. Closes F101 (the last spec-promised derived
output with no producer -- the "done for you" audit gap).
Language: Python (`regolith.realizer.elec`); no schema changes
expected (lockfile rows use existing cause machinery)
Spec: cuprite/04 sec. 1 step 2 (pin assignment -- NORMATIVE:
"monomorphized matching problem"; the `locked: pinmux(...)` escape),
cuprite/02 sec. 5 (allocation feasibility screens), regolith/13
INV-21 (every derived value lockfile-caused); WO-24's close-out
notes (the fake-subprocess KiCad pattern to follow for tool-gated
tests); design-log 2026-07-07-cycle-20 F101/D101.

## Goal

Pin assignment becomes DERIVED: component registry records declare
package pin maps + alternate-function tables; flows demand
bus/timer/ADC/DMA resources; the solver assigns function instances
to ports to pins with every assignment lockfile-caused and every
failure a constructive error naming the contended resource. Plus:
the KiCad layout path runs REAL when the tools are present (the
WO-24 cut retired behind a gate).

## Deliverables

1. **Record model**: extend the elec registry record parsing
   (existing `component` records, `examples/registry/stm32g0.cupr`
   lineage) to expose alternate-function tables and resource
   inventories (peripheral instances with capability flags, e.g.
   DMA-capable) as typed pydantic models. The record FORMAT is
   already speced (cuprite/04 sec. 1); if a fixture record lacks a
   table, that is a fixture to write, not a format to invent --
   escalate any real format gap to a design-log note.
2. **Pin-mux matcher** (`realizer/elec/pinmux.py`): a deterministic
   constraint search (the WO-24 allocation-search + backjump pattern
   -- reuse its search skeleton if importable without contortion,
   else a documented sibling) assigning flow-demanded functions ->
   peripheral instances -> ports -> package pins, subject to: the
   alternate-function table, one function per pin, ERC ledger
   constraints (domain membership), and `locked: pinmux(...)` pins
   honored as fixed pre-assignments. Deterministic order (sorted
   candidates); every assignment emitted as a lockfile row with
   `cause: planner(pinmux <instance>)` (INV-21).
3. **Constructive failure**: an infeasible match returns a typed
   error value naming the contended resource and the competing
   demands ("both flows need the only DMA-capable SPI") -- rendered
   through the ONE diagnostic seam, never a bare exception; a
   `locked:` pin that CAUSES infeasibility is named as such (the
   human's lock, the machine's counterexample).
4. **Pinout table output**: the cuprite/06 L4 row's artifact -- a
   deterministic pinout table (port -> pin -> function) as a
   realizer output consumed by the netlist emitter (WO-24's netlist
   gains real pin numbers where it previously carried port names).
5. **Real-KiCad gate**: the WO-24 layout adapter grows tool
   detection (`kicad-cli` on PATH + `pcbnew` importable); when
   present, the placement/route/DRC step runs REAL and a marked
   test suite (`-m kicad`) asserts the wire protocol against live
   output; when absent, tests skip WITH the skip reason naming the
   tool (the honest cut retired, not deleted -- fake-subprocess
   tests remain the always-on tier).
6. **Docs**: WO-24's cut note updated (pin-mux now owned here;
   KiCad-real gated here); cuprite/04 sec. 1 step 2 marked
   implemented; TODO.md sec. 7 box.

## Acceptance criteria

- The Kestrel-shaped fixture (WO-24's explicit input model) with an
  MCU record carrying alternate-function tables assigns every flow
  demand to a legal pin; rerunning is byte-identical (determinism).
- `locked: pinmux(u_mcu.uart2.tx): pa2` is honored; an infeasible
  lock produces the constructive error naming pa2 and the demand it
  blocks.
- Contention fixture: two flows demanding the single DMA-capable
  SPI fail with both flows named.
- Every assignment appears in the lockfile with the planner cause;
  no assignment appears in design source (grep criterion: pin names
  only in registry records, `locked:` lines, and lockfile).
- Netlist golden gains real pin numbers; DRC/layout tests pass in
  BOTH modes (skip-with-reason absent tools; real when present --
  CI records which mode ran).
- `make check` green with and without KiCad installed.

## Non-goals

- Routing-quality-driven pin choice (the cuprite/04 "routing-quality
  policy" hook: v1 policy is fixed sorted-order determinism; the
  policy seam is a named function, future work).
- Autorouting quality promises (unchanged from WO-24: failed route
  is honest indeterminate).
- The lowering->binding bridge (WO-29 remainder).
- FPGA/IO-bank assignment (`hosted_on` synthesis targets -- future,
  same matcher shape, reopen with the first FPGA fixture).
