# hematite Vocabulary Reference

> Spec 0.14, from the 0.3 vocabulary pass. Every block and keyword: where
> it is legal, what it means, what it lowers to. One construct per idea;
> overloads permitted only where the underlying idea is fundamentally
> identical (section 5 registry). Keywords marked **[S]** are regolith
> vocabulary shared verbatim with the elec track; unmarked ones are
> mech-specific.

## 1. Vocabulary principles

1. **One word, one idea.** A keyword may appear in multiple positions
   only if it means the same thing in all of them. Near-collisions in
   spelling (`fit`/`fix`) are bugs even when meanings differ.
2. **Blocks declare, sources resolve, claims prove.** Every construct is
   exactly one of: declaration (structure), value source (who decides a
   number), claim (what must be true), selector (which entities).
3. **Human words at human boundaries.** Frequently-typed words are short
   and read aloud (`then`, `hold`, `free`); rare load-bearing ones may be
   long (`scatter_factor`).
4. **ASCII canonical, unicode pretty.** `&`, `dia`, `+-`, `deg`, `mu_`
   are canonical; formatters may render unicode; files never store it.
5. **Cross-track homonym policy** (cycle 1). Keywords are per-track;
   [S] words are global. A track must not adopt a keyword that is
   domain jargon *meaning something else in that track* (elec could
   never use `pins:` for budgets). Homonyms across tracks are
   acceptable iff each side is immovable jargon in its own domain and
   neither is [S] -- `setup`/`hold:` (workholding) vs setup/hold
   (timing field names) pass this test.

## 2. The vocabulary

### A. Shared registries (quantity core; neither compiler nor harness owns them)

| keyword | position | purpose |
|---|---|---|
| `namespace` [S] | top-level | groups physical quantities (`mech`, `thermo`, `geom`) |
| `quantity` [S] | in `namespace` | typed physical quantity: unit, tensor rank; interval- and zone-valuable |
| `zones(...)` [S] | quantity values | zone-indexed field value; zone boundaries are datums |
| `class` [S] | top-level | material class hierarchy node (`steel: metal`) |
| `properties:` [S] | in `class` | property schema class members must provide |
| `material` | top-level | concrete material: `f(T)` interval properties, `condition(...)` variants, fatigue data with provenance |
| `contact { A, B }` [S] | top-level | unordered-pair property record (friction, conductance, wear); specificity-resolved |
| `process` [S] | top-level | manufacturing process module: `capability:` table and `dfm:`/`drc:`/`erc:` rule packs (`02-language.md` sec. 10; the elec blocks live in cuprite) |
| `capability:` [S] | in `process`, in `mating` | provider envelope, checked demand <= capability |
| `signature` [S] | top-level | physics model contract: `inputs:`, `outputs:`, `domain:` -- the compiler/harness linker symbol |
| `impl <sig> by <name>` [S] | harness packs | a model implementing a signature: cost, error model, `domain:` |

### B. Sketch layer

| keyword | position | purpose |
|---|---|---|
| `profile` | top-level / in part | a 2D constraint system; a value (borrow-exempt), not topology |
| `walk:` | in `profile` | topology serialization: entity sequence + all discrete branch pins |
| `from <datum>` | first walk statement | the walk's start anchor |
| `line`, `arc` | in `walk` | entities; direction words (`down`, `angled`) are uniqueness-checked hints |
| `tangent`, `perpendicular` | joins | join-condition pins |
| `bulge=left/right` | on `arc` | branch pin, chord-wise in the +normal view |
| `close [via axis]` | last walk statement | closes the loop; `via axis` marks revolve centerline |
| `hole <name>:` | in `profile` | named inner loop (one nesting level) |
| `regions:` | in `profile` | named area expressions consumable by features |
| `constraints:` | in `profile` | the metric layer: orderless constraints |
| `exports:` | in `profile` | datums and named sub-entities published |
| `from_table()`, `from_fn()` | curve sources | data-/math-defined curves; no freehand splines |

### C. Part layer

