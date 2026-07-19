# WO-161 -- registration-derived artifact classification (AD-46)

Status: open (Depends: none -- independent of WO-160's provenance
  field; both touch `artifact_index.py` but different fields, no
  ordering constraint. May land before, after, or in the same wave
  as WO-160.)
Language: Python (`python/regolith/backends/artifact_index.py`,
  `registry.py`, and every `ArtifactFamilyRegistration` site).
Spec: `docs/spec/toolchain/44-boundary-charter.md` sec. 3 (AD-46);
  `docs/spec/toolchain/38-emission-and-release.md` (AD-36 registries).

## Goal

`classify()`'s hand-written relpath-pattern dispatcher (currently
`python/regolith/backends/artifact_index.py:139`,
`def classify(relpath: str, family: str) -> tuple[str, Viewer | None,
str]`) is deleted. Its logic moves INTO `ArtifactFamilyRegistration`
as data: a `path_patterns: list[str]` field plus the existing
`kind`/`viewer` mapping each registration already carries (or gains,
if it does not yet). `build_index` classifies a row by looking up its
family's registration and matching `path_patterns`, not by calling a
separate dispatcher function.

## Deliverables

1. Read `classify()`'s current body in full; enumerate every
   family/relpath-pattern/kind/viewer tuple it hand-dispatches. This
   enumeration IS the migration data -- one line per family.
2. `ArtifactFamilyRegistration` (locate its current definition --
   likely `backends/registry.py`) gains `path_patterns:
   list[str]` (glob or regex, match whatever `classify()`'s current
   matching style is -- do not silently change matching semantics).
3. Migrate every existing registration (mech STEP/STL, elec gerbers/
   KiCad, firmware, HDL, drawings, 3D/GLB, BOM, cost schedules, etc.
   -- enumerate via `grep -rn "ArtifactFamilyRegistration(" python/
   regolith/backends/`) to carry its `path_patterns` derived from
   step 1's enumeration.
4. `build_index` (or wherever rows are classified during index
   construction) calls into the registry lookup instead of
   `classify()`. Delete `classify()` once nothing calls it (grep to
   confirm zero remaining callers before deletion).
5. `check_index_consistency` remains as the belt-and-suspenders gate
   per the charter's own text ("can no longer be the only thing
   holding two independent classification paths together, because
   there is only one path") -- update its implementation if it
   previously cross-checked `classify()` against registrations (that
   cross-check is now trivially true by construction; replace it
   with a check that EVERY row's family has a matching registration
   with a `path_patterns` entry that actually matched, i.e. catch
   the case where a NEW artifact type sneaks in without registering
   patterns at all).

## Non-goals

- No new artifact family/type in this WO (that is each capability
  program's own registration work, e.g. WO-165/166).
- No provenance field work (WO-160, independent).

## Acceptance

- `grep -n "^def classify" python/regolith/backends/artifact_index.py`
  returns nothing (function deleted).
- Existing artifact-index tests (whatever currently exercises
  `classify()`'s per-family cases) are migrated to exercise
  `build_index` against a registration fixture and still pass with
  identical kind/viewer output for every existing family -- i.e. this
  is a behavior-preserving refactor, verified by the existing
  fixtures/goldens (demo manifests under `demos/out/*/manifest.json`
  must regenerate byte-identical modulo the new provenance field from
  WO-160 if that lands first).
- A new negative test: a row whose family has NO registered
  `path_patterns` entry matching its relpath fails
  `check_index_consistency` (proves the gate still catches drift).
- `make check` green.
</content>
