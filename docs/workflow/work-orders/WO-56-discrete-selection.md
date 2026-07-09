# WO-56: discrete selection end-to-end (`by select` + section search)

Status: todo
Depends: WO-55 (engine + ChoicePoint schema; HARD). WO-60's
glue-logic records (SOFT: use `tests/` fixture records if WO-60 has
not merged; swap to std.elec.patterns refs in a follow-up note).
Language: Rust (`regolith-syntax` grammar/CST/AST, `regolith-lower`
ChoicePoint emission) + Python (section-search integration, corpus
goldens). NO SCHEMA_VERSION bump (D160: WO-55 owns the only one).
Spec: docs/spec/toolchain/28-optimization.md secs. 1-2 (NORMATIVE),
00-architecture.md AD-30, design-log 2026-07-09-cycle-30 D161;
regolith/08 sec. 4 (impl strategies -- gains `select`, update it),
regolith/03 (value sources), calcite/03 sec. 5 + WO-48 close-out
(the recorded `section: free` indeterminates), regolith/12 sec. 4.

## Goal

Both discrete demand cases go end-to-end: (a) `by select(...)`
declared-alternative implementation choice through grammar ->
lowering -> ChoicePoint -> `optimize_discrete` -> pinned winner;
(b) the calcite L3 section search resolves the five ratified corpus
designs' `section: free` members over std.civil catalogs, moving
their recorded-indeterminate `civil.utilization`/`mech.deflection`
claims to real verdicts.

## Deliverables

1. **Grammar**: `by select(<impl-ref>, <impl-ref>, ...)` -- the
   sixth impl strategy. grammar.ebnf updated; lexer keyword through
   the one registry-adjacent tables; CST/AST view; formatter
   canonical form; negative fixtures (empty list = parse error;
   duplicate candidate = E-diagnostic with a constructive message,
   pick the next free code in the family the existing impl-strategy
   diagnostics use).
2. **Static tier**: every candidate independently passes the full
   static checks (the integer-domain monomorphization rule applied
   to impls); a candidate failing statically is an ordinary
   per-candidate diagnostic naming the candidate, and the choice
   point is emitted only over statically-valid candidates (all
   invalid => the artifact fails, listing all).
3. **Lowering**: `regolith-lower` emits `ChoicePoint` payloads
   (subject, ordered candidate refs, policy context) onto the D96
   channel; `select` with one candidate lowers to a degenerate pin
   (no search).
4. **Section search** (Python): expose `section: free` members as
   domain-of-candidates over `std.civil` `sections.toml` (reusing
   `frame_resolve`'s record plumbing); wire into `optimize_discrete`
   with feasibility = the member's utilization/deflection claims;
   objective = declared `policy: minimize` (the corpus designs'
   policies; where a corpus design declares none, mass per unit
   length from the section record is the documented tie-breaker --
   record THIS in the WO ledger and the guide, it is the
   defaults-test disclosure).
5. **Corpus proof**: `regolith optimize` over footbridge,
   bus_shelter, pole_barn, small_office (the members WO-48's
   close-out names: G1/G2, G1, T1, G2_AB/GR_AB) produces real
   verdicts; deferral goldens updated (regenerated, never
   hand-edited); retaining_wall's `heel_sg` geotech exclusion
   REMAINS (out of beam-model scope, unchanged).
6. **Elec demo**: a new `examples/` cuprite design `ebi_decode`
   with an external-bus-interface address decode
   `by select(nor_glue, cpld, mcu_chip_selects)` and a
   `policy: minimize` objective (cost via existing costing surface,
   or part count via budgets -- whichever the landed surface
   supports without new grammar); the pin, trace ref, and cause
   visible in the lockfile golden.
7. **Docs**: regolith/08 sec. 4 table row + track vocabulary notes
   (hematite/cuprite vocab files' impl-strategy lists), guide
   section, WO ledger.

## Acceptance criteria

- Grammar fixtures both ways (accept/reject) green; formatter
  idempotent on `select` forms; fuzzers stay green.
- A statically-invalid candidate yields a per-candidate diagnostic
  and search over the survivors; all-invalid fails constructively.
- The five-design corpus run moves every WO-48-named `section: free`
  claim off `frame_section_unresolved`-class deferrals to real
  verdicts, with `cause: optimize(...)` rows citing the trace; zero
  churn in unrelated goldens.
- ebi_decode picks the policy-best candidate; flipping the policy
  order flips the winner (test); the lockfile diff names why.
- No SCHEMA_VERSION change; `make install` + `make check` green;
  Status flipped in this change.
