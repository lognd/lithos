# examples/tracks/fluorite/

Single-file, teaching-scale fluid circuits (design-log cycle 23 /
D122, extended by WO-31 D5). Every construct is hand-validated against
`docs/spec/fluorite/02` (language) and cited to its section. As of WO-31 the
`.fluo` extension is registered (`crates/regolith-syntax`), so `regolith
check` parses these files and runs the fluid net discipline (fluorite/02
sec. 4) over them: every file here is `regolith check`-clean (it parses
losslessly and passes the E02xx fluid-discipline checks). Lowering to
obligations and solving remain WO-32.

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `garden_irrigation.fluo` | drip irrigation | simplest shape: one `medium`, one `reference`, plain `Pipe` edges, a four-emitter `Orifice` orbit (named-list form), `dp` + `flow_imbalance` claims (02 sec. 6) |
| `aquarium_loop.fluo` | filtration loop | `Pump(curve=...)` record, `Filter(dp_curve=...)`, `CheckValve`, `npsh_margin` claim, edge-parameter state + `event ... commanded by`, a startup `settles` transient claim |
| `hydraulic_jack.fluo` | bottle jack | `Imposer(driven_by=...)` cross-track promise (mech handle force -> hydraulic pressure), `volume_consumed` compliance budget, `peak` claim on a release event |
| `shop_air.fluo` | compressed-air drop | gas medium (`ShopAir`) evaluated at temperature corners, `Regulator`, `Plenum` capacitance, `choked` regime screening, `forall` over a declared line-up state |
| `chilled_water_loop.fluo` | enclosure cooling | `HxSegment(zone=...)` mech-zone coupling, thermostat state sweep, `forall` line-up, `leak_total` circuit budget |
| `feed_system.fluo` | pressure-fed propellant leg | `Regulator` pressure imposer + `CheckValve` + metering `Orifice` (the WO-31 D5 feed shape), `dp`/`supply`/`reynolds` claims |
| `dual_brake_circuit.fluo` | dual-circuit hydraulic brake | `Imposer(driven_by=...)` master cylinder, dual-circuit `state` variables (`front_circuit`/`rear_circuit`), `forall` over declared state refs (the WO-31 D5 brake shape, fluorite/02 sec. 5 failure idiom) |

## Conventions

- Comments cite the `fluorite/02` (or `/03` for lowering-visible
  behavior) section a construct exercises.
- Engineering numbers are realistic for the named subsystem (hose-bib
  pressure, ISO VG32 hydraulic oil, 60/40 ethylene-glycol/water, shop
  air at 620 kPa set pressure, etc.).
- Cross-track promise references (`handle.applied_force`,
  `handle_force`, `pump_stroke_displacement` in `hydraulic_jack.fluo`)
  are left unresolved on purpose, exactly like the `pedal_force`
  example in `fluorite/02` sec. 3 -- a single-file teaching fixture
  shows one side of a promise chain that a real multi-file project
  would close on the mech side.
- Reference nodes (`ambient(...)`) are never listed in a flownet's
  `nodes:` line, matching the worked example in `fluorite/02` sec. 4:
  the reference's own name is a synthesized node, not a declared one.

## Status (WO-31 landed)

`.fluo` is registered (`crates/regolith-syntax/src/extension.rs`), so
`regolith check` now parses these files and runs the fluid net
discipline (fluorite/02 sec. 4): imposer-free subnet (E0201) and
unjoined terminal (E0202). Every file here is check-clean. What still
does NOT run is lowering to obligations and solving the network
(the `fluids`/`prop` feldspar solver namespaces) -- that is WO-32.
The medium-consistency and wall-compliance checks (fluorite/02 sec. 4,
fluorite/03 sec. 1) also land in WO-32, because they need the
lowering-time component/geometry binding the front end does not have.

## Candidate findings

- RESOLVED (D125a, cycle 23): flownet names follow the standard
  top-level declaration rule (package-scope uniqueness, INV-18) --
  nothing flownet-specific. `fluorite/02` sec. 4 now states this. The
  original finding (name scope unstated) is closed.
- `fluorite/02` sec. 6's worked example calls `fluids.flow_imbalance
  (injector.elements)` with a dotted orbit reference (a mech
  pattern-instance orbit exposed through an interface), but never
  shows the bracketed-list form used directly on flownet edges (used
  in `garden_irrigation.fluo`'s `balance` claim, mirroring the
  bracketed-list precedent already used for cuprite `budget members:`
  lists, regolith/02 sec. 6 vocabulary). No spec text forbids it, but
  no worked example confirms it either -- flagged so the WO-31 author
  either canonizes the list form or requires an explicit `orbit`
  declaration construct.
- Regulator/Plenum ordering (`shop_air.fluo`): `fluorite/02` sec. 3
  lists `Regulator` and `Plenum` as components but does not say
  whether a `Plenum` edge may sit in series with a `Regulator` edge on
  the same node pair as modeled here, or whether `Plenum` is meant to
  be a node-attached capacitance rather than a two-terminal edge.
  Modeled as a two-terminal edge for consistency with every other
  component in sec. 3 (`Pipe`, `Hose`, `Orifice`, ... are all
  two-terminal); flagged for WO-31 confirmation.
