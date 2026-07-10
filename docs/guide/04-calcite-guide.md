# The calcite guide (civil / architectural design)

calcite describes buildings the same way hematite describes
mechanisms and cuprite describes circuits: contracts and claims
first, implementation and evidence derived. If you have read either
of those guides, most of this is familiar -- the load-bearing words
are shared regolith vocabulary. This guide covers what is
civil-specific: sites, spaces, circulation, the structural load-path
net, and envelope assemblies. Normative sources: `docs/spec/calcite/`
01-04, `docs/spec/regolith/`.

Status note: calcite's spec is elaborated and its corpus compiles
against the corpus README's conventions, but the front end (WO-47)
and lowering (WO-48) are DESIGNED, not yet runnable -- `std.civil`
names in every example below are phantom until the pack lands. Read
this guide as the target shape, the same way the corpus README reads
it.

## 1. The core idea

A building project declares three families of truth and lets the
toolchain derive the rest:

1. **Site** (`site`): the one piece of physical truth every design
   consumes -- wind, snow, seismic category, frost depth, soil
   bearing -- declared once, record-cited, never repeated.
2. **Program** (`space`, `circulation`): what the building is FOR --
   areas, occupancy, egress -- checked at L2, no geometry, no solver.
3. **Structure and envelope** (`member`, `structure`, `assembly`):
   what carries load and what separates inside from outside --
   sized, checked, and rated by packs.

Grids and levels are the only positional vocabulary calcite has:
enough to give every member a deterministic length without ever
authoring geometry (BIM/IFC authoring is a v1 non-goal; drawing
SHEETS are a derived L6 output, not authored input).

## 2. Site, grids, and levels

```
site CurbSide:
    boundary:
        wind_speed:   [0m/s, 47m/s]             by catalog(asce7_fig26)
        ground_snow:  1.9kPa                    by catalog(asce7_fig7)
        frost_depth:  0.9m                      by catalog(county_gis)
    soil:
        bearing:      [95kPa, 145kPa]           by test(geotech_s114)

grid bays: A, B spacing 3.6m
level ground: 0m
level roof:   2.4m
```

- One `site` per project root; every entry is record- or
  report-cited (evidence clauses, regolith/04 sec. 1). Geotech data
  is always `by test`, never a solved model.
- `grid` and `level` declare datum families -- a grid intersection
  (`(A, roof)`) or a level is an addressable datum; members and
  spaces locate against them. This is the entire positional
  vocabulary calcite carries.

## 3. Spaces and circulation (the architectural program)

`space` is the unit of architectural program:

```
space Waiting:
    area:      8.6m2
    occupancy: registry(a3_waiting)             # std.civil table
    at:        level(ground)
    bounded_by: RoofPanel on [top]
```

- `area` is an ordinary interval-valued quantity; `occupancy` binds a
  `std.civil` record (class, load factor, egress factors).
  `civil.occupant_load(space)` = area x load factor is derived
  arithmetic at L2.
- `bounded_by` binds an envelope `assembly` to the space's boundary
  -- a contract consumption (the wall PROMISES a rating; the space's
  claims consume it), never geometry.

Adjacency and access are contracts too, never geometry:

```
access:
    open_front: Exit(width=3600mm)              (Waiting -> exterior)

circulation Egress:
    reference: exterior
    nodes: Waiting
    edges: open_front
```

Egress rides the AD-23 net core with a THIRD discipline (elec and
fluid already use the same core): spaces are nodes, openings
(`Door`/`Exit`/`Stair`/`Ramp`) are edges, `exterior` is the
reference-reachability target. The net discipline is compile-checked
just like a flownet:

| code | condition |
|---|---|
| E0204 | occupiable space joins no circulation net and is not `unoccupied` |
| E0205 | space cannot reach `exterior` through edges |
| E0206 | egress edge on a required path with zero/undeclared width or `path_length` |

Travel distance, common path, and dead-end limits are ordinary
CLAIMS over this net, evaluated at L2 -- no geometry, no solver. This
is the track's headline payoff: a statically code-checked building
program before a single member is sized.

## 4. Members, transfers, and the load-path net

`member` carries the structural role vocabulary -- one word, one
idea: `beam`, `column`, `brace`, `slab`, `wall`, `footing`.

```
member C1: column
    section:  registry(hss89x89x6.4)
    material: registry(astm_a500c)
    from (A, ground) to (A, roof)

member G1: beam
    section:  free                              # L3 resolves
    material: registry(astm_a992)
    from (A, roof) to (B, roof)
```

- `section:` is the value-source grammar unchanged: a registry
  record, `free` (the cheapest code-passing section resolves,
  cause-pinned), or a bounded domain.
- The grid/level anchors give every member a deterministic length
  and orientation for the frame IR -- no other geometry exists.

Members join through **transfers** -- mating-shaped connection
contracts with named sides, `dof:` releases, and a `capability:`
envelope:

```
Pinned()          # dof: kept=rotation
Moment()          # dof: kept=none; full fixity
Bearing()         # gravity bearing; kept=rotation+slip
BasePlate(anchors=...)
Roller()          # kept=rotation+translation(1)
```

