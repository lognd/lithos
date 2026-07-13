# WO-112 -- Lowering-surface expansion (Class E)

Status: honest-partial (all five classes landed with fixtures; named residuals in the close-out ledger: Class 4 corpus record keys await WO-113 data, vias/buses escalated WO112-F4/F5)
Language: Rust (regolith-lower claims/translate surface) + Python
  (orchestrator/translate.py) -- investigate first, split findings
  by side; no schema bump without D225 escalation.
Spec: F130 Class E (the five named machinery gaps); D103 (entity-
  derived bounds); D102 (typed containment); D220 (verdicts
  untouched -- expansion means MORE claims become addressable,
  never different math).

## Goal

The five recorded machinery walls that keep ~220 real claims
unlowerable/unresolvable fall, each with fixtures both ways:

1. ~131 "predicate form outside the scalar-comparison lowering
   surface": survey the ACTUAL forms in the corpus (the waive
   bases point at each site), classify (comparator-after-call
   variants, boolean combinators, range forms, unit-expr shapes),
   and land recognition for every class that has a well-defined
   scalar/window reading. Forms that genuinely have no scalar
   reading get a NAMED unsupported-form diagnostic (not a generic
   one) and a 2(c) ledger row.
2. ~63 D103 entity-derived bounds: the bound lives in an entity/
   registry record; land the ref-resolution path (the D192/D201
   record machinery is the precedent) so the bound literalizes at
   lowering/translate and the claim becomes dischargeable.
3. 15 D102 typed containment scalar shapes (StaysWithin windows):
   thread the window into a scalar request pair (the WO-54 rider
   landed the schema slot).
4. 7 fluid record-chain gaps (`fluids.dp_inputs_missing` where the
   chain, not the data, is missing).
5. 6 rule-pack rules with no engine input: wire the engine input
   channel for the affected packs (WO-28's registry).

## Acceptance

- Per-class fixtures (positive + honest-negative) in the corpus
  test nets; every class's fleet count moves (report before/after
  counts per class in the close-out).
- No golden error-level regressions; `make check` green after
  `make install` (Rust touched).

## Escalation

Any form needing new grammar goes back to the coordinator (grammar
is track-spec territory, not toolchain); D/F numbers are assigned
at integration, use placeholders.

## Execution plan (F131 adjudication; one commit per class, in this order)

Baseline (fleet, default-tier `regolith build`, 15 projects):
unsupported_op 110, unresolved_limit 52,
temporal_reduction_unresolved_limit 5,
temporal_containment_unmodeled 15, fluids.dp_inputs_missing 6,
non_scalar_claim 2; rule-pack domains deferred via `<rule>` refs.

### Class 2 -- entity-derived bounds (D103), Python translate side
- [x] `orchestrator/material_resolve.py`: `MaterialProps` +
      `load_material_records` (std.materials TOML rows via
      `stdlib_records.row_hash` pinning; `yield_MPa`/`ultimate_MPa`
      -> Pa) + `MaterialContext` (records + consumed_pins).
- [x] translate: `_resolve_material_bound` -- `material.<prop>`,
      `material.<prop> / <N>` shapes off `given.materials` key;
      condition-call variants (`sigma_y(T_local)`) defer NAMED
      (`material_property_condition_unresolved`); unrecorded props
      (`tau_allow`) defer NAMED (`material_property_unrecorded`);
      missing record defers NAMED (`material_record_missing`).
- [x] Wire into both `limit is None` sites: generic comparison path
      + `_translate_temporal` reduction branch.
- [x] Thread `material_context` through discharge_one/discharge_all/
      lazy_loop/orchestrate (si_context precedent), loaded from the
      same `record_paths`.
- [x] Fixtures both ways: tests/orchestrator/test_translate_materials.py.
- [x] OUT (named residuals): `design_life` bare-ident refs,
      `w.filler.sigma_allow` 3-segment refs, `build_volume.x`
      constructor-kwarg refs, `partitions.app.size`.

### Class 5 -- rule-engine input channel (WO-28 registry), Rust
- [x] `traces` board domain: measure vocabulary + population from
      `layout.realized` RealizedInput (RoutedSegment width/length),
      so `jlc_2l.trace_width` evaluates at realized tier.
