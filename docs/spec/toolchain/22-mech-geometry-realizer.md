# Mech geometry realizer (WO-22): design + status

Feature IR -> build123d/OCCT -> STEP, registered as a model pack
discharging `geometry_realizable`-shaped evidence (AD-19).

## Modules

- `regolith.realizer.mech.schema` -- the serialized `FeatureProgram`
  IR: stages of resolved feature ops (`ExtrudeOp`, `PocketOp`, `HoleOp`,
  `FilletOp`, `BlankOp`, `PierceOp`, `BendOp`, `PatternOp`), SI metres.
  THIS IS THE REALIZER'S ONLY INPUT (AD-4) -- it never sees the CST.
- `regolith.realizer.mech.interpreter` -- the one module that imports
  build123d (AD-1). Interprets a `FeatureProgram` into a build123d
  `Part`, exports AP242 STEP, and produces a `TopologySummary`
  (solid/face/edge/vertex counts, volume, area, bbox, center of mass).
  Total and honest: an op outside the v1 set, or an OCCT failure on
  otherwise well-formed input, is a named `RealizeError` value, never a
  crash and never a silent skip.
- `regolith.realizer.mech.model` -- `GeometryRealizableModel`, wired
  through the SAME `Model`/`DischargeRequest`/registry path every other
  harness model uses. Compares a realized solid's volume/bbox against
  the static core's predicted measures; the worst relative error is an
  upper-bound claim against a declared `eps_rel` limit.
- `regolith.realizer.mech.pack` -- the `register(registry) -> None`
  entry point (AD-19/D-B). NOT wired into
  `[project.entry-points."regolith.model_packs"]` (see the cuts
  section below) -- call `register()` directly until a real caller
  exists.

## Determinism (AD-6)

- `FeatureProgram.content_hash()` -- SHA-256 of the canonical pydantic
  JSON. Same program, same hash, always (pydantic's field order is
  fixed by the model definition, not affected by dict iteration).
- `RealizedGeometry.step_content_hash` -- SHA-256 of the exported STEP
  bytes AFTER normalizing OCCT's `FILE_NAME(...)` wall-clock export
  timestamp to a fixed sentinel. Without this normalization the
  "byte-identical STEP on one platform" acceptance criterion is FALSE
  (verified: two exports of the identical solid, one second apart,
  differ only in that timestamp field) -- this is a real finding, not
  a hypothetical, and the fix is metadata normalization, not faked
  geometry.
- `TopologySummary.content_hash()` -- the CROSS-platform golden (raw
  STEP bytes are not byte-stable across OCCT builds/platforms).

## Cuts recorded this cycle (WO-22)

See `docs/workflow/work-orders/WO-22-mech-geometry-realizer.md` for the full
list with justification. Summary:

1. **No feature-program producer exists.** `regolith-lower`/
   `BuildPayload` does not emit any stage/feature-op structure (checked
   against `crates/regolith-api/src/session.rs`). `regolith.realizer.
   mech.schema` is therefore a forward contract, exercised against
   hand-built fixtures (`tests/realizer/mech/fixtures.py`), not the
   real `.hema` corpus end to end. Fixing this is `regolith-lower` work,
   out of WO-22's own scope (explicitly reserved for a future WO / an
   escalation, not invented here).
   **PROMOTED (WO-42, AD-25/D128).** The OUTPUT half of this cut is
   closed: `TopologySummary`/`RealizedGeometry` are no longer a
   hand-written Python forward contract -- they are the Rust-sourced,
   schemars-derived `regolith_oblig::geometry` schema (deliverable 1),
   generated into `regolith._schema.models.RealizedGeometry`, `put`
   into the WO-30 content store by `regolith.realizer.mech.interpreter
   .realize_feature_program` (deliverable 4), and fed back into a real
   `regolith-lower` re-lower by the orchestrator's staged build loop
   (`regolith.orchestrator.orchestrate.staged_build`, deliverable 5).
   The INPUT half of this cut still stands as written above: the
   `.hema` corpus has no `regolith-lower`-emitted `FeatureProgram`
   producer yet, so `staged_build`'s `feature_programs` map is still
   caller-supplied (hand-built fixtures or a future `.hema` lowering
   pass), not discovered from a build payload.
2. **Mass verification cut to volume+bbox.** No material density
   source exists anywhere in the repo (checked `regolith-qty`,
   `regolith-sem`, and the Python side). Mass = density * volume needs
   a materials table this WO does not own.
3. **Bend is a rigid-rotation approximation.** No bend-allowance /
   K-factor flat-pattern length correction; real, checkable OCCT
   geometry, never a crash, but not shop-accurate for a bent flange's
   flat length.
4. **Fillet edge selection is coarse** (`all`/`top`/`bottom`/
   `vertical`) -- no feature-to-edge naming scheme exists yet to select
   "the edge feature X produced".
5. **PMI is not carried through STEP.** build123d's STEP export has no
   PMI (dimensions/GD&T annotation) surface at all in 0.11.x; AP242
   geometry-only baseline is what ships.
6. **The pack is not wired into the entry-point group.** Registering
   this repo's own in-tree pack under `regolith.model_packs` would make
   it load in EVERY `default_registry()` call repo-wide (verified: it
   broke an unrelated WO-20 pack-composition-ordering test), which is
   wrong before any obligation routes `geometry_realizable` claims to
   it. `pack.register(registry)` is called directly by the realizer's
   own tests/integration point.

## Amendment (cycle 25, D130/D131 -- the wetted-path contract)

The WO-42 deliverable-4 escalation resolved how the realizer gets
wetted-path data (design-log `2026-07-08-cycle-25`):

- `FeatureProgram` v2 (`FEATURE_PROGRAM_SCHEMA_VERSION` 1 -> 2) gains
  DECLARED part-level `flow_paths` (selector `<stage_name>.wetted`,
  segments with Cause-tagged measures, roughness-class labels from the
  extract seam's single table, optional geometric wall) and
  `material_props` (resolved E/density values, producer-side). Cut #2
  above STANDS -- the realizer still owns no materials table; material
  properties arrive resolved in its input, like every other param.
- The realizer's duty on these is validate-and-emit: cross-check
  declared segments against the realized solid where geometry fixes
  the answer, emit `[lo, hi]` intervals, raise a named `RealizeError`
  on disagreement -- never derive wettedness from the B-rep.
- The emitted wire shape is `regolith_oblig::RealizedGeometry` as
  amended by D131 (selector-keyed paths matching the extract seam's
  field list; the seam's private `RealizedRecord` mirror deleted).
- The eventual `flow_paths` producer is hematite lowering over
  `.cavity(inlet=...)` queries (02-language sec. 6), deferred with a
  reopen criterion in hematite/07 sec. 2a; hand-authored
  `FeatureProgram` fixtures declaring `flow_paths` are legitimate
  producers meanwhile (the same AD-22 posture as cut #1).
