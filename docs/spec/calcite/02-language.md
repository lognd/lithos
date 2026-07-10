# 02 -- Language (track spec 0.2; elaborated cycle 27 / D139, awaiting ratification; sec. 7 load-kind/station grammar per D194/WO-85, cycle 33)

One sentence: sites and grids anchor the building, spaces carry the
architectural program, structures join members through typed
transfers into a load-path net, envelope assemblies separate inside
from outside with derived ratings, and every claim stays pure
quantity-core vocabulary discharged through the one pipeline.

Everything here is a vocabulary over existing regolith machinery
(the charter's F90 rule): contracts (regolith/04), the AD-23 net
core, budgets (D49), records/registries (regolith/02 sec. 6,
regolith/11), value sources (regolith/03), claims and swept
obligations (regolith/07). Constructs cite their mechanism inline;
nothing below introduces machinery.

## 1. Sites, grids, and levels

The site is declared boundary truth -- the D99 `environment` and
hematite `boundary:` precedents at civil scale. One `site` per
project root; its entries are the only human-asserted physical truth
a building consumes:

```
site Riverside:
    boundary:
        wind_speed:      [0m/s, 51m/s]           by catalog(asce7_fig26)
        ground_snow:     2.4kPa                  by catalog(asce7_fig7)
        seismic_sdc:     D                       by catalog(usgs_2023)
        frost_depth:     1.1m                    by catalog(county_gis)
        climate_zone:    5A                      by catalog(iecc_fig301)
    soil:
        bearing:         [140kPa, 190kPa]        by test(geotech_r2071)
        class:           registry(site_class_d)
```

- Every entry is record- or report-cited (evidence clauses,
  regolith/04 sec. 1); geotech data enters as `by test` records with
  trust tiers, never as solved models (charter sec. 7).
- `boundary:` grammar and interval discipline are unchanged; `soil:`
  is an ordinary record-citing block, not new value-source surface.

**Grids and levels** are datum families (borrow-exempt reference
geometry, the hematite `datum` idea at building scale):

```
grid cols: A, B, C, D spacing 7.2m
grid rows: 1, 2, 3   spacing 6.0m
level ground: 0m
level roof:   4.2m
```

A grid intersection (`(B, 2)`) and a level are addressable datums;
members and spaces locate against them. This is the ONLY positional
vocabulary calcite v1 carries -- enough to give every member a
deterministic length and orientation (03 sec. 4) without geometry
authoring (charter non-goal).

## 2. Spaces

`space` -- the unit of architectural program:

```
space Lobby:
    area:      84m2
    occupancy: registry(a3_assembly)      # std.civil occupancy record
    at:        level(ground)
    bounded_by: ExtWall2hr on [north, west]
```

- `area` is an ordinary interval-valued quantity (design areas
  scatter; a literal is the degenerate interval).
- `occupancy` binds a record from the `std.civil` occupancy tables
  (class, load factor, egress factors) -- registry resolution,
  coherence rules, and trust tiers all unchanged.
- `bounded_by` binds envelope assemblies (sec. 8) to the space's
  boundary -- a contract consumption (the wall PROMISES ratings; the
  space's claims consume them through the promise chain), not
  geometry.
- Derived quantities: `civil.occupant_load(space)` = area x the
  record's load factor -- table-driven arithmetic at L2 (03 sec. 2).

**Adjacency and access are contracts, not geometry** (charter 2a).
Two relation forms:

```
adjacent Lobby, Corridor: shared_boundary(ExtWall1hr)
access:
    lobby_door:  Door(width=915mm, swing=egress)   (Lobby -> Corridor)
    exit_east:   Exit(width=1830mm)                (Corridor -> exterior)
```

`Door`/`Exit`/`Stair`/`Ramp` are opening classes from `std.civil`
(component-class pattern, regolith/02 sec. 6): declared width,
swing, hardware parameters; vendor records bind real door schedules
later. The arrow names the edge's positive egress sense, exactly as
a flownet edge arrow names positive flow sense -- direction of
travel is computed, not asserted.

## 3. Circulation -- the third net discipline

Egress rides the AD-23 net core with a `circulation` discipline
(D139): spaces are nodes, openings are edges, exits are the
reference-reachability targets.

```
circulation Egress:
    reference: exterior                  # the safe-discharge reference
    nodes: Lobby, Corridor, Suite101, Suite102, Stair1
    edges: lobby_door, exit_east, s101_door, s102_door, stair1_doors
```

Net discipline (compile-checked, E0204-E0206 -- 03 sec. 3):

- every occupiable space joins the circulation net or is explicitly
  `unoccupied` (the terminal-ledger escape, `sealed`/`discard`
  analog);
- reference reachability: every space reaches `exterior` through
  edges (an unreachable space is the egress analog of an
  imposer-free subnet);
- edge capacity ledger: every edge carries a width; zero-width or
  undeclared width on a `require`d egress path is a compile
  diagnostic, not a solve failure.

Travel distance, common-path, and dead-end limits are CLAIMS over
this net evaluated at L2 (03 sec. 2); the numeric limits come from
code packs (sec. 9), never the compiler.

## 4. Members and sections

`member` declarations carry the structural role vocabulary (one
word, one idea): `beam`, `column`, `brace`, `slab`, `wall`,
`footing`.

```
member G1: beam
    section:  free                        # capacity tables resolve (L3)
    material: registry(astm_a992)
    from (A, 1) to (D, 1) at level(roof)

member C1: column
    section:  registry(hss152x152x9.5)    # or free / in {...}
    material: registry(astm_a500c)
    from (A, 1, ground) to (A, 1, roof)
```

- `section:` uses the value-source grammar unchanged: a registry
  record (shape tables in `std.civil`/vendor packs), `free` (the
  cheapest code-passing section resolves, cause-pinned -- the L3
  discipline of regolith/03), or a bounded domain
  (`in {W8x, W10x} sections`).
- `material:` is the ordinary materials registry (regolith/02
  sec. 6); concrete/steel/timber/masonry classes and records ship in
  `std.materials`/`std.civil`.
- The grid/level anchors give each member a deterministic length and
  orientation for the frame IR (03 sec. 4). No other geometry
  exists in v1.
- `footing` members bind the site's soil record
  (`bearing: site.soil`); soil stays a record, never a solved model.

## 5. Transfers -- connection contracts between members

A transfer is a `mating`-shaped connection contract (regolith/04
sec. 4, vocabulary unchanged): named sides, `dof:` releases,
`capability:` envelopes. `std.civil` ships the classes:

```
Pinned()          # dof: kept=rotation; shear/axial transfer
Moment()          # dof: kept=none; full fixity
Bearing()         # gravity bearing; kept=rotation+slip
BasePlate(anchors=...)   # column base; capability from anchor records
Roller()          # kept=rotation+translation(1)
```

- `dof: kept=` IS the structural release vocabulary -- a pinned
  connection keeps rotation; the assembly DOF ledger (INV-15) that
  already checks mech matings checks stability here (a mechanism --
  under-constrained frame -- is a ledger error before any solve).
- `capability:` is the transmittable envelope (connection strength
  at worst-case corners), checked demand <= capability like every
  capability in the system.
- Connection strength records (bolt groups, weld groups, anchor
  capacities) are pack content with evidence tiers.

## 6. Structures -- the load-path net

The load path is a NET (charter 2b, AD-23): members and supports are
nodes, load transfer is edges. The declaration mirrors the flownet
shape:

```
structure MainFrame:
    support: F1: footing, F2: footing, F3: footing
    members: G1, C1, C2, C3, RoofDeck
    transfers:
        deck_g1: Bearing()      (RoofDeck -> G1)
        g1_c1:   Pinned()       (G1 -> C1)
        g1_c2:   Pinned()       (G1 -> C2)
        c1_f1:   BasePlate()    (C1 -> F1)
        c2_f2:   BasePlate()    (C2 -> F2)
```

Net discipline (E0207-E0209, the INV-15 ledger over the AD-23 core;
03 sec. 3):

- **support reachability**: every member reaches a `support:` node
  through transfer edges -- an unsupported member is a load LEAK,
  exactly the fluid-net leak shape (charter 2b);
- **terminal ledger**: every member end/bearing surface joins
  exactly one transfer or is explicitly `unloaded`;
- **at least one support per subnet** (the imposer-counting analog);
- the transfer arrow names the edge's positive load-transfer sense;
  actual force direction and magnitude are SOLVED (uplift is a sign,
  not a surprise).

**Tributary loads** enter as declared edge parameters -- v1 keeps
tributary assignment declarative (the D130 declared-flow-paths
precedent): `deck_g1: Bearing(tributary=21m2) (RoofDeck -> G1)`.
A tributary ledger checks the declared shares of each loaded surface
sum to its whole (partition checking, the `zones over` precedent);
mismatch is a compile diagnostic.

## 7. Loads, cases, and combinations

Load MAGNITUDES are boundary/site truth and pack records; load
CASES and COMBINATIONS are pack content (charter sec. 3, the D63
"policy math is pack math" precedent):

```
loads:
    dead:  derived                        # member self-weight + declared dead
    live:  2.4kPa on [Suite101, Suite102] by catalog(asce7_t4)
    plat:  3.5kN/m on [Base]              by catalog(platen_mass)
    hoist: 2kN on [G1@0.5]                by catalog(hoist_class)
    snow:  site.ground_snow -> std.civil.asce7.roof_snow
    wind:  site.wind_speed  -> std.civil.asce7.mwfrs
```

- `derived` self-weight comes from resolved sections x material
  density -- ordinary derivation, lockfile-caused.
- The `->` entries name pack MODELS that turn site truth into member
  loads (roof snow from ground snow; MWFRS pressures from basic wind
  speed) -- signature references, discharged in the harness like
  every `effects:` model.
- Combinations are `forall` domains from the pack:
  `forall combo in std.civil.asce7.strength` sweeps ONE obligation
  over the combination set (swept-obligation machinery, D95 coverage
  encoding, never enumeration into copies).

**Load kind derives from the unit dimension** (D194/WO-85 -- one row
form, no load-kind keyword; dimensions partition, so the dispatch
cannot collide):

| unit dimension | example | lowered kind |
|---|---|---|
| pressure | `2.4kPa` | area load over the target surface member |
| force/length | `3.5kN/m` | LINE load along the target member axis |
| force | `2kN` | POINT load (location required, below) |
| force-length | `5kN-m` | applied MOMENT (location required, below) |

A concentrated (point/moment) load needs a LOCATION: either the
target names a joint/support (the joint IS the location), or a
member target carries a station refinement -- `on [G1@0.5]`, a
normalized fraction 0..1 along the member axis. A force-unit load on
a bare member target is a CONSTRUCTIVE compile diagnostic (E0211)
naming both valid spellings; a station outside 0..1, or one that
does not parse as a number, is the same code. The location is never
inferred, and a row the diagnostic rejects never reaches the frame
payload (a guessed station would fabricate a demand).

## 8. Envelope assemblies

Layered constructions (charter 2c). `assembly <Name>: wall|roof|floor`
declares ordered layers of material records and PROMISES derived
ratings. (Homonym note: hematite's `assembly` is the mech system
artifact; the civil "wall assembly" is immovable domain jargon --
the setup/hold cross-track homonym test passes, argued in the
vocabulary registry, sec. 11.)

```
assembly ExtWall2hr: wall
    layers:
        face:  registry(brick_veneer_90mm)
        gap:   registry(air_gap_25mm)
        ins:   registry(mineral_wool_152mm)
        stud:  registry(steel_stud_92mm_600oc)
        board: 2 x registry(gyp_type_x_16mm)
    promises:
        u_value:     derived                       # layer series sum, L2
        fire_rating: >= 2hr    by catalog(ul_u419)
        stc:         >= 50     by test(ra_tl_2214)
```

- `u_value: derived` is computed at L2 from the layer records'
  conductivities (series resistance; the compliance-extraction
  precedent of fluorite/03 sec. 1) and cited to the record hashes.
- Fire ratings and STC are catalog/test promises (tested assemblies
  are how the real industry works) -- evidence clauses unchanged; a
  derived fire rating would be dishonest and is deliberately not
  offered.
- Spaces and the site boundary consume assemblies through ordinary
  contracts: a corridor requiring 1hr separation holds the demand;
  the bounding assembly's promise discharges it (charter 2c).

## 9. Claims (all existing vocabulary)

The `civil` quantity namespace enters `std.quantities` (D145):
occupancy, occupant_load, travel_distance, common_path, dead_end,
exit_width, exit_capacity, u_value, fire_rating, stc, story_drift,
utilization, bearing_pressure, embedment. Structural physics stays in `mech.*`
(shared namespaces are the cross-domain hook, regolith/02 sec. 1).

```
require Egress:
    travel:   civil.travel_distance(Suite102 -> exterior) <= 76m
    capacity: civil.exit_capacity(level(ground))
                  >= civil.occupant_load(level(ground))
    deadend:  civil.dead_end(Corridor) <= 6.1m

require Structure:
    forall combo in std.civil.asce7.strength:
        strength: civil.utilization(members.all, under=combo) <= 1.0
    deflect:  mech.deflection(G1, under=std.civil.asce7.service)
                  <= G1.span / 360
    drift:    civil.story_drift(level(roof), under=wind) <= 10.5mm
    bearing:  civil.bearing_pressure(F1) <= site.soil.bearing, sf=1.0

require Envelope:
    thermal:  civil.u_value(ExtWall2hr) <= 0.29 W/m2K
    fire:     civil.fire_rating(Corridor.bounded_by.all) >= 1hr

budget FloorArea kind=area:
    members: [Suite101, Suite102, Lobby, Corridor]
    allocate: worst_case
    locked:  Lobby: 84m2
```

- Egress claims evaluate over the circulation net at L2 -- no
  geometry, no solver (the charter's headline payoff).
- `civil.utilization` is the code interaction-ratio claim kind;
  which formula (AISC, Eurocode) is the discharging PACK's identity,
  never the claim's (regolith/07 sec. 1 verbatim).
- `sf=`, `trust: >= tier`, `waive`, `assume!`, `forall`, and the
  budget machinery apply unchanged. Building-code numeric limits
  normally arrive as code-pack RULES (`demand:` over queries,
  AD-21) rather than hand-written claims -- the require blocks above
  are what the rules expand to.

## 10. Cross-track composition (MEP)

MEP is composition, not calcite surface (charter sec. 6; SOPEN-2
import machinery, regolith/10 sec. 3). The building hosts other
tracks through ordinary contracts:

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

- `offers:` entries are interface impls on the space (regolith/04
  sec. 2 -- a space is an artifact; its contract offers mounting,
  drainage, and power boundaries).
- The fluorite loop's pump binds `MechRoom.drain` and `.pad`; the
  cuprite panel binds `.power`; obligation ownership follows the
  declaring system (regolith/10). Boundary subsumption guards the
  envelope both ways (a chiller proven for [5C, 40C] rooms demands
  the mech room's temperature interval be contained).
- Load-bearing penetrations (a duct through a rated wall) are
  contract consumptions too: the opening demands the assembly's
  penetration capability (firestop records) -- demand <= capability,
  nothing new.

## 11. Vocabulary (delta table; homonyms argued)

| keyword | position | purpose |
|---|---|---|
| `site` | top-level | declared civil boundary truth + soil records; one per project root |
| `soil:` | in `site` | record-cited geotech entries |
| `grid` / `level` | top-level | datum families; the only positional vocabulary (sec. 1) |
| `space` | top-level | architectural program unit: area, occupancy, boundaries |
| `occupancy:` | in `space` | binds a `std.civil` occupancy record |
| `bounded_by` | in `space` | binds envelope assemblies to the space boundary |
| `adjacent` | top-level | adjacency contract between spaces |
| `access:` | top-level block | opening declarations (edges of circulation nets) |
| `circulation` | top-level | egress net declaration (AD-23 discipline #3) |
| `unoccupied` | space marker | terminal-ledger escape for spaces outside egress |
| `member` | top-level | structural element; roles beam/column/brace/slab/wall/footing |
| `section:` | in `member` | value-source slot resolved against shape/capacity tables |
| `structure` | top-level | load-path net declaration (members = nodes, transfers = edges) |
| `support:` | in `structure` | foundation reference nodes |
| `transfers:` | in `structure` | load-transfer edges (mating-shaped connection classes) |
| `unloaded` | member-end marker | terminal-ledger escape |
| `tributary=` | transfer param | declared tributary share; partition-checked |
| `loads:` | top-level block | case magnitudes: boundary truth + pack model refs |
| `assembly` | top-level (calcite) | layered envelope construction. HOMONYM with hematite's system artifact: both immovable jargon, neither [S]; the setup/hold test passes |
| `layers:` | in `assembly` | ordered material-record layers |
| `offers:` | in `space` | interface impls the space provides to other tracks |

Everything else -- `require`, `forall`, `budget`, `waive`, `policy:`,
value sources, evidence clauses, `import`, `trust:` -- is [S]
regolith vocabulary, verbatim. No retired word is revived; no near
collision is introduced (checked against hematite/04 secs. 4-5 and
the cuprite/08 + fluorite track vocabularies; `level` in cuprite is
prose only, never a keyword).
