# The fluorite guide (fluid-circuit design)

fluorite describes what a fluid system must DO -- carry these flows
between these components within these pressures, temperatures, and
transients -- as a relational circuit over typed fluid ports. It
copies hematite's and cuprite's shared discipline (contracts first,
claims stay pure quantity-core vocabulary, no solver names ever
appear in source) and cuprite's net SHAPE (through/across, node
conservation, reference reachability), but not electrical
vocabulary: fluid edges are nonlinear (dp ~ mdot^2) and media carry
properties and state. Normative sources: `docs/spec/fluorite/`
01-03, `docs/spec/regolith/`.

## 1. Media

A `medium` names a fluid and binds its property records -- interval-
valued functions of state (rho(T), mu(T), pv(T), ...):

```
medium Water: liquid
    props: registry(potable_water_nist)
```

- Property evaluation follows the same corner discipline as
  everywhere else: out-of-record-range is honest indeterminate, never
  a silent extrapolation.
- One medium per connected subnet in v1 -- a mismatch is a compile
  error. Fixed-composition mixtures (60/40 ethylene-glycol/water) are
  just media with their own property records; composition CHANGE only
  happens at a declared `Mixer` boundary (sec. 3 below).

## 2. FluidPort -- the typed boundary

The fluid analog of a cuprite port role: a through/across pair.

```
interface FluidPort<m: medium, dia: length>:
    flow:
        mdot:  through           # conserved at every node
        p, T:  across            # potentials at the port plane
    roles:
        bore: circular(dia)      # the wetted geometry hook (hematite)
```

- `through` quantities (mdot) sum to zero at a node, signed -- flow
  DIRECTION is solved, never declared. Declaring a direction is the
  classic hand-analysis bug this discipline exists to prevent.
- `across` quantities (p, T) are shared by every terminal at a node.
- A hematite part exposes its wetted side by implementing `FluidPort`
  exactly like any other interface: `impl FluidPort<RP1, dia 12mm> for
  self as fuel_in: bore = turned.inlet`. Lowering reads the realized
  geometry behind that role for areas, lengths, bends, roughness --
  fluorite never re-declares geometry (hematite owns it).

## 3. Components

Component classes live in `std.fluorite` and follow cuprite's
component-class pattern: two-or-more-terminal elements with declared
parameters, vendor parts binding datasheet records.

```
Pipe(from=part.role)             # hydraulic side derived from geometry
Hose(from=part.role | compliance=registry(...))
Orifice(cd=..., dia=...)
Valve(cv=..., states={open, closed} | position in [0,1])
CheckValve(crack_dp=...)
Regulator(set=..., droop=...)
Pump(curve=registry(...))        # head-flow curve record, NPSH_r curve
Filter(dp_curve=registry(...))
Plenum(v=...)                    # two-terminal storage edge: negligible
                                 # dp, volume v
Mixer(outlet=<medium>)           # a MEDIUM BOUNDARY: inlets each stay
                                 # on their own single-medium subnet;
                                 # the outlet's medium and properties
                                 # are ordinary mixture records
Imposer(p=<expr>, driven_by=<promise ref>)
                                 # a pressure imposer whose value is an
                                 # ordinary quantity-core derivation --
                                 # the cross-track boundary (a handle
                                 # force driving a hydraulic pressure)
HxSegment(zone=part.zones.x)     # heat-exchange coupling to a hematite zone
```

Parameter-source rules (one word, one idea):

- `from=` names a REALIZED-GEOMETRY source only (`Pipe`, `Hose`): the
  hydraulic side is extracted during lowering, cited to the geometry
  snapshot hash.
- `driven_by=` names a cross-track PROMISE chain: the parameter's
  value expression is ordinary quantity-core derivation over promised
  quantities (a mech handle-force promise driving a pressure, in the
  jack example below).
- Record-bound parameters (`curve=`, `compliance=`, `dp_curve=`)
  resolve hash-pinned registry objects.
