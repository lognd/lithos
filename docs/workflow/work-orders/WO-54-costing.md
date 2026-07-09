# WO-54: costing v1 (profiles, records, estimators, itemized evidence)

Status: in-progress (core schema slice landed; estimator/orchestrator/
grammar/manifest/corpus slices cut and recorded below -- follow-up
dispatch)
Depends: WO-30 (payload channel, done -- the estimate table rides
it), WO-45 (stdlib home for `std.cost`), WO-44 (plugin seam), WO-25
framework (the ship/report surface). The civil takeoff estimator
additionally gates on WO-48 (schedules); the mech plan estimator on
the WO-26/28 planner surfaces where cost legs already exist --
scope the estimator set to what its dependencies have landed and
record the rest in the ledger (the WO-25 close-out precedent).
Language: Rust (`regolith-syntax` profile= claim argument,
`regolith-oblig` estimate/record schemas) + Python (orchestrator
profile resolution, estimator models, CLI `--profile`) + stdlib
records + fixtures.
Spec: docs/spec/toolchain/27-costing.md (NORMATIVE charter),
00-architecture.md AD-29 (+ AD-5/19/26), design-log
2026-07-08-cycle-27 D147; regolith/11 sec. 8 (`std.cost`),
regolith/04 sec. 5.4 (budgets -- kind `cost` lands with this),
regolith/12 sec. 4 (`minimize` objectives).

## Goal

`mfg.cost(<subject>, profile=<name>)` claims discharge end to end
against project-declared profiles: manifest profile tables,
validity-windowed rate/pricing records, per-track estimator models,
itemized content-addressed estimate evidence, `--profile` selection,
and profile-domain sweeps.

## Deliverables

1. Grammar: the `profile=` claim argument; profiles as a declared
   discrete domain for `forall` (D95 encoding; one obligation,
   per-profile axis points).
2. Schemas (`regolith-oblig`): rate record, pricing record
   (quantity breaks + `valid_until`), unit-cost record, and the
   itemized-estimate table payload (line item: item, qty, unit cost
   + record ref, extended; declared exclusions). Currency units in
   the unit tables (USD baseline; conversions are explicit cited
   records).
3. Manifest: `[profiles.cost.<name>]` parsing in magnetite
   (quantity, labor/process_rates, pricing, markup, currency;
   `[profiles.cost.default]`); lockfile pins every consumed record;
   `regolith build --profile <name>` selects.
4. Orchestrator resolution: profile -> record set -> estimator
   inputs; EXPIRED pricing -> indeterminate naming the record
   (waivable with basis); missing estimator -> honest indeterminate
   naming the gap.
5. Estimators (`std.cost` reference models, AD-19 packs): elec BOM
   (pricing breaks + fab table + per-joint assembly), fluid BOM;
   civil takeoff and mech plan estimators as their gates land
   (dependency note above).
6. Budget kind `cost` (D49 registration) + a `minimize mfg.cost`
   policy fixture.
7. Corpus: the small_office claims discharge against fixture
   records; an expired-quote negative fixture; a
   `forall profile in {prototype, construction}` sweep fixture.

## Acceptance criteria

- Charter sec. 4 verbatim (small_office end to end, expired-quote
  indeterminate, profile sweep under one obligation, itemized
  deterministic evidence, `--profile` + lockfile visibility).
- No price, rate, or currency conversion exists outside records;
  grep-provable (the AD-29 rule made checkable).
- `make check` green; schema bump serializes with any concurrent
  SCHEMA_VERSION WO (WO-48 rule).

## Close-out ledger (cycle-27 follow-up dispatch, first slice)

This dispatch also carried the WO-26 rider (see that WO's close-out
ledger item 2, now closed): `ClaimForm::StaysWithin` gained an
optional `window` field, folded into the SAME SCHEMA_VERSION 19->20
bump as this WO's records (per the dispatch instruction -- one bump,
never two in flight).

Landed this dispatch:

- **Deliverable 2 (schemas), in full**: `regolith-oblig::cost` --
  `RateRecord`, `PricingRecord` (quantity breaks + `valid_until`),
  `UnitCostRecord`, `EstimateLineItem`/`ItemizedEstimate` (the
  `table`-kind itemized-estimate payload per feldspar 09 sec. 4's
  existing `table` vocabulary entry -- no new payload kind needed).
  Rust unit tests (round-trip + content-digest stability/sensitivity)
  green; `_schema/models.py` regenerated (`RateRecord`, `PricingRecord`,
  `PriceBreak`, `UnitCostRecord`, `EstimateLineItem`, `ItemizedEstimate`
  now present).
- The SCHEMA_VERSION 19->20 bump itself, folding in the WO-26 rider,
  with the full golden corpus re-folded (WO-48 slice B precedent);
  `make check` green.

Cut, named, and NOT landed this dispatch (the schema is complete and
never half-landed; everything downstream of it is the cut):

1. **Deliverable 1 (grammar)**: the `profile=` claim argument and the
   profile discrete-domain `forall` encoding (D95) in
   `regolith-syntax`/`regolith-lower`. Not started.
2. **Deliverable 3 (manifest)**: `[profiles.cost.<name>]` parsing in
   magnetite (quantity/labor/process_rates/pricing/markup/currency,
   `[profiles.cost.default]`), lockfile pins for consumed cost
   records, and `regolith build --profile <name>` CLI plumbing. Not
   started.
3. **Deliverable 4 (orchestrator resolution)**: profile -> record set
   -> estimator inputs, the EXPIRED-pricing indeterminate path naming
   the record, and the missing-estimator indeterminate path naming the
   gap. Not started -- depends on deliverables 1 and 3.
4. **Deliverable 5 (estimators)**: `std.cost` reference models (elec
   BOM, fluid BOM, civil takeoff over the WO-48 frame/schedule surface,
   mech plan over the WO-26/28 planner surface). Not started -- depends
   on deliverable 4 for its input-resolution contract.
5. **Deliverable 6 (budget kind `cost`)**: the D49 budget-kind
   registration and the `minimize mfg.cost` policy fixture. Not
   started -- depends on deliverable 5 producing a real cost number to
   budget against.
6. **Deliverable 7 (corpus)**: the small_office cost discharge, the
   expired-quote negative fixture, and the `forall profile in
   {prototype, construction}` sweep fixture. Not started -- depends on
   1/3/4/5. Fixture numbers 60/61/62 remain TAKEN by WO-48 slice A;
   the next dispatch must re-grep before claiming numbers.

Rationale for the cut boundary: the schema is the one artifact this
dispatch has EXCLUSIVE, non-reopenable authority over (SCHEMA_VERSION
19->20 is chartered as the LAST bump); every other deliverable can
still be built against these landed shapes by a follow-up dispatch
without touching the schema again. Landing a partial grammar/
orchestrator/estimator slice in the same pass this session's time
budget allowed would have risked a half-wired, undertested surface
riding a schema that must not be reopened -- worse than a clean,
fully-tested schema slice plus an honest, itemized cut list.

## Non-goals

- Live pricing fetches, scheduling, tax/finance, cost-risk Monte
  Carlo (charter sec. 3).
- Registry hosting of priced records beyond fixtures (projects and
  vendors publish; we ship schemas + fixtures).
