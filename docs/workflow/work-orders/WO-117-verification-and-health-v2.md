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
- [ ] `tests/qa/capture.py`: `Model.discharge` capture context
      (request inputs/limit/payload bytes + evidence
      value/eps/margin/status)
- [ ] oracles (fresh from cited sources; NO harness-models/feldspar
      imports): mech (ISO 281 L10h, VDI 2230 clamp, E-B cantilever,
      simple-span UDL, interaction utilization, Shigley crit speed);
      civil/fluid/elec (bearing pressure, Darcy dp, lumped thermal,
      series termination); dfm (stock/tool fit from payload JSON);
      cam (fresh G-code parser + 4 checks); cost (BOM/takeoff
      summation); structural (workload identity, conformance
      refinement, margin-rule recheck for hdl_build)
- [ ] `tests/qa/test_spotcheck.py`: per-family sample + recompute +
      tolerance compare; structural independence assertion; every
      sheet verdict is `discharged`
- [ ] family table (family, oracle source, samples, max delta,
      tolerance) recorded in the close-out

Deliverable 2 -- census v2 (D220.3):

- [ ] one-home waiver classifier (D220.2 classes a/b/c/d from the
      F131/F132/F133 basis vocabulary; unclassifiable = finding)
- [ ] `ProjectCensus` gains `waived_by_class` + `deferred`;
      `discharged` tightened to "model-backed resolved"
      (`evidence.status == discharged`), lockstep with `calc.py`
      (WO117-F1: the pin-unmatched indeterminate double-count)
- [ ] fleet leg diffs PER-CLASS: discharged->waived move or
      out-of-class waiver = FAIL with a named row
- [ ] census golden + calc-book goldens regenerated via tooling,
      diff reviewed

Deliverable 3 -- health consistency additions:

- [ ] fleet leg records each shipped package's audit-index balance
      (WO-114 `balanced()`; zero unexplained rows) in its cache;
      consistency sub-check `calc_books` gates on it fleet-wide
- [ ] consistency sub-check `demos_coverage`: every D222 feature
      family maps to a live pack in `demos.run_all.DEMOS`

Deliverable 4 -- final refresh + close:

- [ ] full `make check` green (foreground)
- [ ] full `make health` PASS (foreground; final fleet-wide
      release-tier evidence refresh)
- [ ] close-out ledger: F130 baseline vs final (obligations /
      discharged / per-class waived / deferred / zero-discharge
      count)
- [ ] Status flip per criteria

Deliverable 5 -- docs touch-up (coordinator-scoped):

- [ ] `docs/guide/12-graphite.md` "still in flight": WO-G5/G7 merged
      (graphite ledgers read-only), G8 the only open one