| keyword | position | purpose |
|---|---|---|
| `import <pkg-or-path> (<names>)` [S] | file top | brings declarations into scope: package names or quoted source paths, including cross-language files (`import "board.cupr" (Pcb)` -- extension selects the front-end); the name list is optional on package imports (a bare `import std.intents` loads registry contributions, resolved by coherence) and mandatory on path imports (regolith `11` sec. 9); registered overload with the data-level `import(path)` stage |
| `part` | top-level | a manufactured component: material + stage pipeline + impls + claims |
| `material:` | in `part`; on `pieces:` entries | binds a registry material |
| `pieces:` | in `part` | named stocks / part refs / imports, each with its own material; makes the part a multi-piece artifact (weldment) |
| `joins=[...]` | on joining stages | the pieces a joining process consumes; placement via mating-style `align:` |
| `variant <name>: {a, b}` | in `part` | externally-chosen discrete config axis; all variants verify; per-variant lockfile sections |
| `when <variant> = <v>` | statement guard | construction branch taken only in the named variant |
| `stage` [S] | in `part` | one process step: `process=`, `from=<stage>`, or `import(path) [sealed]` |
| `sealed` [S] | on import stage | no later stage may modify this geometry |
| `setup` | in machining stages | a workholding state: `hold:`, datum letters, ordered; omitted setups are planner-`allocated` |
| `hold:` | in `setup` | the gripped/fixtured geometry |
| `flip about <axis>` | in `setup` | re-fixturing transform; injects refixture tolerance from capability |
| `then [label] [on <region>]:` [S] | in stage/setup | concurrent scope; snapshot reads; commit at end; guard restricts selection and defaults placement |
| `seq:` [S] | in stage/setup | sequential sugar: each statement its own commit |
| `datum` [S] | in part / assembly; letters in `setup` | immutable reference geometry; borrow-exempt; capturable by query from measured import geometry; setup letters bind GD&T frames to fixturing |
| `impl <Interface> for <Part>` [S] | in part | binds roles to geometry; permanent borrow; `= todo!` defers proof only |
| `merge(a before b / a over b)` [S] | scope commit | explicit ordering/ownership for overlapping same-scope features |
| `rebind()` [S] | feature arg | re-evaluates a borrow after an intervening modifier |
| `sequence: a before b` [S] | in stage | pins manufacturing order otherwise planner-`allocated` |

### D. Contract layer

| keyword | position | purpose |
|---|---|---|
| `interface` [S] | top-level | a contract: `frame:`, `roles:`, `tolerances:`, promise slots |
| `frame:` [S] | in `interface` | the reference frame all contract content is expressed in; undeclared axes declare symmetry |
| `roles:` [S] | in `interface` | named geometric slots with predicates |
| `tolerances:` | in `interface` | GD&T demands on roles relative to the frame, incl. `Ra` |
| `loads:` / `stiffness:` / `thermal:` | in `interface` | promise slots; values use the source grammar |
| `structure:` [S] | on loads | time structure: `static` / `alternating(R=, f=)` / `spectrum(ref)` |
| `refines` [S] | interface header | narrows a contract; one-way substitutable; the only inheritance-like mechanism |
| `mating` | top-level | connection contract between named sides |
| `align:` [S] | in `mating` | frame-coincidence rules; the only positioning mechanism |
| `fit:` | in `mating` / connection | ISO fit designation; expands to interval deviations; capability-checked |
| `dof:` | in `mating` | `removed=` / `kept=` rigid-body freedoms; feeds the assembly ledger (`kept=`, not `free=` -- `free` is a value source) |
| `couples:` [S] | in `mating` | kinematic coupling between config variables |
| `preload:` [S] | in `mating` | internal load state with method-scatter interval |
| `effects:` [S] | in `mating` | declared physics: `model<sig>(inputs)` with `applies ->` routing |
| `capability:` [S] | in `mating` | transmittable envelope at worst-case corners |
| `require <Group>:` [S] | in `mating` | connection-state claims against signature outputs |

### E. Assembly layer

