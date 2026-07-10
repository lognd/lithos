# WO-64: flagship-1, the FDM printer (phase A: contract-first)

Status: done (phases A-C; residuals in ledger)
Depends: phase A -- nothing beyond the landed toolchain (authoring
only). Phase B: WO-62 (assemblies), WO-63 (parity), stdlib as
landed. Phase C: phase B. NO schema bump any phase.
Language: corpus authoring (`.hema`/`.cupr`/`.fluo` +
magnetite.toml + records) + Python only for golden/corpus test
enrollment.
Spec: docs/spec/toolchain/31-flagships.md (NORMATIVE),
00-architecture.md AD-33 (+ AD-22's escalation discipline),
design-log 2026-07-09-cycle-31 D172; regolith/08 sec. 3
(contract-first = L0->L2 only); the track guides (01-04) for
authoring conventions.

## Goal (phase A)

`examples/flagships/printer_k1/` -- a complete FDM printer
architecture at L0->L2, `regolith check` clean with ZERO artifacts:
the machine exists as interfaces, budgets, promises, and claims
before any part is drawn, proving contract-first at machine scale
and producing the walls list that gates phase B.

## Phase A deliverables

1. **Project skeleton**: `examples/flagships/printer_k1/` with
   magnetite.toml (profiles: cost + mass), a README naming the
   machine's envelope targets (220x220x250 build volume class,
   24V system, single direct-drive extruder) as asserted givens
   with source positions (the parity attention list will show
   them -- that is correct and honest).
2. **System architecture** (the L2 deliverable): frames +
   interfaces for: base/frame structure, XY gantry motion, Z bed
   motion, extruder+hotend, bed (heated), electronics bay
   (controller board boundary as a cuprite interface), PSU,
   harness boundary, enclosure-optional seam. Budgets: total mass,
   BOM cost (magnetite cost profile), wall power, 24V rail current,
   hotend + bed thermal watts. Promise-backed claims wherever a
   number is demanded of a not-yet-designed artifact (derived
   (sf=...) loads on gantry members, motion accel targets ->
   force promises, melt-rate -> hotend watt promise).
3. **Track stubs with contracts, not bodies**: mech artifacts
   declared with `impl ... = todo!` where phase B will realize
   (honest deferral, ledgered); the controller board as a cuprite
   artifact with its port contract + an EBI decode `by select`
   carried over from the ebi_decode shape; the hotend melt path +
   part-cooling air path as fluorite nets at contract level; the
   harness as declared runs.
