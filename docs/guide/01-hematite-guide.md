# The hematite guide (mechanical design)

hematite describes manufactured mechanical artifacts: what they are
made of, how they are made, what they promise, and what must be true
of them. This guide walks the language bottom-up, then gives the
complete vocabulary. Normative sources: `docs/hematite/02-language.md`
(the language), `docs/hematite/04-vocabulary.md` (every keyword),
`docs/regolith/` (everything shared with cuprite).

## 1. The core idea

A hematite part is not a solid model you sculpt -- it is a
**manufacturing pipeline with contracts**. You declare stages
(laser-cut, press-brake, mill), features within stages, interfaces
the part implements, and claims that must hold. Geometry is an
OUTPUT (realized at build time), not the input.

Three sentence summary of the whole language: **blocks declare,
sources resolve, claims prove.** Every construct is exactly one of:
a declaration (structure), a value source (who decides a number), a
claim (what must be true), or a selector (which entities).

## 2. Profiles (2D sketches, done differently)

A `profile` is a 2D constraint system serialized as a **walk** --
the topology written as a path, with the metric constraints separate:

```
profile BracketFlat:
    walk:
        from left_edge
        line right                 # a
        line up                    # b
        line left                  # c
        close                      # d
    hole wire_pass:
        circle(dia 8mm)
    constraints:
        a.length = 80mm
        b.length = 50mm
        wire_pass.center to a = 32mm
    regions:
        flange_band: between(c, c.offset(12mm))
        web:         interior - flange_band - holes
    exports:
        mid_plane: datum
```

- The walk pins every discrete branch (direction words like `right`,
  `bulge=left` on arcs, `tangent` joins) so the sketch has ONE
  topology; constraints then pin the metrics. Under- and
  over-constraint are compile diagnostics (the DOF ledger).
- `regions:` names areas features can consume; `exports:` publishes
  datums. No freehand splines -- curves come from `from_table()` /
  `from_fn()`.

## 3. Parts and stages

```
part SensorBracket:
    material: AISI_304

    stage cut: process=laser_cut(sheet=1.5mm)
        then:
            blank  = Blank(BracketFlat)
            mounts = PatternOf<Pierce<circle(dia 4.5mm)>>(n=4,
                         grid(2, 2, 56mm x 30mm),
                         frame=blank.mid_plane.offset(y=8mm))

    stage formed: process=press_brake, from=cut
        flange = Bend(edge=cut.blank.top_edge, angle=90deg, radius=free)
```

- `stage <name>: process=<pack>(...)` binds one process step;
  `from=` chains stages. The process pack brings capability limits
  and DFM rules with it.
- Inside a stage, `then:` opens a concurrent scope (features read a
  snapshot, commit together); `seq:` is the sequential sugar. Bare
  statements are their own scope.
- Machining stages contain `setup` blocks (`hold:` the fixtured
  geometry, `flip about <axis>` to re-fixture); omitted setups are
  planner-allocated.
- Multi-piece parts (weldments) use `pieces:` with per-piece
  materials and joining stages with `joins=[...]`.
- Discrete externally-chosen configurations use
  `variant <name>: {a, b}` with `when <variant> = <v>` guards; every
  variant is verified.

**Ownership is real.** A feature that consumed a face owns it; a
later feature touching it is a borrow conflict (a compile error, not
a surprise at regen). Cross-stage references are qualified
(`cut.blank.top_edge`); `rebind()` re-evaluates after an intervening
modifier; datums (`.as_datum()`) are borrow-exempt reference geometry.

**Queries, never indices.** Entities are addressed semantically:

```
faces.where(normal=+z).only
holes.where(dia < 5mm).all
edges.nearest(mid_plane)
at_intersection(boss, web)      # explicit cross-ownership join
```

`.only` asserts exactly one match (over/under-match is E0301);
`.all` takes the set; `.any` says any member is acceptable
(orbit-checked). Numeric indices do not exist.

## 4. Interfaces, impls, matings

An `interface` is a contract: a reference frame, named geometric
roles, tolerance demands, and promise slots:

```
interface SensorPad:
    frame:
        origin: pad.center
        z: pad.normal
    roles:
        pad: planar, rect(>= 20mm x 20mm)
    tolerances:
        pad: flatness(0.2mm)
    loads:
        static: <= 12N
        structure: static
```

A part binds geometry to the roles with `impl`:

```
impl SensorPad for self:
    pad = formed.flange.face
```

The binding is a permanent borrow; `= todo!` defers the conformance
PROOF (release-gated) while keeping the contract concrete. `refines`
narrows an interface one-way -- the only inheritance-like mechanism.