The load path is a NET (the same AD-23 core, a second discipline):
members and supports are nodes, transfers are edges.

```
structure Shelter:
    support: F1: footing, F2: footing
    members: C1, C2, G1, RoofDeck
    transfers:
        deck_g1: Bearing(tributary=8.6m2)   (RoofDeck -> G1)
        g1_c1:   Pinned()                   (G1 -> C1)
        g1_c2:   Pinned()                   (G1 -> C2)
        c1_f1:   BasePlate()                (C1 -> F1)
        c2_f2:   BasePlate()                (C2 -> F2)
```

| code | condition |
|---|---|
| E0207 | member cannot reach a support through transfer edges (the load LEAK) |
| E0208 | structure subnet with no `support:` node |
| E0209 | member end/bearing terminal unjoined and not `unloaded`; or tributary shares fail partition |

`tributary=` shares are declared, never measured: they must
partition the loaded surface's area exactly, checked at compile time
(the same "zones over" partition discipline hematite uses for area
budgets). The transfer arrow names the edge's positive load-transfer
sense; direction and magnitude of the actual force are SOLVED --
uplift is a sign, not a surprise.

## 5. Loads, cases, and combinations

Load MAGNITUDES are boundary/site truth; load CASES and
COMBINATIONS are pack content -- the same "policy math is pack math"
rule that governs allocation elsewhere in regolith:

```
loads:
    dead: derived                               # sections x density
    snow: site.ground_snow -> std.civil.asce7.roof_snow
    wind: site.wind_speed  -> std.civil.asce7.mwfrs
```

`derived` self-weight comes from resolved sections and material
density -- ordinary lockfile-caused derivation. The `->` entries name
pack MODELS that turn site truth into member loads; combinations
sweep as a `forall` domain, one obligation over the whole combination
set (never enumerated into copies):

```
require Structure:
    forall combo in std.civil.asce7.strength:
        strength: civil.utilization(Shelter.members.all, under=combo) <= 1.0
    deflect: mech.deflection(G1, under=std.civil.asce7.service)
                 <= G1.span / 240
    bearing: civil.bearing_pressure(F1) <= site.soil.bearing
```

