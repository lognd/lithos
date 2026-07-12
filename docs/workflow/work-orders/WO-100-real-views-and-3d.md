# WO-100 -- Real projected drawing views + the 3D artifact family

Status: done
Language: Python (backends/drawings + a new renderer family; OCP)
Spec: D208; charter 38 sec. 1.5/1.6/1.13; charter 25 (DrawingModel
  is the only drawing IR -- producers project, renderers render);
  AD-6 (determinism), AD-31 (self-contained viewer posture);
  WO-96 (instructions honesty posture).

## Goal

Mech drawings stop being bbox stand-ins: OCP/OCCT hidden-line
projections of the pinned STEP bytes become real DrawingModel
geometry (front/top/side + isometric). A deterministic GLB + a
self-contained HTML viewer join the package as the 3D artifact
family. Assembly-instruction steps gain per-step projected views.

## Deliverables

1. Projection producer: `RealizedGeometry.step_content_hash` ->
   pinned STEP bytes -> OCP `HLRBRep` (visible edges; hidden
   edges as a dashed layer) -> DrawingModel segments/arcs/
   polylines per view; front/top/side + iso on one sheet via the
   existing layout machinery; dimensions keep their provenance
   rules (charter 25.3). DETERMINISM: fixed deflection/tolerance
   constants (named module constants), sorted entity emission,
   ryu-style float formatting to match AD-6; two runs
   byte-identical, proven by test.
2. Fallback honesty: when native bytes are absent, the current
   bbox stand-in remains BUT the sheet carries a loud annotation
   ("projected geometry unavailable: <reason>"); never a silent
   stand-in.
3. GLB renderer: OCP incremental-mesh tessellation (fixed
   parameters) -> deterministic binary glTF (sorted buffers,
   no timestamps, no generator variance) per RealizedGeometry
   part and per RealizedAssembly (placed instances via node
   transforms -- reuse placements, never re-solve). Registered
   through WO-99's renderer registry under `3d/`.
4. Viewer: ONE self-contained `viewer.html` per assembly/part
   (inline JS/CSS, zero external requests -- AD-31 graphite
   posture; embed the GLB as base64 or load the sibling file
   relatively). ASCII source. Orbit/pan/zoom + part-name hover
   from the GLB node names. Keep the JS dependency-free or
   vendor a minimal inline renderer -- NO CDN, no npm build step.
5. Instruction step views: for each WO-96 step, a small projected
   view (parts placed so far, current step highlighted) embedded
   in the markdown/PDF render; consumes WO-104's mate edges when
   merged, else the DOF-tier proxy (coordinate via the registry,
   no hard dependency).
6. Tests: projection golden for one real flagship part
   (cnc_router_r1 BedPlate has real STEP); GLB determinism +
   schema-validity (validate header/chunk structure, node count);
   viewer contains no external URL (assert); fallback annotation
   fires on a bytes-less subject; docs: guide section
   ("viewing your build in 3D"), docstrings.

## Acceptance criteria

- cnc_router_r1 preview/ship emits: a part sheet whose front view
  is a real silhouette (not a rectangle) for BedPlate, and
  `3d/<assembly>.glb` + `viewer.html` that opens offline.
- Byte-identical across two runs; `make check` green; no new
  external Python dependency beyond OCP/build123d already present
  (document the toolenv gating if OCP is optional on some hosts:
  degrade to the annotated fallback, never crash).

## Close-out ledger (done, cycle 34)

Delivered, `make check` green (1586 + 21 graphite passed):

1. Projection producer -- `backends/drawings/project.py`:
   `mech_part_projected_drawing` resolves the pinned STEP, runs
   OCCT `HLRBRep` into front/top/right + iso views on ONE ANSI-A
   sheet (visible edges = solid polylines; hidden edges = a
   geometry-level DASHED segment layer, see escalation below).
   Named deflection/quantization constants; canonical sorted
   emission; two-run byte-identity proven. `_mech` in
   `registry.py` now dispatches to it (zero dispatch-site churn;
   no golden regressions -- existing mech callers hit the fallback
   unchanged or pass through untouched).