| keyword | position | purpose |
|---|---|---|
| `assembly` | top-level | the system: parts, connections, boundary truth, claims, budgets |
| `parts:` [S] | in `assembly` | part bindings: native, `import(...)`, `vendor(...)` |
| `vendor()` [S] | parts entry | interface bundle with catalog evidence; internals never modeled |
| `boundary:` [S] | in `assembly` | the only human-asserted physical truth: loads, pressures, temperatures (ambient and zoned), design life, spectra; entries may carry `at=<datum>` application points |
| `connect:` [S] | in `assembly` | named connection instances: `name: Mating(a=..., b=...)` |
| `exposing` [S] | on connection | publishes a config variable, namespaced as `name.var` |
| `redundant(<dof>)` | on connection | declared static indeterminacy; routes through compliance solve; couples tolerance misfit into loads |
| `lubrication:` | on connection | contact state selecting fields in the resolved `contact` record |
| `budget` [S] | in `assembly` | named cross-part allocation scope: `kind=`, `members:`, `allocate:`, `locked:` |
| `members:` [S] | in `budget` | the explicit blast radius |
| `allocate:` [S] | in `budget` | allocation policy (`cost_optimal`; `worst_case`/`rss` math) |
| `locked:` [S] | in `budget` | human-fixed values within an allocated set (the lock family; replaces `pins:`/`locked()`) |

### F. Claims and evidence (all [S])

| keyword | position | purpose |
|---|---|---|
| `require <Group>:` | part, assembly, mating | named group of claims; claims individually nameable for ledgers/waivers |
| `forall <cfg> [in <domain>]:` | claim prefix; rule quantifier | quantifies over a declared domain: a configuration domain in claims, an entity-query domain in rule packs (`forall <var> in <query>`, `02-language.md` sec. 10) |
| `equilibrium(...): stable` | claim form | potential-energy stability claim |
| `sf=` | claims, `derived()` | multiplicative safety factor |
| `scatter_factor=` | fatigue claims | life-scatter divisor |
| `@hint(...)` | on claims | droppable verification hints (symmetry, regime) |
| `all` | claim subjects | the FULL subject domain of the claim form (`mech.mass(all)` = every part; `info.utilization(all)` = every executor); one idea with the `.all` cardinality intent; `all_parts` retired (D59) |
| `assume!(expr, basis=)` | claim position | accepts a claim without evidence; ledgered; release-gated |
| `todo!` | impl position | defers conformance proof; contract stays concrete; ledgered; release-gated |
| `by analysis / catalog(ref) / test(ref)` | promises, overrides | evidence provenance |

### G. Value sources (all [S]; every numeric slot, everywhere)

| form | meaning |
|---|---|
| literal (`5mm`, `25bar`, `>= 80kN/mm`) | the human knows it; comparators are one-sided literals |
| `within [lo, hi]` | two-sided comparator literal: a demanded window (flexure stiffness, oscillator band); distinct from `[lo, hi]` interval values. In claim position it is an **infix comparator** like `<` (`mech.backlash(mesh) within [0.05mm, 0.15mm]` -- never `= within`, which would overload discrete `=`; D42) |
| `in [lo, hi] [minimize/maximize]` | bounded freedom; optimizer decides; integer domains monomorphize |
| `free` | the DFM minimum-legal value decides |
| `derived [(sf=k)]` | consequence of assembly statics over config/boundary corners; lockfile-pinned; re-derived only by explicit `hematite update --contracts` |
| `allocated [(policy)]` | share of a declared budget or planner output |

### H. Queries and selectors (all [S] except `.cavity`)

| form | purpose |
|---|---|
| `.where(pred, ...)` | filter by predicates |
| `.all` / `.only` / `.any` | cardinality intents |
| `.nearest(datum)` etc. | semantic instance addressing; never positional |
| `at_intersection(a, b)`, `&` | explicit cross-ownership joins |
| `.cavity(inlet=...)` | derived void entity: `wetted_faces`, `volume`, `min_section` |
| `.as_datum()` | captures reference geometry out of the borrow system |
| `pairwise(a_set, b_set) [by <Mating>]` [S] | orbit zip: element-wise connection of equal-cardinality sets in shared layout order; `by` instantiates one mating per pair (regolith `04` sec. 4; lifted from elec-only in cycle 6, D53) |
| `n x thing` on `parts:`/instances [S] | count constructor forms part/component orbits (`rails: 4 x Rail`); members are entities per regolith `02` sec. 3 |

