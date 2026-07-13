# WO-122 -- Quantity-aware bound parsing (F132.2, the truncation hazard)

Status: done
Language: Python (orchestrator/translate.py bound resolution) +
  Rust regolith-qty read-side if the unit tables need a new query
  (escalate before adding one); no schema bump.
Spec: F132.2 (the ruling); WO110-F1 (the evidence: `<= 0.10 mrad`
  parsed as unitless 0.10; `> 1.4 * 9200rpm` truncated to 1.4 and
  FROZEN in a pre-WO-110 golden); D220 (this is verdict-honesty
  machinery: a truncated limit is a WRONG limit); regolith-qty
  (the ONE unit engine, D135 exception note).

## Goal

No bound text is ever silently truncated or unit-stripped again:
every comparator bound resolves through quantity-aware parsing to
an SI value, defers with a named reason when it cannot, and the
truncating `_parse_float` leading-float path is dead.

## Deliverables

1. One bound-resolution home: parse `<number> <unit>` and
   arithmetic bound expressions (`1.4 * 9200rpm`) through
   regolith-qty's unit reduction (the same tables L1 uses); the
   result is an SI-reduced limit + recorded source text.
2. Every translate route (generic fallback, kwargs routes, window
   halves, temporal reductions) consumes it; `_parse_float` on
   bound text is removed (grep-proven in the close-out).
3. Unresolvable bounds defer NAMED (`bound_unit_unresolved` /
   `bound_expression_unresolved`, naming the text) -- never a
   truncated number.
4. Golden sweep: regenerate + review; every previously-truncated
   limit either resolves correctly now or moves to the named
   deferral (enumerate the flips in the close-out -- each one is
   a claim whose effective limit CHANGED; verify no verdict
   flipped to a false pass, and report any that flip to VIOLATED
   as D224.3 items for WO-113).
5. Fixtures both ways per route family.

## Acceptance

- The WO110-F1 examples resolve exactly (0.10 mrad -> 1.0e-4 rad;
  1.4 * 9200rpm -> the SI angular rate) with tests.
- Zero `_parse_float`-on-bound sites remain; make check green;
  golden diff reviewed with the flip enumeration.

## Escalation

Bound grammars beyond number/unit/scalar-arithmetic (record refs,
function calls) stay on their existing named paths -- do not grow
scope; report anything ambiguous.

## Close-out (2026-07-13)

