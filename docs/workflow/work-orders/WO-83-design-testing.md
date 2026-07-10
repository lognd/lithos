# WO-83: `regolith test` -- the design test surface + runner

Status: todo (SERIALIZE: dispatch after WO-80 integrates -- both
touch regolith-syntax; WO-80 first, it is small)
Depends: charter 37 (NORMATIVE), D190; WO-28's rules test (the
expect-fixture precedent to unify, not duplicate); WO-55 (seeded
optimizer for winner expectations). Owns a schema bump ONLY if the
test-result artifact genuinely needs one (prefer bump-free; D168
train rule otherwise).
Language: Rust (`regolith-syntax` test declaration grammar/CST;
lowering surfaces the parsed scenario/expect structure) + Python
(runner, cache, CLI).
Spec: docs/spec/toolchain/37-design-testing.md, design-log
2026-07-10-cycle-32 D190, regolith/12 (the ladder = scenario
vocabulary), AD-7 (one renderer).

## Deliverables

1. Grammar: `test <name>:` with `scenario:` (config selections,
   rung-1/2 bindings, seed/budget, realized-input refs) and
   `expect:` (diagnostic / verdict / value-in-range-with-cause /
   count / optimizer-winner forms); `.test.<ext>` discovery
   convention registered beside the ONE extension registry;
   formatter; negative fixtures.
2. Lowering: parsed test decls surfaced to the orchestrator
   (verify the existing payload surface carries it; escalate a
   bump per D168 if truly not).
3. Runner: `regolith test` (discovery, -k, parallel, content-
   address cache, --json, cargo-style summary; failures via the one
   renderer with expected-vs-actual).
4. Unification: rule-pack expect fixtures runnable through the
   same command (no second semantics).
5. Corpus: >= 2 test files per track per charter sec. 3 +
   printer_k1 starter tests; docs (guide "testing your design");
   WO ledger.

## Acceptance: charter 37 sec. 3 verbatim; make install + make
check green; Status flipped.