- Every numeric slot still accepts `free`/`allocated`/`derived`, same
  as hematite and cuprite.

## 4. Flownets

The relational join, shaped like cuprite `nets:` with fluid
discipline:

```
flownet DripZone(medium=Water):
    reference: ambient(280kPa, 288K)            # the pressure/temperature
                                                # reference (elec `gnd`
                                                # analog)
    nodes: bib, manifold, e1_in, e2_in, e3_in, e4_in
    edges:
        supply: Pipe(from=hose.run)             (bib -> manifold)
        lat1:   Pipe(from=lateral.run)          (manifold -> e1_in)
        e1: Orifice(cd=0.61, dia=0.9mm)         (e1_in -> ambient)
```

Compile-checked net discipline (the cuprite-analog ledger):

- **terminal ledger**: every declared `FluidPort` terminal joins
  exactly one node or is explicitly `sealed`;
- **reference reachability**: every node reaches a reference through
  edges;
- **at least one pressure imposer** per subnet (reference, regulator,
  pump curve, `Imposer`) -- otherwise the network is singular by
  construction and rejected at compile time, not at solve time;
- **medium consistency** per subnet;
- the arrow `(a -> b)` NAMES the edge's positive sense; it is not an
  assertion about which way flow actually goes.

## 5. States and events

Valve states and line-ups are ordinary config domains, declared before
any claim conditions on them:

```
flownet AquariumLoop(medium=Water):
    ...
    states:
        pump.state in {off, on}
        event pump.start: commanded by op.power_switch
```

`forall <var> in {<state refs>}` over a finite set of declared state
variables composes the same way it does over boundary intervals
everywhere else in lithos (the dual-line-up idiom below, from
`shop_air.fluo`):

```
require Supply:
    forall line_up in {tool_only, gun_only, both}:
        margin: fluids.dp(tank_out -> tool_in) <= 100kPa
```

This lowers to ONE swept obligation per claim, never enumerated
copies -- the discrete axis rides the same structured coverage
encoding as every other config sweep.

## 6. Claims

All existing quantity-core vocabulary; nothing invented for fluids
except the `fluids.*` namespace itself:

```
require FlowMargin:
    margin: fluids.dp(sump -> tank_in) <= 15kPa
    npsh:   fluids.npsh_margin(pump) > 0.5m, sf=1.3

require Startup:
    fill: settles(fluids.mdot(tank_in), to=+-2%,
              within 5s after pump.start)

require Regime:
    choke: not choked(cv)
```

- The temporal vocabulary (`peak`, `settles`, `rms(band=)`,
  `stays_within(mask)`) is regolith-shared, verbatim. `peak` is
  normatively the worst excursion in the claim's ADVERSE direction, so
  a suction-dip lower bound reads `peak(...) > x` -- there is no
  `.min`/`.max` claim spelling anywhere in lithos.
- `fluids.reynolds(edge) in [...]` and `not choked(edge)` are
  tag-shaped regime screens, feeding the same regime channel as any
  other correlation-domain check.
- `fluids.flow_imbalance(orbit)` takes a query ref, an orbit ref, or a
  bracketed edge list (`[e1, e2, e3, e4]`); an asymmetric feed into a
  symmetric-looking manifold is a real caution here -- verifying one
  emitter never licenses skipping the rest unless the feed is actually
  symmetric.
- `fluids.volume_consumed(edges, at=p)` is the compliance budget form
  -- a network must not consume more volume than its driving source
  can supply.
- `fluids.leak_total(<flownet>)` is a circuit-level leak budget, not a
  per-component claim: the flownet is the budget owner.

## 7. What is deliberately absent

