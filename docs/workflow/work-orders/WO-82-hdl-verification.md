# WO-82: std.hdl verilator pack (simulation discharge for digital logic)

Status: todo
Depends: WO-20/44 (pack seams), cuprite/09 coverage matrix + its
examples/hdl fixture pairs (the calibration corpus), verilator
(present: /usr/local/bin/verilator). NO schema bump; no crates/
(escalate). The std.cam pack (WO-67) is the structural template:
models cheapest-first, conservative-or-silent, line-cited failures.
Language: Python (harness pack + subprocess adapter per AD-19) +
fixtures.
Spec: design-log 2026-07-10-cycle-32 D189, 20-solver-abstraction.md
(subprocess adapter law), cuprite/09-hdl-coverage.md, regolith/08
sec. 4 (extern transparent formats).

## Deliverables

1. `hdl.build`: verilate a cuprite-emitted/extern Verilog module
   (tool failure = INDETERMINATE with stderr excerpt cited, never
   a crash; version pinned in evidence).
2. `hdl.sim_assert`: run directed fixture vectors + SystemVerilog
   assertions through the verilated model; violation cites the
   assertion + cycle.
3. `hdl.equiv_directed`: directed input-space equivalence between a
   cuprite behavioral body's ConverterGraph semantics and its
   paired Verilog (the cuprite/09 fixture pairs ARE the calibration
   set: counter, alu_generic, fsm_traffic, fifo_cdc,
   assertions_map) -- honest about coverage (directed vectors +
   declared seed-driven sampling, NEVER claimed as formal
   equivalence; the evidence names vector counts).
4. Wiring: claim forms routed per the landed translate conventions
   (mirror the std.cam wiring shape); evidence cached by content
   address (tool version folded into keys).
5. Fixtures both ways per model; docs (guide section); WO ledger.

## Acceptance: every cuprite/09 fixture pair discharges through the
pack (or defers with the named tool/coverage reason); broken-variant
fixtures per model; make check green; Status flipped.
