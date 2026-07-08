# examples/tracks/fluorite/

Five single-file, teaching-scale fluid circuits (design-log cycle 23 /
D122). Every construct is hand-validated against `docs/fluorite/02`
(language) and cited to its section; nothing here is compiled by
`regolith check` today -- the `.fluo` extension is not yet registered
in `crates/regolith-syntax` (WO-31). These are spec pressure tests
now, and become WO-31's golden corpus once the extension lands.

## File map

| file | subsystem | pressure applied |
|---|---|---|
| `garden_irrigation.fluo` | drip irrigation | simplest shape: one `medium`, one `reference`, plain `Pipe` edges, a four-emitter `Orifice` orbit (named-list form), `dp` + `flow_imbalance` claims (02 sec. 6) |
| `aquarium_loop.fluo` | filtration loop | `Pump(curve=...)` record, `Filter(dp_curve=...)`, `CheckValve`, `npsh_margin` claim, edge-parameter state + `event ... commanded by`, a startup `settles` transient claim |
| `hydraulic_jack.fluo` | bottle jack | `Imposer(driven_by=...)` cross-track promise (mech handle force -> hydraulic pressure), `volume_consumed` compliance budget, `peak` claim on a release event |
| `shop_air.fluo` | compressed-air drop | gas medium (`ShopAir`) evaluated at temperature corners, `Regulator`, `Plenum` capacitance, `choked` regime screening, `forall` over a declared line-up state |
| `chilled_water_loop.fluo` | enclosure cooling | `HxSegment(zone=...)` mech-zone coupling, thermostat state sweep, `forall` line-up, `leak_total` circuit budget |

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

## WO-31 caveat

None of these files are seen by `regolith check` today. `.fluo` is
absent from the extension registry (`crates/regolith-syntax`); no
diagnostic, no parse, no lowering runs against this directory until
WO-31 registers the extension and wires the `fluids`/`prop` solver
namespaces (feldspar). Until then this directory is pure spec
pressure-testing: each file is hand-checked line-by-line against
`docs/fluorite/02-language.md` and `03-lowering.md`, cited inline.

## Candidate findings

- `fluorite/02` sec. 4 gives `flownet FuelFeed(medium=RP1):` as the
  header form but never states whether a flownet name is
  project-unique or file-scoped (matters once WO-31 supports
  multi-file fluid projects with a shared medium across nets). Not
  exercised by these five single-net files; flagged for the WO-31
  author.
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
