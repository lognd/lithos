# calcite -- the civil/architectural track: v1 charter

> Chartered cycle 26 (D133, owner). calcite is the primary mineral of
> limestone and the calcined heart of cement: the mineral you build
> buildings out of. Files: `.calx`. This charter DECIDES the v1
> shape. ELABORATED cycle 27 (D139, executing WO-46): `02-language.md`,
> `03-lowering.md`, and `04-open-questions.md` now elaborate this
> charter in the fluorite pattern, and the sec. 8 corpus exists under
> `examples/tracks/calcite/` + `examples/systems/small_office/`.
> Status: charter SETTLED; elaboration complete, awaiting owner
> ratification (the D93 precedent) -- then WO-47 (front end).
> Cycle-27 amendment: the sec. 7 drawings non-goal is REVISED by D140
> (derived drawing SHEETS are in scope via toolchain/25 + WO-50;
> geometry/BIM AUTHORING stays out), and sec. 7's HVAC deferral is
> eased by D141 (gas subnets are dischargeable; see 04).

## 1. Scope and personas

Civil engineering / architecture / building planning: declare what a
building (or site structure) must do -- how its spaces serve
occupants, how its structure carries its loads, how its envelope
separates inside from outside -- and let the toolchain derive member
sizes, check code compliance, and attach evidence to every claim.

Personas: the building designer (spaces, program, egress), the
structural engineer (frame, foundations, load paths), and the code
reviewer (whose checklist becomes executable rule packs). The same
inversion as every track: claims + contracts in, implementation +
evidence out.

Like fluorite, calcite is a vocabulary over the regolith, not new
machinery: quantities/intervals (regolith/02), value sources (03),
contracts (04), ownership/queries (05), stages/scopes (06),
claims/evidence (07), lowering L0-L6 (08), build/lockfile (09),
packages (11), the expert ladder (12), and the invariants (13) all
apply unchanged.

## 2. The three artifact families (SETTLED)

### 2a. Spaces

`space` declarations: the unit of architectural program. A space has
an area (interval-valued like every quantity), an occupancy class
(record-typed, from `std.civil` occupancy tables), adjacency and
access relations to other spaces (contracts, not geometry), and
membership in circulation graphs. Claims over spaces:

- occupancy capacity (`civil.occupancy(space) <= ...` from area x
  load factor -- table-driven, pack content);
- egress: travel distance to an exit, aggregate exit width per
  occupant load, dead-end limits -- computed over the circulation
  graph at L2 (statically checkable, no geometry needed);
