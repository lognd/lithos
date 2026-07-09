# 03 -- Lowering (track spec 0.1; elaborated cycle 27 / D139, awaiting ratification)

One sentence: L2 alone delivers a statically code-checked building
program (egress, load-path conservation, occupancy, envelope
ratings, budgets) with zero solvers; L3 resolves sections; L4 emits
the content-addressed `frame` payload; L5 discharges structural
claims through the one obligation pipeline; L6 ships schedules and
sheets. The harness and margin rule are untouched -- calcite adds a
vocabulary, two net disciplines, and a payload kind.

## 1. Levels

| level | calcite content |
|---|---|
| L0-L1 | parse; quantity/unit/claim-form checks (shared, unchanged) |
| L2 | circulation + load-path net disciplines (sec. 3); occupancy arithmetic; envelope derivations (sec. 2); tributary partition ledger; area budgets (E0432 family); DOF/stability ledger over transfers (INV-15) |
| L3 | `section: free` resolution against capacity tables (cause-pinned, cheapest code-passing section -- the DFM-minimum discipline of regolith/03); code-pack rule evaluation over static facts (E06xx) |
| L4 | the `frame` realized-domain IR (sec. 4; AD-25 growth rule) |
| L5 | structural/whole-building obligations discharged by packs (sec. 5): closed-form member checks in-tree precedent, frame analysis/FEA via feldspar |
| L6 | `regolith ship`: schedules + drawing sheets (sec. 6; D140/WO-50) |

## 2. Elaboration (compile-time, deterministic)

- **Occupancy arithmetic**: `civil.occupant_load(space)` = area x
  the occupancy record's load factor, interval arithmetic, cited to
  the record hash. Aggregations (`per level`, `per exit`) are
  ordinary query-scoped derivations.
- **Egress path metrics**: travel distance, common path, and
  dead-end lengths evaluate over the circulation net using declared
  edge/space path lengths (`path_length=` on edges; the declared-
  tributary discipline -- v1 declares, it never measures). Worst
  path per space is a deterministic graph computation (longest
  shortest-path to any reference), part of lowering, no solver.
- **Envelope derivation**: `u_value: derived` = series resistance
  over the `layers:` records (conductivity, thickness), evaluated
  over the record intervals, cited to record hashes -- the
  fluorite/03 sec. 1 compliance-extraction precedent. An assembly
  naming a layer record without conductivity, consumed by a thermal
  claim, is a compile diagnostic (fail at compile, not at solve --
  the E0203 shape).
- **Tributary ledger**: per loaded surface, declared `tributary=`
  shares must partition the surface's declared area (`zones over`
  partition checking); mismatch is the second E0209 condition
  (same block).
- **Load-case resolution**: `loads:` pack-model refs
  (`site.ground_snow -> std.civil.asce7.roof_snow`) lower to
  signature-referenced derivation obligations (the `effects:`
  mechanism); combination sets expand as swept-obligation domains
  (D95 discrete axes), never obligation copies.
- **Self-weight**: `dead: derived` reads resolved sections x
  material density; re-runs when L3 re-resolves a section (ordinary
  staleness through content addressing -- a section change re-keys
  the load, which re-keys dependent obligations, INV-1).

## 3. Net disciplines (E0204-E0209; the AD-23 core, two new plugins)

**Circulation discipline** (nodes = spaces, edges = openings,
reference = `exterior`):

| code | condition |
|---|---|
| E0204 | occupiable space joins no circulation net and is not `unoccupied` |
| E0205 | space cannot reach a reference (exit) through edges |
| E0206 | egress edge on a required path with zero/undeclared width or `path_length` |

**Load-path discipline** (nodes = members + supports, edges =
transfers, reference = `support:` nodes):

| code | condition |
|---|---|
| E0207 | member cannot reach a support through transfer edges (the load LEAK) |
| E0208 | structure subnet with no `support:` node (imposer-counting analog) |
| E0209 | member end/bearing terminal unjoined and not `unloaded`; or tributary shares fail partition |

Both are `NetDiscipline` plugins over the one core in
`regolith-sem::net_core` (AD-23; the ElecDiscipline/FluidDiscipline
precedent) -- check predicates and codes only, zero new traversal
machinery. Stability beyond reachability (mechanism detection) is
the existing assembly DOF ledger over `dof:` releases (INV-15),
shared with mech, not a new check.

## 4. The `frame` payload (L4 realized-domain IR)

