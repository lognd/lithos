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

See `docs/implementation/WO-22-mech-geometry-realizer.md` for the full
list with justification. Summary:

1. **No feature-program producer exists.** `regolith-lower`/
   `BuildPayload` does not emit any stage/feature-op structure (checked
   against `crates/regolith-api/src/session.rs`). `regolith.realizer.
   mech.schema` is therefore a forward contract, exercised against
   hand-built fixtures (`tests/realizer/mech/fixtures.py`), not the
   real `.hem` corpus end to end. Fixing this is `regolith-lower` work,
   out of WO-22's own scope (explicitly reserved for a future WO / an
   escalation, not invented here).
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
