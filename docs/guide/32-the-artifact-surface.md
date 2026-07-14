# The universal artifact surface: one index, no hardcoded families

STATUS: WORKING (WO-130). Every `regolith ship` package carries an
`artifact_index.json` at its root describing EVERY file it emitted --
family, kind, path, content hash, size, media type, a viewer hint, the
subject/claim/obligation ids that produced it (when known), and, for
the three movable families (boards, drawing sheets, assemblies), a
reference to that family's own edit model. `regolith artifacts
<package_dir> [--json]` publishes it straight from the shipped
package -- no rebuild.

Source: design-log F145/D244 (charter `docs/spec/toolchain/
42-injection-and-artifact-surface.md` secs. 6-7, AD-41). Machinery:
`python/regolith/backends/registry.py` (the viewer-hint registry, one
home beside the AD-36 producer/renderer registrations),
`python/regolith/backends/artifact_index.py` (the index itself),
`python/regolith/backends/edit_models.py` (the three edit models),
wired into `python/regolith/backends/ship.py` and the `regolith
artifacts` CLI verb (`python/regolith/cli/app.py`).

## Why this exists

Before this WO, a consumer that wanted to RENDER a shipped package
(graphite's preview pane, an editor, a one-off script) had to know, by
name, which families existed and how to read each one. That list
lived nowhere central and fell behind: F145 recorded graphite
rendering 5 of the fleet's 8 artifact families and previewing only the
`Edge.Cuts` layer of a 14-layer board fab set, because its renderer
carried its own hardcoded family switch that two cycles of new
families (`harness`, the full fab set) never reached.

The fix is structural, not a patch to graphite's switch statement: the
toolchain now publishes ONE typed index describing every file well
enough that a consumer never needs to know what family it is. A new
family is viewable the day it ships, because the index -- not a
viewer's own code -- is what says how to show it.

## The index shape

One row per emitted file (`regolith.backends.artifact_index.ArtifactRow`):

```json
{
  "family": "boards",
  "kind": "gerber_layer.F_Cu",
  "relpath": "boards/gerbers/board-F_Cu.gtl",
  "content_hash": "<sha256 hex>",
  "bytes": 223,
  "media_type": "application/vnd.gerber",
  "viewer": "gerber",
  "source_refs": [],
  "edit_model": "boards/MainboardMcu.edit_model.json"
}
```

`family` is the package's top-level directory the file lives under
(`boards`, `drawings`, `3d`, `bom`, `cost`, `firmware`, `hdl`,
`instructions`, `harness`, `evidence`, `calc`, `mech`), or `"ledgers"`
for the root-level side files (`manifest.json`, `index.md`,
`gate_summary.json`, `parity_ledger.json`, `acceptance_ledger.json`,
and `artifact_index.json` itself -- which never lists its own row, the
same rule `index.md` already followed). `kind` narrows within a
family (e.g. `gerber_layer.F_Cu` vs. `drill.PTH` vs. `job_file` all
live under `boards`). `viewer` is the CLOSED vocabulary:

```
svg | raster | gerber | glb | table | markdown | json | text | binary
```

A viewer that understands none of a family's own richer forms still
has the honest fallback ladder `table`/`json`/`text`/`binary` -- a
consumer always has something truthful to render (a hash + size + a
reason beats a blank pane).

## Where the viewer hint lives

ONE home, beside the family's own registration: `regolith.backends.
registry.default_artifact_family_registry()` -- the same module the
AD-36 producer/renderer registries already live in. Every family
`regolith.backends.package.FAMILY_DIRS` names carries a default
viewer here; a file classifier (`artifact_index.classify`) narrows
individual files whose kind does not match the family default (a
board's `board_status.json` is `json`, not `gerber`; its gerber
layers keep the family default). **A family with no registered
default is a REGISTRATION ERROR** -- `build_index` refuses to build a
lossy index rather than silently omitting rows, and the ship refuses
with it. This is the loud-vs-silent discipline the producer/renderer
registries already enforce for duplicates, extended to viewer hints.

Registering a new family's hint is one call:

```python
registry.register(ArtifactFamilyRegistration("my_family", "table"))
```

## The health consistency check

`regolith.backends.artifact_index.check_index_consistency(index,
files)` enforces three things, ALL as failures (never warnings):

1. every emitted file appears in the index;
2. every index row resolves to an emitted file;
3. every row's family carries a registered viewer hint.

`ship` runs this immediately after building the index and BEFORE
writing `artifact_index.json`; drift refuses the whole ship. A test in
`tests/backends/test_artifact_index.py` demonstrates case 3 directly:
an index row is built against a family that was never registered, and
the check fails naming it -- the acceptance bar this WO's own
deliverable names ("the health check fails a deliberately hint-less
family").

## Publishing the index without a rebuild

```
regolith artifacts <ship_output_dir>
regolith artifacts <ship_output_dir> --json
```

Reads `artifact_index.json` straight from the package; `--json` emits
the raw bytes (what a script/graphite parses), the default renders an
ASCII table (family, kind, viewer, size, path, edit model).

## Edit models (the three movable families)

Three families expose a companion edit model beside their rendered
files -- a canonical JSON description of the movable ENTITIES a person
can legitimately reposition, each carrying the override target path
that would change it (the WO-129 dotted `design.subject.slot` shape,
charter 42 sec. 4 -- e.g. `mainboard_mx.MainboardMcu.placements.
J_DBG1.pose`). An edit model NEVER invents a value the pipeline did
not produce (D224); it is written by a build, read by an editor, and
changed only by writing an override through the AD-40 CLI
(`regolith override set ...`, WO-129) and re-shipping -- artifacts
stay DERIVED, nothing is edited in place.

**Boards** (`<subject>.edit_model.json` beside the board's own
files): every component placement, PLUS -- on a debug-profile ship --
the WO-125 tap header and every labeled test point (neither of which
lives on the realized layout's own placement list; they are the debug
augmentation's own placements). Keepouts are named ABSENT: the
realized-layout surface carries no keepout-region geometry today
(F136 gap, escalated below as F-WO130-1), so every movable board
entity also carries a caveat saying it is draggable WITHOUT
collision-checking.

**Drawing sheets** (`<subject>.edit_model.json` beside a drawing
set's rendered files): every `Annotation` anchor is movable. `View`
entries (charter 42 sec. 7's "view anchors") are present but marked
READ-ONLY: the realized-drawing schema stores no view anchor today
(sheet layout is renderer-computed), so moving one is not yet
possible -- named, not fabricated (F-WO130-2).

**Assemblies** (`<subject>.assembly.edit_model.json` beside the `3d`
family's rendered GLB): every part whose `RealizedAssembly.dof_states`
entry is `"underconstrained"` (the mate solve did not fix it) is
movable; a `"fixed"`/`"placed"` part is read-only WITH its reason
("fixed by the mate solve", "solved by a spanning mate").

## Escalations recorded at close-out

- **F-WO130-1**: board component/test-point/tap-header drags are
  movable without collision-checking (no courtyard/keepout geometry on
  `RealizedLayout` -- the same F136 gap WO-124 already named).
- **F-WO130-2**: drawing sheet `View` entries carry no stored anchor,
  so they are read-only in the edit model until a schema field lands.
- **F-WO130-3**: `source_refs` (subject/claim/obligation ids) is
  populated empty by `ship` today -- threading per-file provenance
  through every backend's `OutputFile` is out of this WO's zero-shot
  scope (`OutputFile` carries no id today); the field exists and is
  honestly empty rather than fabricated, ready for a follow-up WO to
  populate.
- **F-WO130-4**: `edit_model` cross-referencing matches a file to its
  family's edit model by SUBJECT-STRING containment in the relpath --
  exact for the common one-subject-per-family fleet package; a
  multi-subject family's attribution is approximate until WO-129's
  target resolver lands full per-file attribution.
- **F-WO130-5**: the CLI's `builtin_backends["mech"]` package (STEP
  models, its own `bom.csv`/`bom.json`, `fab_notes.json`) had never
  joined `package.FAMILY_DIRS` -- closed in this same change (added to
  `FAMILY_DIRS` and given a viewer hint), itself an instance of the
  exact hardcoded-list drift F145 describes, one layer down.

## Cross-WO seam (WO-129)

This WO emits override target path STRINGS in WO-129's documented
`design.subject.slot` shape (charter 42 sec. 4) but does not import or
depend on WO-129's resolver (parallel branch `wo129`) -- the two WOs
integrate at the string, not the code. Whether WO-129 accepts exactly
these target shapes (`<design>.<subject>.placements.<ref>.pose`,
`<design>.<subject>.annotations.<n>.anchor`,
`<design>.<subject>.parts.<id>.pose`) is a coordinator adjudication at
integration, not assumed here.
