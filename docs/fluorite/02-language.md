# 02 -- Language (RATIFIED v1, cycle 20 / D93)

One sentence: media give fluids identity and properties, FluidPort
gives components a typed through/across boundary, flownets join
terminals relationally, states select line-ups, and claims stay
pure quantity-core vocabulary.

## 1. Media

A medium names a fluid and binds its property records (regolith/02
sec. 6 registries; interval-valued functions of state):

```
medium RP1: liquid
    props: registry(rp1_mil_dtl_25576)     # rho(T), mu(T), pv(T), ...

medium GN2: gas
    props: registry(nitrogen_nist)

medium Coolant60: liquid
    props: registry(egw_60_40)
```

- Property evaluation follows corner discipline; out-of-record-range
  is honest indeterminate (the record's domain is its published
  range).
- One medium per connected subnet in v1; mixing is a compile error
  (FOPEN-1).

## 2. FluidPort -- the typed boundary

The fluid analog of an interface role; through/across pairs:

```
interface FluidPort<m: medium, dia: length>:
    flow:
        mdot:  through           # conserved at every node
        p, T:  across            # potentials at the port plane
    roles:
        bore: circular(dia)      # the wetted geometry hook (hematite)
```

- `through` quantities sum to zero at a node (signed; direction is
  SOLVED, never declared -- declaring it is the classic hand-analysis
  bug).
- `across` quantities are shared by all terminals at a node.
- A hematite part exposes its wetted side by implementing FluidPort
  (`impl FluidPort<RP1, dia 12mm> for self as fuel_in: bore =
  turned.inlet`), exactly like any interface impl. The realized
  geometry behind the role is where lowering reads areas, lengths,
  bend counts, roughness (03).

## 3. Components

Component classes live in `std.fluorite` and follow cuprite's
component-class pattern (regolith/02 sec. 6 hierarchy): each is a
two-or-more-terminal element with declared parameters; vendor parts
bind datasheet records:

```
Pipe(from=part.role)        # hydraulic side derived from geometry
Hose(from=part.role | compliance=registry(...))
Orifice(cd=..., dia=...)
Valve(cv=..., states={open, closed} | position in [0,1])
CheckValve(crack_dp=...)
Regulator(set=..., droop=...)
Pump(curve=registry(...))   # head-flow curve record, NPSH_r curve
Filter(dp_curve=registry(...))
Plenum(v=...)               # two-terminal storage edge: negligible
                            # dp, volume v; BOTH plumbing forms are
                            # expressible -- an in-line receiver tank
                            # (series, a -> b on the flow path) and a
                            # node-to-reference accumulator; solvers
                            # treat v as storage at the edge's span
                            # (D125c, cycle 23)
Imposer(p=<expr>, driven_by=<promise ref>)
                            # a pressure imposer whose VALUE is an
                            # ordinary quantity-core derivation; the
                            # cross-track boundary (a master cylinder
                            # driven by a mech pedal-force promise)
HxSegment(zone=part.zones.x)  # heat-exchange coupling (03 sec. 4)
```

Parameter-source rules (F98 fixes, one word one idea):

- `from=` names a REALIZED-GEOMETRY source only (`Pipe`, `Hose`):
  the hydraulic side is extracted in lowering (03 sec. 1).
- `driven_by=` names a cross-track PROMISE chain: the parameter's
  value expression (`p=pedal_force * ratio / area(19.05mm)`) is
  ordinary quantity-core derivation over promised quantities.
- Record-bound parameters (`curve=`, `compliance=`, `dp_curve=`)
  resolve hash-pinned registry objects.
- Compliance is a first-class edge parameter: bound from a record OR
  extracted from the implementing part's wall record (03 sec. 1);
  it feeds both transient wave speeds and volume budgets.

Parameters accept `free`/`allocated`/`derived` exactly as everywhere
else in lithos; a `free` orifice diameter is resolved by the
orchestrator's lazy loop against the claims.

## 4. Flownets

The relational join, shaped like cuprite `nets:` with fluid
discipline (both ride the AD-23 generalized net core). Flownet names
follow the standard top-level declaration rule (package-scope
uniqueness, the INV-18 discipline) -- nothing flownet-specific
(D125a, cycle 23):

