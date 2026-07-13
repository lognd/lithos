# WO-110 -- Built-in model depth + manufacturability channel (Class C, lithos half)

Status: honest-partial (every channel landed + fixture-proven per
  D232.1; the ONE residual is the bare-unit-cost fixture's full
  release-tier discharge, blocked on the Rust bare-form cost-marker
  gap -- see the close-out ledger's WO110-F3)
Language: Python (harness/models/*, registry wiring); no schema
  bump (D225).
Spec: F130 Class C; D220 (models added, gates untouched); D223
  (split: solver-pack-shaped physics goes to feldspar/WO-111;
  closed-form checks a firm does on a pad land HERE as built-ins);
  charter 34 (removal/DFM machinery); existing model conventions
  (harness/models/ -- match bearing_life.py / beam_bending.py
  idiom: typed inputs, named deferrals, citation in docstring).

## Goal

Every Class C claim kind the fleet actually declares has a real
registered discharge channel with a citation and calibration test.
The census' "no registered model" residue shrinks to kinds that
genuinely have no closed form (those go to WO-111 or stay 2(c)
exclusions).

## Deliverables (survey first -- enumerate the fleet's undischarged
call forms after WO-109 routing, then land the set; the list below
is the known floor)

1. `manufacturable(<process>)` discharge channel: the 40 `makeable:`
   claims evaluate against realized geometry through the existing
   cam/DFM family (charter 34 packs; mill/turn/print/cut process
   envelopes): tool access, min feature vs tool, depth-to-dia,
   stock-fit -- discharging where the realized part passes, VIOLATED
   where it genuinely fails (then the DESIGN gets fixed per D224.3),
   deferring with named inputs where geometry/process data is
   absent.
2. Shaft/rotor critical speed (`crit_speed:` family) -- Rayleigh/
   Dunkerley closed form, cited.
3. Torsion + combined-stress checks for shaft claims (`twist:`) --
   cited closed forms.
4. NPSH available-vs-required check (`npsh:` fluid claims).
5. Label kind `cost`: route to the WO-54/101 costing surface --
   a cost claim compares the estimator's number against the
   declared bound (the estimate machinery exists; this is the
   claim-facing adapter).
6. Label kind `jitter` and the elec residue: adapters onto the
   existing buck/SI/link-budget model family where the call form
   matches; honest named deferral where the physics is
   board-level (goes to the 2(c) ledger).
7. Every new model: docstring citation (textbook/standard,
   editioned), calibration test against a published worked example,
   deferral tests for each missing-input branch.

## Acceptance

- Each landed model discharges (or honestly VIOLATES) at least one
  real fleet claim end-to-end at release tier, demonstrated in the
  WO close-out with build-report evidence.
- No fleet claim defers "no registered harness model" for a kind
  this WO landed.
- `make check` green; census + goldens regenerated and reviewed.

## Escalation

Physics needing real numerics (FEA, modal, fatigue spectra) is
feldspar-shaped: hand it to WO-111 in the close-out, do not
approximate it into a built-in. Schema needs escalate per D225.

## Close-out ledger (2026-07-13, wo110-builtin-models)

Acceptance semantics per D232 (channel proof by fixture; fleet
discharge demos joint with WO-113; the fleet corpus untouched).

Landed, one family per commit:

1. THE HEADLINE (deliverable 1): `harness/models/dfm/` -- the
   `mfg.manufacturable` channel over build-produced realized geometry.
   Two envelope checks grounded in DECLARED data only (charter 39
   sec. 4: no invented thresholds): stock/travel extent fit
   (RealizedGeometry topology vs the `[[machine]]` record) and
   per-hole exists-a-tool feasibility (dia floor + stickout reach vs
   the `[[tool]]` records -- depth-to-dia adequacy grounded in the
   declared tooling rather than a bare ratio constant; "tool access"
   v1 = the reach term). `orchestrator/dfm_staging.py` derives the
   staged `dfm_part` payload from the build's own FeatureProgram +
   snapshots + realized inputs (ONE home for the claim-token and
   stage-process family maps); `_translate_manufacturable` routes the
   bare predicate with five golden-visible deferral reasons. v1
   grounds the MILL family (the only family the existing record
   vocabulary can ground); form-family physics stays in the WO-28
   rule packs + `mech.sheet.min_bend_radius` (no double home). Fleet:
   IdlerBearingPlate `makeable` DISCHARGES for real;
   Spoilboard `makeable` is honestly VIOLATED (below); fixture
   release-tier discharge in `test_wo110_manufacturable.py`.
2. NPSH (deliverable 4): `npsh_margin.py` -- the NPSH energy balance
   (White, Fluid Mechanics, 8th ed., ch. 11), lower bound, worst
   corner, eps 0; calibration against a hand-computed worked example
   over published water-20C property data; wrapped + single-line
   routes with named-inputs deferrals; `.fluo` fixture proves
   discharge + honest violation + the named deferral end to end.
3. Torsion (deliverable 3): `shaft_torsion.py` -- theta = TL/(GJ)
   (Shigley 10th ed. ch. 4), upper bound, worst corner; calibration
   against a hand-computed 25mm steel shaft (G = 79.3 GPa, Shigley
   table A-5); fixture proves discharge/violation/deferral. The
   "combined-stress" half of the deliverable is a NAMED no-demand
   cut: the fleet spells zero combined-stress call forms today
   (reopen: the first such claim).
4. Critical speed (deliverable 2, superseded shape): D223 landed
   `mech.critical_speed` IN FELDSPAR (merged before this WO ran), so
   the WO body's "Rayleigh/Dunkerley built-in" is superseded by the
   one-home rule (charter 39 sec. 4) -- what lands here is the
   ADAPTER: pack-port input pinning (signature pin test against the
   installed pack), friendly kwarg aliases, and a GUARDED bound parse
   (an expression bound like the fleet's `1.4 * 9200rpm` defers
   `unresolved_limit` naming the expression, never truncated to its
   leading factor). Fixture discharges THROUGH the pack end to end.
5. Cost (deliverable 5): `_translate_bare_unit_cost` -- the bare
   `mfg.unit_cost(qty=...)` form derives its subject from the
   snapshot scope, picks the quantity-matching declared profile
   (explicit `profile=` cross-checked), and rides `_translate_cost`'s
   real resolution/staging; where a quantity basis exists the WO-54
   estimator competition compares its number against the bound
   (staged-request proof over a flownet-named subject). HONEST
   RESIDUAL (the Status line's one): full fixture discharge is
   blocked -- see WO110-F3/WO110-F5.
6. Jitter/elec residue (deliverable 6): undotted `rms(<signal>,
   band=[...])` waveform-statistic claims defer `excluded_call_form`
   naming the form and the WO-111 route (the F131 2(c) style; ledger
   row proposed below as WO110-F4).
7. Citations (deliverable 7): every new model carries a docstring
   citation + calibration + per-missing-input deferral tests; the
   WO-114 `Model.citation` seam is now populated for the new models
   AND the existing built-ins whose module docs already name source +
   edition (ISO 281:2007, White 8th ed., VDI 2230 -- transcription
   only). `std.models` names the new modules (charter 39 secs.
   1.5/3.2); guide `docs/guide/25-manufacturability-and-models.md`.

Fleet before/after (census golden, reviewed):

- makeable rows: 42 spelled; before = 100% `unsupported_op`; after =
  2 real verdicts (1 discharged + 1 violated, cnc_router_r1) + the
  rest NAMED (`mfg.manufacturable_inputs_missing` listing exact
  feature scalars, `_records_missing`, `_ungrounded_process`,
  `_process_mismatch`) -- zero `unsupported_op` remain.
- npsh rows (6): before "no registered model"; after
  `fluids.npsh_margin_inputs_missing` naming all six inputs.
- twist row: before label-kind no-model; after
  `mech.twist_inputs_missing` naming the four inputs.
- crit_speed rows (3): before `unmatched_call_path`; after
  `unresolved_limit` naming the expression bound (the D103/WO-112
  class) -- the routing itself is proven by the fixture.
- cost rows (16): before `mfg.cost_inputs_missing` (subject
  missing); after `cost_profiles_unconfigured` (the next honest
  gap: these projects declare no `[profiles.cost.*]`) -- WO-113
  authoring surface.
- census: cnc_router_r1 discharged 9 -> 11; fleet 15/15 green,
  release verdicts otherwise unchanged; no new error-level golden
  rows; calc book + audit index regenerated (the new sheets carry
  real citations).

VIOLATIONS found (for D224.3 design fixes -- WO-113 executes; DO NOT
regenerate goldens to hide):

- cnc_router_r1 Spoilboard `makeable: manufacturable(routed)`:
  VIOLATED, excess 530 mm -- the 830x530 mm spoilboard sheet cannot
  fit the ONLY declared `[[machine]]` record (`router_mill_3axis`,
  300x200 mm travel, the WO-72 demo mill). The honest fix is DATA:
  declare the Burin router's own machine record (the spoilboard is
  surfaced on the machine itself, whose bed is 600/900 mm). NOTE the
  fleet gate stays green because the row's PRE-EXISTING waiver
  ("predicate form is outside the scalar-comparison lowering
  surface") still matches by claim name -- that basis is now FALSE
  and shadows a real violation (D224.2 debt). The violation is
  recorded in the calc book golden (`verdict: violated`,
  margin -530). WO-113 must delete the waiver with the design fix.

Escalations (coordinator placeholders, no self-assigned numbers):

- WO110-F1: bound-text resolution is unit- and expression-blind
  fleet-wide -- `_parse_float` reads the leading float, so `<= 0.10
  mrad` parses as 0.10 (unitless vs an SI-radian prediction) and
  `> 1.4 * 9200rpm` parses as 1.4 in every pre-WO-110 kwargs route
  and the generic fallback (a LIVE truncated limit was frozen in the
  deferral goldens until this WO's guarded routes replaced those
  rows). New WO-110 routes carry `_parse_pure_literal_bound`;
  retrofitting the older routes + real unit conversion is a
  translate-surface work item (Class E shape, WO-112-adjacent).
- WO110-F2: `manufacturable(<family>)` for turn/cut/form/mold/tap/
  plate/print needs either record vocabulary (lathe/laser/press
  envelope records) or is the rule packs' home; `manufacturable
  (all)` additionally needs every stage family groundable. Named
  deferrals carry the routing today.
- WO110-F3: the Rust cost-claim lowering emits `cost_subject`/
  `cost_bom.*` markers ONLY for the marked `mfg.cost(<subject>,...)`
  form; the bare `mfg.unit_cost(...)` form lowers with EMPTY
  given.loads, so a part subject has no BOM basis and the bare
  form's end-to-end discharge is blocked (named deferral carries
  it). Fix is a small Rust increment in `push_cost_claim_obligation`'s
  sibling: emit the same markers for the bare form. No schema.
- WO110-F4: proposed 2(c) ledger row -- undotted waveform-statistic
  claim forms (`rms(...)`: jitter, ripple floors, sensor noise
  floors) are excluded until a sampled-waveform evidence channel
  exists (solver-pack shaped; WO-111). Diagnostic names the form
  (`excluded_call_form`); reopen = that channel.
- WO110-F5: `Pump(curve=registry(<key>))` bindings materialize an
  EMPTY `curves` list in the flownet payload when the named record
  is not resolvable at check time, so the fluid BOM estimator has no
  component to price even when a pricing record exists -- the F131.4
  Class 4 record-chain disambiguation applies (WO-112/113).
- WO110-F6 (for WO-111, per the boundary rule): fleet call forms
  needing pack models -- `mech.fatigue.damage`/`.cycles` (Miner
  accumulation over spectrum payloads; the pack's Goodman/Gerber FoS
  kinds are different physics), `first_mode(...)` (modal FEA; claims
  already pin `model=fea_modal`, unregistered today), and the
  WO110-F4 waveform channel. `mech.plate.*`/`mech.drive.*`/
  `mech.weld.utilization`/thermal-transient kinds are registered by
  the pack but have NO fleet call forms yet -- no adapter needed
  until one is spelled.
- WO110-F7: `stdlib/std.models/magnetite.toml` was missing every
  model landed between WO-45 and WO-110 (noted in-file); WO-118's
  charter-39 drift check should backfill-or-gate.
