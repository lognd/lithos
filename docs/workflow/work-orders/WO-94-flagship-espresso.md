# WO-94 -- Flagship wave 2: espresso_machine promotion (the fluid flagship)

Status: done (2026-07-10 dispatch; full ledger below)
Language: corpus authoring + Python (gap-driven)
Spec: D196.1; toolchain/31-flagships.md; WO-70..75 close-outs;
  F115 addendum census (espresso_machine 127 obligations / 3
  discharged); fluorite/ spec + guide 03 (the track this flagship
  fronts -- the fleet has NO fluorite-led flagship).

## Goal

examples/systems/espresso_machine graduates to
examples/flagships/espresso_machine as the fluorite-led flagship:
thermal/hydraulic flownet claims discharging where models exist,
honest walls ledgered where they do not (the WO-92 close-out noted
nine fluid claims now LOWER but discharge `no_model` -- this WO
inventories exactly which fluid harness models are missing and
either lands the closed-form ones with citations or ledgers them),
plus the same flagship bar as WO-93 (optimizer pin, artifact set,
test net, honest census).

## Deliverables

1. The move (same path-spelling discipline as WO-93 deliverable 1).
2. Fluid-model inventory: for each `no_model` fluid claim, name
   the model it needs; land the citable closed-form ones (pressure
   drop / pump duty / thermal reach -- check what harness/models
   already covers and what feldspar exposes before writing
   anything new; NO DUPLICATION with either); ledger the rest.
3. Census-driven gap pass + one optimizer pin (duct/pump select or
   dimension), WO-93 posture.
4. Artifact bar via preview (flownet sheet + contract graph) +
   `regolith test` scenarios.
5. Docs: flagship README to the fleet shape; guide 03 example
   refresh if spellings drifted.

## Acceptance criteria

- Release build discharge count strictly above baseline (3);
  every remaining deferral specific; any new fluid model
  calibrated against a citable reference (the feldspar law).
- One real optimizer pin with trace. Artifact bar met via preview.
- No spec/grammar changes (escalate instead). `make check` green.

## Dependencies

WO-85/92 + preview landed. Independent of WO-93 (different
directories); both serialize with WO-87/WO-90 at integration only
through goldens (regenerate, never hand-merge).

## Ledger (this dispatch, 2026-07-10)

### Checklist

