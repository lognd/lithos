# 25 -- Drawings and shipped artifacts (design charter; D140, cycle 27)

> Charter for the documentation half of `regolith ship`: engineering
> drawings, diagrams, and schedules as DERIVED, deterministic,
> provenance-carrying artifacts over the AD-25 realized IRs. Ledger
> rule: AD-27 (00-architecture.md). Machinery: WO-50 (sheet
> producers ride WO-25's backend framework). Where this doc and a WO
> body conflict, this doc wins.

## 0. The gap this closes

The owner's north star ends in artifacts: "...makes the
layout/gerbers, geometry, drawings, and whatever other artifacts you
deem necessary." Gerbers and STEP exist (WO-24/25/22); schedules
were chartered for calcite (its 03 sec. 6); DRAWINGS had no home --
yet they are the one output every discipline still contractually
requires (fab drawings, assembly drawings, plan/section sheets,
P&IDs), and this toolchain is unusually positioned to produce them
HONESTLY: every dimension, tolerance, rating, and note that belongs
on a sheet already exists as a datum with provenance. A drawing here
is rendered evidence, never a parallel truth to maintain.

## 1. Design decisions (load-bearing)

1. **One documentation IR.** `DrawingModel` -- a Rust-sourced,
   schemars-derived schema in `regolith-oblig` (AD-5),
   content-addressed via the one encoder (AD-18): `sheets` (size,
   title block fields), `views` (projection of a named source IR:
   which realized-IR digest, which projection/plane/scale), 2D
   `entities` (segments/arcs/polylines/hatches -- projected, never
   authored), `dimensions` (value + THE RESOLUTION CAUSE or record
   ref it renders), `annotations` (notes, symbols, per: citations),
   and `tables` (schedules: typed rows). No producer emits page
   description; no renderer computes geometry.
2. **Producers derive; renderers render** (AD-27). Per-track sheet
   PRODUCERS (Python backends, AD-1) project realized IRs into
   `DrawingModel`: mech part/assembly drawings from
   `RealizedGeometry` + source dimensions/GD&T; elec assembly + fab
   detail sheets from `RealizedLayout` (gerbers stay kicad-cli's
   job); civil plan/section/elevation + schedule sheets from the
   `frame` payload, spaces/grids/levels, and envelope records; fluid
   P&ID-style diagrams from `flownet` payloads (net-derived
   schematics CANNOT disagree with what was verified). RENDERERS
   serialize `DrawingModel` to formats: SVG is the mandatory
   reference renderer (deterministic text output, diffable,
   goldenable); DXF and PDF are sibling renderers of the same IR.
3. **Every number on a sheet is cited.** A dimension renders a
   resolved value AND carries its cause (lockfile cause, record
   hash, obligation id) in the IR; renderers may emit them as
   hover/metadata layers. A drawing that shows a number the build
   cannot attribute is unrepresentable -- the schema requires the
   provenance field.
4. **Determinism and goldens.** Same build state -> byte-identical
   `DrawingModel` and byte-identical SVG (AD-6 rules: ordered
   collections, ryu floats). Drawing goldens join the corpus like
   every artifact; `make snapshots` reviews.
5. **Layout is mechanical, not aesthetic, v1.** View placement and
   dimension placement are deterministic heuristics (grid layout,
   standoff ladders); a human-directed sheet-layout surface (an
   `overlay`/annotation file) is FUTURE, entering as ordinary
   source, and is out of WO-50's scope.
6. **Diagram family included.** Net-derived diagrams (fluid P&ID,
   elec one-line/harness diagrams once WO-34 lands, civil load-path
   diagrams) are the same IR with schematic (non-projected)
   entities; symbol geometry comes from symbol RECORDS
   (pack content, hash-pinned), never hard-coded art.

## 2. What already carries it

The backend framework (WO-25) provides discovery, determinism, and
`regolith ship` wiring; AD-26 provides the plugin seam
(kind=backend); AD-25 provides every input (realized IRs by digest);
the evidence/lockfile machinery provides the numbers and causes.
This charter adds ONE schema and a family of producers/renderers --
no new pipeline, no new discovery, no second renderer per format.

## 3. Non-goals (reopen criteria attached)

- Geometry/BIM AUTHORING, IFC export: calcite/04's criterion stands.
- A WYSIWYG sheet editor: reopen on real demand; the overlay-file
  seam (sec. 1.5) is where it would land.
- Tolerance-stack ANALYSIS on drawings: the budgets own analysis;
  drawings render results.
- Native CAD drawing formats (DWG): DXF covers interchange; reopen
  on a consumer that cannot accept DXF/PDF.

## 4. Acceptance shape (what WO-50 must prove)

One mech part drawing (pillow_block), one civil sheet set
(small_office plan + member schedule), and one fluid P&ID
(feed_system) -- each: produced from real build state, deterministic
across two runs, every dimension carrying provenance, rendered by
the SVG reference renderer, golden-enrolled.
