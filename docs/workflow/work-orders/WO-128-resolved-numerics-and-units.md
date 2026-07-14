# WO-128 -- Resolved numerics + units on the evidence surface (closes WO117-F2; F144)

Status: open
Language: Python (orchestrator translate/discharge evidence surface,
  backends/calc.py, backends/harness_pack.py); Rust ONLY if the
  claim's declared threshold genuinely loses its unit token in
  lowering (investigate first, report before touching crates).
Spec: F144 (the evidence: bring-up ships zero numbers); charter 41
  sec. 2 + D238.4 (every printed number carries its unit and traces
  to the payload); charter 40 sec. 3 + D224 (an expectation without
  a value is a named absence -- honest, but a value we COULD resolve
  and did not is a defect, not honesty); WO-114 (calc book -- the
  evidence source); WO117-F2 (the seed item this closes); WO-122
  (the bound-parse precedent: read-side qty crossing, ratified).

## Goal

Every discharged obligation's evidence carries the RESOLVED numeric
and its unit, so calc sheets print `14875.2 N` (not `14875.2`) and
the bring-up harness prints `expect 3.30 V +/- 0.15 V` (not a named
absence) wherever the toolchain genuinely knows the number.

## Why now (F144)

Cycle 36 shipped the bring-up machinery (WO-125/126) and the
professional sheet renderers (WO-123) -- and both landed on the same
wall: the values are there, the UNITS are not, so honest code either
prints a bare number (refused: a technician cannot act on `45`) or
degrades to `no_verified_expectation`. Today mainboard_mx's harness
pack has SIX taps and ZERO printed expectations. The machinery is
correct and the honesty is correct; the evidence surface is the gap.

## Deliverables

1. INVESTIGATE FIRST, then report before implementing: trace one
   discharged claim (mainboard's `refclk_z0.lo`, the calc book's
   `base_bolts` VDI-2230 sheet) end to end -- claim text -> lowered
   obligation (`rhs`, bound) -> model call -> `Evidence` -> calc
   sheet -- and record exactly WHERE the unit token is dropped and
   whether the resolved value is present. The fix belongs at the
   first surface that loses it, not downstream. Post the trace in
   your close-out ledger regardless of where it lands.
2. Units on the evidence surface: the discharged value, the margin,
   and the bound each carry their unit (the `regolith-qty` unit is
   already the ONE home -- reuse `Unit`/`si_magnitude`, never a new
   unit table, never a renderer-side lookup).
3. Calc sheets (`backends/calc.py`): Inputs rows, Result value, and
   margin print value + unit. Rows whose unit is genuinely
   unresolvable print an explicit `(unitless)` marker and are
   COUNTED in the sheet's own audit line -- no silent bare numbers.
4. Harness expectations (`backends/harness_pack.py`): every
   calc-sheet-backed tap prints its expected value + unit (+ window
   where the claim is a window claim). The WO-126 refusal rule
   (populated value implies units) stays; what changes is that rows
   now HAVE units. Rows still unresolvable stay named absences with
   their reason.
5. Regression tests at each surface; goldens regenerated (reviewed).
6. Census/verdict math UNTOUCHED (D206/D220.1) -- this WO adds no
   discharge, changes no verdict, and must prove it (census equality
   test before/after).

## Acceptance

- mainboard_mx's debug harness pack prints at least one REAL
  expected value with units, and every remaining absence names a
  reason that is not "unit_unresolved" (or, if some legitimately
  remain, they are enumerated with evidence in the close-out).
- demo15's calc sheets print units on every Inputs row, the Result
  value, and the margin (visually inspected; the coordinator
  re-inspects at integration, D238.3).
- Census golden byte-identical (no verdict moved).
- `make check` + `make health` green.

## Escalation

If the unit is dropped in RUST lowering (the claim's declared
threshold loses its unit token crossing into the obligation), STOP
and report with the trace from deliverable 1 -- the coordinator
adjudicates whether the fix is a Rust change and whether it needs
the D239 schema window (which is currently CLOSED and unspent).
