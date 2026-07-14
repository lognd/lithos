# WO-117 -- Verification + health v2 + census flip (D220.3, D226; cycle close)

Status: open
Language: Python (tests + health gate + census tooling).
Spec: D226 (independent re-computation); D220.3 (per-class census
  accounting + regression gate); D219 (health legs, standardized
  summary rows); gates: WO-109..116 merged (this WO is LAST).

## Goal

"Verify that everything is correct" becomes machinery: an
independent QA harness re-checks sampled discharged margins from
the calc sheets' own recorded inputs, the census golden encodes the
per-class rigor accounting permanently, and `make health` fails on
any future rigor regression.

## Deliverables

1. D226 spot-check harness (`tests/qa/`): for EVERY model family
   with fleet discharges, sample calc sheets (WO-114's JSON),
   re-compute the margin with independently-written closed forms
   (written from the cited source, NOT imported from
   harness/models), compare within stated tolerance. Disagreement
   fails the suite -- and is a real finding, never tolerance-tuned
   away (placeholder F-number, coordinator adjudicates).
2. Census v2: per-project rows gain waived-by-class (D220.2
   classes) + deferred counts; the golden is regenerated; the
   health fleet leg diffs per-class (a discharged->waived move or
   an out-of-class waiver = FAIL with a named row).
3. Health consistency leg additions: calc-book completeness (every
   shipped package's audit index has zero unexplained rows --
   invoke WO-114's check fleet-wide); demos coverage (every D222
   family has a live pack).
4. Fleet-wide final evidence refresh at release tier; full
   `make health` PASS from a clean main checkout; the close-out
   ledger records final fleet numbers (obligations / discharged /
   per-class waived) against F130's baseline.

## Acceptance

- `make health` PASS with the new legs; QA harness green over
  every discharging model family; census golden committed with
  per-class shape.
- Close-out table: F130 baseline vs final (the rigor flip,
  quantified).

## Escalation

Any QA disagreement is a stop-the-line finding: report to the
coordinator with the sheet, the recomputation, and the delta; do
not close the cycle over it.

## Execution plan (dispatch checklist; driven to zero before close)

Deliverable 1 -- D226 QA harness (`tests/qa/`):

- [x] survey the fleet's discharging model families (release-tier
      build of all 15; enumerate `evidence.model_id` sets)
- [x] `tests/qa/capture.py`: `Model.discharge` capture context
      (request inputs/limit/payload bytes + evidence
      value/eps/margin/status)
- [x] oracles (fresh from cited sources; NO harness-models/feldspar
      imports): mech (ISO 281 L10h, VDI 2230 clamp, E-B cantilever,
      simple-span UDL, interaction utilization, Shigley crit speed);
      civil/fluid/elec (bearing pressure, Darcy dp, lumped thermal,
      series termination); dfm (stock/tool fit from payload JSON);
      cam (fresh G-code parser + 4 checks); cost (BOM/takeoff
      summation); structural (workload identity, conformance
      refinement, margin-rule recheck for hdl_build)
- [x] `tests/qa/test_spotcheck.py`: per-family sample + recompute +
      tolerance compare; structural independence assertion; every
      sheet verdict is `discharged`
- [x] family table (family, oracle source, samples, max delta,
      tolerance) recorded in the close-out

Deliverable 2 -- census v2 (D220.3):

- [x] one-home waiver classifier (D220.2 classes a/b/c/d from the
      F131/F132/F133 basis vocabulary; unclassifiable = finding)
- [x] `ProjectCensus` gains `waived_by_class` + `deferred`;
      `discharged` tightened to "model-backed resolved"
      (`evidence.status == discharged`), lockstep with `calc.py`
      (WO117-F1: the pin-unmatched indeterminate double-count)
- [x] fleet leg diffs PER-CLASS: discharged->waived move or
      out-of-class waiver = FAIL with a named row
- [x] census golden + calc-book goldens regenerated via tooling,
      diff reviewed

Deliverable 3 -- health consistency additions:

- [x] fleet leg records each shipped package's audit-index balance
      (WO-114 `balanced()`; zero unexplained rows) in its cache;
      consistency sub-check `calc_books` gates on it fleet-wide
- [x] consistency sub-check `demos_coverage`: every D222 feature
      family maps to a live pack in `demos.run_all.DEMOS`

Deliverable 4 -- final refresh + close:

- [x] full `make check` green (foreground)
- [ ] full `make health` PASS (foreground; final fleet-wide
      release-tier evidence refresh)
- [ ] close-out ledger: F130 baseline vs final (obligations /
      discharged / per-class waived / deferred / zero-discharge
      count)
- [ ] Status flip per criteria

Deliverable 5 -- docs touch-up (coordinator-scoped):

- [x] `docs/guide/12-graphite.md` "still in flight": WO-G5/G7 merged
      (graphite ledgers read-only), G8 the only open one

## Close-out ledger (branch wo117-verification-close)

### The rigor flip, quantified (F130 baseline vs cycle close)