`civil.utilization` is the code interaction-ratio claim; WHICH
formula (AISC, NDS, Eurocode) is the discharging pack's identity,
never the claim's. Structural claims come off the `frame` payload
(the L4 realized-domain IR: joints, members, releases, supports,
loads -- the same growth-rule shape as elec's realized boards), and
discharge through closed-form checks in-tree or frame/FEA via
feldspar; the margin picks the tier, claims never name a solver.

A serviceability claim can outrank strength entirely -- the
footbridge corpus example sizes its girders (`section: free`) against
a first-mode vibration claim, not a strength check:

```
vibe: mech.first_mode(Bridge) > 3Hz
```

## 6. Envelope assemblies

Layered constructions -- wall, roof, or floor types -- with ordered
material layers and PROMISED derived ratings:

```
assembly RoofPanel: roof
    layers:
        skin: registry(alum_sheet_3mm)
        core: registry(polycarbonate_16mm)
    promises:
        u_value: derived
```

`u_value: derived` is computed at L2 as a series-resistance sum over
the layer records' conductivities, cited to the record hashes.
Fire rating and STC are catalog/test promises instead -- a derived
fire rating would be dishonest, so the language deliberately never
offers one:

```
assembly ExtWall2hr: wall
    layers:
        face:  registry(brick_veneer_90mm)
        gap:   registry(air_gap_25mm)
        ins:   registry(mineral_wool_152mm)
        stud:  registry(steel_stud_92mm_600oc)
        board: 2 x registry(gyp_type_x_16mm)
    promises:
        u_value:     derived
        fire_rating: >= 2hr    by catalog(ul_u419)
        stc:         >= 50     by test(ra_tl_2214)
```

Spaces and the site boundary consume assemblies through ordinary
contracts: a corridor requiring a 1hr separation holds the demand;
the bounding assembly's promise discharges it.

## 7. Record-driven geotechnical claims

Soil is always a `by test` record with a trust tier, never a solved
model (charter sec. 7). The retaining-wall corpus example shows the
full shape: a lateral-earth-pressure case comes from a PACK MODEL
over a soil record, and overturning stability is the same
`equilibrium(...): stable` claim form hematite already uses for
tip-over checks -- no new civil spelling:

```
loads:
    dead:  derived
    earth: site.soil.backfill -> std.civil.geo.rankine_active

require Stability:
    overturn: equilibrium(Wall, under=std.civil.geo.stability): stable
    sliding:  civil.utilization(heel_sg, under=std.civil.geo.sliding) <= 1.0
    bearing:  civil.bearing_pressure(Heel) <= site.soil.bearing
    trust: >= tested                            # community-tier soil
                                                  # numbers must not
                                                  # underwrite a wall
```

## 8. Cross-track composition (MEP)

MEP is composition, not calcite surface: hydronics/plumbing are
fluorite circuits, power is cuprite, and the building hosts them
through ordinary contracts. A space `offers:` interface impls other
tracks bind:

```
import "hydronics.fluo" (HeatingLoop)
import "power.cupr" (MainPanel)

space MechRoom:
    area: 18m2
    occupancy: registry(b_mechanical)
    offers:
        drain:  FloorDrain(dia=100mm)          # fluorite consumes
        power:  Feeder(capacity=40kW)          # cuprite consumes
        pad:    HousekeepingPad(area=2m2)      # hematite consumes
```

Equipment mass promises enter member loads as ordinary derived
givens through the promise chain -- a rooftop unit's operating mass
is a promise the `loads:` block consumes, exactly like the flagship's
boiler:

```
equip: HeatingLoop.boiler.operating_mass on [Deck2]
```

Boundary subsumption guards the envelope both ways: a chiller proven
for `[5C, 40C]` rooms demands the mech room's declared temperature
interval be contained.

## 9. Worked corpus tour

Read in this order -- smallest to the cross-track payoff:

- `tracks/calcite/bus_shelter.calx` -- the simplest shape: one space,
  four members, one envelope assembly, one circulation edge, the
  load-path net, and the `forall`-combination strength sweep. Start
  here.
- `tracks/calcite/pole_barn.calx` -- a timber frame where SNOW
  governs; tributary partition over a loaded roof; embedded-post
  footings checked against frost depth as a code-pack rule.
- `tracks/calcite/footbridge.calx` -- a structure-only file (no
  spaces at all -- a civil design need not have architectural
  program); steel serviceability governed by the vibration claim,
  not strength.
- `tracks/calcite/retaining_wall.calx` -- record-driven geotechnical
  consumption; the `equilibrium(...): stable` stability claim; the
  `trust: >= tested` soil-data floor.
- `flagships/small_office/` -- the flagship: a two-story program with
  a stair, egress, envelope ratings, a moment + braced steel frame
  with a drift claim, a fluorite hydronic loop, and a cuprite panel
  feeder, all as one project. Read `program.calx`, then `frame.calx`,
  then the README's cross-track claim list last; it is the payoff.

## 10. What is deliberately absent

No geometry or BIM/IFC authoring -- grids, levels, and declared
areas/lengths are the entire positional vocabulary; drawing SHEETS
are a derived L6 output, never authored input (reopens only when a
consumer needs coordinated 3D geometry across trades). No
construction scheduling (cost estimation is IN scope via the `mfg`
cost profile machinery; sequencing stays deferred). No rebar or
connection detailing -- transfer classes carry capability envelopes,
not fabrication designs. No solved soil mechanics beyond declared
bearing/frost records. No zoning/site-plan rule packs shipped in v1
(same shape as building codes, jurisdiction data is unbounded). No
duct-network convenience vocabulary yet -- low-velocity air-side HVAC
is expressible today as a fluorite gas-medium subnet.

## 11. Civil-specific vocabulary (learning view)

Normative: `docs/spec/calcite/02-language.md` sec. 11. Everything in
the hematite guide's shared tables ([S]) applies verbatim: claims,
value sources, queries, budgets, waive/policy/override, `interface`/
`mating` contracts. calcite adds:

| keyword | position | purpose |
|---|---|---|
| `site` | top-level | declared civil boundary truth + soil records; one per project root |
| `soil:` | in `site` | record-cited geotech entries |
| `grid` / `level` | top-level | datum families; the only positional vocabulary |
| `space` | top-level | architectural program unit: area, occupancy, boundaries |
| `occupancy:` | in `space` | binds a `std.civil` occupancy record |
| `bounded_by` | in `space` | binds envelope assemblies to the space boundary |
| `adjacent` | top-level | adjacency contract between spaces |
| `access:` | top-level block | opening declarations (edges of circulation nets) |
| `circulation` | top-level | egress net declaration (third AD-23 discipline) |
| `unoccupied` | space marker | terminal-ledger escape for spaces outside egress |
| `member` | top-level | structural element; roles beam/column/brace/slab/wall/footing |
| `section:` | in `member` | value-source slot resolved against shape/capacity tables |
| `structure` | top-level | load-path net declaration (members = nodes, transfers = edges) |
| `support:` | in `structure` | foundation reference nodes |
| `transfers:` | in `structure` | load-transfer edges (mating-shaped connection classes) |
| `unloaded` | member-end marker | terminal-ledger escape |
| `tributary=` | transfer param | declared tributary share; partition-checked |
| `loads:` | top-level block | case magnitudes: boundary truth + pack model refs |
| `assembly` | top-level (calcite) | layered envelope construction (homonym with hematite's system artifact; the setup/hold test passes) |
| `layers:` | in `assembly` | ordered material-record layers |
| `offers:` | in `space` | interface impls the space provides to other tracks |

Everything else -- `require`, `forall`, `budget`, `waive`, `policy:`,
value sources, evidence clauses, `import`, `trust:` -- is [S]
regolith vocabulary, unchanged.
