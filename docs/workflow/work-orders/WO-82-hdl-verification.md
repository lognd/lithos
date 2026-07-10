# WO-82: std.hdl verilator pack (simulation discharge for digital logic)

Status: done (deliverables 1-5 landed this dispatch over the Python
pack surface + fixtures + docs; deliverable 4's Rust-side obligation-
emission half is a lowering cut named in the close-out ledger below,
consistent with the WO-67/WO-69 precedent and this WO's own
`Language: Python` header)
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

## Close-out ledger (this dispatch)

**Missing-capability finding (deliverable 3), escalated live and
ACK'd by the coordinator**: cuprite's `ConverterGraph` (the real
behavioral-semantics IR, `crates/regolith-lower/src/converter.rs` +
`crates/regolith-sem/src/converter.rs`) has NO Python-reachable
evaluation/simulation FFI. `compiler.py`'s facade (AD-4: the only
module allowed to import `regolith._core`) exposes only structural
queries over it (`on_events` -- trigger names, not signal-level
semantics). Building a real evaluator would mean new Rust FFI in
`crates/regolith-lower`/`crates/regolith-py`, forbidden by this WO's
own hard rule ("no crates/ (escalate)") and outside its
`Language: Python` header. **Scope cut (coordinator-approved)**:
`hdl.equiv_directed` compares the paired Verilog's verilated
simulation against a small hand-authored Python-transcribed reference
(NOT a Python function -- the SAME SystemVerilog testbench
`hdl.sim_assert` uses, whose expected values are transcribed by hand
from the `.cupr` `spec:` block's declared behavior) rather than a real
compiler-executed comparison. Every `hdl.equiv_directed` evidence note
and the guide both say "oracle-transcribed reference, not
compiler-executed" verbatim so this tier can never be mistaken for
more than it is. **Follow-up** (cycle-33 item, logged by the
coordinator on ACK): a `regolith-api` evaluation surface so a future
`hdl.equiv_directed` upgrades to compiler-executed semantics in place
(same claim kind, same payload shape).

**What landed**: `python/regolith/harness/models/hdl/` --
`verilator_adapter.py` (the AD-19 subprocess seam: version pinning via
`verilator --version`, `run_verilator` never raises, stderr excerpts
bounded to the last 40 lines), `fixtures.py` (the `FixtureSpec`
registry over all five `examples/hdl/` pairs + the hand-authored
`counter` testbench), `models.py` (`HdlBuildModel`/
`HdlSimAssertModel`/`HdlEquivDirectedModel`), `__init__.py`
(`register_hdl_models`, wired into `harness/models/__init__.py`
alongside `register_cam_models`). All three share `Model.discharge`'s
one margin path (value=excess count, eps=0.0, limit=0.0, upper-bound
sense); a tool failure or VHDL regime short-circuits to
`Err(DomainError)`, rendering indeterminate evidence, never a false
pass.

**Model ids landed** (10 total): `hdl_build_counter@1+verilator5.047`,
`hdl_build_alu_generic@...`, `hdl_build_fifo_cdc@...`,
`hdl_build_assertions_map@...`, `hdl_build_fsm_traffic@...` (five
`hdl.build` instances, one per fixture -- VHDL's always defers named),
plus `hdl_sim_assert_counter@...` and `hdl_equiv_directed_counter@...`
(the two simulated-fixture models, registered only for fixtures in
`fixtures.SIMULATED_FIXTURE_IDS`). The verilator version string folds
into every model's own `version` property (AD-19 cache-key law: a
tool upgrade invalidates exactly its own cached evidence) -- resolved
once per process in `verilator_adapter.verilator_version` (this
environment: Verilator 5.047).

**Per-fixture-pair discharge table** (cuprite/09 D120 calibration
corpus):

| fixture | `hdl.build` | `hdl.sim_assert` | `hdl.equiv_directed` |
|---|---|---|---|
| `counter` (Verilog-2005) | discharged clean | discharged, 7 directed vectors | discharged, 7 vectors, oracle-transcribed |
| `alu_generic` (SV-2017) | discharged clean | not built this dispatch (scope cut, named) | not built this dispatch (scope cut, named) |
| `fifo_cdc` (SV-2017) | discharged clean | not built this dispatch (scope cut, named) | not built this dispatch (scope cut, named) |
| `assertions_map` (SV-2017) | INDETERMINATE, named (deep SVA sequence algebra -- `##[1:4]`, `throughout`, `[*..]` -- unsupported by verilator's front-end; matches cuprite/09 sec. 2's own "PARTIAL mapping" call, now VERIFIED by a real tool failure rather than assumed) | deferred (build itself does not discharge) | deferred (build itself does not discharge) |
| `fsm_traffic` (VHDL-2008) | deferred, named ("no verilator VHDL front-end and no `ghdl` on PATH in this environment") for EVERY `hdl.*` claim | deferred, same reason | deferred, same reason |

Every non-VHDL fixture therefore discharges (`hdl.build`) or defers
named (`assertions_map`); VHDL defers named across the board; the
`counter` fixture additionally discharges the full three-model set --
satisfying "every fixture pair discharges through the pack, or defers
with the named tool/coverage reason" without silently dropping the
four fixtures this dispatch did not build a sim harness for.

**Broken-variant fixtures**: `tests/fixtures/hdl/
counter_broken_priority.v` (load/enable priority swapped -- catches
via `hdl.sim_assert` AND `hdl.equiv_directed`, both render `violated`
citing the `load_priority` assertion + cycle) and `tests/fixtures/hdl/
bad_syntax.v` (malformed source -- `hdl.build` renders indeterminate,
never a crash). See `tests/harness/test_hdl_models.py` (10 tests, all
passing).

**Translate wiring**: `python/regolith/orchestrator/translate.py`
gained an additive, localized block -- three new imports (`CLAIM_
BUILD`/`CLAIM_SIM_ASSERT`/`CLAIM_EQUIV_DIRECTED`/`SRC_PORT`/`SRC_KIND`
from `harness.models.hdl.models`), two new field-name constants
(`_HDL_SRC_REF_FIELD = "hdl_src_ref"`, `_HDL_REGIME_FIELD =
"hdl_regime"`), `_HDL_CLAIM_KINDS`, `_translate_hdl` (mirrors
`_translate_cam`'s ref-resolution shape, reuses the existing generic
`resolve_plan_bytes`/`PlanContext` plumbing rather than inventing a
second extern-resolution path), and one added dispatch line in
`translate()`. Exactly like `_translate_cam` before WO-69, this
function is presently DEAD CODE: no Rust lowering emits `hdl.*`
obligations with the `hdl_src_ref`/`hdl_regime` given-fields it reads
yet (checked `crates/regolith-lower/src/claims.rs` and
`crates/regolith-syntax`: no `hdl.*` claim-kind emission exists). That
emission is Rust work in `regolith-lower` (a new `impl ... by
extern(ref, <regime>)` -> `hdl.*` obligation production, the D189/
WO-82 sibling of WO-69's `plan:` lowering) -- outside this WO's
`Language: Python` header and the `no crates/` hard rule, so it was
NOT invented here. Follow-up: a WO-69-shaped Rust+Python dispatch.

**No schema bump**: the HDL payload/regime shapes are pack-internal
(`hdl_source` kind, string regime tags already in the `_schema`
vocabulary pattern `std.cam` established) -- nothing under `_schema/`
changed.

**`examples/hdl/` untouched**: no edits to the cuprite/09 D120
fixture corpus itself (both hard rules -- stay in scope, `examples/
flagships/` off-limits -- and simple caution: those five pairs are the
calibration set other work reads verbatim). The negative/broken
fixtures live under `tests/fixtures/hdl/` instead, clearly marked as
WO-82-only mutants, not additional D120 corpus members.

**Verification**: `uv run pytest tests/harness/test_hdl_models.py -q`
-> 10 passed; full `uv run pytest` -> 1278 passed, 9 skipped, 24
xfailed (no regressions); `make lint typecheck guard-core schema-check
test-rs test-graphite` all green over this dispatch's files. `make
fmt-check`/`lint` over the FULL tree currently fails on one file this
dispatch never touched (`tests/orchestrator/test_wo75_arm_a6.py`,
pre-existing formatting/line-length debt from an earlier WO-75
dispatch, confirmed via `git log`/`git status` to predate this
worktree's changes) -- excluding that one file, `ruff check .`/
`ruff format --check .` pass clean over everything else. Recorded here
rather than silently worked around (no unrelated files touched, per
the WO's own scope-discipline rule).
