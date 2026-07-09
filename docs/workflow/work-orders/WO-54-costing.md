# WO-54: costing v1 (profiles, records, estimators, itemized evidence)

Status: todo
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

## Non-goals

- Live pricing fetches, scheduling, tax/finance, cost-risk Monte
  Carlo (charter sec. 3).
- Registry hosting of priced records beyond fixtures (projects and
  vendors publish; we ship schemas + fixtures).
