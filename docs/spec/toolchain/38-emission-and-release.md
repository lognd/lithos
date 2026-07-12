# 38 -- Emission and release, v2 (design charter; D208, cycle 34)

> Charter for the COMPLETE artifact-emission surface: what a
> `regolith ship` release package contains, how producers and
> renderers are discovered and extended, and how the release gate
> reaches green honestly on every fleet design. Ledger rule: AD-36
> (00-architecture.md). Builds on charter 25 (drawings), AD-25
> (realized IRs), AD-26 (plugins), AD-27 (derived documentation),
> regolith/12 (the expert ladder), INV-24 (release-gate totality).
> Where this doc and a WO body conflict, this doc wins.

## 0. The gap this closes

F121 (design-log 2026-07-12) names ten corners the first-generation
emission pipeline painted itself into: placeholder board outlines,
bbox stand-in drawings, caller-only BOMs with an area labeled as
mass, evidence-only costing, unshipped firmware/HDL, unsortable
assembly steps, a hard-coded renderer list, non-canonical
provenance digests, transient native bytes, and an if/elif producer
ladder. Separately, INV-24's acceptance channel (the todo/assume/
waive ledger) exists only on the Rust side of the FFI, so `ship`
refuses fleet-wide with no honest path to green. This charter
closes all of it as ONE coherent surface.

## 1. Design decisions (load-bearing)

1. **The gate consumes the ledger (INV-24 completed).** The Python
   release gate reads the payload's `WaiveLedger`: an
   evidence-carrying waiver whose evidence meets the target claim
   group's trust floor is a DEVIATION -- the obligation's true
   status stands (INV-2), the release passes WITH the deviation
   listed; a bare waiver or `assume!` keeps refusing outside
   per-item exploration acknowledgment; expired waivers behave as
   absent and error as stale (regolith/12 rules 4/8); the accepted
   match set is lockfile-recorded and growth is loud (INV-12).
   `GateCounts` gains `accepted` accounting kept DISTINCT from
   discharged -- a stamp or summary never folds acceptances into
   passes. Engineering memos are a legitimate evidence doc class
   (D207).
2. **Producers and renderers are registries, not ladders.** A
   `ProducerRegistry` maps subject kind -> producer (the
   `model_for_spec` if/elif ladder dies); a `RendererRegistry`
   maps format id -> renderer (the hard-coded quintet in
   `files_for_model` dies). Built-ins register through the same
   API plugins use; AD-26's closed plugin-kind set gains
   `renderer`. `auto_specs` derivation walks the producer
   registry. Adding an artifact type or output format is ONE
   registration, zero edits to dispatch sites.
3. **One release-package layout.** `ship` emits
   `dist/<project>/`: `manifest.json` (blake3 + optional ed25519,
   as today), `index.md` (deterministic, names every artifact
   with its digest and the gate stamp), `gate_summary.json`,
   `acceptance_ledger.json` (every deviation/waiver/assume with
   basis, evidence ref, match set), `parity_ledger.json`, and
   per-family directories: `drawings/`, `3d/`, `bom/`,
   `instructions/`, `boards/`, `firmware/`, `hdl/`, `cost/`,
   `evidence/`. Every file is content-addressed in the manifest.
   Preview keeps its stamped-viewable contract (D197) unchanged.
4. **Provenance digests are canonical.** Every `source_digest` in
   a shipped artifact is the canonical Rust content address
   (AD-18), never a local re-hash. One encoder, one address.
5. **Drawings project real geometry.** Mech part/assembly views
   are OCP/OCCT hidden-line projections of the pinned STEP bytes
   into `DrawingModel` segments/arcs/polylines: front/top/side +
   isometric, deterministic (fixed deflection parameters, sorted
   output, ryu floats). The bbox stand-in survives only as a
   LOUDLY-ANNOTATED fallback when native bytes are absent.
6. **3D is an artifact family.** A deterministic glTF binary
   (GLB: fixed tessellation parameters, sorted buffers, no
   timestamps) per RealizedGeometry part and per RealizedAssembly,
   plus a self-contained zero-external-request HTML viewer (the
   graphite/AD-31 posture: inline everything, no CDN). Renderers
   of realized IRs, registered like any renderer.
