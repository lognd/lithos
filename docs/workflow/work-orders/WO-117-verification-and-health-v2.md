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
