# The universal artifact surface: one index, no hardcoded families

STATUS: WORKING (WO-130; provenance tier WO-160/AD-45; registration-
derived classification WO-161/AD-46). Every `regolith ship` package
carries an `artifact_index.json` at its root describing EVERY file it
emitted -- family, kind, path, content hash, size, media type, a
viewer hint, a required provenance tier, and the subject/claim/
obligation ids that produced it (when known).
`regolith artifacts <package_dir> [--json]` publishes it straight from
the shipped package -- no rebuild.

The index is READ-ONLY DESCRIPTION: it says what a file IS, so a viewer
can render any family without a hardcoded list. The write-back half
(edit models, the `override` ledger and CLI) was PARKED by D253 and is
preserved on the branch `experimental/injection-channel`.

Source: design-log F145/D244 (charter `docs/spec/toolchain/
42-injection-and-artifact-surface.md` secs. 6-7, AD-41). Machinery:
`python/regolith/backends/registry.py` (the viewer-hint registry, one
home beside the AD-36 producer/renderer registrations),
`python/regolith/backends/artifact_index.py` (the index itself),
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
  "provenance": {"tier": "deterministic", "tool": null},
  "source_refs": []
}
```

`provenance` (WO-160, AD-45) is REQUIRED -- no default, never
post-hoc-inferred from relpath naming or toolenv state. `tier` is
`real_tool` (produced by an actual third-party tool invocation --
`tool` required, `{name, version_digest}`) or `deterministic`
(regolith's own deterministic logic, no external tool -- `tool` is
`null`). A producer supplies it at construction time
(`OutputFile.of(relpath, content, provenance=...)`); an untagged
`OutputFile` resolves to the honest `deterministic` default when
`build_index` builds the row, never an invented `real_tool` claim. The
fake/real KiCad fork (`regolith.backends.elec.ElecBackend`) is the
worked example: the real `kicad-cli` leg tags every export with
`tier=real_tool, tool={name: "kicad-cli", version_digest: <observed
version string>}`; the fake-KiCad tier (`elec_fabset.
build_fake_fab_set`) tags its files `tier=deterministic, tool=null`
explicitly.

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
viewer here; each family's own `path_patterns` (WO-161, matched via
`registry.match_path_pattern`) narrow individual files whose kind does
not match the family default (a
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
files)` enforces five things, ALL as failures (never warnings):

1. every emitted file appears in the index;
2. every index row resolves to an emitted file;
3. every row's family carries a registered viewer hint;
4. every row's family carries a `path_patterns` entry that actually
   matches its relpath (WO-161) -- with `classify()` deleted, this is
   the one remaining place a new artifact type could sneak in without
   registering patterns at all;
5. every row's `provenance` is internally consistent -- `tool` present
   iff `tier == "real_tool"` (WO-160).

`ship` runs this immediately after building the index and BEFORE
writing `artifact_index.json`; drift refuses the whole ship. Tests in
`tests/backends/test_artifact_index.py` demonstrate each case: an
index row built against a family that was never registered (case 3),
a family registered but with no matching `path_patterns` entry (case
4), and a `real_tool` row with `tool=None` (case 5) -- the check fails
naming the offending relpath/family in every case.

## Publishing the index without a rebuild

```
regolith artifacts <ship_output_dir>
regolith artifacts <ship_output_dir> --json
```

Reads `artifact_index.json` straight from the package; `--json` emits
the raw bytes (what a script/graphite parses), the default renders an
ASCII table (family, kind, viewer, size, path).

## Escalations recorded at close-out

(The edit-model escalations F-WO130-1/-2/-4 went with the D253 park --
see below; they live on with the code on `experimental/injection-channel`.)

- **F-WO130-3**: `source_refs` (subject/claim/obligation ids) is
  populated empty by `ship` today -- threading per-file provenance
  through every backend's `OutputFile` is out of this WO's zero-shot
  scope (`OutputFile` carries no id today); the field exists and is
  honestly empty rather than fabricated, ready for a follow-up WO to
  populate.
- **F-WO130-5**: the CLI's `builtin_backends["mech"]` package (STEP
  models, its own `bom.csv`/`bom.json`, `fab_notes.json`) had never
  joined `package.FAMILY_DIRS` -- closed in this same change (added to
  `FAMILY_DIRS` and given a viewer hint), itself an instance of the
  exact hardcoded-list drift F145 describes, one layer down.

## What was parked (D253)

WO-130's edit-model deliverable -- the movable-slot models for boards,
drawing sheets, and assemblies, and the `edit_model` reference that
pointed each artifact row at one -- is PARKED, together with the whole
WO-129 injection channel (the `overrides.toml` ledger, target
resolution, and the `regolith override` verbs). All of it is preserved
on the branch `experimental/injection-channel`; D253 is the decision and
F150 is the finding that made it safe (the channel was inert -- no build
or ship path ever read the ledger).

The index half above STANDS and is what the artifact surface is: a
viewer reads `artifact_index.json` and renders any family. Moving an
engineering quantity is a source edit, not a GUI gesture.