- [x] `.where(<field>=<word>)` equality filter over entity measures
      (unblocks `vbus_inrush_protection`).
- [x] Rust tests both ways (populated evaluates, unpopulated defers).
- [x] OUT: vias (drill/annular ring) -- RealizedLayout carries no
      via list; exact shape escalated as WO112-F4. `buses`
      (length_spread) -- no bus-group vocabulary exists; escalated
      WO112-F5. `test_point_probe_clearance` -- needs pad-geometry
      clearance extraction; named residual.

### Class 3 -- D102 StaysWithin window -> scalar request, Python
- [x] `_translate_temporal` ClaimForm6: `mask=floor(<qty> - <qty>)`
      (and `ceiling`) literalizes to a scalar request (limit = the
      resolved level; window duration rides as input); named masks
      keep the named deferral, now naming the mask ref.
- [x] Verify two-sided-window discharge model existence; report
      addressable-vs-dischargeable honestly in close-out.
- [x] Fixtures both ways.

### Class 1 -- named 2(c) diagnostics (F131.1/F131.2), Python
- [x] Temporal-state/event form (`within <t> after <event>:
      state/f(...) = <v>` / `op = <state>`): named deferral
      `temporal_event_form_excluded` citing F131.1 + reopen.
- [x] Quantified bit-field legality (`forall v in bits(...)`):
      named deferral `bitfield_legality_form_excluded` citing
      F131.2 + the D202 reopen.
- [x] Fixtures: both fire on corpus shapes; non-matching forms
      still reach the generic deferral.

### Class 4 -- fluid record-chain walk (F131.4 rule), Python
- [x] Probe result: medium `props: registry(<key>)` chains exist in
      all six deferring designs; the records themselves do NOT
      exist on disk (Class D half, WO-113) and translate never
      walks the chain (Class E half, here).
- [x] Land the walk: fluid context (flownet payloads + fluid
      property records off record paths); `_translate_fluid_dp`
      resolves `density_kgm3` through medium.records; deferral then
      names only the truly-missing inputs (or the missing record).
- [x] Fixtures both ways (record present resolves; absent defers
      naming the key). Per-claim Class D/E split table in close-out.

### Close-out
- [x] make install + make check green (foreground).
- [x] Per-class before/after fleet counts.
- [x] Escalations: WO112-F4 (RealizedLayout vias shape), WO112-F5
      (bus grouping vocabulary), schema needs: none.
- [x] Status flip + close-out ledger.

## Close-out ledger (2026-07-13, wo112-lowering-surface)

Fleet counts: default-tier `regolith build` over all 15 projects
(1,089 obligations), before at master bb4ec71 vs after the five
slices. DISCHARGED stays 45 by design: D220 -- expansion makes
claims ADDRESSABLE; discharging them is model routing/growth
(WO-109/110/111, Classes B/C). `no_model` 324 -> 351 is exactly
those newly-addressable claims arriving at the F126.1 routing
surface with real literalized limits.

| Class | measure | before | after |
|-------|---------|--------|-------|
| 1 | `unsupported_op` (generic wall) | 110 | 75 |
| 1 | `temporal_event_form_excluded` (F131.1) | 0 | 34 |
| 1 | `bitfield_legality_form_excluded` (F131.2) | 0 | 1 |
| 2 | `unresolved_limit` | 52 | 24 |
| 2 | `temporal_reduction_unresolved_limit` | 5 | 1 |
| 2 | named material deferrals (condition/unrecorded/key) | 0 | 9 |
| 3 | `temporal_containment_unmodeled` | 15 | 11 |
| 2+3 | newly lowered -> `no_model` (addressable) | -- | +27 |
| 4 | `fluids.dp_inputs_missing` | 6 | 6 (see below) |
| 5 | rule domains: `traces` populated at realized tier | never | Rust-proven |

Per-class notes:

1. The ~110-claim generic tag was FOUR populations (F131 item 1):
   `within [lo,hi]` bands already lower (pre-existing pair
   expansion); `manufacturable(...)` is WO-110's channel; the two
   genuinely non-scalar families now defer NAMED with their 2(c)
   ledger rows -- F131.1 (35 temporal-state/event claims) and
   F131.2 (1 bit-field legality claim). The remaining 75
   `unsupported_op` rows are assume!/vendor-fact/`==`-equality/
   non-bits-forall shapes -- honest generic deferrals, none with a
   well-defined scalar reading missed by this survey.