- [x] The move: `examples/systems/espresso_machine` ->
      `examples/flagships/espresso_machine`, ALL reference spellings
      updated (grepped both string-joined and Path-joined patterns:
      `tests/golden/test_golden_corpus.py`,
      `tests/golden/test_deferral_corpus.py`,
      `tests/golden/test_rules_cli.py`, `stdlib/jlc_2l/magnetite.toml`,
      `docs/guide/10-writing-dfm-rules.md`; only design-log verbatim
      history and this WO's own body retain the old path). Goldens
      regenerated via `REGOLITH_UPDATE_GOLDEN=1`, never hand-edited.
- [x] Fluid-model inventory + ONE citable closed-form landed:
      `fluid_darcy_weisbach_dp@1`
      (`python/regolith/harness/models/fluid_pressure_drop.py`) --
      single-segment Darcy-Weisbach `fluids.dp` (White, Fluid
      Mechanics 8th ed. sec. 6.6; Crane TP-410-adjacent), calibrated
      byte-for-byte against feldspar's compiled `fluids_darcy_dp`
      (`feldspar.library.fluids.incompressible.darcy_dp`, the SAME
      formula/citations) in `tests/harness/test_fluid_pressure_drop.py`
      -- the feldspar law satisfied. Routed in
      `orchestrator/translate.py` via the WO-72
      `_split_named_call_predicate`/`_match_call_lhs` non-frame
      call-form pattern (`_translate_fluid_dp`); end-to-end routing
      test `tests/orchestrator/test_wo94_fluid_dp_routing.py`.
- [x] Census: fresh baseline (this worktree's master base, after
      WO-87/90/92/96) 126 obligations / 3 discharged; final 126 / 4
      discharged -- strictly above baseline. `thermosiphon.fluo`'s
      `Circulation.dp` (the `feed` edge, a genuine single Pipe
      segment) discharges via the new model with inline Darcy kwargs.
- [x] Optimizer pin: `regolith optimize --spec
      optimize.brew_line_tube.json --budget-evals 20` over the
      `std.fluid.copper_tube` family (ASTM B88 Type L) -> winner
      `type_l_half_in`, `termination=converged`, lockfile row
      `optimize.winner = brew_line_tube=type_l_half_in cause:
      optimize(declared_objective, trace=blake3:43b3db7f...)`
      (committed as `examples/flagships/espresso_machine/regolith.lock`).
      Feasibility per candidate computed with the SAME Darcy closed
      form against the corpus's own 30kPa `supply_dp` budget.
- [x] Artifact bar via preview: `regolith preview --out DIR --spec
      preview.spec.json` writes 21 files -- three fluid P&ID sheet
      quintets (BrewPath 11n/10e, GroupThermosiphon 4n/5e,
      SteamService 3n/3e; drawing.json/svg/pdf/dxf/explain.txt each)
      + the contract-graph quintet (22n/8e) + `gate_summary.json`,
      all stamped `PREVIEW -- NOT RELEASED: 122 unresolved`.
      REQUIRED FIX (in scope, Python-only):
      `regolith.backends.ship.derive_producer_inputs` never populated
      `BackendInputs.flownets` from a real build (a flownet
      `PayloadRef` resolves through the discharge-time `PayloadStore`
      channel, never `report.realized_inputs`) -- the fluid sheet was
      unreachable via preview/ship for EVERY fluorite project; a
      `payload_json["flownets"]` fallback now mirrors the existing
      harnesses/contract_graph fallback (tests in
      `tests/backends/test_ship.py`).
- [x] `regolith test` scenarios, one per track the design spans:
      `reservoir.test.hema` (Capacity.usable, indeterminate),
      `control_board.test.cupr` (Noise.adc_floor, indeterminate),
      `thermosiphon.test.fluo` (Circulation.dp, DISCHARGED -- the
      fleet's first non-indeterminate `.test.<ext>` expectation).
      All 3 pass + the 10 jlc_2l rule-pack fixtures.
- [x] Docs: flagship README rewritten to the fleet-table shape
      (file|track|contract map + "WO-94 flagship bar" section with
      the census, model citations, pin evidence, and escalations).
      Guide 03 spellings checked -- no drift found.
- [x] `make check` green FOREGROUND (fmt/clippy/ty/guard-core/
      schema-check/cargo tests/1486 pytest + 21 graphite).

### Fluid-model inventory (deliverable 2, the no_model census)

LANDED: `fluids.dp` single-segment Darcy-Weisbach (above).

LEDGERED (each needs a model out of this WO's citable-closed-form
scope; named, not fabricated):

- `supply_dp` (brew_water.fluo): also `fluids.dp(...)` but spans
  THREE dissimilar edges (flowmeter dp curve + check valve + braided
  hose) -- a single-segment lumped-pipe fiction would be dishonest;
  defers `fluids.dp_inputs_missing` naming the exact inputs. Needs
  series network reduction over per-edge dp models (feldspar's
  `series_dp` exists but the per-edge inputs do not resolve from the
  net yet).
- `npsh` (fluids.npsh_margin): needs vapor-pressure-at-temperature
  (IAPWS) + suction-side head resolution; feldspar `npsh_available`
  exists, the given-resolution channel does not (escalation 1).
- `hammer`/`no_vac`/`recover`/`brew_hold`/`steam_hold` (peak/settles
  temporal forms): need transient network models (Joukowsky exists in
  feldspar for the instantaneous-closure bound, but the claim
  windows on an event ledger the harness cannot yet evaluate).
- `flow`/`stall` (fluids.mdot on the buoyancy loop): natural-
  circulation loop solve (density-difference driving head vs loop
  resistance) -- pack territory, no closed form fits honestly.
- `swell`/`leaks` (volume/leak budgets): compliance integration over
  edge records; `rate`/`band`/`single_fault` (steam net): gas-regime
  models explicitly deferred by the WO-52 v1 posture.
- `heat_bank`/`group_sag`/`gasket_s`/`gasket_b`/`mains_fit`/
  `headroom`/`split`/`kick`/`adc_floor`/`standby_floor`/`usable`/
  `surface`/`cost`x6/`drc(...)`: mech/elec/cost families outside the
  fluid inventory this WO owns (several are WO-90-territory opaque
  requires).

### Escalations (recorded, not worked around)

1. FLUID GIVENS NEVER REACH DISCHARGE: `push_fluid_obligation`
   (`crates/regolith-lower/src/claims.rs`) hardcodes
   `given: Given { loads: Vec::new(), .. }` -- every corpus fluid
   claim's `given <ident> = <expr>` suffix (`given T_group = 90degC`,
   `given v3 = brew`) is parsed and DROPPED for fluid obligations.
   Recommendation: thread the claim-suffix givens into
   `given.loads` (the `given_for_decl` pattern) in a follow-up Rust
   WO; until then every fluid model must read inline call kwargs
   (this WO's precedent). NO grammar/schema change was made here.
2. NO fluorite discrete-select construct (`in registry(...)` is
   calcite-only): the optimizer pin drives the generic
   `regolith optimize --spec` CLI. Recommendation: a fluorite
   `dia = in registry(std.fluid.copper_tube)` edge-parameter select
   as a cycle-34+ design item.

### Honest golden churn (regenerated, inspected)

Fleet-wide, six `fluids.dp(...)` claims (cnc_router `jet`/`margin`,
dune_buggy `restriction`, small_office `margin`, espresso
`supply_dp`) move from generically "lowered" (then `no_model` at
discharge) to the SPECIFIC `fluids.dp_inputs_missing` deferral naming
the five Darcy inputs -- strictly more informative, zero new VIOLATED
verdicts. espresso `dp` moves lowered -> discharged.
