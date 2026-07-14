# WO-130 -- The universal artifact surface + edit models (D244/AD-41, charter 42 secs. 6-7)

Status: done -- with deliverable 4 (EDIT MODELS) subsequently PARKED by
  D253 (2026-07-15). The index half STANDS on master and is what this WO
  is now: the `Viewer` closed vocabulary + `ArtifactFamilyRegistry`, the
  typed `artifact_index.json` + classifier, the health consistency drift
  check, and `regolith artifacts [--json]` -- read-only description, which
  is exactly what lets a viewer render any family without a hardcoded
  list. The edit models (`edit_models.py`, the per-backend emission, and
  the `edit_model` reference on each artifact row) are REMOVED from master
  and preserved on the branch `experimental/injection-channel`, together
  with the whole WO-129 injection channel they were the write-back half
  of. See D253 (aesthetic/semantic split) and F150 (the channel was
  inert -- no build or ship path read the ledger, so removing it changed
  no behavior).
Language: Python (emission registry, package index, backends, CLI).
  No schema bump without coordinator adjudication (D239/D225) -- the
  artifact index is emission-layer data.
Spec: charter 42 secs. 6-7 (NORMATIVE); AD-41; D244; F145 (the
  evidence: graphite renders 5 of 8 families and previews only
  Edge.Cuts of a 14-layer fab set); AD-36 (the emission registry --
  the ONE home the viewer hint joins); WO-99 (dist/ layout + package
  index); WO-124 (the full fab set the index must describe);
  WO-126 (the harness family with no consumer today).

## Goal

Every file the toolchain emits describes itself well enough that a
viewer can render it WITHOUT knowing what it is -- so a new artifact
family is viewable the day it ships, and no consumer ever again
carries a hardcoded family list that silently falls behind.

## Deliverables

1. Typed artifact index (one per package, canonical + hashed): per
   file -- `family`, `kind`, `relpath`, `content_hash`, `bytes`,
   `media_type`, `viewer` (CLOSED vocabulary: `svg` | `raster` |
   `gerber` | `glb` | `table` | `markdown` | `json` | `text` |
   `binary`), `source_refs` (subject/claim/obligation ids that
   produced it), optional `edit_model` ref.
2. The `viewer` hint lives in the AD-36 emission registry BESIDE the
   family registration -- one home. A family registered without a
   hint is a REGISTRATION ERROR (loud), never a silent gap. Every
   landed family gets its hint in this change (drawings, calc,
   boards incl. all 14 fab layers, 3d, bom, cost, firmware, hdl,
   instructions, harness, evidence, ledgers).
3. Honest fallback ladder: any file whose family has no richer
   viewer resolves to `table`/`json`/`text`/`binary` -- a consumer
   always has something truthful to show (hash + size + reason beats
   a blank pane).
4. Edit models (charter 42 sec. 7) for the three movable families:
   boards (component/test-point/tap-header placements: x, y, rot,
   side; keepouts read-only), drawing sheets (annotation/view
   anchors), assemblies (part poses the mate solve did not fix).
   Each movable entity carries the WO-129 override target path that
   would change it. Read-only entities are marked read-only WITH a
   reason ("fixed by the mate solve", "pinned by claim X").
5. `regolith artifacts <project> [--json]`: publishes the index from
   the SHIPPED package without re-running a build. stdout is data.
6. Consistency check (health): every emitted file appears in the
   index; every index row resolves to a file; every family has a
   viewer hint. Drift is a failure, not a warning.
7. Guide `32-the-artifact-surface.md`: the index shape, the viewer
   vocabulary, how a producer registers a hint, how a consumer
   (graphite, an editor, a script) renders an unknown family
   honestly.

## Acceptance

- A shipped fleet package's index describes 100 percent of its
  files, with a viewer hint on every row and zero unexplained
  entries; the health check fails a deliberately hint-less family.
- The three edit models emit for mainboard_mx (board placements incl.
  the WO-125 tap header), a drawing sheet, and an assembly -- each
  movable entity naming its override target.
- `regolith artifacts --json` round-trips from the package alone.
- Determinism (no timestamps); `make check` + `make health` green.

## Escalation

If an edit model needs geometry the realized surface does not carry
(e.g. footprint courtyards for collision-aware dragging -- the F136
gap), emit the honest named absence and ledger it: the editor may
show the entity as movable-without-collision-checking, and say so.
Never fabricate geometry (D224).

## Note on the consumer

graphite's WO-G9 (render any family via this index, incl. full
RS-274X gerber through its WASM path) and WO-G10 (drag-to-override
editing through WO-129's CLI) are that repo's work, gated on this
WO and WO-129 landing. Nothing in graphite may bypass these
surfaces (D234).

## Close-out

Landed: the `Viewer` closed vocabulary + `ArtifactFamilyRegistry`
beside the AD-36 producer/renderer registrations
(`regolith.backends.registry`); the typed index + classifier + health
consistency check (`regolith.backends.artifact_index`); the three
edit models (`regolith.backends.edit_models`) wired into
`DrawingsBackend`/`ElecBackend`/`ThreeDBackend` -- SINCE PARKED, D253,
see the Status header; `ship()` builds,
consistency-checks, and ships `artifact_index.json`; `regolith
artifacts <package_dir> [--json]`; guide
`docs/guide/32-the-artifact-surface.md`. Verified against two real
fleet packages (`examples/flagships/mainboard_mx`,
`examples/flagships/printer_k1`, both `regolith build --release` +
`regolith ship`) and the full `tests/backends/` suite plus
`tests/test_wo125_debug_profile.py`, `tests/test_wo126_bringup_
harness.py`, `tests/test_cli_preview.py`.

Escalations (see the guide's own section for detail):

- F-WO130-1: board component/test-point/tap-header drags have no
  courtyard/keepout geometry to collision-check against (the F136
  gap); the edit model carries a caveat per entity and an honest
  `keepouts_absent_reason` rather than a fabricated keepout list.
- F-WO130-2: drawing sheet `View` entries carry no stored anchor on
  the realized-drawing schema -- read-only in the edit model, named,
  never fabricated.
- F-WO130-3: `source_refs` ships honestly empty; per-file
  subject/claim/obligation provenance threading through every
  backend's `OutputFile` is out of this WO's zero-shot scope.
- F-WO130-4: `edit_model` cross-referencing matches by subject-string
  containment (exact for one-subject-per-family, approximate for a
  multi-subject family) pending WO-129's target resolver.
- F-WO130-5: `builtin_backends["mech"]` (STEP + its own bom/fab-notes)
  had never joined `package.FAMILY_DIRS` -- closed in this same
  change (an instance of F145's own failure mode, one layer down).

Cross-WO seam (WO-129, parallel branch `wo129`): this WO emits
override target path STRINGS in the documented `design.subject.slot`
shape (charter 42 sec. 4) without importing WO-129's resolver; whether
WO-129 accepts these exact shapes
(`<design>.<subject>.placements.<ref>.pose`,
`<design>.<subject>.annotations.<n>.anchor`,
`<design>.<subject>.parts.<id>.pose`) is a coordinator adjudication at
integration.
