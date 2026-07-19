# factory_p1 -- the factory flagship (WO-137, charter 43/AD-42)

A small industrial facility as ONE design: utility service ->
substation transformer -> main switchgear -> panelboard + MCC ->
motor/lighting loads (`power.cupr`), inside a real calcite building
with a real electrical room (`program.calx`/`frame.calx`) -- the
acceptance test of AD-42's whole power-distribution charter.

| file | track | pressure applied |
|---|---|---|
| `site.calx` | calcite | one `site` per project root; soil bearing, wind/snow/seismic, grids/levels |
| `program.calx` | calcite | `ElectricalRoom` (the WO-136 tandem's subject, with `depth`/`width`/`clear_height`), `ProductionFloor`, egress |
| `frame.calx` | calcite | single-story steel gravity frame + `XfmrPad`, the transformer's declared mass landing as a real bearing-pressure claim |
| `power.cupr` | cuprite | the `power PlantMain:` net (service/generator/transformer/switchgear/MCC/motor loads, all four discipline rules exercised) + the seven WO-135 closed-form claims + the WO-136 `working_clearance` tandem + five honest D250.4 certified-tier deferrals |
| `magnetite.toml` | -- | project manifest + D147 cost profile |

## The tandem (WO-136), proven twice

`power.cupr` declares `MainXfmr` ONCE, as an ordinary `part` (mass +
footprint). `SubstationRoom` binds it into `program.calx`'s real
`ElectricalRoom` and discharges `elec.power.working_clearance` against
the room's REAL declared depth (NEC 110.26 Table 110.26(A)(1),
Condition 2, 0-150V: 1.0m). `frame.calx` separately consumes
`SubstationRoom.xfmr.mass` as a real load on `XfmrPad`, discharging
`civil.bearing_pressure` through the existing frame/footing chain --
the SAME declared apparatus, two domains, checked, not asserted.

## D250.3 -- both honest paths, in the same plant

`fault_main` (`MainBus`, fed from the utility service `MainSvc`) is
DECLARED with a cited real value (a stated utility-letter datum:
Riverside Electric Coop service request #RE-2026-0447, 25kA available
fault, X/R 6.6) and discharges through the T-0009 %Z screening model.
`fault_standby` (`Tie`, the genset side) DELIBERATELY leaves its
transformer's nameplate `pct_z` undeclared -- no nameplate value was
obtained at design time -- so it DEFERS BY NAME (`memos/
release-residuals.md`), never assuming a "typical" %Z. Both behaviors
exist in one plant per this WO's deliverable 2.

## D250.4 -- arc-flash never discharges by screening estimate

`withstand`/`coordination`/`arc_flash`/`grounding`/`harmonics` register
no lithos built-in model by design (`regolith.harness.models.power`'s
own module doc: these five claim kinds are certified/numeric-solver
tier only). All five defer honestly, ledgered in `memos/
release-residuals.md` -- this is the acceptance test named in the
WO: arc-flash is never discharged by a screening estimate wearing a
study's clothes.

## Finding F-WO137-1 (loud, per the WO's escalation directive) -- no one-line diagram surface

`ship.spec.json` ships the frame sheet and the contract graph, but
NOT a one-line diagram for `PlantMain`. The only elec-family drawing
producer, `elec_blocks` (`regolith.backends.drawings.producers`),
projects a `HarnessPayload`'s RUN endpoints (cuprite's board/harness
netlist shape) -- it does not read a `power <name>:` net's buses/
feeders/ties graph (`PowerNetPayload`) at all. No drawing producer in
the registry consumes `PowerNetPayload` today. A one-line diagram is
therefore not a deliverable this drawing surface can express, exactly
the wall the WO calls out: "a power design without a one-line is not
a deliverable an electrical engineer would accept, and that gap
should drive the next cycle." This finding should drive a follow-on
WO (a `power_oneline` drawing producer over `PowerNetPayload`,
mirroring `elec_blocks`'s shape but reading the real net graph:
buses as nodes, feeders/ties/protective devices as edges).

`std.civil`/`std.elec`/`std.power` names are stdlib content (WO-45/48/
134); phantom until the packs land, per corpus convention.

## Finding F-WO137-2 (loud) -- cuprite claims need a `system`/`part`/`board` wrapper

A top-level (dedented) `require <Group>:` claim block does NOT attach
to any obligation when it follows a bare `power <name>:` net
declaration -- verified by direct minimal repro (`regolith check`)
both with the require block nested inside the `power` block's own
body AND as a sibling top-level statement after it: obligations=0
either way. Claims only attach when nested inside a `system`/`part`/
`board` decl body (the shape `sited_transformer.cupr`'s `system
SubstationRoom:` and `cnc_router_r1/power.cupr`'s `board PowerPanel:`
already prove). `power.cupr` here wraps its own claims in
`system PlantChecks:`/`system StandbyChecks:` as a workaround; no
existing corpus example anywhere attaches a `power` net's own claims
(`demand_load`/`voltage_drop`/etc.) directly. This should drive a
follow-on WO: either document the wrapper requirement in cuprite/10,
or land `power <name>:` as a first-class claim-owning decl.

## Finding F-WO137-3 (loud, pre-existing, NOT introduced by this WO) -- `ship` fails on ANY project with a `civil.bearing_pressure` claim

`regolith ship` refuses this project's calc package: the drafting
audit's `no-empty-ruled-table` rule fires on the `bearing_a` calc
sheet (its rendered "Inputs" table has zero body rows). This is NOT
a factory_p1-specific defect -- the SAME failure reproduces on
`examples/flagships/small_office` (`regolith ship
examples/flagships/small_office ...` refuses on its own `bearing`
sheet, identical rule, identical empty-Inputs-table cause) with
today's tree. `regolith build --release` itself is unaffected
(`release_ok=true`); only the `ship` calc-package drafting-audit gate
trips. Recorded here rather than worked around, per this WO's own
directive ("No toolchain changes -- gaps you hit are FINDINGS");
fixing the calc-sheet Inputs-table renderer for `civil.bearing_
pressure` is a toolchain change out of this WO's scope, and it
blocks BOTH this flagship's `ship` step and (pre-existing) the
fleet's health leg for every bearing-pressure-carrying project.
