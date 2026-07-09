# WO-34: Routed runs (wiring-harness declarations + shared extraction)

Status: done (D1-D6 landed; the endpoints-net consistency check is
implemented and unit-tested but stays silent end-to-end pending a
net-membership inference seam -- see the D2 note appended below)
Depends: WO-32 (the routed-geometry extraction seam -- consumed, not
reimplemented), WO-31 (grammar precedent only). Answers feldspar G42
(`../../spec/toolchain/20-solver-abstraction.md` sec. 7 item 8, D99).
Language: Rust (`regolith-syntax` cuprite `harness:` grammar,
`regolith-lower` run elaboration); Python (orchestrator lockfile
causes for planner-routed paths)
Spec: design-log 2026-07-07-cycle-20 D99 (decision; this file
carries the full shape); cuprite/04 (structural layer -- the
`harness:` block lands beside `board`), cuprite/06 lowering table;
fluorite/03 sec. 1 (the extraction seam contract);
AD-17/AD-22/AD-23 (runs are NOT nets -- no net-core involvement);
AD-25/D128 (cycle 24: extraction is in-pipeline over
`RealizedGeometry` compile inputs).

AMENDMENT (cycle 24, D128/AD-25): "realized structural refs" arrive
as `RealizedGeometry` IR compile inputs via WO-42's realized-input
channel, and run extraction happens in-pipeline (never at discharge
time). Dispatch this WO AFTER WO-42 so elaboration consumes the real
channel; the hand-authored realized frame record in deliverable 5
remains the fixture form.

## Goal

A wire run (routed path along structure, bundle membership,
connector environment) becomes declarable and its lengths/bundle
factors become EXTRACTED lowered givens -- so voltage-drop,
ampacity-derating, and mass claims stop depending on hand-asserted
lengths that nothing invalidates when the layout changes.

## The shape (D99, normative here)

```
harness MainLoom:
    run batt_to_kill:  from battery.pos to kill_switch.in
        along frame.spine_tube, frame.hoop_gusset
        bundle primary
    run kill_to_ecu:   from kill_switch.out to ecu.pwr
        along frame.spine_tube
        bundle primary
    run vr_sense:      from vr_sensor.sig to ecu.vr_in
        along route: free          # planner-routed; lockfile-caused
        bundle shielded_signals
    environment engine_bay: [-30degC, 125degC]   # connector env class
```

- A `run` names two cuprite endpoints (ports/connector pins) and a
  routed PATH: either declared waypoints (`along <structural refs>`)
  or `route: free` (resolved by the planner/realizer, materialized
  in the lockfile with `cause: planner(route <run>)` -- never
  hand-asserted in source, D99).
- `bundle <group>` declares co-routing; bundle FACTORS (derating by
  bundle size per the applicable rule pack) are derived from group
  membership, not written per-run.
- Elaboration extracts per-run length (sum of segment lengths along
  the realized structural geometry, via the WO-32 `extract` module's
  segment-list result -- the SAME module, zero duplication),
  environment class per segment, and bundle membership tables --
  all as lowered givens cited to the geometry snapshot hash.
- Claims consume the derived givens through existing vocabulary
  (`elec.v_drop(run) < 300mV`, ampacity rules in E06xx packs
  folding `run.length`/`run.bundle.count`); no new claim forms.
- Runs are NOT nets (AD-23 note): the net says WHAT is connected;
  the run says WHERE the copper goes. A net may be carried by
  several runs; the binding is by the endpoints' net membership,
  checked (a run whose endpoints are on different nets with no
  inline component is a compile diagnostic).

## Deliverables

1. **Grammar** (`regolith-syntax`): the `harness:` block with `run`
   (endpoints, `along` waypoint refs or `route: free`, `bundle`),
   `environment` class declarations; `../../spec/toolchain/grammar.ebnf` + fuzz targets
   in lockstep.