7. **BOM v2 derives, never invents.** Rows are DERIVED from the
   design graph (assembly members, entity DB, frame members, elec
   block instances, flownet fittings) with quantities; part
   numbers come ONLY from hash-pinned records or caller-supplied
   lines (regolith/07 sec. 6 stands -- a backend never invents a
   part number); real mass = record density x OCP volume, carried
   with provenance (the area-as-mass_hint landmine dies); cost
   columns join the costing evidence by digest. Caller
   `AssemblyLine`s override/augment derived rows by subject key.
   Formats: csv, json, pdf, md -- via the renderer registry.
8. **Cost and schedule are sheets.** The costing evidence
   (persisted digests, record pins, profiles) renders into a cost
   sheet; calcite member schedules and CAM plan summaries render
   into schedule sheets -- both ordinary `DrawingModel` tables
   through ordinary producers (AD-27 said schedules were in
   scope; now they exist).
9. **The computer track ships.** A firmware backend emits the
   realized ELF/map/BSP report; an HDL backend emits the verified
   build products. Realization stops being verification-only.
10. **The elec path is real.** The board outline geometry that the
    fake tier already draws feeds the REAL KiCad wrapper (the
    50mm placeholder square dies); `kicad-cli` gerber/drill/
    pick-place export runs wherever toolenv resolves a real
    KiCad; the fake tier remains the deterministic CI leg and is
    stamped as such. "Never a faked layout" on the real leg is
    unchanged.
11. **Native bytes persist at realize time.** Realizers write
    STEP/`.kicad_pcb`/ELF bytes into the content-addressed
    artifact store when they realize (not transiently); `ship
    --build <report>` can never fail to find bytes for geometry
    the report says was realized.
12. **Style is data.** Sheet templates, title-block layouts, line
    weights, pen tables, text heights: hash-pinned style records
    (a `std.style` pack + project overrides selected in
    `magnetite.toml [style]`), consumed by renderers. No renderer
    hard-codes aesthetics beyond the neutral default pack
    (charter 25 sec. 1.5/1.6 extended; drafting-standard AUDIT
    packs are unchanged and still bind).
13. **Assembly instructions sort for real.** RealizedAssembly
    gains mate edges (WO-104's schema bump); steps are a
    deterministic topological order over them; each step renders
    a projected view of the parts placed so far; markdown + PDF
    via the registry. Torque callouts render ONLY discharged
    quantities (unchanged honesty).

## 2. What already carries it

The backend framework (WO-25/43) provides discovery and ship/preview
wiring; `DrawingModel` + the SVG/DXF/PDF renderers exist (WO-50);
the Rust waiver machinery is complete through the payload
(`regolith-lower::waivers`); OCP/OCCT and build123d are importable
and kicad-cli 10.0.4 resolves via toolenv on the reference host;
the D192/D201 record-path resolver carries memo/style records; the
plugin seam (AD-26) carries the new `renderer` kind. This charter
adds registries, producers, renderers, and gate consumption -- no
new pipeline, no second encoder, no second diagnostic renderer.

## 3. Non-goals (reopen criteria attached)

- WYSIWYG sheet/scene editors: charter 25's overlay-file seam
  stands; reopen on real demand.
- Raytraced/photoreal rendering: the GLB + viewer is the 3D
  contract; reopen on a consumer that cannot accept glTF.
- DWG/IFC export: charter 25 / calcite/04 criteria stand.
- Package-format plugins (zip/tar/OCI): `dist/` directory + manifest
  is the contract; archive it with ordinary tools; reopen on a
  registry-hosting consumer.
- Weakening any verdict semantics for shippability: not a reopen
  candidate at all (D206; INV-2/13/24/26 are untouchable).

## 4. Acceptance shape (the fleet gate, WO-106)

A single fleet sweep (`make fleet` + tests) proves: every D210
fleet project `build --release`s green (proven or accepted, gate
summary showing zero UNACCEPTED unresolved) and `ship`s a complete
package (manifest schema-valid, index present, every named family
present-or-explicitly-absent-with-reason, every digest canonical
and verifiable via `ship --verify`); every `examples/tracks/**`
single-file design builds `--release` green; every
`examples/negative/**` fixture still fails exactly as encoded; two
consecutive runs are byte-identical for every deterministic
artifact (GLB, SVG, DXF, PDF, kicad_pcb-fake, index, ledgers).
The sweep is census-goldened: per-project counts of discharged /
deviated / accepted obligations, so acceptance creep is a visible
diff, never drift.
