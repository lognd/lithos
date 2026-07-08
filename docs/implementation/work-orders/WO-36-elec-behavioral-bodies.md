# WO-36: Elec behavioral bodies (typed CST -> ConverterGraph, INV-16 e2e)

Status: todo
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
`../design/23-lowering-output-surface.md` sec. 2 -- this WO retires the "elec
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
   `../grammar.ebnf` in lockstep; fuzz targets inherit; the WO-05
   OpaqueIsland residue row for these bodies is deleted from
   `../design/23-lowering-output-surface.md` sec. 2 in the same change.
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

- `regolith debug ast examples/elec/sampled_buck.cupr` shows typed
  behavioral bodies (no OpaqueIsland for `spec:`/`ports:`/`on`).
- INV-16 fixture passes un-xfailed; full invariant suite still
  green.
- Corpus parse-diagnostic count does not increase on any file.
- `../grammar.ebnf` covers every new production (the drift test the
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