2. **Elaboration** (`regolith-lower`): run -> segment path against
   realized structural refs via the WO-32 extraction seam;
   lowered-given emission (length, env class, bundle tables) with
   snapshot-hash citations; the endpoints-net consistency check; a
   `route: free` run lowers with an UNRESOLVED length that the
   planner materializes (the existing `free` value-source machinery
   -- cause-tagged, INV-21).
3. **BuildPayload**: `runs: IndexMap<RunName, RunRecord>` (lengths,
   bundle membership, env classes, citations) -- the payload field
   consumers (rule packs, mass budgets, the realizer) read (AD-22).
4. **Rule-pack demand fixture**: one E06xx-grammar ampacity rule
   consuming `run.length` and bundle count in a `process`-module
   fixture (the WO-28 grammar already parses rules; this fixture
   proves the run vocabulary reaches it) -- if the WO-28 ENGINE
   remainder has not landed, the fixture is grammar+lowering golden
   only, recorded as such (no fake evaluation).
5. **Fixtures + goldens**: a two-run harness over a hand-authored
   realized frame record; planner-routed run golden showing the
   lockfile cause; negative fixtures (cross-net run, dangling
   endpoint, unknown bundle).
6. **Docs**: cuprite/04 gains the `harness:` section (D99 text
   condensed; the sec. 1 pin-assignment step cross-references it);
   cuprite/06 lowering table row; `../../spec/toolchain/20-solver-abstraction.md` sec. 7
   item 8 marked landed.

## Acceptance criteria

- The fixture harness lowers: each declared-waypoint run's length
  equals the hand-computed segment sum exactly, cited to the
  snapshot hash.
- Changing the fixture's frame geometry record changes the extracted
  lengths and BREAKS dependent goldens (the anti-staleness property
  G42 demanded -- prove it with a second record variant).
- A `route: free` run appears in the lockfile with
  `cause: planner(route ...)` once resolved; unresolved, its
  consumers are honestly indeterminate.
- Cross-net endpoints without an inline component -> compile
  diagnostic naming both nets.
- No routing/extraction logic outside the WO-32 `extract` module and
  this WO's elaboration pass (grep-level reviewer criterion).
- `make check` green; goldens via `make snapshots`.

## Non-goals

- AUTOMATIC route synthesis (choosing waypoints; planner/realizer
  work later -- the language admits `route: free` so the surface is
  ready and source never regresses to hand-asserted lengths).
- Connector/pin assignment (WO-35 pin-mux; a run references already-
  assigned endpoints).
- Fluid hoses (they are fluorite edges; same seam, already WO-32).
- EMC coupling between bundle members (future rule packs; the
  bundle tables land now so those packs have facts to read).

## Progress

This WO was split (comparable in size to WO-32, which took 6 separate
dispatches) after a first full-scope attempt correctly identified it
as too large to responsibly complete and verify in one pass. D1
(grammar only) is landed by this dispatch, in its own worktree branch
`wo34-d1` off `3d96812`; D2-D6 remain, tracked below.

### D1 -- grammar (LANDED)

`regolith-syntax` gains the `harness:` block (D99): a top-level
`harness <name>:` declaration (`HarnessDecl`) whose body holds one
`run <name>: from <ep> to <ep>` line (`RunStmt`, header recorded whole
per the WO-05 header-rest idiom, endpoints re-tokenized by elaboration)
with its own indented `along`/`bundle` lines (`AlongClause`/
`BundleClause`), plus `environment <name>: [lo, hi]` connector-class
lines (`EnvironmentStmt`, reusing the existing `[a, b]` bracket
grammar). All new words (`harness`, `run`, `along`, `bundle`, `route`,
`environment`) are CONTEXTUAL idents (D85 idiom), never new lexer
keywords -- no lexer/layout change.

Delivered:
- `SyntaxKind` variants (`syntax_kind.rs`): `HarnessDecl`, `RunStmt`,
  `AlongClause`, `BundleClause`, `EnvironmentStmt`.