A `mating` is a connection contract between named sides: `align:`
(frame coincidence -- the only positioning mechanism), `fit:` (ISO
286 designations, capability-checked), `dof:` (`removed=`/`kept=`
freedoms feeding the assembly ledger), `preload:`, `effects:`
(declared physics via `model<sig>(...)`), `capability:`, and its own
`require` groups.

## 5. Assemblies

```
assembly SensorMount:
    parts:
        bracket: SensorBracket
        rails:   4 x Rail
    boundary:
        ambient: [-20degC, 60degC]
        event drop: shock(50g, 11ms, half_sine)
    connect:
        mount: PadMate(a=bracket, b=sensor) exposing align.theta
    budget alignment: kind=tolerance
        members: [bracket, rails.all]
        allocate: worst_case
    require Survival:
        shock: peak(mech.stress, during drop) < material.sigma_y, sf=1.5
```

- `boundary:` is the ONLY place a human asserts physical truth
  (loads, temperatures, life, spectra). Parts have no boundary;
  standalone parts take loads from `interface_envelope(<I>)`.
- `budget` blocks allocate a shared quantity across `members:` with
  a policy; `locked:` fixes individual entries by hand.
- `n x thing` forms orbits; `pairwise(a_set, b_set) by <Mating>`
  zips equal-cardinality sets into per-pair connections.
- `redundant(<dof>)` declares static indeterminacy explicitly.

## 6. Claims

Claims live in named `require` groups on parts, matings, and
assemblies. The full shared claim system (windows, events, masks,
`forall`, safety factors) is regolith vocabulary -- see the tables
below and `docs/regolith/07-claims-and-evidence.md`. Mech-specific
claim forms worth knowing by name: `mech.life`/`mech.damage`
(fatigue, `scatter_factor=`), `mech.weld_stress`,
`equilibrium(...): stable`, `manufacturable(stage)`, and the `mfg.*`
namespace (`unit_cost`, `cycle_time`, `lead_time`).

Honest-deferral ladder (shared): `assume!(expr, basis=...)` accepts a
claim without evidence; `todo!` defers an impl's proof;
`waive <target> [on <scope>]: basis: ...` accepts a specific failed
result. All three are ledgered and release-gated; none can turn
violated into discharged.

## 7. The complete vocabulary (learning view)

Normative source: `docs/hematite/04-vocabulary.md` -- the spec wins
on any disagreement. `[S]` = regolith-shared with cuprite.

### Registries (shared foundations)

| keyword | purpose |
|---|---|
| `namespace` [S] / `quantity` [S] | typed physical quantities (`mech.stress: Pa`) |
| `zones(...)` [S] | zone-indexed field values |
| `class` [S] / `properties:` [S] | material class hierarchy + property schema |
| `material` | concrete material: `f(T)` intervals, `condition(...)`, fatigue data |
| `contact { A, B }` [S] | unordered-pair properties (friction, conductance) |
| `process` [S] / `capability:` [S] | manufacturing module: capability table + DFM rules |
| `signature` [S] / `impl <sig> by` [S] | physics model contracts and implementations |

### Sketch layer

| keyword | purpose |
|---|---|
| `profile` / `walk:` / `from <datum>` | 2D constraint system; topology as a walk |
| `line`, `arc`, `tangent`, `perpendicular`, `bulge=left/right` | walk entities, joins, branch pins |
| `close [via axis]` | loop closure; revolve centerline |
| `hole <name>:` / `regions:` / `constraints:` / `exports:` | inner loops, named areas, metrics, published datums |
| `from_table()`, `from_fn()` | data-/math-defined curves |

### Part layer

| keyword | purpose |
|---|---|
| `import <pkg-or-path> (<names>)` [S] | bring declarations into scope (cross-language too) |
| `part` / `material:` | a manufactured component |
| `pieces:` / `joins=[...]` | weldments: per-piece stock and joining |
| `variant <name>: {a, b}` / `when <v> = <x>` | discrete config axes; guarded construction |
| `stage` [S] / `from=` / `sealed` [S] | process steps; import sealing |
| `setup` / `hold:` / `flip about` | workholding states |
| `then [label] [on <region>]:` [S] / `seq:` [S] | concurrent scope / sequential sugar |
| `datum` [S] / `.as_datum()` | borrow-exempt reference geometry |
| `impl <Interface> for <Part>` [S] / `todo!` | role binding; deferred proof |
| `merge(a before b / a over b)` [S] / `rebind()` [S] | overlap ordering; re-borrow |
| `sequence: a before b` [S] / `plan:` | pinned manufacturing order; supplied plan |

### Contract layer