- program-level area budgets (the existing budget mechanism, kind
  `area` -- D49's pack-provided budget kinds already allow this).

### 2b. Structure

`member` declarations (beam, column, brace, slab, wall, footing --
role vocabulary, one idea per word) with material records
(concrete/steel/timber/masonry from `std.materials`/`std.civil`
records) and connection contracts between members. THE LOAD PATH IS
A NET: calcite binds the AD-23 generalized net core (the same core
that carries elec nets and fluid flownets) -- members and supports
are nodes, load transfer is edges, and the L2 conservation check is
the INV-15 ledger: every tributary load reaches a foundation; an
unsupported load is a leak diagnostic, exactly as a fluid net leak.
Structural sizing claims (strength utilization, deflection limits,
story drift) lower to obligations discharged by solver packs --
closed-form beam/column checks in-tree (the harness precedent), FEA
and frame analysis via feldspar (the WO-20/AD-19 seam; feldspar M1
already ships static stress/deflection).

### 2c. Envelope

Layered `assembly` constructions (wall/roof/floor types): ordered
material layers with derived thermal transmittance (U-value), fire
resistance rating, and acoustic class (STC) -- record-backed,
computed by pack models, claimed against code minima. Envelope
assemblies are artifacts with promises; spaces and the site boundary
consume them through ordinary contracts (a wall type PROMISES
`fire_rating >= 2hr`; the corridor that requires it holds the
obligation).

## 3. Loads, site, and environment (SETTLED)

The site is declared boundary truth (the cuprite
`environment`/harness precedent, D99/WO-34): wind speed, ground snow
load, seismic design category, frost depth, soil bearing capacity --
declared once, record-cited, consumed by packs. Load CASES and
COMBINATIONS are pack content (`std.civil`, D135): dead/live/wind/
seismic/snow cases, code-edition-specific combination sets
(e.g. strength vs service combinations). The language provides the
claim surface; the pack provides the numbers and the combination
algebra -- the D63 "allocation policies are pack math" precedent.

## 4. Code compliance = rule packs (SETTLED)

Building codes are DFM-rules-shaped: `forall <var> in <query>` +
`demand:`/`advise:` + `per:` citation is exactly a code section. The
WO-28 rule engine is the compliance engine, unchanged: a code pack
(`std.civil.*` reference packs; real jurisdictions publish their
own) demands egress widths, rise/run limits, fire separations, area
limits per construction type. Overrides go through the existing
waive ladder ONLY (variance = a waiver with evidence and an expiry
-- the mechanism already models real building variances). No new
override surface.

## 5. Lowering shape (v1)

- L0-L1: parse + quantity/unit/claim-form checks (shared).
- L2: the static core -- circulation-graph egress checks, load-path
  net conservation, budget ledgers, occupancy arithmetic, envelope
  U-value/rating derivations from layer records. This level alone is
  the v1 payoff: a statically code-checked building program.
- L3: member sizing resolution (free -> resolved section from
  capacity tables; the `free` value-source discipline unchanged).
- L4: realized structural model -- a frame IR (members, joints,
  releases, loads) as a realized-domain IR per AD-25's growth rule
  (Rust schemars schema, content-addressed, payload-ref channel);
  the feldspar frame/FEA consumer reads it.
- L5: evidence -- closed-form checks in-tree, frame/FEA via
  feldspar, all through the one obligation pipeline.
- L6: ship -- structured schedules (member schedule, door/opening
  schedule, area tabulation, compliance report) via the WO-25
  backend framework. Drawing/BIM export is a NON-GOAL v1 (sec. 7).

## 6. Cross-track composition (SETTLED)

MEP is composition, not calcite surface: hydronics/plumbing are
fluorite circuits, power is cuprite, and the building hosts them
through ordinary contracts (a mechanical room is a `space` whose
contract offers mounting, drainage, and power boundaries). The
cross-language import mechanism (SOPEN-2, settled) carries it. A
building project is the fourth `systems/` corpus flagship: one
manifest, `.calx` + `.fluo` + `.cupr` sources.

## 7. Non-goals v1 (each with a reopen criterion)

- Geometry/BIM authoring or IFC export: reopen when a consumer needs
  coordinated geometry across trades (the realizer seam is where it
  would land; schedules come first).
- Construction scheduling/cost estimation: the `mfg` time/cost
  quantity namespaces exist; reopen on a real estimating use case.
- Rebar/connection detailing: reopen when a fabricator-facing
  backend is asked for.
- Soil mechanics beyond declared bearing/frost records: geotech
  reports enter as records with evidence tiers, not as solved
  models; reopen on a foundation-design use case.
- Zoning/site-plan law: same shape as building codes (rule packs)
  but jurisdiction data is unbounded; reopen when a real
  jurisdiction pack is contributed.
- HVAC air-side: pending fluorite's gas-medium maturity; reopen with
  a duct-network example.

## 8. Corpus plan (WO-46 writes these)

Five pressure tests, smallest first: `bus_shelter.calx` (minimal:
one space, four members, one envelope assembly), `pole_barn.calx`
(timber frame, snow governs), `footbridge.calx` (steel, deflection
+ vibration claim), `retaining_wall.calx` (record-driven geotech
consumption), and `systems/small_office/` (the flagship: two-story
program with egress, envelope ratings, frame, and a fluorite
hydronic loop + cuprite panel as cross-track imports).

## 9. Open-question numbering

Calcite opens use `COPEN-n`. The charter opens NONE: every v1
question above is decided or deferred-with-reopen-criterion, keeping
the project-wide technical open queue empty (F90). WO-46 must
escalate to the design log rather than open a COPEN silently.

## 10. Machinery

- **WO-46**: elaborate this charter into the full track docs +
  corpus (no toolchain code); bump nothing in the extension registry
  yet.
- **WO-47**: front end -- `.calx` in the ONE extension-registry
  module, grammar/CST/AST for the 2a-2c surface, negative fixtures
  (the WO-31 pattern).
- **WO-48**: lowering -- circulation/load-path net binding, claim
  lowering, the frame IR (AD-25 growth rule), `std.civil` reference
  packs (the WO-32 pattern).