- Typed AST wrappers (`ast.rs`): `HarnessDecl`/`RunStmt`/
  `AlongClause`/`BundleClause`/`EnvironmentStmt`, with accessors
  (`name`, `runs`, `environments`, `header_text`, `along`, `bundle`,
  `group`, `is_route_free`, `bound`) and a `File::harnesses()` entry
  point.
- Parser productions (`parser.rs`): `parse_harness_decl`,
  `parse_harness_body`, `parse_run_stmt`, `parse_run_body`,
  `parse_run_line`, `parse_environment_stmt`, wired into `parse_file`'s
  contextual-word dispatch beside `medium`/`flownet`.
- `formatter.rs`: no code change needed -- the formatter is fully
  token-kind driven and no new token kinds were introduced (contextual
  idents reuse `Ident`); round-trip covered by a new test.
- `checks.rs` / diagnostics: a parse-time structural check,
  `E0106 RUN_MISSING_ENDPOINT` (`regolith-diag` `Family::Parse`
  offset 6), rejecting a `run` header spelling neither `from` nor `to`
  -- required-field presence only, no name resolution.
- `docs/spec/toolchain/grammar.ebnf` updated in lockstep
  (`harness-decl`/`harness-body`/`run-stmt`/`run-body`/
  `along-clause`/`bundle-clause`/`environment-stmt`).
- Parser + checks unit tests (round-trip parse -> format -> parse
  included), all passing; no fuzz-target precedent was found in this
  crate for a single grammar addition in isolation (WO-31 did not add
  one either -- the crate's existing arbitrary-ASCII proptest in
  `parser.rs`/`formatter.rs` already exercises the new productions via
  its "never panics, CST covers every byte" property, so no new fuzz
  infrastructure was invented per the dispatch instruction to only
  follow a clear existing per-WO precedent).

**Escalation, documented not invented:** D99's prose describes the
routed PATH as one of two ALTERNATE forms -- declared waypoints
(`along <structural refs>`) XOR the planner-routed marker
(`route: free`) -- but D99's own worked example spells the
planner-routed run as `along route: free` (both words together). This
grammar does not silently pick a reading: `AlongClause` accepts the
run body's routed-PATH line WHOLE under either leading word (`along`
or `route`), covering the ref-list form, the example's combined
spelling, and a bare `route: free`/`route <name>` line, all via the
"structure recorded, not further decomposed" idiom already pervasive
in this grammar (`WorkloadParams`, generic declaration-header tails).
`AlongClause::is_route_free()` reads the recorded text back to decide
ref-list vs. planner-free; elaboration (D2) is expected to do the
same. If this reading is wrong, D2 corrects it without touching D1's
node shape (the text is preserved losslessly either way).

### D2-D6 -- remaining scope (NOT started by this dispatch)

- **D2 elaboration** (`regolith-lower`): run -> segment path against
  realized structural refs via the WO-32 extraction seam;
  lowered-given emission (length, env class, bundle tables) with
  snapshot-hash citations; endpoints-net consistency check;
  `route: free` unresolved-length handling (INV-21). Per the WO
  header's AMENDMENT (cycle 24, D128/AD-25), this should consume
  WO-42's realized-input channel rather than a hand-authored record,
  and per the dependency-graph note this WO should generally be
  dispatched AFTER WO-42 lands.
- **D3 BuildPayload**: `runs: IndexMap<RunName, RunRecord>` schema +
  payload wiring.
- **D4 rule-pack demand fixture**: one E06xx ampacity rule consuming
  `run.length`/bundle count.
- **D5 fixtures + goldens**: two-run harness fixture, planner-routed
  golden, negative fixtures (cross-net run, dangling endpoint, unknown
  bundle) -- D1 covers grammar-level unit tests only, not the corpus
  goldens this deliverable calls for.
