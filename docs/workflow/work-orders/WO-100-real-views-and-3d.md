# WO-100 -- Real projected drawing views + the 3D artifact family

Status: open
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
