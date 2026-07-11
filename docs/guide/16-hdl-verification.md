# 15 -- Verifying digital logic (`std.hdl`)

Status: WO-82 dispatch (D189). The verilator subprocess pack
(`regolith.harness.models.hdl`) is landed and registered; the Rust-side
`.cupr` obligation-emission half (an `hdl_src_ref`/`hdl_regime` given
pair on `impl ... by extern(ref, <regime>)`, mirroring the `plan:`
field WO-69 built for `std.cam`) is NOT built by this dispatch --
`python/regolith/orchestrator/translate.py`'s `_translate_hdl` is
wired and ready, but nothing emits the obligations it consumes yet
(see the WO-82 ledger in `docs/workflow/work-orders/WO-82-hdl-
verification.md`).

Source: `docs/spec/cuprite/09-hdl-coverage.md` (the D120 fixture
corpus this pack calibrates against), `docs/spec/toolchain/
00-architecture.md` AD-19 (subprocess adapter law), design-log
`2026-07-10-cycle-32.md` D189.

## The idea

`std.cam` checks a supplied machining plan against real geometry;
`std.hdl` is its digital-track sibling -- it checks supplied (or
extern-embedded) HDL against directed vectors and, where a `.cupr`
fixture pairs one, against a declared reference for that fixture's
native behavior. It never SIMULATES to explore (that is a formal-
verification future); every run is directed, cited, and honest about
what it did not cover.

## The three models

All three live in `regolith.harness.models.hdl` and share ONE
`Model.discharge` path, so a Valid result carries evidence citing the
HDL source's content digest, the required regime tag, and the pinned
verilator version (folded into the model's own version string --
`hdl_build_counter@1+verilator5.047` -- so a tool upgrade invalidates
exactly its own cached evidence, AD-19's cache-key law).

1. **`hdl.build`** -- `verilator --lint-only` elaborates the HDL
   cleanly. Generic over every non-VHDL `examples/hdl/` fixture
   (counter, alu_generic, fifo_cdc, assertions_map); a real tool
   failure (unsupported construct, syntax error) renders
   INDETERMINATE with the cited stderr excerpt, never a crash, never a
   false pass.
2. **`hdl.sim_assert`** -- directed fixture vectors + assertions run
   through `verilator --binary` against a hand-authored SystemVerilog
   testbench; a violation cites the failing assertion's name and
   cycle. Landed end-to-end for the `counter` fixture this dispatch
   (7 directed vectors: reset, count-up x3, load-priority-over-enable,
   terminal-count, wrap) -- see `python/regolith/harness/models/hdl/
   fixtures.py`'s module doc for why the other fixtures are not yet
   simulated (a named scope cut, not a silent gap).
3. **`hdl.equiv_directed`** -- directed input-space equivalence
   between the paired Verilog and an **oracle-transcribed reference**
   of the native `.cupr` `spec:` block's declared behavior. This is
   explicitly, permanently NOT compiler-executed: cuprite's
   `ConverterGraph` (the real behavioral-semantics IR,
   `regolith-lower`/`regolith-sem`) has no Python-reachable evaluation
   FFI today (AD-4 confines `regolith._core` imports to
   `compiler.py`, whose facade exposes only structural queries like
   `on_events`, never signal-level evaluation). Building that FFI is a
   cycle-33 follow-up (logged on the WO-82 coordinator ACK); until it
   lands, every `hdl.equiv_directed` evidence note says
   "oracle-transcribed reference, not compiler-executed" verbatim, and
   the vector count is always cited -- never claimed formal, never
   claimed even compiler-verified.

## VHDL (`fsm_traffic`)

Verilator has no VHDL front-end, and this environment has no `ghdl` on
PATH (checked, not assumed). Every `hdl.*` claim for `fsm_traffic`
therefore defers with a named reason
(`"...has no verilator front-end and no ghdl was found..."`); the
model is still registered (so "every fixture discharges or defers
named" holds structurally) but its `estimate` always returns that
named `Err(DomainError)`.

## Catching a real bug

`tests/fixtures/hdl/counter_broken_priority.v` is a deliberately
mutated copy of `counter.v` that swaps enable/load priority. Both
`hdl.sim_assert` and `hdl.equiv_directed` render it `violated` (the
`load_priority` directed vector's assertion fails, citing the exact
cycle) -- see `tests/harness/test_hdl_models.py::
test_hdl_equiv_directed_catches_broken_priority_mutant` and its
`sim_assert` sibling.

## Payload/regime shape

Port `hdl_src` (kind `hdl_source`) carries the hash-pinned raw HDL
bytes (D96 payload channel, the same shape `std.cam`'s `plan` port
uses). The regime (`verilog2001`/`verilog2005`/`sv2017`/`vhdl2008`)
is a REQUIRED regime tag matching the paired `.cupr` fixture's own
`by extern(ref, <regime>)` tag -- a request whose regime does not
match a model's fixture is a non-match, never an assumption.

## Where the `hdl.build` obligation comes from (WO-89)

An `impl <Contract> by extern("<file>", <hdl dialect>)` header in a
`.cupr` source now forms an `hdl.build` obligation automatically: the
lowering (`regolith-lower`) emits it alongside the ordinary INV-13
conformance obligation, carrying the extern ref + dialect, and the
orchestrator routes it to this pack (the `verilog2001`/`verilog2005`/
`sv2017` dialects; a mechanical `gcode_*` or non-HDL format emits no
`hdl.*` obligation). This is the digital sibling of the `plan:` ->
`cam.*` linkage; it adds no new claim vocabulary. The RISC-V flagship's
PC-increment leaf (`examples/flagships/riscv_hart_rv1/pc_incr.v`,
bound in `uarch.cupr`) is the first worked example -- its `hdl.build`
obligation verilates clean and discharges. Note: `hdl.build` models
are per-fixture and selected by regime tag, so a second module in the
same dialect currently needs a distinct dialect tag to stay
unambiguous (a known pack limitation, tracked for a follow-up).