- **D6 docs**: cuprite/04 `harness:` narrative section, cuprite/06
  lowering table row, `design/20-solver-abstraction.md` sec. 7 item 8
  marked landed -- D1 updated only `grammar.ebnf`, the grammar
  conformance artifact, not these narrative docs.

### D2-D6 -- landed (this dispatch)

**D2 elaboration.** `regolith_lower::harness_lower` mirrors
`flownet_lower`'s shape exactly: a `HarnessInputs` trait
(`structural_geometry`, `net_of`), an `AstHarnessInputs` (pure,
everything honestly deferred) and a `RealizedHarnessInputs` (layers
the WO-42 realized-input channel on top, matching
`RealizedFlownetInputs`). `elaborate_harnesses` re-tokenizes each
`RunStmt`'s header text into `from`/`to` endpoints, extracts every
`along` structural ref through `crate::extract::extract_path` (the
SAME seam a fluid edge reads -- concatenating multiple refs'
segment lists in declaration order for the multi-segment wire-run
case), and handles `route: free` by lowering an unresolved length
(`RunRoute::PlannerFree { resolved_length: None }`) -- INV-21: no
fabricated value; a later planner dispatch materializes a
`Cause::Planner` resolution.

Escalation, decided and documented (not silently reinterpreted): the
WO's own D5 bullet names three negative fixtures -- "cross-net run,
dangling endpoint, unknown bundle" -- but neither D99 nor this WO's
body defines what makes a bundle group "unknown" (there is no bundle-
declaration construct anywhere in the grammar; bundles are pure co-
membership labels). Read literally per the grammar's own "structure
recorded, not further decomposed" idiom (D1's own escalation
precedent): an `UnknownBundle` is a `bundle` clause present but whose
recorded text carries no group name after the keyword (an empty/
malformed line) -- `BundleClause::group()` already returns `None` for
exactly this case. A "dangling endpoint" is read as a `from`/`to`
header spelling both keywords (so D1's parse-time `E0106` stays
quiet) but naming no non-empty text on one side -- elaboration's own
endpoint re-tokenization failing. Both readings are unit-tested
(`unknown_bundle_is_an_error`, `dangling_endpoint_is_an_error`) and
self-calibrated against real compiler output in the negative corpus
(examples 52/51).