2. Fallback honesty -- `_fallback` re-emits the v1 bbox stand-in
   plus a loud `projected geometry unavailable: <reason>`
   annotation; fires on absent bytes AND OCP-unavailable
   (`_project_views` returns `None`), never crashes.
3. GLB renderer -- `backends/three_d/{tessellate,glb}.py`:
   fixed-parameter BRepMesh tessellation -> canonical
   vertex/index buffers -> deterministic GLB (fixed generator,
   no timestamp, sorted). Part = one node; assembly = one node per
   part instance with its solved transform, meshes deduped by
   geometry digest. Registered through the WO-99 registry's new
   realized-IR family (`RendererRegistry.register_realized`,
   families `3d.part`/`3d.assembly`).
4. Viewer -- `backends/three_d/viewer.py`: one self-contained
   ASCII `viewer.html`, GLB embedded as base64, inline
   dependency-free WebGL2 renderer (orbit/pan/zoom, flat shading
   from screen-space derivatives, id-colour picking for part-name
   hover). Zero external requests, asserted.
5. Instruction step views -- `instructions.step_view_svgs` embeds
   a per-place-step projected front view (prior parts gray,
   current highlighted) into the markdown; honestly omitted when
   bytes/OCP absent. Wired through preview + `InstructionsBackend`.
6. Tests -- `tests/backends/test_wo100_projection_and_3d.py` (10):
   BedPlate real-silhouette + two-run identity, GLB header/chunk/
   node-count + determinism, assembly instancing, viewer offline/
   ASCII, bytes-less fallback, OCP-unavailable degrade, step
   views, registry families. Guide chapter 20 gains "Viewing your
   build in 3D".

### Escalations / documented simplifications

- **Hidden-line style has no schema field.** The entity schema
  carries no per-entity line-style/layer attribute and this WO
  bumps NO schema (per instruction). Hidden edges are therefore
  realized as fixed-length DASHED segments at the geometry level
  (a documented simplification, not a fabricated attribute). A
  first-class `layer`/`style` entity field is a future schema-bump
  WO if a renderer ever needs true dash-pattern semantics.
- **Realized-IR renderer callable shape.** `RendererRegistry`'s
  `DrawingRenderer` is `DrawingModel -> bytes`; the 3D renderers
  consume a `RealizedGeometry`/`RealizedAssembly` + native store
  and emit a coupled file set. Rather than force a type-dishonest
  `DrawingModel` callable, a sibling realized-family API
  (`register_realized`/`for_realized_family`, `RealizedRenderer`)
  was added to the SAME registry object (the module docstring's
  "same RendererRegistry, distinct family" promise), keeping one
  dispatch seam while staying type-honest. No architecture change
  requested; recorded here for the reviewer.
- **`source_digest` stays the local blake3.** Charter 38 decision
  4 (canonical Rust content address for `source_digest`) is a
  separate deliverable not in this WO's list; the projected views
  keep the existing producers' blake3-of-IR-bytes digest
  convention (unchanged from `mech_part_drawing`).
- **CLI 3D emission is opt-in** via a ship-spec `"three_d"` block
  (mirrors the drawings block); `regolith preview` renders it
  automatically. Full CLI `ship --release` of a source-driven
  flagship still hits the pre-existing "no `.hema` reaches T3 with
  a wired realized-geometry input" wall the WO-72 sheet tests
  already record -- so acceptance is exercised at the producer/
  backend API level exactly as those flagship tests are.
- **OCP has no type stubs**: the two direct OCP consumers get a
  scoped `ty` `unresolved-import = "ignore"` override; the viewer
  JS template gets a scoped ruff `E501` ignore (mirrors the
  generated-`models.py` precedent). No new runtime dependency.