| keyword | purpose |
|---|---|
| `interface` [S] / `frame:` / `roles:` / `tolerances:` | contract, its frame, slots, GD&T demands |
| `loads:` / `stiffness:` / `thermal:` + `structure:` [S] | promise slots + time structure |
| `refines` [S] | one-way contract narrowing |
| `mating` / `align:` [S] / `fit:` / `dof:` (`removed=`/`kept=`) | connection contract |
| `couples:` [S] / `preload:` [S] / `effects:` [S] / `capability:` [S] | kinematics, internal state, physics, envelope |

### Assembly layer

| keyword | purpose |
|---|---|
| `assembly` / `parts:` [S] / `vendor()` [S] | the system and its part bindings |
| `boundary:` [S] | THE human-asserted physical truth |
| `connect:` [S] / `exposing` [S] / `redundant(<dof>)` / `lubrication:` | connection instances |
| `budget` [S] / `members:` / `allocate:` / `locked:` | cross-part allocation |
| `zones over <set>:` / `remainder` | named partitions of entity sets |
| `target <name> of <system>` [S] / `reserves:` / `draws:` [S] | additive overlays and set-asides |

### Claims and evidence (all [S])

| form | purpose |
|---|---|
| `require <Group>:` | named claim group |
| `forall <cfg> [in <domain>]:` | quantify over a config domain |
| `sf=` / `scatter_factor=` | safety multiplier; fatigue scatter divisor |
| `@hint(...)` | droppable guidance (never load-bearing) |
| `all` | the full subject domain (`mech.mass(all)`) |
| `during` / `within .. after` / `until` | time windows over events |
| `peak`, `settles`, `overshoot`, `rms(band=)`, `stays_within(mask)` | transient/frequency claim forms |
| `event` / `mask` | named time datums; piecewise envelopes |
| `equilibrium(...): stable` | stability claim |
| `manufacturable(stage)` / `mfg.*` | planning claims |
| `trust: >= <tier>` | evidence-tier floor |
| `assume!(expr, basis=)` / `todo!` / `waive ... basis:` | the honest-deferral ladder |
| `by analysis / catalog(ref) / test(ref)` | evidence provenance |
| `model=<impl>` | pin the discharge model (cannot forge a pass) |

### Value sources (all [S]; every numeric slot)

| form | meaning |
|---|---|
| literal (`5mm`, `>= 80kN/mm`, `3.3V +- 5%`) | asserted truth (comparators are one-sided literals) |
| `within [lo, hi]` | demanded two-sided window (infix in claims) |
| `in [lo, hi] [minimize/maximize]` | bounded freedom; optimizer decides |
| `free` | process-rule (DFM/DRC) minimum decides |
| `derived [(sf=k)]` | consequence of system analysis; lockfile-pinned |
| `allocated [(policy)]` | share of a budget / planner output |

### Queries and selectors

| form | purpose |
|---|---|
| `.where(pred, ...)` | filter |
| `.all` / `.only` / `.any` | cardinality intents |
| `.nearest(datum)` | semantic addressing (never positional) |
| `at_intersection(a, b)`, `&` | explicit cross-ownership joins |
| `.cavity(inlet=...)` | derived void entity |
| `pairwise(a, b) [by <Mating>]` [S] / `n x thing` [S] | orbit zip; count constructor |
| `[a, b]` vs `[i .. j]` [S] | closed interval vs half-open positional range |

### Coherence, override, policy (all [S])

| form | purpose |
|---|---|
| `override <record> by <evidence>` | shadow a registry record (evidence mandatory) |
| `use { A, B }` / `use <impl>` | pin an ambiguous resolution |
| `policy:` with `prefer x [over y]` / `forbid x` / `minimize <global>` | allocation preferences and global objectives |
| `extern(<ref>, <format>)` | foreign content, checked against contract, never merged |

### Retired words (do not write these)

`pairs`, `var()`, `rated()`, `promised()`, `with`, `scope:`,
`verify-only`, `generates:`, `state_requirements:`, `environment:`,
`fix:`, `margin=` (as multiplier), `requires` (in classes),
`domain_decl`, bracket query sugar, `==` on continuous quantities,
positional mating sides, `.original`/`.current`, freehand splines,
numeric entity indices, `pins:`, `locked()`, `dof: free=`,
`preload_at:`, `minimize(<arg>)`/`maximize(<arg>)`, `@ <value>`
point-conditions, `artifact("path", Name)`. (Full list with reasons:
hematite/04 sec. 4.)

## 8. Reading diagnostics

Families you will meet (normative: regolith/09): E01xx quantity/type
(the `==` ban is E0102), E03xx queries (`.only` mismatch E0301,
borrow conflicts E0302), E04xx contracts/ledgers (boundary
subsumption E0407, over-allocation E0432), E05xx
generics/orbits, E06xx DFM/DRC rule violations, E07xx waivers
(stale E0701, basis-less E0702). Every code is stable and
`regolith explain <code>` is the planned lookup (DESIGNED).
