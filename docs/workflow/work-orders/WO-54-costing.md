# WO-54: costing v1 (profiles, records, estimators, itemized evidence)

Status: done (schema slice landed first dispatch; grammar/manifest/
orchestrator/estimators/budget-fixture/corpus/docs landed second
dispatch; residuals named in the second close-out ledger below --
scoped cuts inside deliverables 5/6, never dropped)
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


## Close-out ledger (cycle-28 follow-up dispatch, second slice)

Everything below landed WITHOUT reopening the schema: SCHEMA_VERSION
stays 20 (the first slice's bump is final). Charter sec. 4's
acceptance shape, item by item, quoted verbatim:

- **"The small_office flagship's two cost claims discharge end to
  end against fixture records (a construction estimate over takeoff
  x unit-cost records; a BOM estimate over pricing records with a
  quantity break)"** -- LANDED. `tests/orchestrator/test_cost_build.py::
  test_small_office_flagship_cost_claims_discharge` builds the real
  flagship against `stdlib/std.cost` fixture records: the
  program.calx whole-project claim discharges via `cost_civil_takeoff`
  (frame member-length takeoff x the rsmeans-SHAPED per-meter
  unit-cost fixture) and power.cupr's BOM claim via `cost_elec_bom`
  (sqd distributor pricing with quantity breaks).
- **"an expired-quote fixture goes indeterminate naming the
  record"** -- LANDED. `stdlib/std.cost/records/pricing.toml` ships
  the deliberately-expired `acme.quote_2025q4` source;
  `resolve_profile_inputs` defers with `pricing_record_expired`
  naming the record key and its `valid_until` ("waivable with
  basis": the deferral rides the ordinary INV-24 indeterminate
  surface the waive ladder already governs). NOTE on placement: the
  D123 negative-corpus driver is check-time-only by its own header
  contract, and expiry is a DISCHARGE-time outcome -- so the
  `examples/negative/` fixture 63 carries the check-time half
  (malformed `mfg.cost` args, EXPECT E0438) and the expiry acceptance
  lives as orchestrator corpus tests
  (`test_expired_quote_is_indeterminate_naming_the_record`).
- **"forall profile sweeps produce per-profile evidence under one
  obligation"** -- LANDED (D95 encoding). `forall profile in {a, b}:`
  lowers through the existing D105a prefix into ONE obligation's
  `SweepDomain`; the orchestrator stages every axis point's resolved
  profile into the estimator-inputs doc; the estimator prices every
  profile, predicts the WORST total, and records the axis as
  structured coverage (`CoverageAxis{axis="profile", discrete,
  enumerated}`); one itemized estimate per axis point is persisted
  (`<subject>/<profile>` -> digest on the build report). Corpus:
  `examples/tracks/cuprite/cost_profiles.cupr` +
  `test_profile_sweep_is_one_obligation_with_per_profile_evidence`.
- **"the estimate payload is itemized, cited, and
  byte-deterministic"** -- LANDED. One arithmetic home
  (`harness/models/cost_common.py`) builds `ItemizedEstimate` line
  items (item, qty, unit cost + hash-pinned `RecordRef`, extended)
  with declared exclusions; the orchestrator persists it into the
  WO-30 payload store (the WO-42 `put_realized_geometry`
  fresh-blake3-of-JSON-bytes precedent for Python-produced payloads).
- **"`regolith build --profile production` selects the profile and
  the lockfile shows it"** -- LANDED. `--profile` on the build verb
  (unknown name is a loud error, never a silent default; claim-level
  `profile=` still overrides per-claim); the lockfile carries a
  `cost.profile` row (`cause: cost_profile(cli)` /
  `cost_profile(manifest_default)`) plus one `pin <key>@1 = <digest>`
  line per consumed record (INV-22). Real-subprocess CLI tests.
- **"No price, rate, or currency conversion exists outside records;
  grep-provable"** -- HOLDS. Every number multiplied or summed by the
  estimators comes from a record body carried in the staged doc;
  grep for priced literals in `crates/`/`python/` stays clean.

What landed, per deliverable:

1. **Grammar**: `mfg.cost(<subject>[, profile=<name>])` validated at
   compile time (new E0438, constructive) in BOTH claim positions --
   decl `require` groups (`push_cost_claim_obligation`) and top-level
   require groups (`push_top_level_cost_obligations`, the calcite
   program.calx shape the frame/fluid passes deliberately skip);
   `cost_subject:`/`cost_profile:` plus the decl's `parts:` BOM lines
   thread into `given.loads` (the conformance-windows precedent -- no
   schema change). The profile `forall` domain rides the EXISTING
   D105a discrete-sweep prefix; nothing new was encoded.
2. **Manifest**: `[profiles.cost.<name>]` -> `CostProfile` on
   `Manifest` (quantity/labor/process_rates/pricing/markup/currency,
   `[profiles.cost.default]`; loud errors for malformed tables and a
   default naming no profile). Lockfile pins + `--profile` as above.
3. **Orchestrator** (`orchestrator/costing.py`): profile -> record
   set (rates by exact key; pricing/unit-cost SOURCES by key prefix
   `<source>.<item>`, declared source order, first source pricing an
   item wins) -> staged estimator-inputs `table` payload (D96; kind
   vocabulary untouched) with per-basis marker ports so registry
   selection stays signature-honest. Expired pricing and missing
   record refs defer NAMING the record; a cost claim with no
   estimator basis falls to the existing total no-model
   indeterminate naming `mfg.cost`. CLOCK: no ambient build clock
   exists anywhere in the toolchain (the mech realizer normalizes
   wall-clock out of artifacts; the adapter's `timeout_s` is the only
   wall-clock use) -- so expiry's date enters at ONE seam
   (`load_cost_context(as_of=...)`, defaulting to today's UTC date
   there and nowhere else) and an expired record produces a DEFERRAL,
   which is never cached and never content-addressed; wall time still
   never enters hashed bytes. Decision recorded in the module
   docstring.
4. **Estimators** (std.cost, AD-19; `harness/models/cost_estimators
   .py` + the `stdlib/std.cost` package home naming them, the
   std.models code-does-not-move precedent): `cost_elec_bom` (BOM x
   pricing breaks at the profile quantity), `cost_fluid_bom`
   (flownet component-record edges), `cost_civil_takeoff`
   (member-length takeoff x per-meter unit costs). Three models, ONE
   `mfg.cost` claim kind (D94 competition), per-basis payload ports.
5. **Budget kind `cost` + policy fixture**: D49 says budget kinds
   are PACK-provided, not compiler built-ins -- grep confirms no
   kind registry/validation surface exists to edit, so "registration"
   is corpus + pack content: `cost_profiles.cupr` declares
   `budget unit_cost: kind=cost` and `policy: minimize mfg.cost(all)`
   (check-clean).
6. **Corpus**: fixture 63 (`63_cost_claim_malformed_args.hema`,
   EXPECT E0438; numbers 60/61/62 confirmed taken, 63 next free);
   `cost_profiles.cupr` (sweep + budget + minimize);
   `stdlib/std.cost` fixture records (every number INVENTED -- never
   transcribed vendor/RSMeans data, research note 2026-07-09 sec. 4);
   small_office end to end; small_office golden refolded twice (given
   threading, then the new program.calx obligation: 23 -> 24).

Cut/residual, named (scoped inside deliverables, not dropped):

1. **Mech plan estimator**: CUT. The WO-26/28 planner surface ships
   no landed plan payload with cost legs (`orchestrator/planner.py`
   and the mech realizer schema carry no cost fields; no `plan`-kind
   payload is produced by any landed pass), so there is nothing for
   a plan-based estimator to consume. Lands with the WO-28 engine
   remainder / plan-as-evidence surface.
2. **Elec BOM scope**: per-joint assembly and the fab table are
   DECLARED EXCLUSIONS in the estimate (a `USD/joint` process rate
   with no joint count, and no fab basis, cannot price honestly --
   the landed BOM basis is the decl's `parts:` lines, qty 1 each).
3. **Civil takeoff scope**: member-length (`m`) and `each` bases
   only, priced against the profile's FIRST per-meter unit-cost
   record; supports, deck/assembly areas, connections, and
   per-section assembly mapping are declared exclusions (the landed
   `FramePayload` carries lengths + name-only section refs; area
   takeoff and section-record resolution are follow-ups).
4. **Fluid BOM scope**: component-record edges only (curve/vendor
   bindings); pipe/plenum runs are declared exclusions (no
   length-based pipe pricing v1).
5. **Cross-track `all` SUM**: a `mfg.cost(all, ...)` claim is priced
   by the single deterministically-selected governing estimator
   (civil takeoff when a frame exists) with the other tracks as
   declared exclusions; the charter's sum-through-promise/budget-
   chain composition is future work on the D49 budget math.
6. **Evidence-cache key does not fold record content**: the
   obligation cache key (INV-1 fold) is obligation+pack-identity;
   record content reaches the EVIDENCE hash via the staged doc's
   digest in `settings_digest`, but a `persist=True` evidence cache
   would serve stale cost evidence after a record-content change
   (obligation unchanged). Default builds use a fresh per-build
   store, so this bites only persistent-cache callers; fixing it
   properly means folding the staged-doc digest into the cache key
   at `discharge_one` -- a small, recorded follow-up.
7. **Record resolution is local-path only**: the search set is the
   project root plus caller-supplied paths (tests pass `stdlib/`);
   the CLI exposes no `--record-path` and does not yet resolve
   `[depends] "std.cost"` into a search path via magnetite --
   registry fetch is a charter non-goal, the depends-driven local
   resolution is a follow-up.
8. **`mfg.unit_cost` / `mfg.lead_time`**: untouched (still generic
   comparison claims); charter sec. 1.1 keeps them, `profile=` lands
   on `mfg.cost` only in v1.
9. **Budget math for kind `cost` / the minimize objective in the
   lazy loop**: the fixture parses and lowers; the allocation math
   and the SOPEN-4 objective actually driving component trades are
   pack/loop content beyond this WO (the mass-budget precedent's own
   boundary).

## Non-goals

- Live pricing fetches, scheduling, tax/finance, cost-risk Monte
  Carlo (charter sec. 3).
- Registry hosting of priced records beyond fixtures (projects and
  vendors publish; we ship schemas + fixtures).
