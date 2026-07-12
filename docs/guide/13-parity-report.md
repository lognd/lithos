# Reading the parity report (`regolith ship --explain`)

STATUS: WORKING (WO-63). `regolith ship --explain` renders the D170
parity ledger over the SAME lockfile + release-gate artifacts a
normal `ship` gates on -- no package is written; `--explain` is a
report-only mode, exactly like `ship --verify`.

Source: charter `docs/spec/toolchain/31-flagships.md` sec. 1 (the D170
parity bar, NORMATIVE), `00-architecture.md` AD-33 (+ AD-30's honesty
non-goal -- this report never claims "optimal"), design-log
`2026-07-09-cycle-31.md` D170 and its addendum D170-a. Machinery:
`python/regolith/backends/parity.py`.

## Why this report exists

A hand designer's real edge isn't magic numbers -- it's that nothing
in a good design is arbitrary and nothing is forgotten. AD-33 makes
that an ATTRIBUTION claim the toolchain can check, not an optimality
claim: for every resolved value, *who decided this and why* is a
matter of record, not memory. The parity report is that record,
rendered.

## Running it

```
regolith build --release --out build/
regolith ship --build build/ --explain
```

Or against a fresh build (no prior `regolith build --release`
needed -- `--explain` runs the same T3 release gate a normal ship
would, just without writing a package):

```
regolith ship path/to/design.hema --explain
```

Add `--json` for the structured form (the same `ParityReport`
pydantic model, round-trippable).

## What's in the report

**Class counts by subject.** Every lockfile row (recall: only
NON-literal `value-source` slots resolve into the lockfile,
`03-value-sources.md` sec. 2) is classified by its rendered `cause:`
prefix into one of six provenance classes:

| class | lockfile cause prefixes | meaning |
|---|---|---|
| `optimize` | `optimize(...)` | the WO-55/56 engine pinned it, trace-cited |
| `dfm_drc_rule` | `dfm(...)`, `drc(...)`, `erc(...)`, `rule(...)` | a DFM/DRC/ERC rule's eager `free` resolution |
| `budget` | `budget(...)` | a budget allocator's share |
| `planner` | `planner(...)`, `policy(...)` | a routing planner or a `policy:` block decision |
| `derived` | `obligation(...)`, `derived(...)`, `derived_intent(...)`, `topology(...)` | a system-analysis consequence, not a free choice |
| `process` | `process(...)`, `realizer(...)`, `extern(...)`, `cost_profile(...)` | a manufacturing process fact or a realizer/tooling pin |

Any cause string this list doesn't recognize is a **report error**
(deliverable 1's own honesty check) -- loudly listed under "report
errors:", never silently folded into a bucket that doesn't fit.

**Decision table.** The subset of classified rows that are
DECISION-shaped (`optimize`/`dfm_drc_rule`/`budget`/`planner` --
free/select/allocated values an engine pinned per
`03-value-sources.md` sec. 1's table), separate from the
`derived`/`process` rows (consequences, not choices).

**Demand table.** Every obligation's discharge state --
`discharged` / `indeterminate` / `violated` / `deviation` (an
evidence-carrying waiver, regolith/12 sec. 3 rule 3) -- keyed by its
subject ref and obligation key.

**Assumed/waived.** Every `assume!`/`waive` ledger entry
(regolith/12 rungs 6-7) with its basis, straight from the build's
`WaiveLedger`.

**Attention list (asserted literals).** This is where the bar is
HONEST about a real gap, not silently "clean": no artifact this
toolchain emits today names a literal value's source position (see
design-log D170-a). The report renders a single, loud caveat line
here instead of a falsely-empty list. Closing this is future work,
tracked at D170-a's reopen criterion -- it does not block `ship
--explain` from being useful today for everything the lockfile DOES
carry.

**Report errors.** Any lockfile row whose cause this classifier
doesn't recognize (see class-counts above).

**Gate summary line.** `parity: clean` / `parity: attention(n)` /
`parity: failing(n)` -- summarizes, never relabels a verdict (INV-2):
a violated demand or a report error makes the build `failing`; an
indeterminate demand or an accepted assume/waive makes it
`attention`; otherwise `clean`.

## Worked examples (WO-63's own test suite)

- `coolant_gallery.hema` (+ its `.fluo` loop): a real `staged_build`
  realizes its geometry and pins a `realizer(...)` lockfile row --
  classifies `process`, zero report errors
  (`tests/backends/test_parity.py::test_coolant_gallery_realizer_cause_classifies_as_process`).
- `ebi_decode.cupr`: the WO-56 discrete driver's real winner pins
  `optimize(declared_objective, trace=<digest>)` -- classifies
  `optimize`, lands in the decision table
  (`tests/backends/test_parity.py::test_ebi_decode_optimize_cause_classifies_as_optimize`).
  This also stands in for `duct_vane` (WO-57's own staged-loop
  continuous exemplar, not yet landed in this tree): the same
  `optimize(...)` cause shape a continuous winner over a dimension
  would carry.
- The injection test (`test_build_parity_report_surfaces_injected_report_error`)
  proves an unrecognized cause is a loud report error, not a silent
  drop.

## Accepted deviations and the acceptance ledger (WO-98)

A green `--release` build can still carry *accepted deviations*: an
obligation that is not proven but is explicitly accepted by an
evidence-carrying `waive`. The release gate (INV-24) consumes the
build's waiver ledger and reaches green only when every obligation is
PROVEN or ACCEPTED -- nothing between (D206):

- A `waive Group.claim on <scope>: basis: ... by <evidence>` whose
  evidence meets the claim's trust floor (INV-14) is a deviation: the
  obligation's true status is untouched (INV-2), the release passes with
  the deviation LISTED and counted distinctly (never a discharge).
- `by doc(memos/<name>.md)` (D207) resolves to a hash-pinned in-project
  engineering memo -- an unsigned memo confers `community` tier, so it
  cannot waive a claim demanding `trust: >= tested`/`certified`. A memo
  ref that resolves to no file refuses loudly.
- A bare `waive` (no `by`), an `assume!`, or a `todo!` stays
  release-gated. `regolith build --accept <target>` acknowledges one for
  a single exploratory run only (it never persists, and the build report
  records that it was used).
- `expires:` past today makes the waiver behave as absent (the failure
  returns) and surfaces the stale error.

`regolith ship` writes `acceptance_ledger.json` into the package (every
deviation with its basis, evidence pin, kind, match set, and expiry),
and the parity report's demand table shows each accepted obligation as
`deviation` rather than its raw indeterminate/violated status. The
honesty stamp reads `RELEASE-CLEAN (<n> accepted deviations)`.