The endpoints-net consistency check (`E0306`) is a genuine open
integration point, escalated rather than invented: cuprite net
membership (which net a `component.port` endpoint belongs to) is not
exposed to `regolith-lower` through any existing seam today -- unlike
a flownet's self-contained net (built fresh per-flownet in
`fluid.rs::check_flownet` from that flownet's own AST), an electrical
net spans the whole entity DB via `connect`/query machinery this WO's
scope does not touch (adding that seam would be a `regolith-sem`/
`regolith-lower` cross-cutting change well beyond "no
routing/extraction logic outside the WO-32 `extract` module and this
WO's elaboration pass"). The check itself IS implemented against a
`net_of(endpoint) -> Option<NetName>` resolver method and fires
correctly whenever a resolver supplies both endpoints' nets
(`cross_net_run_is_an_error`, unit-tested); `AstHarnessInputs`/
`RealizedHarnessInputs` both honestly return `None` (mirrors
`AstFlownetInputs::geometry`'s D128-era deferred-ref precedent), so
the check stays silent in the real `check()` pipeline until a future
WO wires net-membership inference through. The 53rd negative fixture
(`53_run_cross_net.cupr`) is `EXPECT-TODO: E0306`, self-calibrated,
naming this gap in its own header.

Diagnostics render inline (`E0306`/`E0307`/`E0308`/`E0309`, new
`Family::References` offsets 6-9 in `regolith-diag`), not deferred to
"a later dispatch" the way `flownet_lower`'s own errors are: WO-34's
acceptance criteria explicitly demand a compile diagnostic for the
cross-net case, so rendering could not wait.

**D3 BuildPayload.** `regolith_oblig::harness::HarnessPayload`
mirrors `FlownetPayload`'s shape (content-addressed via
`HARNESS_DOMAIN_TAG`, `IndexMap<RunName, RunRecord>` sorted by name,
`BTreeMap` environments) with a `RunRoute` enum (`Waypoints` /
`PlannerFree`) carrying `RunSegment`s. Wired into
`LowerOutput.harnesses` / `BuildPayload.harnesses` (both `lower()` and
`lower_and_discharge()`) alongside `flownets`, with its own schemars
root export (`encoding.rs`, mirroring `FlownetPayload`'s "not reached
from any other Rust boundary type" note) and `SCHEMA_VERSION` bumped
15 -> 16. No obligation carries a `PayloadRef{kind: "harness", ..}`
(WO-34 adds no new claim form, per its own Goal text), so no
orchestrator payload-store wiring was needed -- a legitimate,
documented scope boundary, not a cut.

**D4 rule-pack demand fixture.** `examples/tracks/cuprite/
wiring_harness.cupr`: a `process wire_ampacity` pack with one
`dfm: rule ampacity_margin` whose `demand:` references
`r.length`/`harness.runs` (`forall r in harness.runs`), attached via
`stage bare: process=wire_ampacity`. Grammar+lowering golden only --
WO-28's engine remainder (static rule EVALUATION, `E0601`) has not
landed (`WO-28-*.md` Status: "deliverables 1-2 DONE"), so no
evaluation is claimed or faked, matching this WO's own D4 allowance
and the existing `35_rule_violation.hema` precedent for the same gap.

**D5 fixtures + goldens.** `wiring_harness.cupr` (two-run harness:
one declared-waypoint run, one `route: free` run, one `environment`
class) enrolled in `tests/golden/test_golden_corpus.py`'s `_CORPUS`
(golden: `tests/golden/data/wiring_harness.json`). It supplies no
realized-geometry compile input (the CLI `check()` path always passes
an empty `RealizedInputs` -- WO-42's orchestrator-side wiring for a
non-flownet consumer is a later integration than this WO), so its
`along` run honestly defers (`E0309`), the same "honest deferral"
shape already accepted for the WO-33 `regen_chamber`/
`suspension_link` fixtures in this corpus. The acceptance criterion's
"hand-computed segment sum exactly" and "changing the frame geometry
record ... breaks dependent goldens" (the G42 anti-staleness property)
are proven instead at the unit level, over a real realized-geometry
record via `RealizedHarnessInputs`/`extract_path`:
`two_run_harness_lowers_extracted_lengths` and
`changed_frame_geometry_changes_extracted_length`
(`crates/regolith-lower/src/harness_lower.rs`) -- the second asserts
the digest changes when only the frame record's length changes,
verbatim the property G42 demanded. Three negative fixtures landed at
`examples/negative/51_run_dangling_endpoint.cupr` (E0307, self-
calibrated), `52_run_unknown_bundle.cupr` (E0308, self-calibrated),
`53_run_cross_net.cupr` (E0306, `EXPECT-TODO` -- see D2's escalation).
Every existing golden-corpus fixture's committed JSON was regenerated
(`BuildPayload.harnesses` changes every payload's stable-snapshot
shape, same mechanical churn WO-33's `field_datums` addition caused).

**D6 docs.** `cuprite/04-structural-layer.md` gains sec. 1a ("Wiring
harnesses [SETTLED, cycle 20 D99; WO-34]"), condensing D99's shape,
the extraction-seam reuse, the net-check status, and the diagnostic
codes; sec. 1 item 2 (pin assignment) cross-references it.
`cuprite/06-lowering.md`'s construct x level matrix gains a
`harness:` run row. `20-solver-abstraction.md` sec. 7 item 8 is
marked `Status: LANDED`, naming the same net-check open point.

Status: `done`. `make check` green (fmt, clippy, Rust + Python tests,
core-import guard); no invariant this WO enables was reddened (WO-34
adds no new invariant).
