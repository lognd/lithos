# WO-89 -- Digital vocabulary cluster + riscv phase B

Status: done
Language: Rust (regolith-lower claims/translate seams) + Python
  (harness routing) + corpus (riscv_hart_rv1)
Spec: F112 (the cluster's four named asks, verbatim: "per-
  instruction ISA semantics, CSR bit-field legality, memory-model
  claims, generic-default deref via parts:"); WO-81 (the riscv
  flagship -- phase A landed the ratified-extension contract
  catalog; phase B is UN-GATED by WO-82); WO-82 (std.hdl verilator
  pack: build/sim/equiv tiers -- the discharge machinery phase B
  consumes); cuprite/08 (computer-track claim forms -- VERIFY what
  it already declares before implementing ANY form; undeclared
  shapes are escalations, the D194/D200 precedent); charter
  36/WO-79 (board-correctness posture for rule-shaped legality
  checks).

## Goal

riscv_hart_rv1 is the fleet's only all-zero flagship left with a
landed discharge path (WO-82's sim/equiv tiers + ghdl/verilator
present on the host). Phase B: its contract catalog's digital
claims move from catalog-only to formed-and-evaluated obligations
through the WO-82 tiers, using the F112 vocabulary where cuprite/08
already declares it.

## Deliverables

1. VERIFICATION FIRST (the protocol's step 1, and this WO's most
   important deliverable): for each of the four F112 asks, locate
   what cuprite/08 (and the WO-81 catalog) ALREADY declares --
   claim-form shape, spelling, obligation shape. Produce the
   declared-vs-undeclared table in your plan BEFORE any code.
   Undeclared shapes: STOP that leaf, record the ask + a concrete
   recommendation (the D194 pattern); the coordinator rules and
   re-dispatches. Do NOT invent grammar.
2. For DECLARED shapes: lowering/translate wiring so the claims
   form obligations routed to the WO-82 tiers (sim expectations
   through the verilator pack; ghdl for VHDL fixtures) or to
   rule-shaped legality checks (CSR bit-fields may be
   rule-pack-shaped -- follow what the spec says, WO-79's posture
   if rules).
