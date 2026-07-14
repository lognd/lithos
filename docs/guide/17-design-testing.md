# 17 -- Testing your design (`regolith test`)

Status: WORKING end to end (WO-83 slice B). Slice A landed the
grammar/lowering (`test <name>:` declarations, `.test.<ext>`
discovery, `BuildPayload.tests`); slice B is the runner, the
content-address cache, rule-pack unification, and the corpus.

Source: `docs/spec/toolchain/37-design-testing.md` (NORMATIVE
charter, D190), `docs/spec/toolchain/00-architecture.md` AD-22 (one
producer, no consumer side channels), `docs/spec/regolith/12-
overrides-and-hints.md` (the expert ladder -- a scenario's vocabulary).

## The idea

`check`/`build` answer "does the design meet its stated
requirements." `regolith test` answers the OTHER question: "does the
design behave the way I, the author, expect under THIS scenario" --
the cargo-test complement, author-written and checked against the
REAL pipeline output, never a private one (INV-2: an expectation
observes, it never overrides).

A test file sits beside its subject design, named by convention:

```
spar_bracket.hema           # the design
spar_bracket.test.hema      # its tests
```

Each `test <name>:` declaration carries a `scenario:` block (config-
axis selections, rung-1/2 pins, `seed =`/`budget_evals =` for
optimizer expectations) and an `expect:` block (one or more of the
five forms):

```
test mount_bore_case:
    scenario:
        locked: material AL_6061_T6
        seed = 7
        budget_evals = 20

    expect:
        diagnostic E0501 on SparBracket.mount
        verdict Structural.mount_dia = discharged
        value mount.dia within [5mm, 6.5mm] cause bearing
        count SparBracket.holes = 1
        winner mount.section = registry(std.fasteners.m6_clearance)
```

## Running tests

```
regolith test <paths...>          # discover + run every .test.<ext>
regolith test <paths...> -k name  # only tests whose name contains "name"
regolith test <paths...> --json   # machine-readable summary
```

Output is cargo-style, one line per test, with expected-vs-actual
detail lines under a failure:

```
test examples/flagships/printer_k1/printer_k1.test.cupr::build_sanity ... ok
test examples/tracks/hematite/spar_bracket_wo83.test.hema::mount_bore_case ... FAIL
    FAIL: expected verdict Structural.mount_dia = discharged; actual = indeterminate
    ...

test result: FAILED. 8 passed; 1 failed
```

Exit codes follow `check`'s convention: clean (0) iff every test AND
every rule-pack fixture passed, diagnostics (1) otherwise, internal
error (2) on an infrastructure failure.

Scenarios within one test file run in parallel (each is an isolated
overlay build; the core releases the GIL across `check`/`compile`);
files run sequentially so per-project cache writes never race.
Declaration order is preserved in the output regardless of
completion order.

## Scenario application mechanics (AD-22: no private pipeline)

A scenario entry is EITHER a real source statement or a real CLI
parameter -- never a hand-rolled elaboration of the ladder
(`regolith.orchestrator.test_scenario`):

- `seed = <n>` / `budget_evals = <n>` are OPTIMIZER PARAMETERS,
  threaded straight into `optimize_discrete` exactly as `regolith
  optimize --seed --budget-evals` already does.
- Every other entry is a REAL SOURCE STATEMENT. The runner builds a
  synthesized overlay compile-input: a copy of the subject design
  (or, when a `magnetite.toml` sits beside the test file, the WHOLE
  project) with one `locked:` block appended -- INDENTED as a member
  of the design's trailing top-level declaration (verified against
  the real parser: a column-0 free-standing `locked:` block is
  `E0192`, so it must nest under the design's last `part`/
  `assembly`/`system`/`board`) -- and hands that overlay to the
  SAME `compiler.check`/`compiler.compile` door `regolith check`/
  `regolith build` use.

This means a scenario can only ever narrow or pin what the design
already allows -- it can never forge a pass (the rung-2 safety
property, `12-overrides-and-hints.md` sec. 1).

## The five expectation forms

