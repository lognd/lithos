# The Structural Layer: Components, Pins, Layout

> cuprite spec 0.11. The elec binding of L4 (Realized IR): behavioral blocks
> bound to real components, packages, pins, placement, and routing. This
> is where classic EDA tools *start*; here it is mostly output. 0.11
> (cycle 18) specifies sec. 4: the `drc:`/`erc:` rule grammar and the
> discipline boundary.

## 1. Binding

The L3->L4 realizer performs, in order, each step lockfile-materialized
with cause:

1. **Component binding.** Each block (or fused block group) binds to a
   catalog component or a synthesis target. Vendor components come from
   the registry with datasheet-interval contracts; passives resolve
   value-source variables to preferred series (E24/E96) -- snapping to a
   series is a structure-boundary-aware rounding step, checked against
   claims after snapping.
2. **Pin assignment.** Ports map to package pins. Pins never appear in
   *design* source (like entity IDs in mech) -- `component` registry
   records are where package pin maps and alternate-function tables
   legitimately live (see `examples/registry/stm32g0.cupr`); the
   assignment is derived and locked by the human only via the standard
   lock family when needed:
   `locked: pinmux(u_mcu.uart2.tx): pa2` -- the one position where a
   package pin may appear in design source (e.g. to match an existing
   connector); deliberate, auditable, lockfile-mirrored. Pin-mux is a **monomorphized
   matching problem**: the component record declares alternate-function
   tables; flows demand bus/timer/ADC resources; the solver assigns
   function instances to ports to pins, subject to ERC ledgers and
   routing-quality policy. Every assignment is lockfile-caused
   (`cause: planner(pinmux u_mcu)`); a failed match is a constructive
   error naming the contended resource ("both flows need the only DMA-
   capable SPI"). IMPLEMENTED (WO-35, cycle 24): the deterministic
   constraint search lives in `realizer/elec/pinmux.py`
   (`assign_pinmux`) against the typed `AlternateFunctionTable`/
   `FlowDemand` shape deliverable 1 asks for; `locked_pin` honors the
   `locked: pinmux(...)` escape and an infeasible lock is named
   distinctly from a generic contention failure (the human's lock, the
   machine's counterexample); the pinout table feeds
   `realizer/elec/netlist.apply_pinout` so the netlist carries real
   pin numbers (deliverable 4).
3. **Placement and routing** against the board stage's process
   capability (layer count, trace/space, drill) and rule pack (DRC), with
   region ownership: courtyards, keepouts, and impedance-controlled
   routing regions are owned entities; a route crossing an owned keepout
   is a borrow conflict, not a post-hoc DRC surprise.
4. **Extraction.** Parasitics, actual lengths/skews, copper for thermal
   -- the measured entity DB that T2 conformance and L5 obligations
   consume.

## 2. Stages

A board's process pipeline, per regolith stage semantics:

```
board ThermostatMain:
    stage bare:       process=pcb_fab(jlc_2l_standard)
    stage assembled:  process=smt_assembly(jlc_basic), from=bare
    stage programmed: from=assembled
        firmware = load(image_ref)       # hash-pinned; a construction step
```

- Fab and assembly capability tables are imported vendor files (the
  process registry); demand <= capability is static (`E0410` family:
  "this fit needs 4 layers / laser vias; the declared fab class cannot
  hold it").
- `stage src: import("legacy.kicad_pcb") sealed` is the brownfield
  entry: an existing design enters at L4, gets retro-contracts, and the
  verification machinery works immediately -- the same adoption wedge as
  mech.
- **Panelization is not a stage and not an artifact** [SETTLED,
  cycle 2]: the board is the product; the panel (rails, fiducials,
  v-scores, copy count) is decided by the fab/assembly process pack +
  planner and emitted as plan evidence at L6, lockfile-caused
  (regolith `07-claims-and-evidence.md` sec. 6). Boards that ARE
  products made of joined boards (module-on-carrier) use the
  multi-piece `pieces:` machinery instead.

## 3. Tolerances, corners, fits

- Component tolerance (1% R, 20% ceramic with bias derating as `f(V)`
  interval), supply windows, and PVT corners are one interval system;
  each claim is checked at its own worst corner (setup at slow/low/hot,
  hold at fast/high/cold, droop at max load step + min bulk C).
- **Logic-level compatibility is the fit system:** driving family x
  receiving family expands (like ISO 286) into VOH/VIL margin intervals,
  capability-checked, with constructive fixes (level shifter = add
  finishing op).
- Derating packs (voltage/temperature derating of passives,
  semiconductor SOA) are rule packs: eager, closed-form, provenance-
  carrying.

## 4. DRC/ERC as the rule-pack tier [SETTLED, cycle 18]

ERC (drive/load, floating inputs, domain crossings) runs at L3 --
it is the ownership/ledger machinery, not a separate tool. DRC
(geometry-dependent rules) runs eagerly during L4 realization and as
`free`-value resolution before it (trace width `free` resolves to the
DRC/IPC-2221 minimum for its current, like a bend radius resolving to
the DFM minimum).

**The rule grammar** is the regolith rule-pack shape, shared verbatim
with hematite (`../hematite/02-language.md` sec. 10; vocabulary rows
`../hematite/04-vocabulary.md` sec. I5, mirrored in `07` sec. A2):
`process` modules carry a `capability:` table plus `drc:` and `erc:`
blocks of `rule` declarations -- `forall <var> in <query>`,
`demand:`/`advise:`, `resolves: <field> from free`, `per:`, `why:`,
`expect:` with `pass:`/`fail:` fixtures.

```
process jlc_2l:
    capability:
        min_trace: 0.09mm
        min_space: 0.09mm
        min_drill: 0.2mm

    erc:
        rule fanout_drive:
            forall n in nets.where(kind=signal)
            demand: sum(n.loads.i_input) <= n.driver.i_drive
            per: "family drive spec, cmos_3v3"
            why: "aggregate input current beyond drive collapses edges"

    drc:
        rule bus_length_match:
            forall b in buses.where(matched)
            demand: spread(routes(b).length) <= 2mm
            per: "IPC-2141A, matched group skew"
            why: "length spread eats the timing budget"
```

Elec-specific notes on the shared shape:

1. **Rules are vendor-LUT-driven, not count-driven.** A rule
   expression may fold a quantity over a query result (`sum(...)`,
   `count`, `max(...)`, `spread(...)`) and dereference the registry
   records bound to matched entities: `n.loads.i_input` /
   `n.driver.i_drive` resolve through each entity's
   `component`/`family` record (datasheet intervals, `f(T)`/`f(V)`
   derating), hash-pinned, evaluated at the check's worst corner --
   rules never spell corners. Both are existing machinery (queries +
   the record system), not new syntax.
2. **Discharge level is derived.** `fanout_drive` reads netlist facts
   and fires on every `check`; `bus_length_match` references routed
   geometry (`routes(...)`), so it lowers to an obligation that stays
   honestly indeterminate until extraction and discharges post-route.
   A predicate referencing a fact no layer provides is a compile
   error on the rule.
3. **Built-in discipline is NOT a rule** -- packs extend the floor;
   core semantics ARE the floor. The v1 net discipline (`03` sec. 2:
   terminal ledger, reference reachability, one voltage-imposer,
   supply-short) and the single-driver check are E03xx COMPILE
   ERRORS: they fire with no pack attached, cannot be detached, and
   are not waivable. The intentional escape is the in-language
   construct -- `arbitrate` for shared drive, declared joins for
   deliberate supply ties -- never an override, and a pack must not
   restate them as E06xx rules.
4. **Overrides are the waive ladder only**: `waive drc(<pack>.<rule>)
   on <query>: basis: ...` (regolith `12` sec. 3). Derating packs
   (sec. 3) are rule packs in exactly this grammar.

## 5. Budgets on structure

The classic engineering budgets are regolith budgets over structural
contributors:

```
budget vdd_core_droop: kind=noise
    require: elec.min(v(vdd_core)) > 3.0V during load_step(2A/us)
    members: [regulator, bulk_caps, decouple.instances.all, plane]
    allocate: cost_optimal
    locked: decouple.value: 100nF     # the lock family; never `pins:`
                                      # in a language with package pins

budget ddr_timing: kind=timing
    require: setup_slack(ddr_bus) > 0 at corners(all)
    members: [controller, dram, routes(ddr_bus)]
    allocate: worst_case         # route length share vs silicon share
```

Timing budgets allocating slack between silicon promises and route
lengths are the direct analog of tolerance chains allocating error
between machining operations -- same math shape (sum of interval
contributions vs a limit), same `E0432` failure naming the worst
contributors.

## 6. Frequency-domain and noise verification

Noise and signal integrity follow the standard margin-driven ladder,
with the geometric preconditions handled *eagerly* so the classic
failures never reach (or need) simulation:

- **Return-path rule pack (eager, L4).** Every net is classed by edge
  rate / bandwidth (from driver contracts and protocol class). Nets
  above a class threshold demand a continuous reference plane within a
  layer distance, stitching vias at layer changes, and no slot
  crossings. *A high-speed trace over a gap in the ground plane is an
  `E06xx` rule violation with the offending region highlighted* -- cheap,
  geometric, no field solve needed to catch the bug class.
- **Coupling screens (eager, L4).** Parallel-run length x spacing x
  edge-rate tables flag aggressor/victim pairs; `routes(net).coupled_to`
  entities are derived at extraction for the claims below.
- **Noise claims (L5).** `rms(v(node), band=...)`, `crosstalk(victim,
  aggressors) < ...`, `stays_within(emissions, mask=CISPR_11_B)`,
  eye-mask claims on links. Discharge ladder: closed-form coupled-line
  and PDN target-impedance models (cheap) -> IBIS/transmission-line
  simulation (mid) -> 2.5D/3D field solve (expensive). Thin margins buy
  more physics automatically; fat margins discharge from the screens'
  conservative bounds.
- **PDN as a budget.** Target impedance over frequency is a noise
  budget across regulator, bulk, ceramics, planes; the missing-decap
  resonance shows up as a violated interval corner, named.

EMC boundary claims remain writable early and dischargeable late
(`assume!` / `by test` in v1) [SETTLED, cycle 8, D74 -- closes
EOPEN-11]: the claim structure is real today, the harness models are
future registry content, and `--release` refuses the unacknowledged
gap -- the honest-deferral machinery doing exactly its job.
