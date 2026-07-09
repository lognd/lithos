# 27 -- Costing (design charter; D147, cycle 27)

> Charter for pricing estimates across every track, project-
> configurable by construction. Ledger rule: AD-29
> (00-architecture.md): cost is a claim, an estimate is evidence,
> and every priced number comes from a profile-selected, hash-pinned
> record -- the compiler contains no prices, rates, or currencies
> beyond unit machinery. Machinery: WO-54. The owner's directive:
> "pricing estimates across everything... project-configurable...
> production, prototyping, whatever profile (again, CONFIGURABLE)."

## 0. The gap this closes

Cost was always designed for (`mfg.unit_cost/cycle_time/lead_time`;
"manufacturability/cost/time are claims discharged by planner
models"; plan = evidence) but never chartered: no profile mechanism,
no record schemas, no estimators, no cross-track story. Meanwhile
every real design decision is a cost decision, and every track has a
natural estimate basis the toolchain already computes: mech plans,
elec BOMs, fluid BOMs, civil quantity takeoffs (the L6 schedules ARE
a takeoff).

## 1. Design decisions (load-bearing)

1. **The claim surface** is one argument on the existing namespace:
   `mfg.cost(<subject>, profile=<name>) <= <money>`, plus
   `mfg.unit_cost` (per-unit at the profile's quantity basis) and
   `mfg.lead_time` unchanged. `<subject>` is any claimable subject
   (part, board, structure, system, `all`). Profiles form a declared
   DISCRETE DOMAIN: `forall profile in {prototype, production}`
   sweeps one obligation across pricing worlds (D95 encoding) -- a
   design can demand it is affordable to prototype AND economic at
   volume, in two claim lines.
2. **Profiles are project manifest data.**
   `magnetite.toml [profiles.cost.<name>]`: `quantity` (the basis),
   `labor`/`process_rates` (rate-record refs), `pricing` (ordered
   pricing-source record refs), `markup`, `currency` (default USD).
   `[profiles.cost.default]` names the default. Everything is a
   record REF, lockfile-pinned (INV-22); `regolith build --profile
   <name>` selects, claims may override per-claim. No toolchain
   config, no environment state -- a project's economics are in its
   repo, diffable.
3. **Records: rates and prices with validity windows.** `std.cost`
   defines the schemas: rate records (shop/labor/regional rates),
   pricing records (vendor price breaks by quantity, hash-pinned
   quotes/catalogs), unit-cost records (RSMeans-shaped assemblies
   for civil). Every pricing record carries `valid_until`; a claim
   consuming an EXPIRED record is INDETERMINATE (never silently
   stale), waivable through the ordinary ladder with basis. Currency
   is a unit family (unit-table content); conversion records are
   explicit and cited, never ambient.
4. **Estimators are ordinary models** (AD-19 packs; `std.cost` ships
   the reference set): mech -- plan-based (setup + cycle time x
   rates + stock, the CAM planner's cost leg made real); elec -- BOM
   x pricing breaks + fab table + assembly per-joint rates; fluid --
   BOM over component records; civil -- takeoff (member schedule,
   assembly areas from the L6 tables) x unit-cost records.
   Cross-track subjects SUM sub-estimates through the ordinary
   promise/budget chain. Where no estimator matches, honest
   indeterminate names the gap (the "what would resolve it" family).
5. **Evidence is an ITEMIZED estimate**: a `table`-kind payload of
   line items (item, quantity, unit cost + record ref, extended),
   content-addressed -- auditable and diffable across builds, so a
   price change shows as a line-item diff. Coverage states what the
   estimator did NOT price (declared exclusions), keeping the
   number honest.
6. **Budgets and objectives**: std budget kinds gain `cost` (D49;
   members may span tracks); `policy: minimize mfg.cost(all)` is the
   ordinary lexicographic objective (SOPEN-4 machinery). The lazy
   loop may therefore trade component choices against a cost budget
   exactly as it trades mass.

## 2. What already carries it

Claims/obligations/evidence, the D95 sweep encoding, registry
records + trust tiers + INV-22 pinning, budgets (D49), policy
objectives (SOPEN-4), the pack seam (AD-19/26), plan-as-evidence.
This charter adds: the `profile=` claim argument, the manifest
profile table, the `std.cost` schemas, the estimator models, and
`--profile` -- nothing else.

## 3. Non-goals (reopen criteria attached)

- Live vendor API pricing: records are pinned snapshots; a fetch
  tool that WRITES fresh pricing records is magnetite tooling,
  future, and never runs inside a build (determinism).
- Construction SCHEDULING (durations/sequencing): reopen on a real
  scheduling use case (calcite/04).
- Tax/finance modeling (NPV, depreciation): out; markup is the only
  overhead knob v1.
- Probabilistic cost risk: intervals already carry spread; Monte
  Carlo cost tiers are pack content whenever demanded, not charter
  scope.

## 4. Acceptance shape (what WO-54 must prove)

The small_office flagship's two cost claims discharge end to end
against fixture records (a construction estimate over takeoff x
unit-cost records; a BOM estimate over pricing records with a
quantity break); an expired-quote fixture goes indeterminate naming
the record; `forall profile` sweeps produce per-profile evidence
under one obligation; the estimate payload is itemized, cited, and
byte-deterministic; `regolith build --profile production` selects
the profile and the lockfile shows it.
