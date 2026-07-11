# WO-81: flagship riscv_hart_rv1 (ground-up RISC-V hart)

Status: phase A done; phase B seeded by WO-89 (C gated)
Depends: phase A -- landed toolchain only (authoring). Template:
WO-64's arc + ledger discipline; D189 (NORMATIVE phasing).
Language: corpus authoring (.cupr + records refs) + test enrollment.
Spec: 31-flagships.md, design-log 2026-07-10-cycle-32 D189,
cuprite/02-05 + 09-hdl-coverage.md (the behavioral/HDL surface),
regolith/08 sec. 4 (extern Verilog is the phase-B linkage).

## Phase A deliverables

1. `examples/flagships/riscv_hart_rv1/`: the extension contract
   CATALOG -- RV64I base as the core interface; M/A/F/D/C,
   Zicsr/Zifencei, S-mode, H (hypervisor) as first-class interface
   contracts with their architectural state (CSR sets, privilege
   transitions) as typed contracts/temporal claims; remaining
   ratified extensions as contract stubs (impl todo!) so catalog
   coverage is COMPLETE at contract altitude.
2. Microarchitecture boundaries: fetch/decode/execute/mem/WB
   frames, hart-level memory subsystem (I$/D$/MMU/PTW boundaries),
   debug module boundary -- promises + budgets (area class, power
   class, fmax target as declared basis-cited literals).
3. The walls list (motion-hunt discipline applied to digital):
   every ISA-semantics construct the type system cannot yet express
   (per-instruction semantics, CSR bit-field legality, trap
   priority ordering) recorded with citations -- this list is the
   phase-B/C gate input and feeds the cuprite vocabulary roadmap.
4. Corpus enrollment + contract-graph golden; check clean; zero
   waivers.

## Acceptance (phase A): WO-64 phase-A shape verbatim (check clean,
budgets close, two-sided interfaces, todo! = declared count,
contract-graph golden, walls ledgered, make check green, Status
`phase A done (B/C gated)`).

## Ledger (this dispatch)

**Done.** `examples/flagships/riscv_hart_rv1/` -- 10 files, 9 of them
sources (`magnetite.toml`, `README.md`, `contracts.cupr`,
`rv64i_core.cupr`, `ext_std.cupr`, `priv_smode.cupr`,
`priv_hmode.cupr`, `ext_stubs.cupr`, `uarch.cupr`, `package.cupr`,
`riscv_hart_rv1.cupr`). `regolith check` over the whole project: 0
errors, 55 `todo!`-honest-deferral warnings (matches the declared
`impl ... = todo!` site count exactly, per file: rv64i_core 3,
ext_std 5, ext_stubs 25, priv_smode 5, priv_hmode 2, uarch 10,
package 5) -- zero unexpected diagnostics, zero `waive` statements.
`regolith fmt` is byte-idempotent on every file (verified via
md5sum before/after a second run). `examples/flagships` was already
a corpus root (`tests/test_corpus_clean.py` `_CORPUS_ROOTS`, added by
WO-64 D4), so this flagship rides the same clean-check gate with no
test-dict change needed.

### Deliverable 1: the extension contract catalog

`rv64i_core.cupr` -- `RV64ICore` (RV64I base architectural state:
GPR/PC/fetch ports, the shared CSR bus every extension below binds
against, a representative mandatory-CSR subset, `exposing priv:
{M, S, U}` mode variable) + its two mandatory companions `Zicsr`
(the CSR read/write bus contract) and `Zifencei` (the fetch-fence
ordering promise). Privilege-transition claims use the typed
temporal vocabulary WO-26 landed and `examples/hdl/fsm_traffic.cupr`
exemplifies (`within d after e: priv = X`, `require Reset`/
`TrapEntry`) -- reset-into-M and machine-level trap entry are both
checked claims, not comments.

`ext_std.cupr` -- `ExtM`/`ExtA`/`ExtF`/`ExtD`/`ExtC`: the G-minus-
base standard extensions, each a full architectural-state contract
binding against `RV64ICore`'s shared bus (NO DUPLICATION -- M/C
declare zero new ports of their own beyond what they narrow/reuse).
`ExtA` carries an `Atomicity` temporal claim (RMW indivisibility);
`ExtF`/`ExtD` carry the FCSR rounding-mode legality claim and D's
NaN-boxing relation.

