# WO-64: flagship-1, the FDM printer (phase A: contract-first)

Status: phase A done (B/C gated)
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

**Done.** `examples/flagships/printer_k1/` -- 12 source files
(`magnetite.toml`, `README.md`, `contracts.hema`, `frame.hema`,
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