### I2. Added in 0.5 (seam resolutions, time domain, targets, planning)

| keyword | position | purpose |
|---|---|---|
| `refining` | feature-class property | geometry-class-preserving, tolerance-tightening op (Ream, Polish, Grind); composes into role bindings within the finishing stage |
| `zones over <set>:` | in `part` / `interface` | named partition of an entity set; `remainder` = complement; boundaries become datums |
| `event` [S] | boundary / derived | named time datum (`drop`, `supply.on`, `theta.crosses(...)`) |
| `during` / `within .. after` / `until` [S] | claim modifiers | time windows over events and config domains |
| `mask` [S] | registry object | piecewise envelope (SRS, vibration profile); claim form `stays_within(x, mask)` |
| `peak`, `settles`, `overshoot`, `rms(band=)` [S] | claim forms | transient and frequency-domain claims |
| `structure: transient(ref)` [S] | on loads | explicit time-profile load structure |
| `manufacturable(stage)` | claim form | discharged by DFM rules (cheap) or CAM planner (expensive); plan = evidence |
| `mfg.*` [S] | quantity namespace | unit_cost, cycle_time, lead_time |
| `spec:` [S] | in contracts | behavioral specification; conformance = equivalence obligation (light mech use) |
| `target <name> of <system>` [S] | top-level | additive overlay (debug/fixturing); may only add; consumes reserves |
| `reserves:` / `draws: reserves` [S] | system / target | declared set-asides (mass, volume, spare stock) targets may consume |
| `trust: >= <tier>` [S] | in `require` | evidence-tier floor for the claims in the group |

### I3. Added in 0.6 (cycle 1: examples-driven)

| keyword | position | purpose |
|---|---|---|
| `pieces:` / `joins=` | part / joining stage | multi-piece parts (weldments); see section C |
| `variant` / `when =` | part / statements | externally-chosen discrete axes; see section C |
| `within [lo, hi]` [S] | value slots | two-sided comparator literal |
| `[i .. j]` [S] | buses, address maps | half-open positional range; semantic positions only (regolith `02` sec. 3) |
| `n x thing` [S] | counts | count constructor (`2 x AA_alkaline`) |
| `mech.life`, `mech.damage` | claim forms | fatigue life/damage claims (`under=<spectrum>`, `scatter_factor=`); resolves OPEN-4 spelling |
| `mech.weld_stress` | claim form | weld joint claims on `weld` entities (`welded.welds.all`); taxonomy 0.7, models 0.8 via `std.mech.weld` (02-language sec. 7a; OPEN-13 closed) |
| `interface_envelope(<I>)` [S] | claim `under=` | loads from an interface's promises; the standalone-part load source |

### I4. Added in 0.8 (cycle 3: the expert ladder + linkage)

| keyword | position | purpose |
|---|---|---|
| `waive <target> [on <scope>]:` [S] | part / assembly / system | in-source acceptance of a violated/indeterminate claim or rule; `basis:` mandatory; `by <evidence>` upgrades it to a release-permitted deviation (regolith `12` sec. 3) |
| `basis:` [S] | in `waive`; arg of `assume!` | the human reason; ledgered, diff-reviewable |
| `policy:` [S] | assembly / system / budget | `prefer x [over y]` (soft ordering), `forbid x` (hard domain cut), `minimize <global>` (lexicographic global objectives; resolved SOPEN-4) |
| `prefer` / `forbid` [S] | in `policy:` | soft preference / hard exclusion over allocation candidates |
| `locked:` [S] | assembly / system / board (beyond budgets) | free-standing lock-family block for planner decisions (fits, pinmux, hosting) |
| `model=<impl>` [S] | on any claim | rung 5: pin the discharge model; margin math unchanged, cannot forge a pass |
| `extern(<ref>, <format>)` [S] | impl strategy (`by extern`), `profile`, `plan:`, `image` | external linkage: foreign content checked against the contract, never merged (regolith `08` sec. 4) |
| `plan:` | in stage / setup | attach a supplied manufacturing plan (`extern(...)`), planner-checked, evidence-dischargeable |

