# 10 -- The power layer (cuprite 0.13, cycle 36 / D248/D249/D250, AD-42)

> One sentence: facility power distribution is a FOURTH `NetDiscipline`
> over the AD-23 net core -- buses are nodes, apparatus (services,
> generators, transformers, feeders, protective devices) are edges,
> current (kVA) is the conserved flow, voltage is the potential -- and
> its vocabulary is ordinary cuprite artifacts with power roles, the
> same way fluorite's `Pipe`/`Valve`/`Pump` need no new grammar.

Status: WO-132 (front-end: grammar, the discipline plugin, its
lowering-to-diagnostic wiring, corpus). WO-133 (payload/schema,
`PowerNetPayload`), WO-134 (`std.power` records), WO-135 (models, both
repos), WO-136 (the calcite tandem: sited equipment), WO-137 (the
factory flagship) are separate, later work orders; this section
documents only what WO-132 ships. Charter `docs/spec/toolchain/
43-power-distribution.md` (AD-42) is normative over this section for
anything the two disagree on; this section is the cuprite track's own
citable home for the same rulings, per the charter's directive that
each governed track's spec directory carries its slice.

## 1. `power <name>:` -- the power net

A facility's power system is declared as a `power <name>:` top-level
declaration, the fourth AD-23 net discipline (after `elec` nets,
fluorite's `flownet`, and calcite's `structure`/`circulation`):

```
power PlantMain:
    sources: Utility, Genset
    buses: Utility, Genset, Tie, MainSwgr, PanelA
    ties: Tie
    loads: PressMotor, LightingLoad
    feeders:
        svc:      service(voltage=13.2kV, available_fault=25kA, x_r=6.6) (Utility -> Tie)
        gen:      generator(kva=750kVA, voltage=480V)                   (Genset -> Tie)
        main_bkr: breaker(frame=2000A, aic=65kA)                        (Tie -> MainSwgr)
        xfmr:     transformer(kva=1000kVA, primary=13.2kV, secondary=480V) (MainSwgr -> MainSwgr)
        feed:     feeder(size=cu_4_0awg, length=45m)                    (MainSwgr -> PanelA)
        pnl_bkr:  breaker(frame=225A, aic=25kA)                         (PanelA -> PanelA)
```

