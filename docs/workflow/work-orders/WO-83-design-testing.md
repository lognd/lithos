# WO-83: `regolith test` -- the design test surface + runner

Status: done (slice A: grammar+lowering; slice B: runner+corpus).
Slice A landed: `test <name>:` grammar/CST (`scenario:`/`expect:`
blocks, the five `expect:` forms), the `.test.<ext>` discovery
convention in the ONE extension registry, the `BuildPayload.tests`
lowering surface (SCHEMA_VERSION 25 -> 26, taken per D168 -- no
existing generic declaration surface carried this), and a proof
fixture (`examples/tracks/hematite/spar_bracket_wo83.{hema,test.hema}`
+ `tests/test_wo83_test_decl_lowering.py`).

Slice B (this dispatch) landed: `regolith test` (`regolith.
orchestrator.test_runner` + `test_scenario` + `test_expect`; CLI
`test` subcommand in `regolith.cli.app`) -- discovery, `-k`, content-
address caching (`.regolith/test-cache.json`), `--json`, cargo-style
output, expected-vs-actual failure rendering through the ONE renderer;
scenario application via a synthesized overlay compile-input (real
source statements / real CLI optimizer params, never a private
pipeline -- AD-22, see `regolith.orchestrator.test_scenario`'s module
doc for the mechanics + the verified `locked:` indentation
requirement); rule-pack `expect: pass:`/`fail:` fixtures discovered
and run through the SAME summary via the existing `compiler.
rules_test` (deliverable 4, no second runner semantics); corpus:
>= 2 `.test.<ext>` files per track (hematite/cuprite/fluorite/calcite)
plus `examples/flagships/printer_k1/printer_k1.test.cupr` (verdict +
seeded winner over the real project); guide `docs/guide/
17-design-testing.md`; acceptance test `tests/test_wo83_test_runner.
py` (discovery, a green corpus member, a red corpus member --
slice A's own untuned fixture, kept as-is -- the winner form, the
diagnostic form, a cache-hit proof, and rule-pack unification).

Recorded v1 cuts (not silently dropped, see the module docs for full
argument): (1) `value`/`count` expectations hit a genuine AD-22 wall
-- `regolith_qty::Resolution` carries no slot/path field, so they
match best-effort (magnitude+cause-text / obligation-prefix scan),
the SAME documented-simplification posture `regolith.docgen.status.
claim_statuses` already uses (D127 precedent); a producer-side fix is
a future WO-29-shaped follow-up. (2) Scenario overlays for non-project
(no `magnetite.toml`) designs copy only the test/design pair, not a
shared directory's unrelated siblings -- a multi-file design without
a project manifest is out of v1's scope. (3) Scenarios within one
test file run in parallel (a small thread pool over isolated overlay
temp dirs; the core releases the GIL across `check`/`compile`); FILES
run sequentially so per-project cache writes never race -- cross-file
parallelism is a follow-up, not a missing mechanism. `make check`
green; NO schema bump (slice A's SCHEMA_VERSION 26 stands unchanged).
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