### I5. Added in 0.14 (cycle 18: rule packs; `02-language.md` sec. 10)

| keyword | position | purpose |
|---|---|---|
| `dfm:` [S] | in `process` | the mech rule-pack block; one `rule` per checklist line (elec mirrors with `drc:`/`erc:` -- cuprite `04` sec. 4, `07` sec. A2) |
| `rule <name>:` [S] | in `dfm:`/`drc:`/`erc:` | one named, citable rule: the name is what `waive dfm(<pack>.<name>)`, lockfile causes, and E06xx provenance cite |
| `forall <var> in <query>` [S] | first rule line | the rule's match domain: the settled claim quantifier extended with an entity query as the domain |
| `demand: <expr>` [S] | in `rule` | the claim that must hold for every match; error severity, release-gated; aggregates and record dereference are ordinary expression forms |
| `advise: <expr>` [S] | in `rule` (in place of `demand:`) | warning severity: rendered, verdict-inert, never an obligation, never release-gated |
| `resolves: <field> from free` [S] | in `rule` | marks the rule as the eager resolver of a `free` slot; pins `cause: dfm(<pack>.<rule>)` (regolith `03`) |
| `per: "<source>"` [S] | in `rule` | the citation (handbook, IPC table, shop data); renders in the diagnostic |
| `why: "<reason>"` [S] | in `rule` | the one-line physical reason; IS the diagnostic's explanation text |
| `expect:` / `pass:` / `fail:` [S] | in `rule` | in-pack fixtures that must hold; a rule without both a pass and a fail case is a lint warning |

### I. Coherence and override (all [S])

| keyword | purpose |
|---|---|
| `override <record> by <evidence>` | shadows a registry record at the same key; evidence mandatory |
| `use { A, B }` / `use <impl>` | pins resolution on specificity/impl ambiguity (`model=<impl>` is this pin) |

### J. Build and lifecycle (CLI, not source; all [S])

`check` / `build` / `optimize` / `--release` /
`--waive <Group.claim>` (exploratory only -- never persists; durable
acceptance is the in-source `waive`, regolith `12`) /
`update --contracts` / lockfile causes (`dfm`, `budget:<name>`,
`topology`, `obligation:<id>`, `planner`, `extern:<ref>`,
`derived(intent ..)`).

## 3. Adopted changes (0.2 -> 0.4, consolidated)

From the syntax audit (FIX) and vocabulary pass (V), all adopted:

| id | change |
|---|---|
| FIX-1 | unified value-source grammar; `var()`/`rated()`/`promised()` deleted |
| FIX-2 | mating sides are named (`between: a:, b:`); `symmetric()` waiver |
| FIX-3 | method-chain queries canonical; bracket sugar deleted |
| FIX-4 | `with` deleted; scopes gained labels + region guards |
| FIX-5 | every block is `then:`; `scope:` deleted |
| FIX-6 | bare names in-stage; qualifiers cross-stage and in impls |
| FIX-7 | config variables namespaced by connection (`pivot.theta`) |
| FIX-8 | claims nameable; ledgers/waivers cite names |
| FIX-9 | ASCII canonical operators |
| FIX-10 | every import is a stage; `verify-only` deleted |
| V1 | `environment:` deleted; ambient conditions live in `boundary:` |
| V2 | `state_requirements:` deleted; matings use `require <Group>:` |
| V3 | setup `fix:` -> `hold:` |
| V4 | safety multiplier is `sf=` everywhere; `margin` = evidence distance only |
| V5 | class member list `requires` -> `properties:` |
| V6 | `domain_decl` -> `domain:` everywhere (signatures, impls, rules) |
| V7 | mating `generates:` -> `effects:` with `model<sig>` refs and `applies ->` routing |
| V8 | inside `then L on R:`, feature `on=` defaults to R |

