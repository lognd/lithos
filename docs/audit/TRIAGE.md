# Audit triage (cycle 11)

Disposition of the spec-conformance findings in this directory
(`frontend-conformance.md`, `backend-conformance.md`). Fixed items
landed with tests; deferred items carry greppable `TODO(<id>)` markers
at the code site.

## Fixed (this cycle, with regression tests)

- **FE-5 (HIGH-ish, wrong result)** -- offset-unit tolerances no longer
  apply the absolute +273.15 offset (`convert_delta`, scale-only for
  deltas). Test: `interval::tests::plus_minus_offset_unit_tolerance_is_a_delta_not_absolute`.
- **FE-2 (MEDIUM, INV-21)** -- the `Cause` enum now carries all eight
  INV-21 provenance kinds (added `Extern`, `DerivedIntent`, `Policy`).
  Test: `resolution::tests::all_eight_inv21_causes_render_and_round_trip`.

## Deferred with tracked markers (need a feature/architecture pass)

- **FE-1 (HIGH)** -- logarithmic-unit views (`dB`/`dBm`, substrate/02
  sec. 5a) are unimplemented, so `dBm + dBm` is not caught at L1
  (INV-17). This is a numeric subsystem (stored-linear log views + one
  reference-legality check), sized for its own work order, not a patch.
  Marker: `rockhead-qty` unit table / `checks.rs`. -> new WO recommended.
- **BE-1 (HIGH, INV-1)** -- obligation/evidence key omits the harness
  model-registry version; a model upgrade can silently reuse stale
  cached evidence. Registry versions are Python-side (AD-1); the fix
  threads the version into the evidence-cache key at discharge time.
  Marker: `TODO(BE-1)` on `Obligation` (obligation.rs).
- **BE-2 (HIGH, INV-1)** -- `given:` is unconditionally empty in
  lowering, so claims differing only in materials/loads hash
  identically. Blocked on the materials/loads grammar (WO-05 residual).
  Marker: `TODO(BE-2)` in `claims.rs`. Same root cause as the recorded
  WO-19 partial-lowering (resolutions=0); its INV-1 mutation-sensitivity
  test stays `xfail` until this lands.
- **BE-3 / BE-4 (MEDIUM)** -- per-subject INV-20 gating and INV-11
  monomorphization expansion are absent in `rockhead-lower`. Recorded as
  WO-19 partial cuts (WO-19 status note; INV-20 xfail reason names the
  missing gate).

## Discovered (cycle 11): parser sibling-ejection desync

The 31 residual parse diagnostics over cubesat are NOT top-level garbage
-- they are indented body statements (`require X:`, `budget X:`,
`policy:`, `forbid/prefer/minimize/margin`, and even `interface/board/
computer` decls) that reached the top-level error path because a
`parse_stmt_block` exited early and ejected its remaining siblings to
the file level. ~19 of 31 are in `kestrel.cupr`, i.e. one early desync
cascades through the rest of that file. This LOSES obligations (the
ejected `require` blocks never lower), so it must NOT be masked by
treating keyword-led top-level lines as opaque (that would hide the
lost lowering). Minimal repros with a deep `during` continuation +
comments + blank line before a sibling did NOT reproduce it, so the
exact trigger is still unidentified -- needs methodical layout/parser
dedent-accounting debugging (a WO-05 hardening pass). Tracked, not
fixed.

## MEDIUM / LOW backlog

The remaining FE/BE MEDIUM and LOW findings (finer vocabulary/spelling
and doc items) are enumerated in the two findings files with code
locations; none are soundness bugs. Address opportunistically as the
relevant WOs are completed.
