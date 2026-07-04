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
- **Parser sibling-ejection desync (HIGH, lost obligations)** -- FIXED.
  Root cause: the layout pass does not shift the indent stack for blank
  or comment lines, so a body's `Indent` token can be separated from its
  header by `Newline`/`Comment` trivia (as in `kestrel.cupr`'s
  comment-led `intents:` body). `enter_body_block` and
  `parse_value_and_tail` tested for the body `Indent` after skipping only
  `Whitespace`, so a comment-led body was never entered: it ejected to
  the parent level and its `Indent`/`Dedent` pair desynced the layout
  stack, cascading `parse:0092` errors and dropping the ejected `require`
  blocks (their obligations never lowered). Fix: `enter_body_block` now
  looks PAST `Whitespace`/`Comment`/`Newline` trivia (without consuming
  it) to the body `Indent`, opening the block iff one follows;
  `parse_value_and_tail` delegates to it. Cubesat parse diagnostics
  31 -> 0; whole corpus 79 -> 18 (residual 18 are unrelated mech
  domain-body opaque constructs -- `walk`/`constraints`/`regions`);
  cubesat obligations 21 -> 40 (recovered from the previously-ejected
  `require` blocks). Regression tests:
  `parser::tests::comment_before_body_does_not_eject_the_block` and
  `parser::tests::kestrel_intents_body_retains_require_blocks`; goldens
  `cubesat`/`buck_converter`/`gear_reducer` regenerated.

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

## Resolved (cycle 11): parser sibling-ejection desync

The 31 residual cubesat parse diagnostics were indented body statements
(`require X:`, `budget X:`, `policy:`, ...) ejected to the file level by
an early `parse_stmt_block` exit -- LOSING obligations. FIXED this cycle
(see the Fixed section above): the true trigger was NOT the `hosted_on`
tail nor a layout-pass miscount but a comment-led body -- the layout
pass emits the body `Indent` after the (stack-neutral) comment/blank
lines, and the parser only skipped `Whitespace` before testing for it.
The `kestrel.cupr` line-50 bisection landed on the first comment-led
body in the file (`intents:`, whose header is followed by three comment
lines). Not masked: obligations recovered (cubesat 21 -> 40), diagnostics
31 -> 0.

## MEDIUM / LOW backlog

The remaining FE/BE MEDIUM and LOW findings (finer vocabulary/spelling
and doc items) are enumerated in the two findings files with code
locations; none are soundness bugs. Address opportunistically as the
relevant WOs are completed.
