# WO-34: Routed runs (wiring-harness declarations + shared extraction)

Status: in-progress
Depends: WO-32 (the routed-geometry extraction seam -- consumed, not
reimplemented), WO-31 (grammar precedent only). Answers feldspar G42
(`../design/20-solver-abstraction.md` sec. 7 item 8, D99).
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
   `environment` class declarations; `../grammar.ebnf` + fuzz targets
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
   cuprite/06 lowering table row; `../design/20-solver-abstraction.md` sec. 7
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
- `docs/implementation/grammar.ebnf` updated in lockstep
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

Status stays `in-progress` (not `done`) until D2-D6 land.
