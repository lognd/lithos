# WO-56: discrete selection end-to-end (`by select` + section search)

Status: todo
Depends: WO-55 (engine + ChoicePoint schema; HARD). WO-60's
glue-logic records (SOFT: use `tests/` fixture records if WO-60 has
not merged; swap to std.elec.patterns refs in a follow-up note).
Language: Rust (`regolith-syntax` grammar/CST/AST, `regolith-lower`
ChoicePoint emission) + Python (section-search integration, corpus
goldens). SCHEMA note (amended by D168 after the first dispatch):
the completion dispatch OWNS the final cycle-30 bump 22->23, adding
`BuildPayload.choice_points` (subject-keyed `ChoicePoint` list, the
flownets/frames/harnesses precedent) -- the D168 ruling that
un-blocks deliverables 3-6; the train closes at 23.
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

## Partial dispatch record (this pass) -- Status NOT flipped

Landed, verified (`make install` + `make check` green, zero churn in
unrelated goldens/tests, `make schema` diff-clean, no SCHEMA_VERSION
change):

- **Deliverable 1 (grammar), most of it**: `select` lexer keyword
  (`regolith-syntax::syntax_kind`, the one registry-adjacent table);
  negative fixtures `examples/negative/64_select_empty_candidate_list.cupr`
  (E0107) and `65_select_duplicate_candidate.cupr` (E0446), both
  green under the real `regolith.compiler.check` driver (no golden
  file, per that suite's own contract). Formatter idempotency and the
  ASCII/CST fuzzers verified unaffected (`format_is_idempotent_over_*`,
  `cst_covers_every_byte_for_arbitrary_ascii` still green). NOT done:
  a dedicated CST/AST typed view for `select` sites (today `select`
  parses through the same generic `ImplStmt` rest-of-line/header-token
  path `extern` already uses -- functionally accepted, but the WO's
  "CST/AST view" phrase implied more; left as the generic path since
  `extern` itself has no dedicated AST wrapper either -- see
  `crates/regolith-syntax/src/ast.rs`, no `ImplStmt` struct exists at
  all today).
- **Deliverable 2 (static tier), the syntax-adjacent half**: new
  `regolith_diag::codes::SELECT_EMPTY_CANDIDATE_LIST` (E0107,
  `Family::Parse`, next free offset after `RUN_MISSING_ENDPOINT`) and
  `SELECT_DUPLICATE_CANDIDATE` (E0446, `Family::Contracts`, next free
  offset after `CAVITY_CHAIN_INEXPRESSIBLE`); `check_select_candidates`
  in `regolith_syntax::checks` (same L1 tier/pattern as
  `check_run_endpoints`), with unit tests. NOT done: "every candidate
  independently passes the full static checks (the integer-domain
  monomorphization rule applied to impls)" -- this needs each
  candidate ref resolved to its own declaration and run through
  `regolith-sem`'s monomorphization sweep, which is `regolith-lower`/
  `regolith-sem` territory, not this L1 pass; cut for the reason
  below (it is downstream of the deliverable-3 blocker).
- **Deliverable 7 (docs), most of it**: `regolith/08` sec. 4 prose
  (the sixth impl strategy paragraph); `hematite/04-vocabulary.md` and
  `cuprite/07-vocabulary-sketch.md` impl-strategy rows; `regolith-ls`
  completion/semantic-token keyword lists updated for parity with
  `extern`. NOT done: the guide section (`docs/guide/11-optimization.md`
  addendum) -- deferred with deliverables 4-6 below (nothing to guide
  yet without a working end-to-end path).

**Escalated, not invented (deliverables 3-6 cut this pass):**

`regolith-lower`'s `ChoicePoint` emission (deliverable 3) hits the
exact structural gap this cycle's design log already named once,
D167: "`BuildPayload` carries no readable L2 structure (no interface/
impl names)" for a brand-new cross-FFI value, and D167's resolution
for the analogous `ContractGraphPayload` case was a NEW producer
field -- which needs its own schema-versioned WO (landed as WO-61),
explicitly NOT this dispatch (WO-56 forbids a bump, D160: WO-55 owns
the only one). Two schema-safe candidate mechanisms exist and neither
is named by 28-optimization.md/AD-30/D161 as the intended one:

  (a) Extend `regolith_lower::contracts::impl_edge` to emit a
      `ConformanceEdge{kind: "select", upper: <interface>,
      lower: "<cand1,cand2,...>", subject}` -- reuses the EXISTING
      generic string-keyed edge shape `extern`/`impl` already produce
      (no schema change, `BuildPayload.conformance` is unchanged
      shape), but encodes the candidate list as a delimited string
      inside an existing `String` field -- a representational choice,
      not literally a `ChoicePoint` on "the D96 channel" the
      deliverable names.
  (b) Have `regolith-lower` compute a real
      `regolith_oblig::optimize::ChoicePoint` value, digest it
      (`ChoicePoint::content_digest`), and attach a
      `PayloadRef{ kind: "optimize.choice", digest, origin }` onto
      SOME `Obligation.payloads` entry (the `payloads: Vec<PayloadRef>`
      field is already schema-v21, so this is schema-safe) -- but
      `select` has no natural existing claim/obligation to attach to
      (unlike `flownet`/`frame`, which piggyback on a `require`
      claim already present); manufacturing a synthetic obligation
      whose `Claim`/`ClaimForm` shape represents "a pending choice"
      is itself a new semantic convention `regolith-ir::ClaimForm`
      does not have a variant for today, and inventing one is exactly
      the kind of architecture decision the dispatch protocol
      reserves for `00-architecture.md`/design-log, not a WO
      implementer.

  Per the dispatch protocol ("on spec ambiguity, STOP and escalate...
  never invent"), this is escalated here rather than picked ad hoc:
  which of (a)/(b) (or a third shape) is the intended
  `ChoicePoint`-on-D96-channel mechanism needs an owner/design-log
  decision (or an explicit ruling that (a) is acceptable, since it
  costs nothing schema-wise) before `regolith-lower` should emit
  anything. Deliverables 4 (Python section search wiring), 5 (corpus
  proof regeneration over 5 designs), and 6 (the `ebi_decode` elec
  demo + lockfile golden) all CONSUME deliverable 3's output shape
  and are cut in lockstep -- building them against an invented
  interim shape would mean redoing all four once the real mechanism
  lands, which is worse than leaving them honestly not-started.

  Note for the next dispatch: `python/regolith/orchestrator/
  optimize.py::discrete_domains_from_spec`'s docstring (landed by
  WO-55) already anticipates this exact fork ("WO-56 replaces this
  with real objective extraction from the lowered payload/lockfile
  surfaces... this module's driver signatures do not change; only
  the caller wiring here does") -- so once (a)/(b)/other is decided,
  the Python-side change is additive (a new caller function beside
  `discrete_domains_from_spec`, not a rewrite of the engine).

Status stays `todo`: this WO is not closed. `make check` is green
for everything actually landed; nothing half-built was left in a
broken state.
