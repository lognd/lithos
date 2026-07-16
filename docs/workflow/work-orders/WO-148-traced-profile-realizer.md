# WO-148 -- traced-profile Python realizer + citation + artifact-index consumption (D261.4)

Status: open (Depends: WO-147, done)
Language: Python (`python/regolith/orchestrator/programs.py` consumer
  wiring, `python/regolith/backends/artifact_index.py` extension row,
  calc-sheet/citation surfacing). No Rust.
Spec: WO-147's elaborated `.rgp` payload (the resolved-outline shape
  it produces is the interface this WO consumes -- do not re-derive
  or re-validate geometry here, that is WO-147's job, already done);
  `scratch_recon_graphite_cad.md` sec. 7c (calc sheets and the
  artifact index cite the trace: "traced from scan blake3:...,
  calibrated to 0.15mm rms / 0.4mm max over a 9x7 grid
  (homography+radial), traced by <name> 2026-07-16"); D257 ruling 2
  (structured citation shape -- coordinate field names with WO-145's
  `Citation`/`Cited[T]` models, one citation family across stdlib and
  traces); `python/regolith/orchestrator/programs.py:96-183` (the
  existing `Blank`/sheet-part consumption of a promoted profile --
  this WO widens it to accept an elaborated extern profile wherever a
  promoted profile is accepted today); `python/regolith/backends/
  artifact_index.py:105` (the existing `.dxf`-as-text classification
  this WO's new `.rgp`/`traced` family row sits beside).

## Goal

An elaborated `.rgp` profile is usable wherever a promoted profile is
usable today (`Blank`, sheet parts, extrusion sections where free),
its provenance is visible on the calc sheet in the structured-citation
shape, and the artifact index carries a `traced` family row so
graphite's hub renders it richly instead of falling back to a generic
viewer.

## Deliverables

1. `programs.py` widening: accept an elaborated extern profile
   (WO-147's resolved-outline output) at every call site that accepts
   a promoted CARDINAL-walk profile today (`Blank(<profile>,
   thickness=)` at minimum; extrusion sections if the shape is
   compatible without new solver work -- if not, name the gap and
   defer it, do not force-fit).
2. Artifact-index extension row: `.rgp` classified under a new
   `traced` family (not generic `text`), viewer hint set per the
   D244 typed index convention, so graphite's honest-fallback ladder
   resolves it to a real viewer once graphite's WO-G13 lands (this WO
   does not touch graphite; it only makes the lithos-side index entry
   correct).
3. Calc-sheet/citation surfacing: the trace's provenance (scan hash,
   capture kind, calibration rung, residuals, tracer) renders on the
   consuming part's calc sheet through the existing evidence-citation
   rendering path, in the D257-coordinated structured shape -- same
   field names as WO-145's `Citation` model wherever the concepts
   overlap (document/reference-equivalent fields), not a second
   parallel shape.
4. Golden corpus: the espresso-machine group-gasket demo fixture (or
   an equivalent small fixture) exercising a real `.rgp` trace through
   a full build, with its calc sheet showing the citation text.
5. Integration tests (Python-level) proving: a `Blank` built from a
   traced profile produces the same downstream artifact shapes (STEP,
   drawing) as one built from a cardinal-walk profile; the calc sheet
   contains the expected provenance substring.

## Out of scope

- Any change to WO-147's Rust elaboration, diagnostics, or schema --
  consume its output as given.
- Any graphite-side code (WO-G11..G13, separate repo).
- Native-walk fitting / promotion-surface extension -- WO-149.
- `BoardOutline` profile-valued outline (cuprite v2) -- unscheduled,
  named in the recon sec. 3, not this WO.

## Acceptance

- `uv run pytest tests/ -k traced_profile -q` (or the equivalent new
  integration-test path) green, covering the `Blank`-from-trace case
  and the citation-rendering case.
- `regolith build --release <fixture-with-a-.rgp-trace>` succeeds and
  the emitted calc sheet's text contains the scan hash and residual
  values: `grep -E 'blake3:|residual' <calc-sheet-output-path>`
  matches.
- The artifact index row for the fixture's `.rgp` file shows family
  `traced` (not `text`): `regolith artifacts --json <fixture>` (or
  the project's equivalent invocation) greps to `"family": "traced"`.
- Citation field names in the rendered provenance match WO-145's
  `Citation` model field names wherever the same concept appears
  (a reviewer diff of the two field sets shows no unexplained
  divergence).
- `make check` green; demo/golden corpus regenerated in the same
  change if this WO's fixture touches existing goldens.

## Escalation

If extrusion-section consumption of a traced profile needs solver
work beyond a straight shape-compatibility check, name that gap in
the close-out as a residual for a later WO rather than expanding this
WO's scope to include new solver work.
