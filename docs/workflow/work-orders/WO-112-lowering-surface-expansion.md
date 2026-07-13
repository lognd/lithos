# WO-112 -- Lowering-surface expansion (Class E)

Status: open
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
- [ ] `orchestrator/material_resolve.py`: `MaterialProps` +
      `load_material_records` (std.materials TOML rows via
      `stdlib_records.row_hash` pinning; `yield_MPa`/`ultimate_MPa`
      -> Pa) + `MaterialContext` (records + consumed_pins).
- [ ] translate: `_resolve_material_bound` -- `material.<prop>`,
      `material.<prop> / <N>` shapes off `given.materials` key;
      condition-call variants (`sigma_y(T_local)`) defer NAMED
      (`material_property_condition_unresolved`); unrecorded props
      (`tau_allow`) defer NAMED (`material_property_unrecorded`);
      missing record defers NAMED (`material_record_missing`).
- [ ] Wire into both `limit is None` sites: generic comparison path
      + `_translate_temporal` reduction branch.
- [ ] Thread `material_context` through discharge_one/discharge_all/
      lazy_loop/orchestrate (si_context precedent), loaded from the
      same `record_paths`.
- [ ] Fixtures both ways: tests/orchestrator/test_translate_materials.py.
- [ ] OUT (named residuals): `design_life` bare-ident refs,
      `w.filler.sigma_allow` 3-segment refs, `build_volume.x`
      constructor-kwarg refs, `partitions.app.size`.

### Class 5 -- rule-engine input channel (WO-28 registry), Rust
- [ ] `traces` board domain: measure vocabulary + population from
      `layout.realized` RealizedInput (RoutedSegment width/length),
      so `jlc_2l.trace_width` evaluates at realized tier.
- [ ] `.where(<field>=<word>)` equality filter over entity measures
      (unblocks `vbus_inrush_protection`).
- [ ] Rust tests both ways (populated evaluates, unpopulated defers).
- [ ] OUT: vias (drill/annular ring) -- RealizedLayout carries no
      via list; exact shape escalated as WO112-F4. `buses`
      (length_spread) -- no bus-group vocabulary exists; escalated
      WO112-F5. `test_point_probe_clearance` -- needs pad-geometry
      clearance extraction; named residual.

### Class 3 -- D102 StaysWithin window -> scalar request, Python
- [ ] `_translate_temporal` ClaimForm6: `mask=floor(<qty> - <qty>)`
      (and `ceiling`) literalizes to a scalar request (limit = the
      resolved level; window duration rides as input); named masks
      keep the named deferral, now naming the mask ref.
- [ ] Verify two-sided-window discharge model existence; report
      addressable-vs-dischargeable honestly in close-out.
- [ ] Fixtures both ways.

### Class 1 -- named 2(c) diagnostics (F131.1/F131.2), Python
- [ ] Temporal-state/event form (`within <t> after <event>:
      state/f(...) = <v>` / `op = <state>`): named deferral
      `temporal_event_form_excluded` citing F131.1 + reopen.
- [ ] Quantified bit-field legality (`forall v in bits(...)`):
      named deferral `bitfield_legality_form_excluded` citing
      F131.2 + the D202 reopen.
- [ ] Fixtures: both fire on corpus shapes; non-matching forms
      still reach the generic deferral.

### Class 4 -- fluid record-chain walk (F131.4 rule), Python
- [ ] Probe result: medium `props: registry(<key>)` chains exist in
      all six deferring designs; the records themselves do NOT
      exist on disk (Class D half, WO-113) and translate never
      walks the chain (Class E half, here).
- [ ] Land the walk: fluid context (flownet payloads + fluid
      property records off record paths); `_translate_fluid_dp`
      resolves `density_kgm3` through medium.records; deferral then
      names only the truly-missing inputs (or the missing record).
- [ ] Fixtures both ways (record present resolves; absent defers
      naming the key). Per-claim Class D/E split table in close-out.

### Close-out
- [ ] make install + make check green (foreground).
- [ ] Per-class before/after fleet counts.
- [ ] Escalations: WO112-F4 (RealizedLayout vias shape), WO112-F5
      (bus grouping vocabulary), schema needs: none.
- [ ] Status flip + close-out ledger.
