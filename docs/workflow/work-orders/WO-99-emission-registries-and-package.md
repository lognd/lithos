# WO-99 -- Emission registries + the release package layout

Status: in-progress
Language: Python (backends; one AD-26 spec touch)
Spec: D208 (cycle-34 log); charter 38 sec. 1.2/1.3/1.4/1.11/1.12;
  AD-22/26/27/36; charter 25 (DrawingModel contract unchanged);
  D197 (preview/ship shared producer set -- preserved).

## Goal

Kill the two hard-coded dispatch sites (the `model_for_spec`
if/elif ladder and the `files_for_model` renderer quintet) in
favor of registries with a plugin seam; emit ONE `dist/<project>/`
release-package layout; persist native bytes at realize time; make
every shipped provenance digest the canonical content address.

## Deliverables

1. `ProducerRegistry`: subject-kind -> producer callable
   (mech/fluid/civil/elec_blocks/contract_graph/si/opt_trace as
   built-in registrations; `model_for_spec` becomes a registry
   lookup; `auto_specs` derives from registered kinds, not
   hard-coded track wiring). Registration API is the same one
   plugins use.
2. `RendererRegistry`: format id -> renderer over `DrawingModel`
   (svg/dxf/pdf/json/explain built-ins) AND realized-IR renderer
   family (consumed by WO-100/101 registrations later).
   `files_for_model` walks the registry. Per-project format
   selection via `magnetite.toml [artifacts] formats = [...]`
   (default: all built-ins).
3. AD-26 plugin kind `renderer` (spec text + `plugins.py`
   `PluginKind`): third-party renderers/producers enter through
   the ONE seam; duplicate ids loud, never shadowing.
4. Package layout: `ship` emits `dist/<project>/` per charter 38
   sec. 1.3 -- `manifest.json`, deterministic `index.md` (every
   artifact + digest + gate stamp), `gate_summary.json`,
   `acceptance_ledger.json` (WO-98's writer -- coordinate; if
   WO-98 unmerged, leave the hook), `parity_ledger.json`, family
   directories. Existing per-backend outputs move INTO the
   layout; `ship --verify` re-verifies the whole tree.
5. Native-byte persistence: realizers persist STEP/`.kicad_pcb`
   bytes into `.regolith/artifacts/` (the `NativeArtifactStore`)
   at realize time inside `staged_build`; `ship --build REPORT`
   never errs `native_artifact_not_found` for subjects the report
   realized. Test both fresh-ship and ship-from-report paths.
6. Canonical digests: every producer's `source_digest` uses the
   canonical content address from the payload (AD-18), not a
   local blake3 re-hash; assert equality against the Rust address
   in a test.
7. Style records seam: renderers accept a style record (sheet
   template, line weights, text heights) resolved via the record
   machinery from `magnetite.toml [style]`, defaulting to a new
   neutral `std.style` pack row; NO behavior change with the
   default pack (goldens byte-identical, proven).
8. Tests: registry registration/collision/plugin-entry tests;
   package-layout golden for one flagship (deterministic index);
   determinism (two ships byte-identical); docs: guide chapter
   for the package layout + extending with a renderer plugin.

## Acceptance criteria

- Adding a toy renderer via a test plugin requires ZERO edits to
  dispatch sites and appears in the package.
- `ship` on espresso_machine (with `--spec`) emits the full
  layout; `ship --verify` passes; two runs byte-identical.
- Existing drawing goldens unchanged under the default style
  pack; `make check` green.

## Close-out ledger (cycle 34)

Landed GREEN (`make check`: 1568 py + rust clippy + ty + 21 graphite),
default drawing goldens byte-identical (registries reproduce the exact
historical file set; proven by the untouched WO-50/58/78 sheet goldens).

DONE:
- D1 `ProducerRegistry` (`backends/registry.py`): `model_for_spec` is a
  registry lookup; `auto_specs` walks the registry; registration API is
  the plugin one. The if/elif ladder is gone.
- D2 `RendererRegistry`: `files_for_model` walks the registry;
  `[artifacts] formats` selection (parsed in `magnetite/manifest.py`);
  realized-IR renderer family seam present (`over` family key) for
  WO-100/101 to register into.
- D3 AD-26 `PluginKind.RENDERER` (spec text in 00-architecture.md +
  `plugins.py`); `backends/renderer_plugin.py` loader -- duplicate ids
  loud, never shadowing; built-ins never overridden.
- D4 One `dist/<project>/` layout: `index.md` (deterministic, gate
  stamp + family present/absent table + per-file digest),
  `gate_summary.json`, `parity_ledger.json`, `acceptance_ledger.json`
  (WO-98 hook -- placeholder, ZERO gate/acceptance semantics computed
  here), beside the per-family artifact files; every side file
  content-addressed in the manifest and re-verified by `ship --verify`.
- D5 Native-byte persistence at realize time in `staged_build`
  (STEP + `.kicad_pcb` into `NativeArtifactStore` rooted where `ship`
  reads); `ship --build <report>` can no longer miss bytes it realized.
- D8 Tests (`tests/backends/test_wo99_registries.py`: registry
  registration/collision, toy-renderer-plugin-appears-with-zero-edits,
  auto_specs registry walk, format selection, package determinism) +
  guide chapter `docs/guide/20-emission-and-packaging.md`.
- D7 (config half): `[style] pack` parsed into the manifest model.

ESCALATED (deferred, reopen pointers -- NOT silently dropped):
- D6 canonical digests. A producer's `source_digest` is serialized INTO
  the `DrawingModel` JSON, so swapping the local blake3 for the Rust
  AD-18 content address changes the drawing goldens -- it cannot land in
  the same change that must prove goldens byte-identical, and for a
  standalone `RealizedGeometry` there is no upstream Rust-computed digest
  to reproduce (`put_realized_geometry`'s own note: it uses
  `PayloadStore.put`, a fresh blake3). Needs either a golden regen pass
  with a census diff, or a Rust surface that exposes the canonical
  address for the standalone-realized IRs. Recommend a dedicated slice
  (with the fleet golden regen) rather than forcing it here.
- D7 (renderer half): threading a resolved `StyleRecord` through
  `render_svg`/`render_dxf`/`render_pdf` (each with its own hard-coded
  aesthetic constants) is a real 3-renderer refactor whose neutral
  default must reproduce every constant exactly. The `[style]` config
  surface + the seam intent are landed; the renderer plumbing + the
  `std.style` neutral pack record are the remaining work. Recommend a
  slice paired with the golden regen so the byte-identical claim is
  proven mechanically.