```
flownet FuelFeed(medium=RP1):
    reference: ambient(101kPa, 293K)      # the pressure/temperature
                                          # reference (elec `gnd`
                                          # analog); >=1 per subnet
    nodes: tank_out, mv_up, mv_dn, jkt_in, jkt_out, inj_in
    edges:
        feed:   Pipe(from=feed_tube.run)        (tank_out -> mv_up)
        mv:     vendor(mv74_ball)               (mv_up -> mv_dn)
        jacket: Pipe(from=liner.cooling)        (jkt_in -> jkt_out)
        inj:    InjectorHead.fuel_path          (... -> inj_in)
    states:
        mv.position in {closed, open}           # edge-parameter domain
        state feed_leg in {primary, backup}     # declared net-level
                                                # config variable
```

Net discipline (compile-checked, the cuprite-analog ledger; AD-23
core with the fluid discipline plugin):

- terminal ledger: every declared FluidPort terminal joins exactly
  one node or is explicitly `sealed`;
- reference reachability: every node reaches a reference through
  edges;
- at least one pressure IMPOSER (reference, regulator, pump curve,
  `Imposer`) per subnet -- otherwise the network is singular by
  construction and rejected at compile time, not at solve time;
- medium consistency per subnet;
- arrow syntax `(a -> b)` is a NAMING convention for the edge's
  positive sense, not an assertion about flow direction.

## 5. States and events

Valve states / line-ups are ordinary config domains
(`forall FuelFeed.state in line_ups(...)`); net-level config
variables are DECLARED (`state <name> in {...}`, sec. 4) before any
claim conditions on them. Commanded transitions are EVENTS shared
through the quantity core (`event mv.close: commanded by ctrl.mv_f`
-- the cuprite crossing; the event is one datum in one ledger,
regolith/02 sec. 5).

`forall <var> in {<state refs>}` over a FINITE set of declared state
variables is admitted (the dual-circuit failure idiom: `forall
circuit in {circuit_f, circuit_r}: ... given circuit = failed`). It
lowers to ONE swept obligation whose discrete axis points are
(state-variable, value) bindings -- carried by the structured
coverage encoding (D95), never enumerated into obligation copies.

## 6. Claims (all existing vocabulary; nothing new invented)

```
require Feed:
    margin:  fluids.dp(tank_out -> inj_in) <= 6bar
    supply:  fluids.pressure(inj_in) - thermo.pressure(chamber) >= 5bar
    balance: fluids.flow_imbalance(injector.elements) < 5%
                                       # entity-set args take a query
                                       # ref, an orbit ref, OR a
                                       # bracketed edge list
                                       # [a, b, c] -- the regolith
                                       # list precedent (D125b)
    npsh:    fluids.npsh_margin(pump) > 3m, sf=1.3
    regime:  fluids.reynolds(jacket) in [4e3, 1e6]     # tag-shaped
    choke:   not choked(mv)                            # tag-shaped
                                                       # screening
    hammer:  peak(fluids.pressure(mv_dn),
                 within 20ms after mv.close) < 80bar
    fill:    settles(fluids.mdot(inj_in), to=+-2%,
                 within 300ms after mv.open)
    budget:  fluids.volume_consumed(all_edges, at=80bar)
                 < 0.75 * mc_displacement(front)       # compliance
                                                       # budget form
    leaks:   fluids.leak_total(FuelFeed) < 10scc/s     # circuit leak
                                                       # budget (D93)
```

- The temporal vocabulary is regolith/02 sec. 5 VERBATIM
  (`peak`/`settles`/`rms`/`stays_within`); `peak` is normatively the
  worst excursion in the claim's ADVERSE direction (sense-driven), so
  a suction-dip lower bound is `peak(...) > x` -- there is no
  `.min`/`.max` claim spelling.
- `fluids.leak_total` is a budget over fitting/seal contributors; a
  component's own seal leakage is a mech interface promise consumed
  through the ordinary promise chain (one quantity kind, one budget
  owner -- the flownet).
- `forall` over states and boundary intervals composes as everywhere
  else; corner discipline picks worst line-up corners per claim.
