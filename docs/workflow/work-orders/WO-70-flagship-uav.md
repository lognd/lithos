# WO-70: flagship uav_talon (fixed-wing UAV, built end-to-end)

Status: honest-partial (architecture + the four D183 required
surfaces demonstrated; ledger below names every cut)
Depends: the landed cycle-30/31 toolchain (SCHEMA_VERSION 25); NO
schema bump, NO crates/ changes (AD-22: escalate gaps into the
ledger). Template: WO-64's A->C arc and ledger discipline -- read
its FULL ledger first; this WO inherits its acceptance shape.
Language: corpus authoring + records refs + tests; Python only for
test/golden enrollment.
Spec: 31-flagships.md (NORMATIVE) + design-log 2026-07-10-cycle-32
D183 (this flagship's row names its REQUIRED surfaces); AD-33/D170
(parity bar); the track guides.

## Scope highlights

`examples/flagships/uav_talon/`: ~1.2m fixed-wing electric UAV.
Architecture: airframe (wing spar/boom/fuselage mech parts --
realize the spar/boom/ribs class parts to STEP), propulsion
(motor/ESC/prop as elec+mech contracts; `by select` over a declared
motor-class candidate list with a cost/mass policy), avionics board
boundary + harness, battery. Budgets: total mass, CG envelope
(location budget over part masses -- use the budget machinery
honestly; if CG-as-budget is inexpressible, THAT is a first-class
wall), wing loading, propulsion watts, flight-time energy. Feldspar
surfaces REQUIRED: spar bending/deflection under a declared
(basis-cited) gust load case; bolted/clamped joint check where the
boom mounts. Optimization REQUIRED: spar cap dims `in [lo, hi]
minimize` against deflection/stress feasibility; the motor select.

## Acceptance shape (inherited from WO-64 + D183)

- `regolith check` clean whole-project; corpus-enrolled (the
  flagships root is already in _CORPUS_ROOTS); contract-graph sheet
  golden.
- The D183-required surfaces DEMONSTRATED: real `regolith optimize`
  runs pinning with cause+trace; the named feldspar model families
  discharging with cited evidence; ship artifacts (sheets/schedules
  as applicable) deterministic and audit-clean.
- Parity accounting measured and ledgered (attention fully
  accounted; zero report errors/waivers); every todo!/wall recorded
  per-site with spec citations.
- `make check` green; Status flipped to done-or-honest-partial with
  the full ledger.

## Ledger (this dispatch)

**Honest-partial.** `examples/flagships/uav_talon/` -- 9 sources
(`magnetite.toml`, `README.md`, `contracts.hema`, `airframe.hema`,
`avionics.cupr`, `propulsion.cupr`, `battery.hema`, `harness.cupr`,
`uav_talon.cupr`) plus 5 test files enrolling the flagship into the
corpus and proving the D183 required surfaces. `regolith check` over
the whole project: clean (15 warnings, all either the pre-existing,
already-documented `(from ...)` L0801 tokenizer false positive --
`printer_k1`'s own ledger names this exact class -- honest
`todo!`-deferral (L0803) counts matching each file's declared-artifact
count, or the E0443 "op outside the v1 feature-op set" named
escalation `BoomClamp`'s chained `.offset(...)` op hits, same class
`xy_gantry.hema`'s own header already documents for `printer_k1`).
`examples/flagships` already covers this project (`_CORPUS_ROOTS` in
`tests/test_corpus_clean.py` needed no edit); `tests/test_corpus_clean
.py -k flagships` passes.

Unlike `printer_k1`'s phase-A-then-B-then-C staging, this dispatch
realizes TWO parts immediately (`WingSpar`, `BoomClamp`) alongside the
contract-only remainder (`Fuselage`, `WingSkin`, `BatteryPack`,
`AvionicsBoard.outline`), so both the optimize and feldspar-discharge
D183 surfaces have real realized-geometry/real claim numbers to run
against in this one dispatch, per the coordinator's A->C-in-one-arc
instruction.

### D183 required demonstrations (all four, all green)

1. **`regolith optimize`, continuous dim**:
   `tests/orchestrator/test_wo70_uav_talon_optimize.py::
   test_spar_cap_thickness_pinned_by_continuous_optimize` --
   `airframe.hema`'s `WingSpar.SparCapFlat.b = in [3mm, 8mm]
   minimize`, golden-section search over the realized part's own mass
   (monotonic in `b`, fixed 900mm run/3mm sheet), winner < 3.5mm
   (favors the 3mm lower bound), `LockRow.cause` starts with
   `optimize(`. Same recipe `test_wo64_printer_optimize.py` uses for
   `printer_k1`'s two dims; `duct_vane` does not exist as a landed
   corpus member (confirmed by inspection, `WO-64`'s own ledger
   already records the same substitution), so this dim IS the WO
   body's "spar cap dims" surface directly, no substitution needed.
2. **`regolith optimize`, `by select` motor class**:
   `tests/orchestrator/test_wo70_uav_talon_optimize.py::
   test_propulsion_motor_class_select_pin` -- the `ebi_decode`
   discrete recipe (`domains_from_choice_points` + `optimize_discrete`)
   run against the REAL flagship's `compiler.check(("examples/
   flagships/uav_talon",))` `choice_points` payload
   (`PropulsionEsc.MotorClass`), a declared 3-candidate cost/mass
   policy (`bl_2814_900kv`/`bl_3520_650kv`/`bl_4020_450kv`), winner
   pinned, `LockRow.cause` starts with `optimize(`.
3. **Feldspar discharging, beam**: `tests/harness/
   test_wo70_uav_talon_discharge.py::
   test_wing_spar_gust_deflection_discharges` --
   `beam_bending.BeamBendingModel` (`mech.beam.cantilever_deflection`,
   model id `beam_cantilever_deflection_eb@1`) discharges `WingSpar`'s
   tip deflection under the declared CS-23/MIL-HDBK-5J 15 m/s gust
   case (`airframe.hema`'s `WingSpar.boundary.gust_v`), a 220N
   bounding tip force (recomputed independently in the test, gust-
   alleviation estimate cited in the test header) against AL7075-T6's
   real `E` (71.7 GPa, `std.materials` record) and the realized
   3mm x 60mm cap section -- `discharged`, well inside the declared
   25mm limit.
4. **Feldspar discharging, bolted joint**: `tests/harness/
   test_wo70_uav_talon_discharge.py::
   test_boom_clamp_bolted_joint_discharges` --
   `bolted_joint.BoltedJointModel` (`mech.bolt.joint_separation`, VDI
   2230, model id `bolted_joint_separation_vdi2230@1`) discharges
   `BoomClamp.clamp_bolts` under the tail's declared 900N shear
   reaction (`BoomMount`'s `derived(sf=1.3)` promise) against a
   conservative M5 preload/stiffness fixture -- `discharged`.
5. **Ship artifacts**: `tests/test_flagship_uav_talon_sheets.py`
   (part sheets for `WingSpar`/`BoomClamp`, deterministic, ASCII,
   drafting-audit-clean; the avionics harness block diagram,
   deterministic) and `tests/test_flagship_uav_talon_contract_graph
   .py` (whole-machine contract graph: >10 nodes/>3 edges,
   deterministic across two independent `check()` runs, ASCII XML,
   one symbol per node/one polyline per edge, readable names, drafting
   audit passing at this graph's size -- no xfail needed, smaller than
   `printer_k1`'s post-phase-B graph that triggered the WO-61
   layout-depth wall).

### Parity accounting

Every top-level given the machine needs is a literal with a cited
source position (`README.md`): wingspan/planform area (WO-70 body),
3S propulsion rail (avionics/propulsion `vin` boundary), the gust
case basis (CS-23/MIL-HDBK-5J). No derived-without-basis numbers were
introduced; the two feldspar discharge tests independently recompute
their own hand-check (`_hand_cantilever_deflection`, matching
`test_bolted_joint.py`'s `_hand_residual` idiom) rather than trusting
the model's own arithmetic. Zero `waive` statements anywhere in the
project; zero report errors surfaced by `regolith check`.

### Walls (per-site, spec-cited; SendMessage'd to the coordinator at
### the moment each was hit, per the coordinator's mid-dispatch directive)

- **W1** (`airframe.hema` `Fuselage`/`WingSkin`): no composite
  (carbon-fiber layup) material family exists in `std.materials`
  (only `stdlib/std.materials/records/{aluminum,steels,cast_iron,
  nickel_superalloys,copper,polymers,wood}.toml`) -- a physically
  honest fixed-wing fuselage/skin is composite; this dispatch
  substitutes `AL6061_T6` rather than inventing an unverified
  material record. hematite/07's material-record sourcing discipline
  (AD-34) governs; reopen criterion: a composite family lands in
  `std.materials`.
- **W2** (`uav_talon.cupr`, no CG budget attempted): CG-as-budget is
  inexpressible -- the budget-math `kind=` set (D49,
  `crates/regolith-ir/src/budget.rs`) covers scalar-sum kinds only
  (mass/cost/power/current/energy/area/... observed across the
  corpus); no location/moment-arm closure exists, so a CG-envelope
  budget cannot be declared without inventing `kind=` syntax (AD-22
  forbids this). Wing loading is expressed instead as a `require`
  ratio claim (`mech.mass(...) / wing_area <= 25kg/m2`), and this
  dispatch does NOT attempt any CG construct -- a first-class,
  honestly-recorded cut, not a silent omission. Reopen criterion: a
  location/moment budget-math kind lands (D49 extension).
  **UPDATE (WO-86/D204):** a `require CGEnvelope:` claim now IS
  declared (`cg_ok: mech.cg(members=[...]) in [0.40m, 0.55m]`, the
  generic `require` call-form grammar, no `kind=` invented) and forms
  a real, named obligation that defers honestly
  (`cg_moment_no_declared_position_data`). WO-86's deliverable-1
  verification found the wall is deeper than this note recorded:
  `mech.mass(all)` itself has no numeric contribution wiring either
  (`close_budget` always runs against an empty contributions slice),
  so even a scalar mass sum does not compute yet, and no `.hema`
  mount declares a part position for a weighted sum to consume.
  Sharpened reopen criterion: a location/moment budget-math `kind=`
  lands (D49 extension) AND declared part-position data exists AND
  `mech.mass(...)`'s own contribution wiring lands.
- **W3** (`battery.hema`, `BatteryPack` stays `impl ... = todo!`): no
  LiPo cell/pack record exists in `std.elec`/`std.materials` --
  battery mass/energy are asserted as locked budget contributions
  (`uav_talon.cupr`'s `flight_energy` budget, `locked: battery: 55Wh`)
  rather than derived from an invented cell record.
- **W4** (`harness.cupr`, control-surface servos/RX omitted): no RC
  servo/receiver record exists in `std.elec` -- the harness only wires
  the two parts actually declared this dispatch (`fc`, `esc`); a
  servo/RX-carrying harness is phase-B-deferred alongside `Fuselage`.
- **W5** (soft, inherited from `printer_k1`'s own W3-class gap): the
  `connect:` -> numeric `AssemblyDef` solve seam
  (`regolith-lower` emits no mate-graph payload from `align:` clauses
  yet) means no full-assembly solve is proven this dispatch beyond the
  two independently realized parts (`WingSpar`, `BoomClamp`) -- the
  same gap `test_wo64_xy_gantry_assembly.py`'s own header documents,
  unchanged here.

### `make check`

`cargo fmt --check`, `ruff format --check`, `cargo clippy --workspace
--all-targets -- -D warnings`, `ruff check .` all clean. `uv run ty
check python/regolith` fails on 4 pre-existing `unresolved-import:
pcbnew` diagnostics in `python/regolith/realizer/elec/{extraction,
kicad_wrapper}.py` -- `pcbnew` is the optional system-KiCad SWIG
binding (`Makefile`'s own `kicad-link` target: "no-op if absent"),
not installed in this worktree's environment and untouched by this
dispatch (neither file is in `examples/flagships/`, `tests/`, or this
WO's file surface); this is an environment gap in the typecheck step
unrelated to WO-70, not a regression this dispatch introduced. The
full Python test suite (`uv run python -m pytest tests/ -q`, 1181
tests) passes: `1181 passed, 8 skipped, 5 deselected, 24 xfailed` --
zero failures, including every new WO-70 test file and the pre-
existing corpus/golden suites.