| form | checked against |
|---|---|
| `diagnostic <CODE> on <subject>` | the ONE renderer's text (AD-7), reused verbatim |
| `verdict <Group.claim> = <status>` | the real `BuildReport.results` (discharged/violated/indeterminate) |
| `value <path> within [lo,hi] [cause <class>]` | `BuildPayload.resolutions` |
| `count <path> = <n>` | `BuildPayload.obligations` |
| `winner <subject> = <candidate>` | a real `optimize_discrete` run over `BuildPayload.choice_points`, seeded |

**A recorded AD-22 wall** (not hidden): `regolith_qty::Resolution`
carries a value and a `Cause` reference string but no slot/path
field, so `value`/`count` expectations cannot bind to a source path
structurally today. The runner matches them best-effort (magnitude +
cause-text scan for `value`; obligation subject/claim-name substring
for `count`) -- the SAME documented-simplification posture
`regolith.docgen.status.claim_statuses` already uses for verdict-by-
name matching (D127 precedent). A producer-side fix (naming the
slot on `Resolution`) is a future WO-29-shaped follow-up, not
slice B's scope.

## Content-address caching

A scenario's digest (its `scenario_entries`, canonical JSON) crossed
with the design file's raw-byte digest keys a small JSON store at
`<project>/.regolith/test-cache.json` (blake3, the same domain-tag
discipline as `regolith.orchestrator.cache`). An unchanged scenario
over an unchanged design is a cache hit -- the summary line marks it
`(cached)`.

## Rule-pack fixtures, unified

`regolith test` also discovers every source file under the given
paths that declares `expect: pass:`/`fail:` fixtures (the WO-28
authoring convention -- rule packs are ordinary source files, no
separate extension) and runs them through the existing `compiler.
rules_test` machinery, merged into the SAME summary -- one test
surface, no second runner semantics.

## Corpus

Every track carries at least two `.test.<ext>` files exercising the
charter sec. 3 matrix (diagnostic negative-twin, verdict + config-
axis scenario; `printer_k1` additionally exercises the winner form
against its real `by select(...)` address-decode choice point):

- hematite: `examples/tracks/hematite/spar_bracket_wo83.test.hema`
  (slice A's grammar/lowering proof -- all five forms, kept as
  slice A left it; a red rendering of "verdict/value/count/winner
  under a design nobody tuned for pipeline accuracy" is itself a
  useful demonstration of `regolith test`'s honesty), plus
  `lug_bracket.test.hema` (config-axis pin + verdict, green).
- cuprite: `examples/negative/03_volt_plus_amp.test.cupr`
  (diagnostic) + `examples/tracks/cuprite/buck_converter.test.cupr`
  (pin + verdict).
- fluorite: `examples/negative/40_fluo_medium_mismatch.test.fluo`
  (diagnostic) + `examples/tracks/fluorite/aquarium_loop.test.fluo`
  (pin + verdict).
- calcite: `examples/negative/48_calx_no_circulation_edges.test.calx`
  (diagnostic) + `examples/tracks/calcite/bus_shelter.test.calx`
  (pin + verdict).
- flagship: `examples/flagships/printer_k1/printer_k1.test.cupr`
  (verdict + seeded winner over the whole project) -- the regression
  net's first flagship member.

## Physical bring-up (debug profile)

Design tests prove a design in simulation; the DEBUG EMISSION PROFILE
(charter 40, WO-125) instruments the built artifact so the same
claims are physically probeable after manufacture. `regolith ship
--emit-profile debug` augments the package -- board tap header +
labeled test points (`boards/tap_placements.json`), a firmware
trace-hook table (`debug_taps.h`, compiles to nothing in release), an
HDL tap module routed to declared debug pins -- and emits the machine
tap record `harness/tap_map.json`, checked for tap-map/artifact
agreement (INV-32) before the package exists. Verdicts and census
output are IDENTICAL between profiles; the release artifact set is
byte-identical with the profile off.

The full bring-up harness pack (procedure document, expected-signal
manifest with provenance, analyzer capture configs) and its guide
land with WO-126; the logic-analyzer jig exemplar that mates the tap
header lands with WO-127.
