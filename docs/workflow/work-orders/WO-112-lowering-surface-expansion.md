# WO-112 -- Lowering-surface expansion (Class E)

Status: open
Language: Rust (regolith-lower claims/translate surface) + Python
  (orchestrator/translate.py) -- investigate first, split findings
  by side; no schema bump without D225 escalation.
Spec: F130 Class E (the five named machinery gaps); D103 (entity-
  derived bounds); D102 (typed containment); D220 (verdicts
  untouched -- expansion means MORE claims become addressable,
  never different math).

## Goal

The five recorded machinery walls that keep ~220 real claims
unlowerable/unresolvable fall, each with fixtures both ways:

1. ~131 "predicate form outside the scalar-comparison lowering
   surface": survey the ACTUAL forms in the corpus (the waive
   bases point at each site), classify (comparator-after-call
   variants, boolean combinators, range forms, unit-expr shapes),
   and land recognition for every class that has a well-defined
   scalar/window reading. Forms that genuinely have no scalar
   reading get a NAMED unsupported-form diagnostic (not a generic
   one) and a 2(c) ledger row.
2. ~63 D103 entity-derived bounds: the bound lives in an entity/
   registry record; land the ref-resolution path (the D192/D201
   record machinery is the precedent) so the bound literalizes at
   lowering/translate and the claim becomes dischargeable.
3. 15 D102 typed containment scalar shapes (StaysWithin windows):
   thread the window into a scalar request pair (the WO-54 rider
   landed the schema slot).
4. 7 fluid record-chain gaps (`fluids.dp_inputs_missing` where the
   chain, not the data, is missing).
5. 6 rule-pack rules with no engine input: wire the engine input
   channel for the affected packs (WO-28's registry).

## Acceptance

- Per-class fixtures (positive + honest-negative) in the corpus
  test nets; every class's fleet count moves (report before/after
  counts per class in the close-out).
- No golden error-level regressions; `make check` green after
  `make install` (Rust touched).

## Escalation

Any form needing new grammar goes back to the coordinator (grammar
is track-spec territory, not toolchain); D/F numbers are assigned
at integration, use placeholders.
