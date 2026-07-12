# WO-99 -- Emission registries + the release package layout

Status: open
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