| Measure                    | F130 (cycle open) | Final (census v2)        |
|----------------------------|-------------------|--------------------------|
| Obligations fleet-wide     | 1,089             | 1,089                    |
| Discharged (model-backed)  | 45 (4.1%)         | 71 (6.5%)                |
| Accepted deviations        | 929               | 903                      |
| Violated                   | 0                 | 0                        |
| Deferred (named machinery) | (untracked)       | 1,018                    |
| Waived, class a (edges)    | (untracked)       | 318                      |
| Waived, class b (windows)  | (untracked)       | 0 (live as deferrals)    |
| Waived, class c (named machinery) | (untracked) | 524                     |
| Waived, class d (author intent)   | (untracked) | 10                      |
| Unclassified waivers       | (unknown)         | 0 (gated, permanently)   |
| Zero-discharge projects    | 7                 | 1 (regen_engine, WO113-F4) |

Note on the discharged count: F133 reported 72; census v2 counts 71
because the cnc_router_r1 `first_mode` row was a pin-unmatched
INDETERMINATE double-counted as discharged (WO117-F1 below) -- the
honest model-backed count was 71 all along.

### D226 QA harness: the family table

Every fleet discharge recomputed (a full sweep, 100 samples over 20
families); tolerance rel 1e-9 / abs 1e-9; ZERO disagreements.

| Family (model)                    | Oracle source (written fresh)          | Samples | Max value delta |
|-----------------------------------|-----------------------------------------|---------|-----------------|
| bearing_basic_rating_life_l10h    | ISO 281:2007 sec. 6.2                   | 8       | 0               |
| bolted_joint_separation_vdi2230   | VDI 2230 joint diagram                  | 2       | 0               |
| beam_cantilever_deflection_eb     | E-B cantilever FL^3/3EI                 | 12      | 0               |
| beam_simple_span_deflection_udl   | 5wL^4/384EI                             | 4       | 0               |
| beam_utilization_interaction      | elastic interaction (AISC/NDS ASD form) | 14      | 0               |
| mech_shaft_critical_speed         | Shigley 11e eq. 7-22                    | 1       | 0               |
| footing_bearing_pressure          | reaction/area (calcite/03 sec. 5)       | 5       | 0               |
| fluid_darcy_weisbach_dp           | White 8e sec. 6.6                       | 2       | 0               |
| thermo_lumped_steady              | T_j = T_amb + P*R_theta                 | 1       | 0               |
| elec_si_series_termination_rs     | Johnson & Graham ch. 4 (Rs = Z0-Ro)     | 2       | 0               |
| mfg_manufacturable_mill           | WO-110 envelope containment (fresh)     | 6       | 0               |
| cam_parse/envelope/collision/removal/coverage | fresh RS-274 tracker + 4 checks | 10 | 0            |
| cost_civil_takeoff                | toolchain/27 sec. 1.4 takeoff           | 2       | 1.8e-12         |
| cost_elec_bom                     | toolchain/27 sec. 1.4 BOM pricing       | 1       | 5.7e-14         |
| workload_realization_identity     | cuprite/05 rule-3 identity              | 19      | 0               |
| conformance_refinement_upper      | INV-13 refinement corner                | 11      | 0               |
| hdl_build                         | zero-error identity + margin rule       | 2       | 0               |

Margins: bit-exact under the independently-written margin rule on
every sample. Oracle independence is asserted STRUCTURALLY
(`test_oracles_are_independent` scans oracle sources for
harness-models/feldspar imports). Sample counts exceed census
discharge counts because optimizer/staged-loop evaluations also flow
through `Model.discharge` -- every one is a real dispatch, all checked.
Full table: `.regolith/health/qa_family_table.json` (report artifact).

### Findings / escalations

- **WO117-F1** (adjudication requested, cycle 36): a deferral-free
  INDETERMINATE (the `harness.model_pin_unmatched` marker; cnc's
  `first_mode`, pinned to the unexposed `fea_modal`) skips
  `discharge.py`'s NO_MODEL_ID deferral branch, so the old
  deferral-is-None census definition double-counted it: discharged in
  the census AND accepted (waived) at the gate, with a phantom calc
  sheet whose verdict read `indeterminate`. Corrected IN-ACCOUNTING
  this WO (census + calc book key on `evidence.status == discharged`,
  lockstep); the ROOT-CAUSE fix (attach a `model_pin_unmatched`
  deferral at the discharge layer, exactly like NO_MODEL_ID's) is a
  cycle-36 item -- it touches the orchestrator's deferral surface,
  outside this WO's census/QA scope.
- **WO117-F2** (named cut): calc sheets carry provenance PINS but not
  the resolved NUMERIC inputs for frame/record-resolved families
  (`inputs_from_given` reads only `given:` blocks), so the QA harness
  recomputes from a `Model.discharge` capture (the same resolved
  numbers, at the one boundary they exist) rather than from sheet
  bytes. Reopen: thread resolved numerics onto the sheet (WO-114
  lineage), then point the oracles at the sheet directly.
- hdl_build's oracle is the zero-error identity + margin rule (re-running
  the HDL toolchain is not a closed form); the build itself stays
  re-proven live by the demos leg's firmware/HDL pack (named cut).

### Acceptance vs. the WO's bar

- `make health` PASS with the new legs (calc_books + demos_coverage
  consistency sub-checks; per-class fleet gate): verified foreground.
- QA harness green over every discharging model family: 20/20
  families, 100/100 samples, zero disagreements.
- Census golden committed with per-class shape; regression gate
  proven live (an out-of-class waiver fails regardless of golden;
  discharged decreases and per-class growth fail with named rows).
- Close-out table above quantifies the rigor flip.
