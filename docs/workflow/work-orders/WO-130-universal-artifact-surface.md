# WO-130 -- The universal artifact surface + edit models (D244/AD-41, charter 42 secs. 6-7)

Status: open
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