2. `material.<prop> [/ <N>]` bounds literalize from std.materials
   records via the new MaterialContext (loader shared with
   frame_resolve, ONE home; INV-22 pins flow to the lockfile). 23
   claims now lower with real limits; 9 defer NAMED (7
   condition-call `sigma_y(T_local)` variants -- property-curve
   records are D224 data growth; 1 `tau_allow` unrecorded; 1
   missing material pin). OUT, recorded: `design_life` bare-ident
   refs (5), `w.filler.sigma_allow` 3-segment refs (4),
   `build_volume.x` constructor-kwarg refs, `partitions.app.size`,
   `capability.*` (Class 5's channel covers the rule shapes).
3. The 4 `floor(...)` rail-droop masks lower to scalar requests
   (Rust resolves units inside floor/ceiling constructors only --
   named masks stay hash-pinned verbatim; window duration rides as
   an input). NO two-sided-window discharge model exists in the
   registry, so these land ADDRESSABLE (no_model at discharge),
   not discharged. The 11 remaining containment deferrals are
   named spectrum/template masks (CISPR_11_A, dune_jump_srs,
   usb2_hs_template1, ...) -- genuinely non-scalar, deferral now
   names the mask.
4. F131.4 probe verdict: ALL six designs reference medium records
   (`props: registry(<key>)`) and the chain was never walked
   (Class E half -- landed: FluidContext walks obligation ->
   flownet payload -> medium.records -> std.fluid `[[medium]]`
   row, density as lowest-priority input, INV-22 pinned, proven
   both ways against the real `water` record). The fleet count
   does not move yet because the referenced KEYS
   (water_iapws_liquid, egw_60_40, semisynthetic_5pct) exist on
   disk NOWHERE -- the Class D half: WO-113 authors them under
   D224 and the walk closes density fleet-wide the moment they
   land. Per-claim split: espresso brew_water + steam_service,
   cnc coolant x2, small_office hydronics, dune_buggy cooling --
   all Class D on the record data, all also still missing
   diameter/friction/length (edge records/extraction -- D224 data
   or the WO-34 routed-run channel).
5. The engine input channel is wired: `layout.realized` inputs
   gain their first re-lowering consumer (traces domain; entities
   with mm quantity text per RoutedSegment), the realized-tier
   gate defers BY NAME when un-realized (never a vacuous pass),
   and `.where(field=word)` equality filters evaluate (missing
   filter fields defer per-entity). `jlc_2l.trace_width` is
   proven evaluating (pass + violation) in Rust tests;
   `vbus_inrush_protection`'s filter now evaluates and defers
   naming `inrush_protection_count` (populating it needs an
   inrush-limiter record class -- data vocabulary, not machinery).
   OUT: vias (WO112-F4), buses (WO112-F5),
   `test_point_probe_clearance` (pad-geometry clearance
   extraction; realizer territory).

Escalations (D/F numbers at integration):

- WO112-F4 (schema-shape need, D225 bundle): `RealizedLayout`
  carries no via list, so `jlc_2l.drill_size`/`annular_ring`
  cannot evaluate at any tier. Exact shape: add
  `vias: Vec<RoutedVia>` to `regolith-oblig::layout::
  RealizedLayout` with `RoutedVia { net: String, position_mm:
  [f64; 2], drill_mm: f64, annular_ring_mm: f64 }` (realizer-
  sorted, AD-6), plus the fake-KiCad tier populating it. Joins
  the cycle's single adjudicated bump alongside ArcGeometry.radius
  (WO116-F1); the traces/where machinery landed independently.
- WO112-F5 (track-spec/grammar): `forall b in buses` needs a
  bus-group vocabulary (which nets form a matched group) that no
  cuprite construct declares; `b.length_spread` is computable from
  `CopperSummary.net_lengths_mm` once membership exists. Grammar
  is track-spec territory -- escalated, not invented.
- No other schema needs: Classes 1-4 landed with ZERO wire-schema
  changes (D225 honored).

Verdict math untouched (D220): every change either literalizes an
input/limit the design already declares, or renames a deferral;
`make check` green end-to-end including the census golden
(fleet discharged/accepted counts byte-identical).