## 4. Retired vocabulary (do not reintroduce)

`pairs` - `var()` - `rated()` - `promised()` - `with` - `scope:` -
`verify-only` - `generates:` - `state_requirements:` - `environment:` -
`fix:` - `margin=` (as multiplier) - `requires` (in classes) -
`domain_decl` - bracket query sugar `[...]` (bus/address ranges
`[i .. j]` are a distinct, blessed form) - `==` on continuous
quantities - positional mating sides - `.original`/`.current` - freehand
splines - numeric entity indices - `pins:` (budgets; now `locked:`) -
`locked()` (wrapper form; now `locked:` entries) - `dof: free=`
(now `kept=`) - `preload_at:` (never spec'd; `preload: at <cfg>=<v>`) -
`minimize(<arg>)` / `maximize(<arg>)` (directions take no arguments;
SOPEN-4) - `@ <value>` claim point-conditions (corner discipline owns
worst-case evaluation; `@` survives only in `@hint`) -
`artifact("path", Name)` (cross-language reference is the ordinary
`import`). Retired PROJECT names (not statement vocabulary, listed
here as the one retired-names registry): `mill`/`loom`/`dcad`/`deda`
(pre-D81 language names), `quarry`/`lodestone` (pre-D132 package
tool/registry names; now **magnetite**), and calcite's draft use as
the fluid track's name with `.calc` (D93; the civil track, D133,
uses `.calx`).

## 5. Justified overloads (the "fundamentally same" registry)

| word | positions | the one idea |
|---|---|---|
| `require` | part / assembly / mating | a claim needing evidence; identical lowering (L5 obligation) |
| `impl` | interface impls / signature impls | provide an implementation of a declared contract |
| `capability` | process / mating | provider envelope, always demand <= capability |
| `from` | stage `from=` / walk `from <datum>` / rule `resolves: <field> from free` | begin from this basis |
| `forall` | claim prefix / rule quantifier | universal quantification over a declared domain (config domain / entity query) |
| `demand` | interface `demands:` (elec binding) / rule `demand:` | the required side of the one demand <= capability check |
| `on` | scope guard / feature placement | spatial context of an operation (guard *is* the default placement, V8) |
| `as` | impl aliases / `as_datum()` | naming/aliasing |
| `in` | value domains / `forall` domains (rule query domains included) | domain membership |
| `model` | `model<sig>()` refs / `model=<impl>` pins | reference into the signature/impl system |
| lock family (`locked:`, `use`, `sequence:`, `merge()`, `hosted_on`) | budgets / coherence / planner / scopes / hosting | human fixes an otherwise-resolved decision; lockfile-visible; rung 2 of the expert ladder (regolith `12`) |
| `by` | evidence / overrides / signature impls / impl strategies (`by extern`) / waive deviations | provenance attribution |
| `datum` | part capture / setup letters | immutable reference geometry; letters bind datums to fixturing |
| `within` | `within(a,b,tol)` / `within <d> after <e>` / `within [lo, hi]` (slot literal and infix claim comparator) | containment: tolerance ball, time window, value window |
| `import` | `import <pkg> (...)` / stage `import(path)` | bring foreign content into this compilation (source-level / data-level) |
| `align` | matings / joining stages | frame-coincidence placement rules; the only positioning mechanism |
| `when` | variant guards / spec expressions (elec) | conditional on a discrete selector |

## 6. Reserved, undesigned

Workholding nouns for `hold:` - `joint`/mechanism sugar over
`exposing` - drawing/annotation vocabulary (L6).

(Zone syntax and time-domain claim words graduated to designed in 0.5;
`variant`, `pieces:`, fatigue claim spellings graduated in 0.6;
weld taxonomy/models (OPEN-13) and `policy:` global objectives
(SOPEN-4) graduated in 0.8 -- sections C, I3, I4; the `process` rule
pack body graduated in 0.14, cycle 18 -- section I5.)