One schema-versioned, Rust-sourced record (AD-25 growth rule:
schemars schema in `regolith-oblig`, content-addressed via the one
encoder, a payload kind on the D96 channel -- kind string `frame`,
D139/D145, single-homed in feldspar's kind table):

```
FramePayload {
  joints:  [ { id, at: {grid_refs, level|elevation} } ],
  members: [ { id, role,                    # beam|column|brace|...
               a, b,                        # joint ids
               length, orientation,         # derived from grid/level datums
               section: RecordRef,          # resolved (post-L3)
               material: RecordRef,
               releases: { a: [dof], b: [dof] } } ],   # from transfer dof:
  supports: [ { joint, fixity: [dof] } ],
  loads:   [ { case, target: member|joint,
               kind: distributed|point|moment,
               value: Interval, direction } ],
  combinations: RecordRef,                  # the pack's combination set
}
```

- Joints are synthesized from transfer endpoints and grid/level
  anchors (member ends meeting at a shared anchor coalesce);
  lengths/orientations derive from the datums deterministically.
  A footing member MAY be point-anchored (both ends on the same
  datum, zero length): it contributes a support/reaction point,
  not a span -- lowering must not reject it.
- Releases come from each transfer class's `dof: kept=` -- the
  mating vocabulary IS the release model; no second encoding.
- `free` sections not yet resolved leave the member's `section`
  as the pre-resolution placeholder and dependent obligations
  honestly indeterminate (the AD-25 GeomExtract rule, verbatim).
- The payload is produced by lowering (like `flownet`), not
  extracted from a native artifact -- there is no realizer in the
  loop v1; if a BIM import path ever lands (charter reopen), it
  enters as an AD-25 producer, not a second frame schema.

## 5. Obligation shapes

| claim form | obligation carries |
|---|---|
| `civil.utilization(member, under=combo)` | frame ref + member id + combination axis (swept, D95) + code-pack identity via the discharging model |
| `mech.deflection(member, under=case)` | frame ref + member id + service case givens |
| `civil.story_drift(level, under=case)` | frame ref + level joint set + lateral case |
| `civil.bearing_pressure(footing)` | frame ref (reactions) + soil record ref |
| `mech.first_mode(structure)` | frame ref + modal case (mass from sections + declared loads); discharged by the pack vibration tier (sec. 5 prose) -- claims never name solvers |
| `civil.travel_distance / exit_capacity / dead_end` | statically discharged AT L2 (evidence: the graph computation, cited to declared lengths/widths and occupancy records) -- no pack |
| `civil.u_value / fire_rating / stc` | record-derivation evidence (u_value) or promise consumption (fire/stc catalog+test promises) through the ordinary chain |
| code-pack `rule` demands | the WO-28 engine unchanged: static facts at L3 (E06xx), realized facts as obligations |

Structural discharge tiers: closed-form member checks
(`mech.static_stress`, `mech.static_deflection`, plus the
`civil.utilization` code checks) come from packs -- feldspar's
`mech.struct` wave (its Phase 6, pulled forward by this track) does
direct-stiffness frame analysis consuming the `frame` payload;
`std.models` keeps the beam-formula floor. The margin picks the
tier; claims never name solvers.

## 6. Ship surface (L6)

Structured schedules (member schedule, opening/door schedule, area
tabulation, compliance report) via the WO-25 backend framework --
each a deterministic projection of the lockfile + frame payload +
circulation net + evidence set. Drawing SHEETS (plan/section/
elevation diagrams from grids, spaces, and the frame; the
member-schedule sheet) ride the D140 `DrawingModel` IR (toolchain/25,
WO-50): producers derive, renderers render, and every dimension on a
sheet carries its resolution cause. BIM/IFC stays out (charter
sec. 7).

## 7. Cross-track couplings

- **Hydronic/plumbing (fluorite)**: a space's `offers:` drain/pad
  impls bind fluorite components; heat loads couple through zone
  data exactly as fluorite/03 sec. 4 (HxSegment) -- the building's
  thermal claims consume envelope u_values and the loop's capacity
  promises through one promise chain.
- **Power (cuprite)**: `Feeder(capacity=...)` offers are supply
  contracts; panel schedules stay cuprite artifacts; the building's
  energy budget (kind `energy`, D49) may span tracks (members from
  both languages in one budget, the D49 rule).
- **Structural loads from equipment (hematite/fluorite)**: equipment
  mass promises enter member loads as ordinary derived givens via
  the promise chain (the dissipation-promise precedent); a rooftop
  unit's operating mass is a promise the `loads:` block consumes.
- **Firmware/controls**: nothing calcite-specific -- building
  automation is cuprite + its computer track, hosted through space
  contracts.

## 8. Trust, evidence, determinism

Nothing new: obligations discharge through the model registry;
evidence is content-addressed, signable, coverage-stating;
`frame` payload determinism = datum-derived geometry + record refs
+ resolved sections (all deterministic inputs). Code packs carry
their jurisdiction and edition in the pack identity; a variance is a
`waive ... by <evidence>` with expiry -- the existing ladder models
real building variances verbatim (charter sec. 4).