3. riscv phase B corpus: the flagship's catalog claims wired to
   real fixtures (WO-82's fixture tiers are the precedent);
   `regolith test` scenarios; census before/after (74/0 is the
   F115 baseline).
4. Docs: WO-81 phase-B ledger; guide additions only where
   user-facing behavior exists.

## Acceptance criteria

- riscv_hart_rv1 release build: discharge count strictly above 0
  OR every remaining zero honestly attributed to an escalated
  undeclared shape (the declared-vs-undeclared table is the
  ledger).
- No SCHEMA_VERSION bump; no grammar invention; goldens via make
  targets; zero lowered->deferred fleet-wide.
- `make check` green.

## Dependencies

WO-82 (landed), WO-81 phase A (landed), host verilator+ghdl
(present). Serializes with WO-78 at integration (both touch elec
translate surfaces; WO-78 is in flight -- rebase over it).

## Close-out ledger (this dispatch)

Rebased over the landed WO-78 SI merge. Fresh riscv census taken
FIRST via `build((riscv,), BuildTier.BUILD)`: **77 obligations, all
indeterminate, 0 resolved (77/0)** -- the task note's "77/3" did not
reproduce; the honest measured fresh baseline is 77/0. After phase B:
**79/1** (one `hdl.build` resolved through verilator 5.047; 78
indeterminate, zero violated, zero lowered->deferred). Discharge
strictly above the fresh baseline -- acceptance route A.

### Deliverable 1 (KEYSTONE): the declared-vs-undeclared table

For each of the four F112 asks, checked against what cuprite/08 (the
computer-track open queue -- EMPTY by design, F90) and cuprite/03/05/09
plus the WO-81 phase-A catalog ACTUALLY declare. WO-81's own phase-A
walls list (W1-W4) is the authoritative prior finding; this dispatch
CONFIRMED it against the live compiler and the obligation census
(59 `conformance_windows_unresolved`, 15 `unsupported_op`, 2
`si_stackup_unknown`, 1 `no_model`).

| F112 ask | Declared in cuprite? | Verdict | Disposition |
|---|---|---|---|
| **per-instruction ISA semantics** | NO native vocabulary (WO-81 **W1**: cuprite/03 `spec:` is dimensional/discrete-equality algebra over ports, never a decode table). BUT cuprite/09 sec. 3 DECLARES the embedding route: `impl ... by extern(ref, <hdl format>)` bound to a contract by an equivalence obligation. | UNDECLARED as native; **DECLARED** as an embedded-discharge route | **WIRED** this dispatch: `impl ... by extern("x.v", <hdl dialect>)` now forms an `hdl.build` obligation routed to the WO-82 verilator pack (deliverable 2). Native decode-table primitive **ESCALATED** -- recommend the extern route IS the v1 answer (matches W1's own phrasing); a native primitive is grammar growth gated on a failing corpus. |
| **CSR bit-field legality** | NO vocabulary (WO-81 **W2**: CSRs declared at presence + width + access-class-by-comment only; no per-bit WARL/WLRL predicate). Reproduced as the `frm_legal` obligation deferring `unsupported_op`. | UNDECLARED | **ESCALATED** -- recommend a bit-field predicate form `bits(csr)[hi..lo] in {legal_set}` over `digital` ports (a cuprite/03 grammar growth), OR a rule-pack-shaped legality check (WO-79/charter-36 posture) if kept out of core grammar. NOT invented here. |
| **memory-model claims** | NO whole-system claim form (WO-81 **W3**: ExtA `Atomicity` + Ztso `memory.order(tso)` are the coarsest contract-expressible approximations; a program-order/happens-before relation over the memory subsystem has no home). Reproduced as `indivisible` deferring `unsupported_op`. | UNDECLARED | **ESCALATED** -- recommend a memory-model claim primitive riding the temporal-claim extension, discharged via `by extern` against an axiomatic-model/litmus checker (`by test` evidence), the SAME embedding route as ask 1. |
| **generic-default deref via `parts:`** | NO in-language claim form; D103 reproduced verbatim in WO-81 phase A (`core.f_clk` "expression given did NOT resolve") (WO-81 **W4**). | UNDECLARED / compiler gap | **ESCALATED** -- recommend (matching the WO's own phrasing + printer_k1's envelope-literal precedent, WO-64 D1) that fmax-through-`parts:` stays a declared basis-cited literal on the attention list, NOT a checked claim, in phase B; a real generic-parameter deref path is separate compiler work with a failing-corpus reopen criterion. |

Net: three of the four asks are UNDECLARED native vocabulary whose
introduction would be grammar invention (forbidden by this WO and by
cuprite/08's empty-by-design queue) -- escalated with recommendations
above. The ONE declared shape (ask 1's `by extern` embedding route) is
wired to discharge.

### Deliverable 2: lowering/translate wiring (the DECLARED shape)

`crates/regolith-lower`: `ConformanceEdge` gained a `dialect` field
(`contracts.rs`, populated from the `by extern("ref", <dialect>)`
second argument). `claims.rs` gained `KNOWN_HDL_REGIMES` +
`hdl_build_obligation`: for every `impl ... by extern` edge whose
dialect is a known HDL format, ONE `hdl.build` obligation is emitted
alongside the unchanged INV-13 conformance obligation, carrying
`hdl_src_ref`/`hdl_regime` in `given.loads` -- the exact spelling
`orchestrator/translate.py::_translate_hdl` already reads (that
function was dead code awaiting this Rust emission, per the WO-82
ledger; it is now LIVE). This is the digital sibling of WO-69's
`plan:` -> `cam.*` emission, NO new claim vocabulary, NO schema bump.
Only `hdl.build` is emitted from source (sim_assert/equiv_directed
need a per-fixture testbench + oracle the compiler cannot author --
WO-82's own scope shape). Rust tests:
`hdl_extern_edge_emits_one_hdl_build_obligation_carrying_ref_and_regime`,
`non_hdl_extern_dialect_emits_no_hdl_obligation`.

### Deliverable 3: riscv phase-B corpus

`examples/flagships/riscv_hart_rv1/pc_incr.v` (new, pure Verilog-2001)
+ a `PcIncrement` block in `uarch.cupr` realized `impl PcIncrement by
extern("pc_incr.v", verilog2001) as pc_incr_rtl` -- the flagship's
FIRST behavioral body (PC+4 with taken-branch redirect, the smallest
honest slice of the fetch datapath). std.hdl gained a `riscv_pc_incr`
`FixtureSpec` (`hdl.build` model) with a UNIQUE `verilog2001` regime
tag. Census test: `tests/test_wo89_riscv_digital_vocabulary.py` (3
tests: census >= 78/1, the discharged one IS `hdl.build`, zero
violated). `regolith check` over the corpus stays clean (7 warnings =
the unchanged 55-site todo tally's file subset; no new diagnostic);
`regolith fmt` byte-idempotent; the WO-81 contract-graph golden
(`tests/test_flagship_riscv_contract_graph.py`) unchanged (5 pass).

### ESCALATION (architecture, ACK requested): hdl.build model selection

`ModelRegistry.select` picks an `hdl.build` model by regime-SUBSET
(`signature.accepts_regimes`), and WO-82's `hdl.build` models are
fixture-BOUND (each names its own `top_module`/`hdl_filename`). Two
fixtures sharing a dialect tag (e.g. `counter` and any second
`verilog2005` module) therefore cannot be told apart through the
registry -- both match, tie broken by (cost, id), so the wrong model
verilates the wrong top module. WO-82 never exercised `select` (its
translate path was dead code), so the gap was latent. This dispatch
SIDESTEPS it honestly for the one binding it lands by giving the
riscv leaf a genuinely distinct dialect (`verilog2001`), keeping
selection unambiguous. **Recommendation**: make `hdl.build` a
source-generic model that verilates the request's bytes against a
REQUEST-carried top module (drop per-fixture build models), OR key the
regime tag by `(dialect, fixture_id)`. Left to a coordinator ruling +
follow-up WO; not redesigned here (landed-WO surface, out of scope).

### `make check`

Green (foreground) -- see the dispatch report.