Fields: `sources:` (comma-list, the net's source imposers -- utility
service or generator apparatus names), `buses:` (comma-list, every
node in the net), `ties:` (comma-list, buses where a declared parallel
source path is intentional -- the "unless a TIE is explicitly
declared" escape charter 43 sec. 1 rule 2 names), `loads:` (comma-list,
every demand-side apparatus that must trace to a source). `feeders:`
types a nested edges block exactly like a flownet's `edges:` block or
a `structure`'s `transfers:` block: `<name>: <apparatus>(<params>)
(<from> -> <to>)`, one line per bus-to-bus apparatus. A protective
device (or any apparatus that need not narrow ampacity) is written as
a self-loop edge (`<name>: breaker(...) (Bus -> Bus)`) when it sits at
one bus rather than between two.

## 2. The vocabulary (WO-132 deliverable 3)

Apparatus are declared as ordinary constructor names used as a
`feeders:` edge's value -- the SAME shape fluorite's `Pipe`/`Valve`/
`Pump`/`Regulator` already use, needing zero new grammar per word
(charter 43 sec. 2's "ordinary cuprite artifacts with power roles" is
the point): `service`, `generator`, `transformer`, `switchgear`,
`panelboard`, `mcc`, `feeder`, `busway`, `breaker`, `fuse`, `relay`,
`motor`, `load`. The one piece of new grammar this layer needed is the
`power <name>:` net declarator itself (a CONTEXTUAL ident, the same
D85 idiom `flownet`/`structure`/`circulation` use, never a lexer
keyword) and its `feeders:` field reusing the existing `EdgesBlock`/
`EdgeStmt`/`SensePair` typed CST verbatim -- no duplication.

## 3. Discipline rules (charter 43 sec. 1)

Rule 1 rides the AD-23 core exactly like `FluidDiscipline`/
`LoadPathDiscipline`: `regolith_sem::net_core::PowerDiscipline` flags a
net with no declared `sources:` at all (`E0212`,
`POWER_SUBNET_UNSOURCED`) -- an unsourced load is a diagnostic, never
an assumption.

Rules 2-4 need an edge walk the `NetDiscipline` trait does not provide
(it only counts imposer terminals per net, mirroring the calcite
`LoadPathDiscipline`/`CirculationDiscipline` scope cut named in
`regolith_lower::calcite`'s module doc comment), so they are
hand-written DIRECTED graph walks over the `feeders:` edges in
`regolith_lower::power`:

- **`E0213`** (`POWER_UNDECLARED_PARALLEL_PATH`): a bus reachable
  (following the declared feed direction) from more than one source
  and not named in `ties:`, and not itself downstream of a declared
  tie (once sources merge at a tie, everything downstream legitimately
  carries both feeds -- the tie declaration covers its whole
  downstream tree, not only the tie bus).
- **`E0214`** (`POWER_UNPROTECTED_TRANSITION`): a `feeders:` edge whose
  apparatus (`transformer`, `feeder`, `busway`) narrows ampacity, with
  no `breaker`/`fuse`/`relay` edge touching either of its endpoints.
- **`E0215`** (`POWER_LOAD_UNREACHABLE`): a declared `loads:` entry no
  source can reach forward through the `feeders:` graph.

Reachability here is DIRECTED, unlike calcite's egress walk: a power
feed has a real direction (source toward load), so an undirected walk
would let a bus "reach" every other source sharing a downstream node
-- a false positive caught in WO-132's own review (see
`regolith_lower::power::reachable_from`'s doc comment).

## 3a. `buses:`/`loads:` per-item properties (WO-133 deliverable 2, coordinator adjudication F-WO133-1)

`buses:`/`loads:` items may carry OPTIONAL declared properties, in the
SAME `name(key=value, ...)` shape the apparatus edge vocabulary (sec.
2) already uses -- no new syntax, mirroring the existing convention
rather than inventing one:

```
buses: Utility, MainBus(nominal_voltage=480V, phases=3)
loads: LightingLoad, PressMotor(kva=45, class=motor, code_letter=G)
```

A bare name (no parenthesized properties) is the pre-existing shape
and stays valid; `regolith_syntax::ast::PowerDecl::bus_items`/
`load_items` parse each item into its name plus its declared
`(key, value)` pairs (`crate::ast::PowerListItem`), a small hand-rolled
text scan over the field's lossless value text -- additive, zero
blast radius on any other field/claim shape (it re-parses nothing the
shared statement grammar already owns).

These properties are how `regolith_lower::power::emit_power_payloads`
(WO-133 deliverable 2) fills the `PowerNetPayload` schema's REQUIRED
fields (`Bus.nominal_voltage`, `Bus.phases`, `Load.connected_kva` --
the schema itself stayed FROZEN, D272 spent): a bus/load that omits
one is not silently defaulted (D250.3) -- payload emission for the
WHOLE net refuses, naming the exact gap, coded `E0217`
(`POWER_PAYLOAD_FIELD_UNRESOLVED`). See
`examples/negative/77_cupr_power_payload_field_unresolved.cupr` for
the refusal case and `examples/tracks/cuprite/power_plant_main.cupr`
for the complete-declaration case (a byte-stable payload, WO-133
deliverable 5).

## 4. Claim forms (WO-132 deliverable 4; routing/discharge WO-133/135)

The following claim kinds parse today with zero grammar changes --
claims are ordinary dotted-path/call expressions inside `require
<Group>:` claim groups (`docs/spec/regolith/07-claims-and-evidence.md`),
not a fixed enum, so a new claim kind is only ever a NAME, never new
syntax: `elec.power.demand_load`, `voltage_drop`, `ampacity`,
`fault_current`, `withstand`, `transformer_loading`,
`motor_start_dip`, `coordination`, `arc_flash`, `grounding`,
`power_factor`, `harmonics`, `working_clearance`. They parse and reach
lowering as recognized (unrejected AST nodes). WO-133 deliverable 3
routes seven of these kinds (`demand_load`, `voltage_drop`, `ampacity`,
`fault_current`, `motor_start_dip`, `transformer_loading`,
`power_factor`) to their T-0009 `regolith.harness.models.power` models
via `regolith.orchestrator.translate._translate_power_claim`; the
remaining six (`withstand`, `coordination`, `arc_flash`, `grounding`,
`harmonics`, `working_clearance`) register no model (D250.4) and stay
on the generic dotted-call fallback, which names the call in an honest
deferral rather than a misleading "missing inputs" one.

## 5. Non-goals and deferred work (named, not invented)

- The `PowerNetPayload` lowering slot itself has landed (sec. 3a,
  WO-133 deliverable 2); actual numeric discharge of the sec. 4 claim
  forms above (routing to `regolith.harness.models.power` where a
  model is registered) is WO-135/D250.4.
- `std.power` component records (transformer catalogs, breaker
  frames, motor code letters): WO-134 (data already lands in
  `stdlib/std.power/`, ahead of this front-end landing).
- The calcite tandem (sited equipment: mass on a slab, working
  clearance as a spatial containment claim): WO-136, charter 43 sec. 4.
- The factory flagship demonstrating this whole charter end to end:
  WO-137.
- Safety honesty (charter 43 sec. 5: cited standards/editions,
  "not a certification" statement, no typical-value fallback, arc
  flash release-tier only through a certified solver) governs every
  later WO that actually computes a power claim; this front-end layer
  computes nothing yet, so it has nothing to violate, but the rule is
  recorded here so no later WO can plead ignorance of it.