`priv_smode.cupr` -- `SmodeCsrs` (S-mode CSR set: sstatus/stvec/
sepc/scause/stval/sscratch/satp, plus `Delegation`/`Returns` mode-
transition claims mirroring `SmodeCsrs`'s exhaustiveness discipline
against `fsm_traffic.cupr`'s own `exclusive:`/`only during` row) +
four S-mode-adjacent supervisor-extension stubs (Svinval, Sstc,
Smstateen, Sscofpmf).

`priv_hmode.cupr` -- `HmodeCsrs` (the H hypervisor extension: the
four-privilege-level model M/HS/VS/VU per privileged 20211203 sec.
9.1, guest CSR set incl. the SEPARATE vs*/host CSR pairs, a
`ModeMatrix` exhaustiveness claim, and a `Trap`/`Return`
trap-and-emulate claim pair) + `GStagePtw` (the second-stage
guest-physical translation boundary).

`ext_stubs.cupr` -- 25 contract stubs covering every remaining
ratified extension this catalog does not give a full architectural
contract: B (Zba/Zbb/Zbs/Zbc), the scalar-crypto Zk* family (Zbkb/
Zkn/Zks/Zkr/Zkt), V (vector), Zfh/Zfa (half-precision + additional
float), Zfinx (float-in-integer-register), Zicntr/Zihpm (counters),
Zmmul, the Zc* compressed subsets (Zca/Zcmp/Zcmt), Ztso/Zawrs
(memory-ordering), Zicbom/Zicboz (cache-block management),
Svnapot/Svpbmt (translation refinements). Catalog coverage is
COMPLETE at contract altitude (D189's own bar): every extension in
the unpriv 20240411 (RVA23 profile) + privileged 20211203 tables has
either a full contract or a named stub -- see the README's catalog
table for the per-extension file/citation mapping.

### Deliverable 2: microarchitecture boundaries

`uarch.cupr` -- the 5-stage in-order pipeline frame boundaries
(fetch/decode/execute/mem/writeback, each a promise-only `block`),
I$/D$/MMU/PTW boundaries (16KiB-class caches, a shared PTW-walk
contract both S-mode's first-stage and H-mode's second-stage
translation bind against), and the debug module boundary (RISC-V
Debug Spec v1.0 stable, transport-agnostic per `std.debug`'s
`debug_access` intent verb, cuprite/02 sec. 3). `riscv_hart_rv1.cupr`
wires 11 of these boundaries (10 uarch + `HartPackage`'s external
contract set) into one `system` with `budget area_total`/
`power_total` (kind=area/kind=power, both `<=`-bounded, `locked:`
per-part shares that sum to the limit -- the D183/WO-64 "budgets sum
and CLOSE" demonstration) over a declared 28nm-class synthesizable
in-order-hart basis (README cites the class basis: the public
SiFive E20/S21 and lowRISC Ibex product-brief order of magnitude for
a single in-order RV32/RV64 hart, cited as a CLASS reference per
AD-34's sourcing law, no vendor-specific number copied).

`contracts.cupr` + `package.cupr` -- the hart's package/board-facing
EXTERNAL interface set (`DieOutline`, `ExternalMemPort`, `DebugPort`,
`ClockInput`, `CorePowerDomain`), bound onto one `HartPackage`
artifact -- this is what makes the machine-scale contract-graph sheet
non-trivial (WO-61's `build_contract_graph_payload` keys nodes off
declared `interface`s + `system` artifact names, per
`crates/regolith-lower/src/contracts.rs`; a project built purely from
`block`s -- the initial draft of this dispatch -- renders an EMPTY
graph, a real finding this dispatch worked around by adding the
package boundary rather than forcing the test).

### Deliverable 3: the walls list

- **W1 -- no per-instruction ISA semantics vocabulary exists in
  cuprite (cuprite/03 sec. 1, `spec:` relations are dimensional/
  discrete-equality algebra over ports, never an instruction-decode
  table).** Every extension's `spec:`/comment marks this explicitly
  (`rv64i_core.cupr`'s own header, `ext_std.cupr`'s `ExtC.spec`
  `expand(instr16)` placeholder) -- the base ISA's ~47 instructions,
  M's 13, F/D's ~50, C's ~30, and every stub extension's opcodes are
  cited by unpriv 20240411 chapter/section, never encoded as
  individual relations. Phase-B/C ask: this is the single largest
  gate on phase B's "behavioral bodies" deliverable -- either a new
  cuprite decode-table primitive, or phase B routes through `by
  extern(ref, format)` against a real RTL/ISS reference (regolith/08
  sec. 4, cuprite/09 sec. 3's OPAQUE-with-contracts route), the SAME
  choice `fsm_traffic.cupr` demonstrates at FSM scale.
- **W2 -- no CSR bit-field legality vocabulary exists (privileged
  20211203 ch. 2's WARL/WLRL per-BIT-FIELD semantics, not just
  per-register access class).** Every CSR in this catalog
  (`rv64i_core.cupr`'s M-mode set, `priv_smode.cupr`'s S-mode set,
  `priv_hmode.cupr`'s H-mode set) is declared at presence + width +
  access-class-by-comment altitude only -- the real per-bit
  legalization rules (e.g. mstatus's MPP field is a 2-bit WARL
  subfield with only 3 of 4 encodings legal) have no home. This is
  the CSR-specific instance of W1's underlying gap (no bit-field
  predicate language), not a separate primitive -- recorded
  separately because the WO explicitly asks for "CSR bit-field
  legality" as its own catalog item (D189 phase-A deliverable 3).
  Phase-B/C ask: a bit-field/subfield predicate form over `digital`
  ports (`bits(csr)[hi..lo] in {legal_set}`), a cuprite/03 grammar
  growth ask.
- **W3 -- no per-instruction memory-ordering vocabulary (A's aq/rl
  bits, unpriv 20240411 sec. 8.2) or whole-system memory-consistency-
  model claim form (Ztso's "total store order" contract,
  `ext_stubs.cupr`'s `ZtsoExt`) exists.** `ExtA`'s `Atomicity` claim
  and `ZtsoExt`'s `memory.order(tso)` promise are both the coarsest
  contract-expressible approximation (RMW indivisibility; a named-
  but-unproven ordering tag) -- the real claim (a program-order/
  happens-before relation over the whole memory subsystem) needs a
  claim form this catalog does not have. Phase-B/C ask: a
  memory-model claim primitive, likely riding the same temporal-claim
  extension W1 would need for trap-priority ordering (below).
- **W4 -- no in-language claim form binds a caller-chosen generic
  default (`<f_clk: frequency = 1.0GHz>`) to a system-level `require:`
  once the block is used as a `parts:` entry.** Tried directly
  (`require Fmax: target_class: core.f_clk <= 1.0GHz` in
  `riscv_hart_rv1.cupr`) and reverted this dispatch: `regolith check`
  reported `D103` ("expression given did NOT resolve",
  `reference=core.f_clk`) -- a real, reproduced compiler gap, not a
  typo. The fmax target (1.0GHz class, same 28nm basis as the area/
  power budgets) is instead a DECLARED literal in the file's own
  comment, honestly un-checked. Phase-B/C ask: either a generic-
  parameter dereference path through `parts:` instantiation, or (more
  likely, matching the WO's own phrasing "fmax... as declared
  basis-cited literals") this may simply be the CORRECT phase-A
  posture -- fmax as an attention-list literal, not a checked claim,
  same posture printer_k1's envelope targets take (WO-64 D1). Not
  re-attempted as a forced fix.
- **Trap priority ordering** (D189 phase-A deliverable 3's third
  named example): NOT separately walled -- it reduces to W1 (no
  per-instruction/per-exception-cause semantics vocabulary exists to
  express "which of several simultaneous trap causes wins", unpriv
  20240411 sec. 3.1.9's priority table), not a distinct gap.

No other wall: every OTHER construct phase A's deliverables asked
for (interfaces at package/board altitude, `exposing priv: {...}`
mode machinery + `within...after`/`only during` temporal claims for
privilege transitions, budgets incl. `kind=area` -- exactly as legal
as `kind=current` was for WO-64, `regolith-ir`'s `Budget` struct
carries no kind field at all) was directly expressible with landed
syntax.

### Deliverable 4: corpus enrollment + contract-graph golden

`tests/test_flagship_riscv_contract_graph.py` (new, 5 tests, all
green) -- mirrors `tests/test_flagship_printer_contract_graph.py`
(WO-64) and `tests/test_flagship_mainboard_contract_graph.py`
(WO-71) exactly: pulls the REAL `ContractGraphPayload` off
`compiler.check(("examples/flagships/riscv_hart_rv1",))`'s
`BuildOutcome.payload_json`, renders it through WO-61's
`diagram.contract_graph` producer, and asserts: >=5 nodes (the
`HartPackage` boundary's 5 interfaces -- see W-note above on why
`block`-only content renders empty), determinism across two
independent `check()` runs (payload + rendered SVG bytes), valid
ASCII XML, one symbol per node / one 3-segment polyline per edge, and
a clean drafting audit. No `_CORPUS_ROOTS` change needed (already
covered by `examples/flagships`, WO-64 D4).

### Files touched

`examples/flagships/riscv_hart_rv1/` (new, 11 files: `magnetite.toml`,
`README.md`, `contracts.cupr`, `rv64i_core.cupr`, `ext_std.cupr`,
`priv_smode.cupr`, `priv_hmode.cupr`, `ext_stubs.cupr`, `uarch.cupr`,
`package.cupr`, `riscv_hart_rv1.cupr`); `tests/
test_flagship_riscv_contract_graph.py` (new); this WO file (Status
line + this section). No `crates/` changes; no schema bump; no files
outside `examples/flagships/` + `tests/` +
`docs/workflow/work-orders/`.

### `make check`

Green for this dispatch's own surface: `cargo fmt --all --check`
passes; `uv run ty check python/regolith` passes; the corpus-clean
gate (`tests/test_corpus_clean.py::
test_corpus_root_has_no_unexpected_warnings[examples/flagships]`)
and the new contract-graph golden both pass. One PRE-EXISTING,
UNRELATED failure observed and NOT touched (out of this WO's file
surface per the dispatch's own hard rule): `uv run ruff format
--check .` flags `tests/orchestrator/test_wo75_arm_a6.py` (a WO-75
file, untouched by this dispatch, confirmed via `git diff --stat`
showing zero changes to it) -- recorded here, not silently worked
around, and not fixed (outside `examples/flagships/riscv_hart_rv1/` +
this WO's own test file).

## Architecture summary (close-out)

- **Interfaces declared:** 5 (`contracts.cupr`: `DieOutline`,
  `ExternalMemPort`, `DebugPort`, `ClockInput`, `CorePowerDomain`) --
  the package/board-facing boundary.
- **Blocks declared (contracts):** 50 (`RV64ICore`, `Zicsr`,
  `Zifencei`; `ExtM/A/F/D/C`; `SmodeCsrs` + 4 stubs; `HmodeCsrs`,
  `GStagePtw`; 25 `ext_stubs.cupr` stubs; 10 `uarch.cupr`
  microarchitecture boundaries) -- 10 with a full architectural-state
  contract (RV64I core + Zicsr/Zifencei + M/A/F/D/C + S-mode + H-mode
  = 10 counting each of M/A/F/D/C as one), 25 catalog stubs, 10
  microarchitecture-boundary promise stubs, 1 external-boundary board
  (`HartPackage`).
- **Boards/systems:** 2 (`HartPackage`, `RiscvHartRv1`).
- **Claims:** temporal-form claims in `require:` blocks: `Reset`,
  `TrapEntry` (rv64i_core); `Rounding`, `Atomicity` (ext_std);
  `Delegation`, `Returns` (priv_smode); `ModeMatrix`, `Trap`,
  `Return` (priv_hmode) -- 9 named claim groups using the typed
  temporal vocabulary (`within d after e`, `only during`,
  `settles`).
- **Budgets:** 2 (`area_total` kind=area <= 0.35mm2, `power_total`
  kind=power <= 45mW), both closing over 11 members with `locked:`
  per-part shares.
- **`todo!` honest-deferral sites:** 55, matching the declared
  `impl ... = todo!` count exactly (verified by `regolith check`'s
  own L0803 warning tally, per-file breakdown above).
- **Walls recorded:** 4 (W1 per-instruction semantics, W2 CSR
  bit-field legality, W3 memory-ordering/consistency-model claims,
  W4 generic-parameter-through-`parts:` dereference), plus a note
  that trap-priority ordering reduces to W1 rather than being a
  fifth independent gap.

## Phase B ledger (WO-89, 2026-07-10)

Phase B (UN-gated by WO-82) landed its FIRST behavioral body under
WO-89 (digital vocabulary cluster). The four phase-A walls (W1-W4)
were re-confirmed against the live compiler and mapped 1:1 to the
four F112 asks in WO-89's declared-vs-undeclared table: three
(W1 native per-instruction semantics, W2 CSR bit-field legality, W3
memory-model claims) are UNDECLARED native vocabulary -- escalated
with recommendations, NOT invented (cuprite/08's technical queue is
empty by design). The ONE declared shape -- the `by extern` embedding
route (cuprite/09 sec. 3), which W1 itself named as phase B's answer
-- is now wired: `impl PcIncrement by extern("pc_incr.v", verilog2001)`
in `uarch.cupr` forms an `hdl.build` obligation that verilates clean
through std.hdl (WO-82). Discharge census moved 77/0 -> 79/1. The
remaining ISA-semantics depth (full decode tables, CSR bit-field
predicates, memory-consistency claims) stays phase-B/C work behind
the escalated vocabulary asks. See WO-89 for the full table + ledger.