No solver names in a claim, ever (no `fluids.colebrook` -- the
correlation is the discharging model's business, chosen by the
harness, not declared in source). No declared flow direction -- the
arrow in `(a -> b)` names an edge's positive sense, not a flow
assertion. No freehand geometry -- a `Pipe`/`Hose` edge's hydraulic
parameters come from a hematite part's realized geometry, never a
second declaration. No composition state carried on a node -- medium
change happens only at a declared `Mixer` boundary.

## 8. Fluorite-specific vocabulary (learning view)

Normative: `docs/spec/fluorite/02-language.md`. Everything in the
hematite guide's shared tables (`[S]`) applies verbatim: claims, value
sources, queries, budgets, waive/policy/override, `interface`/`mating`
contracts.

### Registries and boundary

| keyword | purpose |
|---|---|
| `medium` | fluid identity + bound property records |
| `interface FluidPort<m, dia>` | the through/across typed boundary |
| `impl FluidPort<...> for <part> as <role>` [S] | a hematite part's wetted-side binding |

### Circuit layer

| keyword | purpose |
|---|---|
| `flownet` / `reference:` / `nodes:` / `edges:` | the relational join |
| `Pipe`, `Hose` | geometry-derived edges (`from=`) |
| `Orifice`, `Valve`, `CheckValve`, `Regulator` | flow-control components |
| `Pump`, `Filter` | curve/record-bound components |
| `Plenum` | storage edge (capacitance) |
| `Mixer(outlet=<medium>)` | declared composition-change boundary |
| `Imposer(p=, driven_by=)` | cross-track pressure imposer |
| `HxSegment(zone=part.zones.x)` | heat-exchange coupling to a hematite zone |
| `states:` / `state <name> in {...}` | edge-parameter and net-level config domains |
| `event ... : commanded by ...` [S] | shared event vocabulary, fluid side |

### Claims (fluid-specific forms; rest all `[S]`)

| form | purpose |
|---|---|
| `fluids.dp(a -> b)` | pressure-drop margin between two nodes |
| `fluids.pressure(node)` / `fluids.mdot(node)` | potential and flow queries |
| `fluids.flow_imbalance(orbit \| [list])` | distribution-uniformity claim |
| `fluids.npsh_margin(pump), sf=` | cavitation guard |
| `fluids.reynolds(edge) in [...]` | regime-tag screening |
| `choked(edge)` / `not choked(edge)` | choke-regime screening |
| `fluids.volume_consumed(edges, at=)` | compliance budget |
| `fluids.leak_total(<flownet>)` | circuit leak budget |

### Retired / never-existed spellings

There is no `.max`/`.min` claim form -- worst-case excursion is always
`peak(...)`, sense-driven by the claim's comparator direction. There
is no declared flow direction anywhere in the language; the arrow in
`(a -> b)` is naming sugar only.

## 9. Worked corpus tour

Five single-file circuits in `examples/tracks/fluorite/`, in teaching
order:

- `garden_irrigation.fluo` -- the simplest shape: one medium, a plain
  reference, `Pipe` edges, a four-emitter `Orifice` orbit (named-list
  form), and the `flow_imbalance` + `dp` claim forms. Start here.
- `aquarium_loop.fluo` -- a `Pump` curve record, `Filter` dp curve, a
  `CheckValve`, the `npsh_margin` cavitation claim, and a startup
  `settles` transient.
- `hydraulic_jack.fluo` -- the `Imposer` cross-track component
  (`driven_by=` a mech handle-force promise), a `volume_consumed`
  compliance budget, and a `peak` claim on a release event.
- `shop_air.fluo` -- a gas medium evaluated at temperature corners, a
  `Regulator`, `Plenum` capacitance, `choked` regime screening, and a
  `forall` sweep over declared line-up states.
- `chilled_water_loop.fluo` -- `HxSegment` zone coupling, a thermostat
  state sweep, `forall` over line-ups, and the `leak_total` circuit
  budget. Read this one last; it ties fluid claims to a hematite zone.

Every construct these five files use appears in `docs/spec/fluorite/02`
above; there is nothing in them that is not also in this guide.
