# WO-34: Routed runs (wiring-harness declarations + shared extraction)

Status: todo
Depends: WO-32 (the routed-geometry extraction seam -- consumed, not
reimplemented), WO-31 (grammar precedent only). Answers feldspar G42
(`20-solver-abstraction.md` sec. 7 item 8, D99).
Language: Rust (`regolith-syntax` cuprite `harness:` grammar,
`regolith-lower` run elaboration); Python (orchestrator lockfile
causes for planner-routed paths)
Spec: design-log 2026-07-07-cycle-20 D99 (decision; this file
carries the full shape); cuprite/04 (structural layer -- the
`harness:` block lands beside `board`), cuprite/06 lowering table;
fluorite/03 sec. 1 (the extraction seam contract);
AD-17/AD-22/AD-23 (runs are NOT nets -- no net-core involvement).

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
   `environment` class declarations; `grammar.ebnf` + fuzz targets
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
   cuprite/06 lowering table row; `20-solver-abstraction.md` sec. 7
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
