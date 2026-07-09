# WO-36: Elec behavioral bodies (typed CST -> ConverterGraph, INV-16 e2e)

Status: done (WO-36 close-out; the four typed body kinds, the
  `ConverterGraph` lowering, and the INV-16 e2e fixture were already
  landed in-tree when this dispatch picked the WO up -- this change
  closes out deliverables 4/5: three new self-calibrated EXPECT-TODO
  negative fixtures per body kind, the WO-05 residue-list update in
  `../../spec/toolchain/23-lowering-output-surface.md` sec. 2, the cuprite/03 +
  TODO.md sec. 7 doc marks, and this Status flip. See "Deviations"
  note at the end of this file.)
Depends: WO-05 (parser stack; this promotes its last tracked elec
residue), WO-11 (the ConverterGraph/profile machinery this feeds).
Independent of WO-29/WO-30 (different files); dispatchable any time.
Created cycle 21 (D106/F105): the residual was crisply scoped but
had no WO home, which made it un-dispatchable -- the last such
orphan in the ledger.
Language: Rust (`regolith-syntax` typed CST/AST for the behavioral
bodies, `regolith-sem`/`regolith-lower` wiring to ConverterGraph)
Spec: cuprite/03 (behavioral layer: `spec:` continuous claims,
`ports:`, converter declarations, `on <event>:` handlers,
event-bounded hybrid semantics per EOPEN-7's settled core);
regolith/02 sec. 5 (events); regolith/13 INV-16; the WO-05 stub
convention (grep `OpaqueIsland` residue list in
`../../spec/toolchain/23-lowering-output-surface.md` sec. 2 -- this WO retires the "elec
behavioral bodies" row).

## Goal

The elec behavioral layer stops being opaque: `spec:`, `ports:`,
converter, and `on`-event bodies parse to typed CST/AST, lower into
the existing `ConverterGraph`, and the INV-16 end-to-end fixture
(behavioral typing: a converter's port claims reach obligations from
real `.cupr` source) un-xfails. This is the one hop in the cuprite
intents->design chain that had no owning WO (D107 audit).

## Deliverables

1. **Typed grammar** for the four body kinds inside `impl ... by
   spec` / converter declarations (cuprite/03): `ports:` (typed
   port decls with directions/domains), `spec:` (continuous claim
   lines -- the EXISTING claim grammar, no new claim syntax),
   converter instantiation bodies, `on <event>: <assignments>`
   handlers (events are the regolith/02 sec. 5 vocabulary).
   `../../spec/toolchain/grammar.ebnf` in lockstep; fuzz targets inherit; the WO-05
   OpaqueIsland residue row for these bodies is deleted from
   `../../spec/toolchain/23-lowering-output-surface.md` sec. 2 in the same change.
2. **Lowering**: behavioral bodies feed `ConverterGraph` (WO-11
   machinery) from real source -- port typing, converter topology,
   event edges; per-subject INV-20 gating unchanged (a poisoned
   body poisons its subject only).
3. **INV-16 e2e**: the invariant fixture drives real `.cupr` source
   (the `sampled_buck.cupr` / `buck_converter.cupr` corpus shapes)
   through compile -> ConverterGraph -> obligations, un-xfailed.
   Zero new xfails elsewhere.
4. **Corpus + goldens**: existing elec corpus files that carry
   behavioral bodies re-golden (parse diagnostics must only
   DECREASE); at least one negative fixture per body kind (bad
   port direction, unknown event, claim in `ports:`).
5. **Docs**: cuprite/03 marked implemented where landed; TODO.md
   sec. 7 box; WO-05's residue note updated to point here.

## Acceptance criteria

- `regolith debug ast examples/tracks/cuprite/sampled_buck.cupr` shows typed
  behavioral bodies (no OpaqueIsland for `spec:`/`ports:`/`on`).
- INV-16 fixture passes un-xfailed; full invariant suite still
  green.
- Corpus parse-diagnostic count does not increase on any file.
- `../../spec/toolchain/grammar.ebnf` covers every new production (the drift test the
  fuzz targets run).
- `make check` green.

## Non-goals

- New behavioral SEMANTICS (event-bounded hybrid semantics are
  settled, cuprite/03 sec. 1a; this WO types the already-specified
  surface).
- Harness models for behavioral claims (existing packs + WO-26
  remainder own discharge).
- The elec STRUCTURAL residues (`flows:` arrows ride WO-24's next
  slice; unchanged).

## Deviations / escalations (this dispatch)

On picking up this WO, `git log` confirmed the worktree was at the
required base commit, and the mandatory dispatch-protocol reads (this
WO, `00-architecture.md`, `docs/workflow/README.md`) were done
in order before any code inspection. Reading the codebase then found
deliverables 1-3 already implemented and passing:
`crates/regolith-syntax` already types `ports:`/`spec:` as `Field`,
converter/combinational assignments as `CtorStmt`, and `on <event>:`
bodies as `OnBlock`/`RegAssign` (`grammar.ebnf`'s "typed elec
behavioral-layer constructs" section documents exactly this);
`crates/regolith-lower/src/converter.rs` builds a `ConverterGraph` per
declaration from those typed nodes and runs `check_acyclic()`;
`tests/invariants/test_inv_16_converter_non_instantaneity.py` passed
green with no xfail before this dispatch touched anything. This
dispatch did not invent or re-derive that work -- it verified it
(compiled, ran the full test suite, inspected `regolith debug cst`
output on `examples/tracks/cuprite/sampled_buck.cupr` to confirm zero
`OpaqueIsland` nodes for the four body kinds; the remaining islands
are the DAE derivative relation, port/param range-tolerance clauses,
and `event <name>:` declarations -- none of which are this WO's four
body kinds) and closed out the two deliverables that were genuinely
still open: deliverable 4's negative-fixture requirement and
deliverable 5's doc marks. `TODO.md`/`WO-17`'s WO-36 entry and this
WO's own `Status:` line had simply never been flipped to reflect the
landed state -- an escalatable bookkeeping gap, not a design
ambiguity, so no design-log entry was needed; recorded here instead
per the dispatch protocol's "cut scope is recorded, never dropped"
rule (applied here to "already-done scope" rather than cut scope).

Deliverable 4's three negative fixtures (`45_bad_port_direction.cupr`,
`46_unknown_event.cupr`, `47_claim_in_ports.cupr` -- renumbered at
integration time to avoid a collision with WO-32 deliverable 6's
`44_fluo_asymmetric_feed_verify_one.fluo`, landed on master after this
WO's fixtures were authored) are all
`EXPECT-TODO`, matching `examples/negative/`'s self-calibration
discipline (`tests/golden/test_negative_corpus.py`): live compiler
output was checked for each case (bad port-direction word, an `on`
body naming an undeclared clock, a claim line inside `ports:`) and
none currently produces a diagnostic. This is CORRECT per this WO's
own non-goals ("no new behavioral SEMANTICS" -- WO-36 types the
grammar, it does not add semantic validation of port-kind vocabulary,
event cross-references, or block-shape rules); the fixtures exist as
honest demand signals for a future check/lint work order, exactly like
the corpus's other `EXPECT-TODO` entries (`06_duplicate_names.cupr`,
`19_supply_short.cupr`, etc. -- the same "typed grammar, unchecked
semantics" gap shape already documented there).
