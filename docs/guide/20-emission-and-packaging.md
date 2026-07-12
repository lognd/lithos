# 20 -- Emission and packaging

How `regolith ship` turns a clean release build into one artifact
package, and how to add your own output formats or artifact kinds
without touching the toolchain. Normative charter: `docs/spec/toolchain/
38-emission-and-release.md`; architecture ledger AD-36/AD-26.

## The release package

`regolith ship --out dist/<project>` writes one package directory. Its
top level always carries:

- `manifest.json` -- the signed (blake3 + optional ed25519) manifest;
  every file below is content-addressed here.
- `index.md` -- a deterministic listing of every artifact with its
  sha256 digest, headed by the release-gate stamp and a
  present/absent-with-reason table for each artifact family.
- `gate_summary.json` -- the machine-readable gate verdict (the SAME
  accounting the release gate itself draws; never a softened one).
- `parity_ledger.json` -- the parity report over the lockfile, gate
  results, and waive ledger (AD-22).
- `acceptance_ledger.json` -- the deviations/waivers/assumes ledger
  (written by the acceptance-gate machinery; a placeholder until that
  writer runs).

Artifacts sit under per-family directories (`drawings/`, `3d/`, `bom/`,
`instructions/`, `boards/`, `firmware/`, `hdl/`, `cost/`, `evidence/`).
`ship --verify <dir>` re-hashes every file in the manifest and checks
the signature, so a package proves its own integrity.

Two ships of the same clean build are byte-identical for every
deterministic artifact -- the index and ledgers included. The package
never partially writes: if the release gate is not clean, `ship`
refuses before any file is written (INV-24).

## Choosing output formats

Every drawing renders to a set of formats. The built-ins are `json`,
`svg`, `dxf`, `pdf`, and `explain`. Select a subset per project in
`magnetite.toml`:

```toml
[artifacts]
formats = ["svg", "pdf"]
```

Omit the table (or the `formats` key) to emit all built-in formats.

## Viewing your build in 3D

Mechanical drawings are no longer bbox stand-ins: a part sheet is a real
OCP/OCCT hidden-line projection of the part's pinned STEP bytes --
front, top, side, and isometric views on one sheet, visible edges solid
and hidden edges dashed. If the native STEP bytes are missing (or OCP is
not installed on the host), the sheet degrades to the old bounding-box
outline with a loud `projected geometry unavailable: <reason>`
annotation -- never a silent stand-in.

Alongside the sheets, `ship` and `regolith preview` emit a **3D artifact
family** under `3d/`:

- `3d/<subject>.glb` -- a deterministic binary glTF (fixed tessellation
  parameters, sorted buffers, no timestamps) for each realized part and
  for each assembly. An assembly GLB places one node per part instance
  using the solved mate transform (parts are never re-solved), deduping
  shared geometry into one mesh.
- `3d/<subject>.viewer.html` -- a single self-contained page that opens
  the GLB **offline**: it makes zero network requests (the model is
  embedded, the WebGL renderer is inline), so you can double-click it
  from a shipped package with no server, no CDN, and no build step.
  Drag to orbit, shift-drag (or right-drag) to pan, scroll to zoom, and
  hover a part to see its name.

Opt in from a ship spec:

```json
{ "three_d": {} }
```

An empty block renders every part and assembly the build carries;
`{"three_d": {"parts": ["BedPlate"], "assemblies": ["router"]}}` narrows
it. `regolith preview` renders the family automatically for every subject
whose STEP bytes are on hand.

Assembly **instructions** (`instructions/<subject>.instructions.md`) also
gain a small projected front-view image per build step -- the parts
placed so far in gray, the step's own part highlighted -- so the ordered
step list reads as a real illustrated build sheet.

## Extending emission with a plugin

Producers (subject kind -> a `DrawingModel`) and renderers (format id ->
a file's bytes) are registries, not hard-coded lists. A third-party
package adds either through the ONE plugin seam (`regolith.plugins`,
`kind = "renderer"`) -- ZERO edits to any dispatch site, and the new
format/kind appears in the package automatically.

A renderer plugin exports a `PluginManifest` whose `register_fn`
receives a `RegistryBundle` and registers into it:

```python
from regolith.backends.registry import RendererRegistration, DRAWING_FAMILY
from regolith.backends.renderer_plugin import RegistryBundle
from regolith.plugins import PluginKind, PluginManifest

def _render_ascii(model):
    return f"drawing: {model.subject}".encode("ascii")

def register(bundle: RegistryBundle) -> None:
    bundle.renderers.register(
        RendererRegistration("ascii", "ascii.txt", DRAWING_FAMILY, _render_ascii)
    )

MANIFEST = PluginManifest(
    id="my.ascii-renderer",
    kind=PluginKind.RENDERER,
    version="1.0.0",
    register_fn=register,
)
```

Point an entry point in the `regolith.plugins` group at `MANIFEST` and
install the package; `ship` then emits `drawings/<subject>.ascii.txt`
for every drawing. A producer plugin registers a `ProducerRegistration`
into `bundle.producers` the same way; its subjects are auto-derived by
`regolith preview` (no `--spec` needed) if its registration declares a
subject source.

A plugin that claims a format id or subject kind already registered
(by a built-in or another plugin) is a loud, logged duplicate -- it is
skipped whole, never silently shadowing the existing one.

## Derived bill of materials (BOM v2)

`ship` emits a DERIVED bill of materials under `bom/` -- csv, json, md,
and pdf. Its rows are not authored: they are derived from the design
graph the build already produced (mech parts, assembly members, frame
members, elec block instances, flownet fittings). Each row carries:

- a **part number** ONLY from a hash-pinned record or a caller
  `AssemblyLine` (a line overrides or augments a derived row by subject
  key); a row with neither ships a loud `UNSOURCED` marker, never a
  fabricated number;
- **real mass** = material-record density x the realized solid's volume,
  with both the material record pin (`<key>@<rev>`) and the geometry pin
  (the STEP content hash) carried as provenance. Where either input is
  missing (no material, no density record, no realized geometry) the mass
  cell is honestly empty WITH a stated reason -- an honest empty cell
  beats a mislabeled number (this is why the old `mass_hint` column, which
  labeled a part's SURFACE AREA as its mass, is gone);
- **joined cost** from the build's persisted itemized-estimate evidence
  (matched by subject); a row with no estimate ships an empty cost cell
  with a reason.

The four formats render through the same `RendererRegistry` (WO-99) as
every drawing, under the `bom` model family; a plugin adds a BOM format
with one `RendererRegistration(over="bom", ...)`.

Costing evidence and schedules also ship as sheets: a **cost summary
sheet** (each estimate line item + a profile-cited total) and a calcite
**member schedule sheet** (id / role / section / material / length),
both ordinary `DrawingModel` tables through the ordinary PDF renderer.
