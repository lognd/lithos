# 37 -- Design testing: `regolith test` (design charter; D190, cycle 32)

> Charter for author-written, scenario-based tests over engineering
> sources -- the cargo-test complement to the validation pipeline.
> Machinery: WO-83. Where this doc and a WO body conflict, this doc
> wins.

## 1. Design decisions (load-bearing)

1. **Test files by convention**: `<name>.test.<track-ext>` beside
   the sources (discovery needs no manifest change); a `test
   <name>:` declaration carries a scenario block and an expect
   block.
2. **Scenarios are ladder-legal inputs only**: config-axis
   selections, rung-1 assertions/rung-2 pins (the expert ladder IS
   the scenario vocabulary -- no test-only backdoors), optional
   supplied realized inputs (digest-pinned), optional seed/budget
   for optimizer expectations.
3. **Expectations observe, never override** (INV-2): expected
   diagnostics (code + subject), claim verdicts, resolved values
   (within [lo,hi], optionally with an expected cause class),
   entity/obligation/net counts, optimizer winners under the named
   seed. An expectation failure renders through the ONE renderer
   with both expected and actual.
4. **Runner** (`regolith test`, Python orchestrator): discovery,
   `-k` filtering, parallel scenarios, content-address caching
   (scenario digest x design digest -> cached result; INV-1
   spirit), `--json`, exit codes cargo-style. Every scenario run is
   an ordinary check/build invocation -- no private pipeline.
5. **Rule-pack expect fixtures unify**: `regolith rules test`
   remains, and the same fixtures surface through `regolith test`
   (one test surface; no second runner semantics).

## 2. Non-goals (reopen criteria)

Property-based/fuzz scenario generation (reopen on demand once the
directed form is proven); mocking/stubbing physics (the ladder is
the only input surface, deliberately); coverage metrics v1.

## 3. Acceptance shape (WO-83)

Grammar + runner landed; each track carries >= 2 test files
exercising: a diagnostic expectation (negative twin), a verdict +
value-with-cause expectation, a config-axis scenario, and one
optimizer-winner expectation (seeded); flagship printer_k1 gains a
starter test file; cache hit proven on an unchanged rerun; failure
output renders expected-vs-actual through the one renderer;
make check green.