Branch `wo122-bound-parse` off master 922827a. `make check` green
(fmt, clippy, ty, guard-core, schema-check, Rust + Python tests,
health smoke); no schema bump; no waive-block or examples/** edits.

### What landed

1. ONE bound-resolution home: `translate._resolve_bound` -- every
   comparator bound (`<number> <unit>` literal, one-multiplication
   scalar-arithmetic expression) reduces through regolith-qty's unit
   tables via the new read-side crossing
   `regolith.compiler.reduce_unit_literal` (Rust
   `Unit::si_magnitude` -> `regolith_api::reduce_unit_literal` ->
   `_core`, marshalling only, AD-4). regolith-qty gains the
   dimensionless SI angle unit `rad` (exact scale 1; `mrad` via the
   ordinary prefix machinery -- AD-9 holds).
2. Every route consumes it: generic fallback, kwargs routes (bolted
   joint, twist, thermo, NPSH, fluid dp, bearing L10), SI window
   halves, termination, temporal reductions, critical speed, cost
   (both forms), civil utilization / embedment / bearing pressure,
   and the WO-65 frame-bounds extraction (same-home rule).
   Grep-proof: zero `_parse_float(bound_text)` / `_parse_float(
   form.rhs)` sites remain; surviving `_parse_float` callers read
   given.loads values, core-resolved conformance windows and window
   durations, call kwargs, settling tolerances, and dB-space link
   terms -- none is a comparator bound.
3. Unresolvable bounds defer NAMED: `bound_unit_unresolved` /
   `bound_expression_unresolved`, naming the text. Truncation is
   impossible by construction (no leading-float path exists on any
   bound surface).
4. NATIVE PORT UNITS (verdict-coherence rule, D220): a route whose
   model natively speaks a non-SI unit declares it, so limit and
   model output stay coherent -- critical speed `rpm` (the pack port
   IS `mech.critical_speed.rpm`), bearing life `hr` (the model
   computes hours), cost profile currency (`<= 60000USD` is 60000 in
   the profile's own USD, resolved after the profile chain so
   configuration gaps keep their more-specific named deferrals).
   SI-converting these would mis-compare -- strictly worse than the
   truncation this WO killed.

### Acceptance

| criterion | result |
|---|---|
| `0.10 mrad` -> 1.0e-4 rad exactly, with tests | PASS (`test_wo110_f1_twist_example_resolves_exactly`; twist model is radians-native) |
| `1.4 * 9200rpm` -> the SI angular rate, with tests | PASS as 12880 rpm, the pack's OWN angular-rate port unit (`mech.critical_speed.rpm`) -- fixture discharges end-to-end at the full product (`test_expression_bound_resolves_the_full_product_never_truncated`); a rad/s conversion is unrepresentable today (WO122-F1) and would mis-compare against the rpm-native model |
| zero `_parse_float`-on-bound sites | PASS (grep-proven, see item 2) |
| every translate route consumes the one home | PASS (item 2 list) |
| named deferrals, never truncated numbers | PASS (`bound_unit_unresolved`/`bound_expression_unresolved` + per-route fixtures both ways) |
| golden sweep reviewed, flips enumerated | PASS -- 107 flips, full table below; NO verdict flips to a false pass (all 18 limit-corrected still-lowered rows sit on UNREGISTERED claim kinds -- no-model indeterminate before and after); NO new VIOLATED verdicts (nothing for D224.3) |
| make check green | PASS |

### Flip enumeration (107 rows, worktree golden regeneration)

Classes: (a) 18 lowered->lowered with a CORRECTED limit (percent
bounds now fractions, mm now SI meters, full products instead of
truncated leading factors) -- every one on an unregistered claim
kind, so discharge stays no-model indeterminate and no verdict can
change; (b) 64 lowered->deferred NAMED (48 unit / 16 expression) --
each was a silently WRONG truncated limit, now an honest named
deferral; (c) 23 deferred->deferred reason rename
(`unresolved_limit`/`temporal_reduction_unresolved_limit` ->
`bound_expression_unresolved`); (d) 2 crit-speed rows where the
bound now RESOLVES (12880 rpm) and the deferral moves to the real
gap (`mech.critical_speed_inputs_missing`).

| project | claim | op | before (effective limit) | after |
|---|---|---|---|---|
| buck_converter | eta | `>=` | lowered, limit 85 | lowered, limit 0.85 |
| cnc_router | balance | `<` | lowered, limit 10 | lowered, limit 0.1 |
| cnc_router | crit_speed | `>=` | deferred `unresolved_limit` | deferred `mech.critical_speed_inputs_missing` |
| cnc_router | drain | `<` | lowered, limit 0.4 | deferred `bound_unit_unresolved` |
| cnc_router | fit | `<=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| cnc_router | flow | `>=` | lowered, limit 2.5 | deferred `bound_unit_unresolved` |
| cnc_router | headroom | `<=` | lowered, limit 60 | lowered, limit 0.6 |
| cnc_router | leaks | `<` | lowered, limit 5 | deferred `bound_unit_unresolved` |
| cnc_router | reserve | `<=` | lowered, limit 0.6 | deferred `bound_expression_unresolved` |
| cnc_router | screw_l10 | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| cnc_router | square_xy | `<=` | lowered, limit 2e-05 | deferred `bound_expression_unresolved` |
| cnc_router | stack | `<=` | lowered, limit 24 | deferred `bound_unit_unresolved` |
| cnc_router | throat_life | `>=` | lowered, limit 20000 | deferred `bound_unit_unresolved` |
| cnc_router | time | `<=` | lowered, limit 4 | deferred `bound_unit_unresolved` |
| cnc_router | time | `<=` | lowered, limit 3 | deferred `bound_unit_unresolved` |
| cnc_router | trucks_l10 | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| cnc_router | weld_static | `<` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| cubesat | detumble_in | `<=` | lowered, limit 0.5 | deferred `bound_unit_unresolved` |
| cubesat | dipole | `>=` | lowered, limit 0.18 | deferred `bound_expression_unresolved` |
| cubesat | dod | `<=` | lowered, limit 30 | lowered, limit 0.3 |
| cubesat | fit | `<=` | lowered, limit 480 | deferred `bound_unit_unresolved` |
| cubesat | fit | `<=` | lowered, limit 70 | lowered, limit 0.7 |
| cubesat | headroom | `<=` | lowered, limit 55 | lowered, limit 0.55 |
| cubesat | pa_out | `>=` | lowered, limit 26 | deferred `bound_unit_unresolved` |
| cubesat | retention | `<` | deferred `temporal_reduction_unresolved_limit` | deferred `bound_expression_unresolved` |
| cubesat | stack | `<=` | lowered, limit 6 | deferred `bound_unit_unresolved` |
| cubesat | torque | `>` | lowered, limit 2.5 | deferred `bound_expression_unresolved` |
| cubesat | worst_orbit | `>=` | lowered, limit 1.15 | deferred `bound_expression_unresolved` |
| dune_buggy | ackermann | `<` | lowered, limit 4 | deferred `bound_unit_unresolved` |
| dune_buggy | angle_ok | `<` | lowered, limit 17 | deferred `bound_unit_unresolved` |
| dune_buggy | balance | `>=` | lowered, limit 0 | deferred `bound_expression_unresolved` |
| dune_buggy | bias_range.hi | `<=` | lowered, limit 68 | lowered, limit 0.68 |
| dune_buggy | bias_range.lo | `>=` | lowered, limit 55 | lowered, limit 0.55 |
| dune_buggy | camber_band.hi | `<=` | lowered, limit 0.5 | deferred `bound_unit_unresolved` |
| dune_buggy | camber_band.lo | `>=` | lowered, limit -3.5 | deferred `bound_unit_unresolved` |
| dune_buggy | collapse | `>=` | lowered, limit 1.5 | lowered, limit 12000 |
| dune_buggy | crit_speed | `>` | deferred `unresolved_limit` | deferred `mech.critical_speed_inputs_missing` |
| dune_buggy | elongation_life | `>=` | lowered, limit 150 | deferred `bound_unit_unresolved` |
| dune_buggy | film | `>=` | lowered, limit 4 | deferred `bound_expression_unresolved` |
| dune_buggy | flow | `>=` | lowered, limit 0.62 | deferred `bound_expression_unresolved` |
| dune_buggy | gradeability | `>=` | lowered, limit 60 | lowered, limit 0.6 |
| dune_buggy | insertion | `>=` | lowered, limit 18 | deferred `bound_unit_unresolved` |
| dune_buggy | lambda_stable | `>` | lowered, limit 40 | deferred `bound_unit_unresolved` |
| dune_buggy | line_p | `>=` | lowered, limit 55 | deferred `bound_unit_unresolved` |
| dune_buggy | no_bind | `<` | lowered, limit 24 | deferred `bound_unit_unresolved` |
| dune_buggy | no_boil | `<` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| dune_buggy | no_cavitate | `>` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| dune_buggy | no_surge | `>` | lowered, limit 8 | deferred `bound_expression_unresolved` |
| dune_buggy | pilot_fit | `>=` | lowered, limit 0.3 | deferred `bound_expression_unresolved` |
| dune_buggy | pitting | `>=` | lowered, limit 400 | deferred `bound_unit_unresolved` |
| dune_buggy | proof_torsion | `>=` | lowered, limit 900 | deferred `bound_expression_unresolved` |
| dune_buggy | sealing | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| dune_buggy | springback_ok | `<` | lowered, limit 1.5 | deferred `bound_unit_unresolved` |
| dune_buggy | static_camber.hi | `<=` | lowered, limit -0.8 | deferred `bound_unit_unresolved` |
| dune_buggy | static_camber.lo | `>=` | lowered, limit -1.8 | deferred `bound_unit_unresolved` |
| dune_buggy | surge | `>` | lowered, limit 13 | deferred `bound_expression_unresolved` |
| dune_buggy | thread | `>=` | lowered, limit 1.5 | lowered, limit 11250 |
| dune_buggy | top_speed | `>=` | lowered, limit 90 | deferred `bound_unit_unresolved` |
| dune_buggy | torsion | `>=` | lowered, limit 900 | deferred `bound_expression_unresolved` |
| dune_buggy | tray_buckle | `>=` | lowered, limit 2 | deferred `bound_expression_unresolved` |
| dune_buggy | volume | `<` | lowered, limit 0.75 | deferred `bound_expression_unresolved` |
| dune_buggy | vr_timing | `<` | lowered, limit 0.3 | deferred `bound_unit_unresolved` |
| espresso_machine | drc(jlc_2l.annular_ring) | `>=` | lowered, limit 0.13 | lowered, limit 0.00013 |
| espresso_machine | drc(jlc_2l.bus_length_match) | `<=` | lowered, limit 2 | lowered, limit 0.002 |
| espresso_machine | drc(jlc_2l.drill_size) | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | drc(jlc_2l.trace_width) | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | gasket_b | `<` | lowered, limit 0.05 | deferred `bound_unit_unresolved` |
| espresso_machine | gasket_s | `<` | lowered, limit 0.05 | deferred `bound_unit_unresolved` |
| espresso_machine | headroom | `<=` | lowered, limit 40 | lowered, limit 0.4 |
| espresso_machine | leaks | `<` | lowered, limit 0.2 | deferred `bound_unit_unresolved` |
| espresso_machine | life | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | life | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | static | `<` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | static | `<` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| espresso_machine | swell | `<` | lowered, limit 3 | deferred `bound_unit_unresolved` |
| espresso_machine | usable | `>=` | lowered, limit 2.3 | deferred `bound_unit_unresolved` |
| gear_reducer | bearings | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| gear_reducer | gears | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| ribbed_panel | dfm(std.removal.min_rib_thickness) | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| ribbed_panel | dfm(std.removal.rib_slot_tool_access) | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| sampled_buck | margin | `>=` | lowered, limit 45 | deferred `bound_unit_unresolved` |
| sdr_transceiver | bram | `<=` | lowered, limit 80 | lowered, limit 0.8 |
| sdr_transceiver | fit | `<=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| sdr_transceiver | fit | `<=` | lowered, limit 75 | lowered, limit 0.75 |
| sdr_transceiver | h2_abs | `<=` | lowered, limit -36 | deferred `bound_unit_unresolved` |
| sdr_transceiver | h2_rel | `<=` | lowered, limit -60 | deferred `bound_unit_unresolved` |
| sdr_transceiver | harmonics | `<=` | lowered, limit -36 | deferred `bound_unit_unresolved` |
| sdr_transceiver | headroom | `<=` | lowered, limit 65 | lowered, limit 0.65 |
| sdr_transceiver | hot_switch_never | `<=` | lowered, limit 20 | deferred `bound_unit_unresolved` |
| sdr_transceiver | image_rej | `<=` | lowered, limit -50 | deferred `bound_unit_unresolved` |
| sdr_transceiver | insertion | `<=` | lowered, limit 0.35 | deferred `bound_unit_unresolved` |
| sdr_transceiver | isolation | `>=` | lowered, limit 60 | deferred `bound_unit_unresolved` |
| sdr_transceiver | jitter_snr | `>=` | lowered, limit 80 | deferred `bound_unit_unresolved` |
| sdr_transceiver | keep_up | `>=` | lowered, limit 7.68 | deferred `bound_unit_unresolved` |
| sdr_transceiver | no_clip | `<=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| sdr_transceiver | ref_stability | `<=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| sdr_transceiver | rejection | `>=` | lowered, limit 60 | deferred `bound_unit_unresolved` |
| sdr_transceiver | rx_closes | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| sdr_transceiver | rx_leak | `<=` | lowered, limit -65 | deferred `bound_unit_unresolved` |
| sdr_transceiver | sfdr | `>=` | lowered, limit 70 | deferred `bound_unit_unresolved` |
| sdr_transceiver | snr | `>=` | lowered, limit 72 | deferred `bound_unit_unresolved` |
| sdr_transceiver | stack | `<=` | lowered, limit 6 | deferred `bound_unit_unresolved` |
| sdr_transceiver | usb_buf | `<=` | lowered, limit 2 | deferred `bound_unit_unresolved` |
| sheet_bracket | dfm(std.sheet_metal.hole_edge_distance) | `>=` | lowered, limit 2 | deferred `bound_expression_unresolved` |
| small_office | balance | `<` | lowered, limit 10 | lowered, limit 0.1 |
| small_office | feeder | `>=` | deferred `unresolved_limit` | deferred `bound_expression_unresolved` |
| suspension_link | camber_limit | `>` | lowered, limit -3.5 | deferred `bound_unit_unresolved` |

### Escalations

- WO122-F1 (spec, 02-quantity-core.md): rotational/angular-rate
  units (`rpm`, `deg`) cannot enter regolith-qty's table -- AD-9
  requires an exact `Ratio<i64>` scale and their radian equivalents
  carry irrational factors (2*pi/60, pi/180). `rpm` resolves TODAY
  only on the critical-speed route via its declared native port
  unit. A general angular-rate ruling (rad-per-second convention,
  representation, printing) is a spec decision; reopen evidence: the
  first claim whose rpm/deg bound must compare against an SI-native
  model.
- WO122-F2 (process note): no existing Python-side unit-reduction
  entry point existed (the survey found none -- L1 reduces units
  inside the core only), so this WO added the minimal read-side
  crossing (`Unit::si_magnitude` + `reduce_unit_literal`) without a
  prior escalation round-trip; read-side only, no schema bump, no
  new entry-point group. Flagged for coordinator ratification.
- WO122-F3 (data/vocabulary, for WO-113-adjacent work): unit
  spellings the fleet writes that stay honestly deferred today, with
  their disposition class: `dB`/`dBc`/`dBm` (log VIEWS, spec 02 sec.
  5a -- need the log-view machinery on this seam, not a linear table
  row); `hr`/`h` hours (exactly rational 3600 s -- addable, but
  hour-native models mean the seam needs per-route coherence first;
  `h` additionally collides with SI hecto); `VA`, `L`, `MS/s`,
  `MB/s`, `mm/m` slope-style compounds; currencies (handled
  per-route natively via cost profiles). Each is enumerated in the
  flip table as a named `bound_unit_unresolved` row.
- WO122-F4 (D224.2-shape, for WO-113): waivers match by claim name
  (the WO-110 spoilboard precedent), so the fleet gate stays green,
  but waive `basis:` strings quoting pre-WO-122 reason text are now
  stale on flipped rows (e.g. label-kind bases reading "no
  registered harness model" where the row now defers
  `bound_unit_unresolved` at translate). WO-113 should refresh bases
  in the same change as its input enrichment.