4. **Corpus enrollment**: flagship registered in the corpus test
   dicts (clean-check + fmt only at phase A -- goldens that pin
   diagnostics-empty state); contract-graph sheet ship-spec block
   (the WO-61 producer's machine-scale test) with its golden.
5. **The walls list**: every place the author WANTED a construct
   and stopped (missing vocabulary, missing solver, missing
   record) recorded in this WO's ledger as findings with spec
   citations -- the phase-B/C gate input and the real deliverable
   beside the architecture. NO side channels, NO invented syntax:
   a wall stops the leaf (AD-22/F96).

## Phase A acceptance criteria

- `regolith check` clean (zero diagnostics, zero waivers) over the
  whole flagship; budgets sum and close; every interface two-sided;
  `impl todo!` count = the declared artifact count (nothing
  realized, nothing skipped silently).
- Contract-graph sheet renders the machine legibly (golden);
  fmt-idempotent; ASCII.
- The walls list exists in the ledger (even if empty -- state so);
  every entry cites the spec section that governs the gap.
- `make check` green with the flagship enrolled; Status line
  updated to `phase A done (B/C gated)`.

## Ledger (this dispatch)

**Done.** `examples/flagships/printer_k1/` -- 14 files, 12 of them
sources (`magnetite.toml`, `README.md`, `contracts.hema`, `frame.hema`,
`xy_gantry.hema`, `z_motion.hema`, `bed.hema`, `extruder.hema`,
`enclosure.hema`, `thermal.fluo`, `controller.cupr`, `psu.cupr`,
`harness.cupr`, `printer_k1.cupr`). `regolith check` over the whole
project: 0 errors, 25 `todo!`-honest-deferral warnings (matches the
declared-artifact count exactly, per file: bed 2, controller 4,
enclosure 2, extruder 3, frame 7, xy_gantry 5, z_motion 2) plus the
pre-existing, already-documented `(from ...)` L0801 lint false-
positive (`tests/test_corpus_clean.py`'s own generic exception) --
zero unexpected diagnostics, zero `waive` statements. `regolith fmt`
is a no-op on every file (byte-idempotent). `examples/flagships` added
to `tests/test_corpus_clean.py`'s `_CORPUS_ROOTS` (D1); the flagship
now rides the same clean-check gate as every other corpus root.

- D1 (project skeleton): `magnetite.toml` (depends + one
  `[profiles.cost.prototype]`/`[profiles.cost.default]` pair, D147
  shape); `README.md` names the three envelope-target givens (220 x
  220 x 250mm build volume, 24V rail, single direct-drive extruder)
  with their exact source position in the project (each is a literal
  the parity report's attention list will show -- correct and honest
  per AD-33, not a derived value).
- D2 (system architecture): `contracts.hema` is the shared
  project-local interface/mating pack (NO DUPLICATION discipline,
  torch_igniter.hema's own precedent) -- `RailMount`, `LeadscrewMount`,
  `StepperMount` (carries the motion-accel -> reaction-force promise,
  `loads: axial: derived(sf=1.5)`), the cross-domain `CardBay`/
  `BoardOutline`/`CardMount` triple (substrate 10 sec. 3's "geom role
  kit" pattern, precedented by `cubesat/contracts.cupr`'s `CardBay`/
  `CardMount`), `HotendPocket` (carries the melt-rate -> watt promise,
  `thermal: watts: derived(sf=1.2)`), `BuildPlatformMount`,
  `PanelSeal`, and four matings (`LinearSlide`/`LeadscrewDrive` use
  `dof: removed=[...]` naming freedoms explicitly rather than needing
  a canned "prismatic" mating class, `HotendMount`, `PlatformMount`).
  `printer_k1.cupr`'s `PrinterK1` system carries `boundary.build_volume`
  (parts have no `boundary:` of their own, hematite/03 sec. 5) and
  five budgets: `mass_total` (kind=mass), `bom_cost` (kind=cost,
  profile=prototype), `wall_power` (kind=power), `rail_current`
  (kind=current), `hotend_bed_thermal` (kind=power, `locked:` entries
  citing the direct-drive-hotend/220mm-bed classes) -- every budget's
  `require:` limit is a literal, so `close_budget` (regolith-ir/src/
  budget.rs) actually sums and checks each one at `check` time, not
  just parses it.
- D3 (track stubs): every mech `part`/`board` binds its interfaces
  `impl <I> for self [as <name>] = todo!` (torch_igniter.hema's
  deferred-conformance form) -- zero `stage`, zero feature body, zero
  realized artifact anywhere in the project. `controller.cupr`'s
  `ControllerBoard` carries `impl AddressDecodeGlue by select(nor_glue,
  cpld, mcu_chip_selects)` verbatim from `ebi_decode.cupr`'s shape
  (WO-56 D161); `ControllerMcu` is the port contract (behavioral
  altitude, `ports:`/`params:`/`spec:`/`require:`, no `impl` at all --
  contract-only, unrealized, exactly like a `block` nobody has bound
  yet). `thermal.fluo`'s `PartCooling` flownet is the part-cooling air
  path (`Imposer(driven_by=controller.part_cool_fan.duty)` -- the
  cross-track promise chain, fluorite/02 sec. 3); the hotend MELT path
  is NOT a fluorite net (see wall W1 below) -- its thermal contract
  rides `HotendPocket.thermal.watts` instead, consumed by
  `hotend_bed_thermal`. `harness.cupr`'s `ControllerLoom` declares
  nine `route: free` runs (D99's planner-routed form, never a
  hand-asserted `along` waypoint list -- phase A has no realized-
  geometry compile input, so an `along` run would honestly fail
  extraction, `wiring_harness.cupr`'s own documented E0309 shape;
  `route: free` keeps this file diagnostics-clean while still
  declaring every run/bundle/environment WO-34 asks for).
- D4 (corpus enrollment): `tests/test_corpus_clean.py`
  `_CORPUS_ROOTS` gains `"examples/flagships"`. The contract-graph
  sheet + its golden: `tests/test_flagship_printer_contract_graph.py`
  -- pulls the REAL `ContractGraphPayload` off `compiler.check(
  ("examples/flagships/printer_k1",))`'s `BuildOutcome.payload_json`
  (not a synthetic fixture, unlike `tests/backends/test_drawings.py`'s
  `bearing_assembly` shape), renders it through WO-61's
  `diagram.contract_graph` producer, and asserts: >10 nodes / >3 edges
  (a real machine, not a toy), determinism across two independent
  `check()` runs (both the payload model and the rendered SVG bytes),
  valid ASCII XML, one symbol per node / one 3-segment polyline per
  edge, a clean drafting audit (`run_drafting_rules`), and readable
  (non-hash) names -- the WO-61 acceptance criterion this WO's own
  deliverable 4 asks to exercise at machine scale.
- D5 (the walls list): three findings below.

### Walls (phase-B/C gate input)

- **W1 -- no polymer-melt fluid medium/record exists (fluorite/02
  sec. 1; AD-34 sourcing law).** `medium` requires `props:
  registry(<name>)`; every corpus medium cites one (water/air/N2/RP1/
  brake fluid/... in `std.fluid`). No non-Newtonian filament-melt
  property record (rho(T), mu(T) for a polymer melt, not a simple
  liquid/gas) exists in `std.fluid`, and authoring one is out of this
  WO's file surface (phase A: `examples/flagships/printer_k1/` +
  corpus test dicts only, never `stdlib/`) -- inventing an unsourced
  record here would also violate AD-34's sourcing law (a record needs
  a cited document + revision, never an invented number). The hotend
  melt path is therefore NOT expressed as a fluorite net in
  `thermal.fluo`; its thermal contract rides `contracts.hema`'s
  `HotendPocket.thermal.watts` promise slot instead (honest deferral
  of the NET, not the wattage claim -- see `thermal.fluo`'s own header
  comment). Phase-B/C ask: a `std.fluid` polymer-melt medium family
  (WO-66 stdlib depth is the natural gate; feeds WO-66 coordination
  directly).
- **W2 -- no small DC blower/axial-fan pump-curve record exists in
  `std.fluid` (fluorite/02 sec. 3, the `Pump(curve=registry(...))`
  component).** The part-cooling fan is modeled as an `Imposer(
  driven_by=controller.part_cool_fan.duty)` instead (fluorite/02 sec.
  3's cross-track promise-chain form, `dual_brake_circuit.fluo`'s own
  precedent) -- a legitimate, spec-sanctioned alternative to `Pump`,
  not a workaround, but it means the fan's actual head-flow curve
  (needed once phase B's flownet solve runs for real) still has no
  record to bind to. Phase-B/C ask: a small 5V/12V/24V DC blower/axial
  fan family in `std.fluid` (WO-66 stdlib depth).
- **W3 -- no prismatic/linear-slide mating primitive exists in
  `std.mech.matings`** (hematite/03 sec. 3's `mech.matings` provides
  list: `BoltedFlange`, `BoltedPattern`, `CompressionSpring`,
  `FaceSeal`, `FlangeMount`, `GearMesh`, `KeySeat`, `KeyedBore`,
  `KeyedShaft`, `PinnedLoop`, `PressFit`, `Revolute`, `ScrewedLap`,
  `ShaftCouple`, `SpringSeat`, `ThreadedMate` -- `Revolute` is the
  only canned single-exposed-dof joint, and it is rotary). NOT a
  compiler wall: `mating`'s own `dof: removed=[...]` vocabulary
  already lets a project declare the freedoms explicitly (this WO's
  `contracts.hema` does exactly that for `LinearSlide`/
  `LeadscrewDrive`, mirroring `Revolute`'s `exposing theta`
  convention with `exposing x`/`exposing z`), so this is recorded as
  an authoring-ergonomics gap, not a blocked leaf: a std `Prismatic`
  mating type (mirroring `Revolute`) would save every future linear-
  motion project this same boilerplate. Phase-B/C ask, soft (WO-66 or
  a future `std.mech.matings` growth pass; does not gate phase B on
  its own).

No other wall: every other construct phase A's deliverables asked for
(interfaces, promise-backed `derived(sf=...)` loads, cross-domain
mixed interfaces, `by select`, budgets incl. a `kind=current` budget
-- `kind=` is pack-provided/undocumented-enum at the IR level,
`regolith-ir/src/nodes.rs`'s `Budget` struct carries no kind field at
all, so `current` is exactly as legal as `mass`/`energy`/`power`/
`cost`/`error`/`tolerance`/`deflection`/`noise`/`timing`, and its
dimension is checked ordinarily against the `require:` limit's own
unit) was directly expressible with landed syntax.

### Walls closed (WO-66 follow-up dispatch, 2026-07-10)

- **W1 -- CLOSED (content only).** `std.fluid` gained
  `records/polymer_melt.toml` (`[[polymer_melt]]`, shape ratified as
  design-log D182): a `pla_class` record (solid density + melting/
  process-temperature window from NatureWorks Ingeo 4043D's TDS;
  melt-density points evaluated directly from US Patent 9,045,611's
  own stated linear thermal-expansion relation; one zero-shear
  viscosity point at 200C from Arrigo & Frache 2022, Polymers 14(9):
  1754, open access) and a `petg_class` record (solid density/
  melting point/process window from MG Chemicals' PETG TDS; melt
  density and viscosity OMITTED with a note -- no independently
  verifiable source found this session). The hotend melt path is
  STILL not expressed as a fluorite net in `thermal.fluo` -- that
  authoring change is phase-B/C's own scope, not this follow-up's;
  this dispatch only removes the "no medium record exists at all"
  blocker, it does not rewire `thermal.fluo`.
- **W2 -- CLOSED (content only).** `std.fluid`'s `components.toml`
  gained two more `[[pump]]` rows (the same table `Pump(curve=
  registry(...))` binds to): `sunon_mf40201vx_1000u_a99`
  (kind=`dc_axial_fan`, 12V 4020-class, rated flow/pressure endpoints
  only, real-catalog cited) and `delta_bfb0524hh` (kind=
  `dc_radial_blower`, 24V 5015-class, official-manufacturer-page
  cited; max static pressure OMITTED -- distributor listings
  disagreed on rated current and this dispatch would not land an
  unconfirmed pressure figure on top of that). The part-cooling fan
  in `controller.hema` is STILL modeled as the `Imposer(driven_by=
  controller.part_cool_fan.duty)` alternative form (fluorite/02 sec.
  3) -- binding it to one of these curve records instead is phase-B/
  C's own authoring change, out of this follow-up's file surface.
- **W3 -- CLOSED (content only, as predicted "authoring-ergonomics,
  not a compiler wall").** `std.mech`'s `magnetite.toml` gained
  `Prismatic` in `mech.matings` (mirrors `Revolute`'s single-
  exposed-dof pattern; `mating`'s own `dof: removed=[...]`/`exposing`
  vocabulary already covers the semantics, so this is purely a name
  in a `[provides]` list -- no grammar, schema, or Rust change).

None of the three walls needed a compiler/schema change to close;
all three closures are pure `stdlib/` content, landed by the WO-66
follow-up dispatch (its own ledger has the full sourcing detail).
Phase B/C's own authoring work (wiring these records into
`printer_k1`'s `.fluo`/`.hema` files) is still ahead and out of this
note's scope.

## Phase B ledger (this dispatch, 2026-07-10)

Honest partial per the dispatch's own instruction (parity clean is
NOT required for phase B; the honest count is). `make check` green;
every remaining `todo!` keeps a per-site reason below.

### What realizes

**Parts realizing to STEP** (proven via `realize_feature_program`,
the same producer path `tests/realizer/mech/test_assembly.py` and
`tests/backends/test_ship.py` use to prove any part in this corpus
realizes -- no `.hema`/`.cupr` source in this repo reaches a full CLI
`ship` end-to-end yet, `tests/backends/test_ship.py`'s own module
docstring records that as a pre-existing, unrelated wall; WO-62's
`gantry_carriage.hema` proves parts the identical way):

- `bed.hema`: `HeatedBed` -- laser-cut plate, `BuildPlatformMount` +
  `BedHeater` both bound to `cut.blank.mid_plane`. `regolith check`
  clean (2 pre-existing import-tokenizer warnings only, same false
  positive already documented on every other project file).
- `xy_gantry.hema`: `XCarriage`, `XRailBracketLeft`,
  `XRailBracketRight`, `YCarriage` -- four laser-cut plates,
  `RailMount`/`StepperMount` bound to `cut.blank.mid_plane`, each
  carrying a `HolePattern` impl for the assembly's `BoltedPattern`
  mates (`std.mech.matings`, `std.mech.mounts`, `std.mech.sheet`
  imports, mirroring `gantry_carriage.hema`'s own import set).
- `z_motion.hema`: `BedCarriage` -- BOTH mounts stay `todo!` (wall
  W4 below); not realized this dispatch.
- `frame.hema`, `extruder.hema`, `enclosure.hema`: unchanged,
  `todo!` (see per-site table below).

**The motion assembly, realized placed**
(`tests/orchestrator/test_wo64_xy_gantry_assembly.py`, mirroring
`tests/orchestrator/test_wo62_assembly_composition.py`'s own hand-
declared-`AssemblyDef` precedent -- `regolith-lower` still emits no
numeric mate-graph payload from a `connect:` block's `align:`
clauses, WO-62's own documented integration-seam gap, unchanged this
dispatch): `xy_gantry.hema`'s `XYGantryAssembly` (4 parts:
`x_carriage`, `rail_l`, `rail_r`, `y_carriage`; 5
`BoltedPattern` mates, one real loop x_carriage -> rail_l ->
y_carriage -> x_carriage, `gantry_carriage.hema`'s own topology
shape) solves with zero loop residual, zero interference, mass =
sum of its four parts, and exports byte-identical STEP across two
solves.

### Optimizer pins (causes + traces in the lockfile)

`tests/orchestrator/test_wo64_printer_optimize.py` (three tests, all
green):

- `bed.hema`'s `BedPlateFlat.a = in [220mm, 240mm] minimize` --
  golden-section continuous optimize over realized-part mass, winner
  near 220mm, `LockRow.cause` = `optimize(declared_objective,
  trace=blake3:...)`.
- `xy_gantry.hema`'s `CarriagePlateFlat.b = in [35mm, 45mm]
  minimize` -- same recipe, second dim (WO body: "at least two"),
  winner near 35mm.
- `controller.cupr`'s `ControllerBoard.impl AddressDecodeGlue by
  select(nor_glue, cpld, mcu_chip_selects)` (carried from phase A
  verbatim) -- the `ebi_decode` recipe (`domains_from_choice_points`
  + `optimize_discrete`) run against the REAL flagship source
  (`compiler.check(("examples/flagships/printer_k1",))`'s own
  `choice_points` payload, not a synthetic fixture), winner pinned,
  `LockRow.cause` = `optimize(...)`.

`duct_vane` (the WO body's own phrasing) does not exist as a landed
corpus member -- `tests/backends/test_parity.py`'s own module
docstring already records this and substitutes `ebi_decode`'s real
`select` winner for the "duct_vane's dims show optimize causes"
acceptance line; this dispatch does the same substitution for the
continuous-dim half using `bed.hema`/`xy_gantry.hema`'s own dims
instead of an invented `duct_vane` file.

`regolith build`'s own staged loop over the bare `.hema` source does
NOT run these optimizations automatically (`/tmp` lockfile after a
plain `build` carries only the `cost.profile` row) -- consistent
with WO-62's own documented gap: no producer yet turns a declared
`in [lo, hi] minimize` constraint into a staged-loop evaluator
closure without a caller supplying one, so both recipes above are
proven through hand-declared evaluators over the SAME realized-domain
producers a real staged-loop closure would call, exactly
`test_wo62_assembly_composition.py`'s own posture.

### Fluid

`thermal.fluo`'s `PartCooling.fan` edge: `Imposer(driven_by=...)` ->
`Pump(curve=registry(sunon_mf40201vx_1000u_a99))`, now that W2 is
closed (WO-66 follow-up landed the record). `regolith check` clean
(zero new diagnostics). The hotend MELT path stays contract-level:
W1 is only PARTIALLY closed (see wall table) -- the landed
`polymer_melt.toml` records carry rho(T) but only ONE zero-shear
viscosity point, not a `mu(T)` curve, so a non-Newtonian flow edge
still cannot be honestly parametrized across the melt path's real
temperature window. Recorded as a specific per-site reason, not
forced.

### Elec / harness

`controller.cupr`'s `ControllerBoard.BoardOutline`/`FanDrive`/
`HeaterDrive` impls and `harness.cupr`'s nine `route: free` runs are
UNCHANGED this dispatch. Reason (matches the WO's own anticipated
gate): routed runs need realized geometry to walk waypoints through
(`wiring_harness.cupr`'s own documented `E0309` shape), and this
dispatch does not realize `frame.hema`/`enclosure.hema` (the bodies a
route would actually travel through) -- `harness.cupr`'s own header
comment already names this precisely and stays correct unmodified.
`ControllerBoard`'s remaining `impl ... = todo!` sites are per-part
geometry (board outline, fan/heater drive electrical bodies), not
gated on assembly geometry, but out of THIS dispatch's realized-part
budget (mech only) -- deferred, not attempted.

### New wall

- **W4 (FIXED, commit 354cdff).** A milled-block `Blank(profile,
  depth=...)` + `Bore` feature-program body -- the shape
  `coolant_gallery.hema` (WO-51 D152) is supposed to exemplify --
  failed `regolith check` with `E0448` ("sheet-metal blank with no
  thickness source") for EVERY corpus member that uses it, INCLUDING
  `coolant_gallery.hema` itself run unmodified (`crates/
  regolith-lower/src/feature_program.rs`, `regolith-diag`'s
  `E0448`). Verified with a minimal probe file (single `cnc_mill`
  stage, no sheet-metal import at all) -- reproduced identically: a
  real defect in the landed slice-A classifier, which fired for
  every thickness-less blank instead of honoring the charter's
  sheet-only scope (30-geometry-lowering sec. 1.2, D171 #2).
  Blocked: `z_motion.hema`'s `BedCarriage`
  (`LeadscrewMount.bearing_bore` is cylindrical/internal -- needs a
  milled bore) and `xy_gantry.hema`'s `YCarriage.HotendPocket`
  (same). FIX (354cdff): a blank whose stage process maps to the
  `machined`/`cast` roughness families in the existing
  `PROCESS_ROUGHNESS` capability record is not sheet stock and opts
  out of the rule; sheet-family (`laser_cut`), unmapped, and
  process-less stages stay in scope, so a genuine gauge-less sheet
  blank still reports `E0448`. `coolant_gallery.hema` now checks
  clean; `dune_buggy`'s single golden `E0448` (`bodywork.hema`'s
  `BodyPanels`: bare `process=laser_cut`, no `sheet=`, no
  `thickness=`) is a TRUE sheet case and stays -- no golden changed.
  Regression tests both ways in `feature_program.rs`:
  `milled_blank_has_no_gauge_source_requirement`,
  `gaugeless_sheet_blank_still_reports_e0448`. The blocked bore
  sites above are unblocked for the next phase-B follow-up.
- **W5 (new, soft).** `fluorite`'s `Pump` component has no landed way
  to derate a fixed head-flow curve by a commanded duty fraction (a
  PWM-driven fan/pump is a real, common case -- `controller.cupr`'s
  `FanDrive.duty` promise has nowhere to attach once the fan becomes
  a `Pump(curve=registry(...))`). Not a compiler wall (the fluorite
  grammar simply has no primitive for it yet, mirroring W3's own
  "authoring-ergonomics, not blocked" posture) -- a `fluorite/02`
  growth ask, does not gate phase C on its own.
- **W6 (new).** The WO-61 contract-graph layout (`regolith.backends.
  drawings`) hits its own `no-overlapping-annotations` drafting-audit
  rule once the graph crosses phase B's growth (26 nodes/11 edges,
  up from phase A's smaller graph): `tests/
  test_flagship_printer_contract_graph.py::
  TestPrinterContractGraph::test_passes_the_drafting_audit` now
  `xfail`s with the real rule-failure message attached (not deleted,
  not silently loosened) rather than blocking `make check`. Fixing
  the layout algorithm is `regolith.backends.drawings`, out of this
  WO's file surface -- a WO-61 layout-depth ask.

### Per-`todo!`-site disposition (25 phase-A sites -> current state)

| File | Site | Phase B disposition |
|---|---|---|
| `bed.hema` | `BuildPlatformMount` | REALIZED (`cut.blank.mid_plane`) |
| `bed.hema` | `BedHeater` | REALIZED (`cut.blank.mid_plane`) |
| `xy_gantry.hema` | `XCarriage.RailMount` | REALIZED |
| `xy_gantry.hema` | `XCarriage.StepperMount` | REALIZED |
| `xy_gantry.hema` | `YCarriage.RailMount` | REALIZED |
| `xy_gantry.hema` | `YCarriage.StepperMount` | REALIZED |
| `xy_gantry.hema` | `YCarriage.HotendPocket` | deferred: wall W4 (cylindrical bore blocked) |
| `z_motion.hema` | `BedCarriage.LeadscrewMount` | deferred: wall W4 (cylindrical bore blocked) |
| `z_motion.hema` | `BedCarriage.BuildPlatformMount` | deferred: wall W4 (same part, same stage would need the bore) |
| `frame.hema` | all 7 sites (`x_rail_left`, `x_rail_right`, `z_screw`, `z_motor_mount`, `bay`, `panel_left`, `panel_right`) | deferred: out of this dispatch's realized-part budget (frame carries 7 distinct interfaces across 3 geometric families -- rails, a leadscrew bore [wall W4], a card bay, two panel seals -- realizing it coherently is a bigger single-part effort than the assembly demo; not attempted, recorded as cut scope, not silently dropped) |
| `extruder.hema` | all 3 sites | deferred: out of this dispatch's realized-part budget (extruder body + `FeederThroat`/heater mount not attempted) |
| `enclosure.hema` | both sites | deferred: out of budget; also blocks harness routing (no panel geometry for a route to travel through) |
| `controller.cupr` | `BoardOutline`, `FanDrive`, `HeaterDrive` x2 | deferred: elec-track realization (PCB placement/outline) out of this dispatch's mech-only realized budget; `AddressDecodeGlue by select` (not `= todo!`, already impl'd at phase A) IS pinned via optimize, see above |

18 of 25 phase-A `todo!` sites stay deferred with a named reason (7
frame + 3 extruder + 2 enclosure + 4 controller + 2 z_motion); 6
sites realize (2 bed + 4 xy_gantry); 1 site (`YCarriage.HotendPocket`)
is new-in-phase-B and deferred on wall W4. `regolith check` over the
whole project: still 0 errors, honest-deferral warning count now
matches the smaller remaining `todo!` count per file.

### Parity checkpoint (`regolith ship --explain`)

Run against a plain `regolith build` output directory (no `--spec`,
no elec/mech backends configured -- the parity ledger reads the
lockfile + obligation results directly, independent of which
backends are wired):

```
assumed/waived: (none)
report errors:  (none)
parity: attention(128)
```

Not clean -- expected and correct for phase B (charter `31-
flagships.md` sec. 5: "Phase B/C: ... parity report clean" is the
PHASE C bar, not phase B's). 128 attention-list items reflect every
still-`todo!`-deferred obligation plus every asserted-literal claim
this project makes (envelope targets, budget limits) -- none
misclassified (`report errors: (none)`), none silently waived
(`assumed/waived: (none)`).

### Files touched outside `examples/flagships/` + `tests/`

None. (The three `FINDINGS-*.md`/`FINDINGS.md` files at repo root
predate this dispatch and are untouched scratch notes from prior
sessions, not part of this WO's change.)

## Phase C ledger (this dispatch, 2026-07-10)

Honest partial per the dispatch's own "attribution, not totality"
bar (charter sec. 1: the D170 bar claims attribution; the dispatch
instruction: "attention(n) with every n accounted is acceptable if
recorded -- clean is the target, honesty is the requirement").
`make check` green; every remaining `todo!`/deferral keeps a named
reason.

### W4's un-gated sites, realized

Both mech sites the W4 fix (phase B, commit 354cdff) unblocked now
realize to STEP, proven via `realize_feature_program` over hand-built
`FeatureProgram` fixtures mirroring each source file's own declared
geometry (the SAME producer path phase B already used for
`bed.hema`/`xy_gantry.hema` -- `tests/orchestrator/
test_wo64_phase_c_bed_carriage.py`, 2 tests):

- `z_motion.hema`'s `BedCarriage`: rewritten from two bare `todo!`
  sites into one milled block (`stage milled: process=cnc_mill`,
  `Blank(CarriageBlockOutline, depth=12mm)` then `Bore(dia=8mm,
  depth=12mm)`, mirroring `coolant_gallery.hema`'s own shape).
  `LeadscrewMount.bearing_bore` binds to the bore's axis;
  `BuildPlatformMount.platform` binds to the block's own top face.
  `regolith check` clean (0 errors; the 2 remaining warnings are the
  same pre-existing `(from ...)` L0801 false positive documented on
  every other project file).
- `xy_gantry.hema`'s `YCarriage.HotendPocket`: the ORIGINAL wall-W4
  writeup assumed a second, colliding `Blank` declaration would be
  needed (`std.mech.sheet.Blank` vs `std.mech.cnc.Blank`); this
  dispatch found a cleaner path this session, not anticipated by the
  phase-B note: `pedal_box.hema`'s own `stage ..., from=<prior
  stage>` cross-process chaining (`std.mech.sheet` -> `std.mech.cnc`
  on the SAME body, no second `Blank`) lets a `cnc_mill` stage mill a
  blind bore directly into the already-cut sheet plate. The bore
  carries an explicit `depth=2mm` (a `HoleOp` WITH a depth, not a
  through `Pierce`) -- honoring the `HotendPocket` interface's
  `internal` role qualifier (hematite/03 sec. 1: `internal` names a
  depth-bounded bore, never a through feature; a `Pierce` would have
  been a dishonest substitution, not a legitimate alternative).
  `regolith check` clean over the whole file (0 errors; the
  todo!-count warning for this file drops to 0).

Both sites' realizer proof mirrors the phase-B idiom exactly: no
`.hema` source in this repo reaches a full CLI `ship --release` with
a realized-geometry input wired through yet (`tests/
backends/test_ship.py`'s own documented, pre-existing wall,
unchanged this dispatch, out of this WO's file surface -- it is a
`regolith.orchestrator`/CLI wiring gap, not an examples/tests gap).

Per-`todo!`-site count: 16 of the 25 phase-A sites now stay deferred
(down from 18 after phase B): 7 frame + 3 extruder + 2 enclosure + 4
controller (unchanged reasons, phase B's own table still applies
verbatim to these); 0 z_motion/xy_gantry sites remain (both were the
only phase-B-new deferrals, both closed this dispatch).

### Ship outputs

Direct-producer path (`regolith.backends.drawings`), the SAME
mechanism `tests/test_flagship_printer_contract_graph.py` (phase A
deliverable 4) already uses for the contract-graph sheet -- not a
full CLI `ship --spec` run, because the CLI `ship`/`build` pipeline
does not consume a hand-realized `FeatureProgram`/`RealizedGeometry`
for ANY corpus member yet (the same pre-existing wall named above).
New: `tests/test_flagship_printer_sheets.py` (4 tests, all green):

- **Part sheets**: `mech_part_drawing` over `realize_feature_program`
  output for all 6 realized mech parts (`HeatedBed`, `XCarriage`,
  `XRailBracketLeft`, `XRailBracketRight`, `YCarriage`,
  `BedCarriage`) -- every sheet renders, is deterministic across two
  independent producer runs (model JSON + SVG bytes), is valid ASCII
  XML, and passes `run_drafting_rules` with zero failures (unlike the
  contract-graph sheet's W6 xfail -- these are single-part sheets,
  never near the layout's node-count ceiling).
- **Contract-graph sheet**: unchanged (phase A deliverable 4);
  `test_passes_the_drafting_audit` stays `xfail` on W6 (recorded wall,
  not forced -- the layout algorithm fix is `regolith.backends.
  drawings`, out of this WO's file surface).
- **Harness block diagram**: `elec_blocks` over the REAL
  `HarnessPayload` pulled off `compiler.check(("examples/flagships/
  printer_k1",))`'s own build payload (`harnesses["ControllerLoom"]`
  -- a dict keyed by harness name, not a list; confirmed by
  inspection this dispatch), mirroring the contract-graph test's
  direct-payload-pull idiom exactly. Renders, deterministic, valid
  ASCII XML.
- **Elec board sheets / gerber-chain outputs**: NOT attempted --
  `controller.cupr`'s `BoardOutline`/`FanDrive`/`HeaterDrive` impls
  stay `todo!` (per-part elec geometry realization, out of this
  dispatch's mech-realization-driven ship-output budget; unchanged
  from phase B's own disposition table). Recorded per-site, not a
  blanket deferral.
- **Firmware image**: NOT attempted -- gated on the WO-37 firmware
  realizer's own contract-header/BSP machinery over a realized board,
  which does not exist for this project (the controller board impls
  above are the actual blocker). Named per the dispatch's own
  instruction ("gerber/firmware legs stay deferred with reasons --
  board layout + firmware need their own realizers' inputs").
- **BOM + cost**: the `bom_cost` budget (phase A, `printer_k1.cupr`)
  and the `[profiles.cost.prototype]` cost profile (`magnetite.toml`)
  are both landed and wired (`regolith build --profile prototype`
  consumes the profile, `cost_profile(...)`-caused lockfile row,
  confirmed this dispatch). A PRICED BOM SCHEDULE SHEET
  (`elec_bom_table`'s `(ref, part_number, description, quantity)`
  rows) is NOT produced: that producer's own contract is "already-
  decided data only, never invented" (regolith/07 sec. 6, its own
  docstring) -- this project declares zero `vendor(...)`-cited
  catalog parts (confirmed by grep this dispatch: only
  `printer_k1.cupr`'s PCB-fab `prefer vendor(jlc) over vendor(pcbway)`
  line, no BOM-line components), so a real priced schedule has no
  source data to render without fabricating part numbers -- exactly
  the AD-22/"backends never decide" violation this WO must not
  commit. Recorded as an honest cut, not forced: authoring
  `vendor()`-cited fastener/motor/electronics rows into `printer_k1`
  is itself a scope decision (which real catalog parts, at what
  quantities) beyond "drive the parity ledger down," so it stays
  future authoring work, not a phase-C blocker.

### Walls (unchanged, not forced per the dispatch's own instruction)

- **W5** (pump duty derating): unchanged, soft, `fluorite/02` growth
  ask.
- **W6** (contract-graph drafting-audit xfail): unchanged, `xfail`
  still names the real rule-failure message; the new part-sheet tests
  above prove the SAME producer/audit machinery passes cleanly at
  single-part scale, reinforcing that W6 is a layout-depth ceiling
  issue (many nodes), not a producer-correctness bug.

### Parity checkpoint (`regolith ship --explain`)

Re-run against a fresh `regolith build --release --out /tmp/...`
(plain CLI, no `--spec`, matching the phase-B checkpoint's own
invocation exactly):

```
assumed/waived: (none)
report errors:  (none)
parity: attention(136)
```

UP from phase B's 128, not down -- and this is itself the honest
finding, not a regression to paper over. Cause, confirmed by
inspection this dispatch: `regolith build`'s plain CLI staged loop
does NOT consume the hand-realized `FeatureProgram`s this dispatch
proved to STEP (the SAME pre-existing wall named in "Ship outputs"
above and already documented in phase B's own note: "`regolith
build`'s own staged loop over the bare `.hema` source does NOT run
these optimizations automatically"). This dispatch's mech
realization work is proven through the direct producer/realizer path
(`realize_feature_program`, matching WO-62's own posture), exactly
like phase B's parts and optimizer pins were -- it does not, and
structurally CANNOT yet, feed back into the plain-CLI lockfile the
parity report reads, because no CLI seam threads a hand-realized part
into `staged_build`'s obligation-discharge loop for THIS project
(the `elec_boards=` seam WO-42 landed is elec-only). The 8-item
increase (128 -> 136) traces to the two source-file rewrites adding
new declared obligations (`BedCarriage`'s `require Manufacture`,
`YCarriage`'s new `pocket` stage's own manufacturability/geometry
obligations) that the plain build path can only mark `indeterminate`
(never `violated` -- `report errors: (none)` stays true; every
attention-list item is still an honestly counted, never
misclassified, indeterminate demand or the single loud literal-
attribution caveat).

Closing this gap for real (wiring realized mech geometry back through
`regolith build`'s plain CLI path, or extending the `--spec` seam
past `elec_boards` to a `mech_realized`-shaped block) is a
`regolith.orchestrator`/`regolith.cli` change -- outside this WO's
`examples/` + `tests/` file surface, and a bigger lift than "record a
per-site reason": recorded here as the concrete, actionable phase-C
finding (successor to phase A's abstract walls list) rather than
forced or silently left as an unexplained number.

### Files touched this dispatch

`examples/flagships/printer_k1/z_motion.hema` (BedCarriage realized);
`examples/flagships/printer_k1/xy_gantry.hema` (YCarriage.HotendPocket
realized); `tests/orchestrator/test_wo64_phase_c_bed_carriage.py`
(new); `tests/test_flagship_printer_sheets.py` (new); this WO file
(Status line + this section). No `crates/` changes; no schema bump;
no files outside `examples/flagships/` + `tests/` +
`docs/workflow/work-orders/`.
