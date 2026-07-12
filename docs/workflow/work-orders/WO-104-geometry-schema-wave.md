# WO-104 -- Geometry + schema wave: RectPocket, arc sketches, mate edges, bounded segments (SCHEMA 29)

Status: in-progress
Language: Rust (regolith-oblig schema + regolith-lower) + Python
  (realizer/mech interpretation of the new ops)

## Close-out ledger (WO-104, cycle 34 -- F122)

LANDED (green, `make check`): the cycle's ONE schema bump, 28->29,
in exactly one place (`regolith-util::canon::SCHEMA_VERSION`),
covering all four shapes, `make schema`-regenerated + reviewed:
- `SegmentLength::Bounded { lo, hi, direction }` -- inert IR variant
  (D205/D209), round-trip tested; WO-97 consumes it.
- `FeatureOp::RectPocket` removal family + `RectPocketOp` OCP box-cut
  realizer (pocket volume / corner-radius / no-fit diagnostic tests).
- Arc sketch segments: arc-AWARE Rust promotion (`ClosureSegment.arc`
  / `ArcGeometry`, guard kept not deleted) + Python realizer real arc
  edge (`Sketch.arcs` -> b3d `RadiusArc`; arc-edge-count + extrusion
  tests). Corpus-promotion snapshot re-reviewed (arc profiles now
  promote, no error-level diagnostics added).
- `RealizedAssembly.mates: [MateEdge]` exposed from the WO-62 solve
  (never re-derived); `mating_graph_hash` now hashes them; the WO-96
  instructions producer fills `mate_ref` from the placing mate --
  proven on the exemplar (`test_placed_part_step_cites_the_placing_
  mate_edge`).

LANDED (F122 continuation, green `make check`): the weldment
`RectTube` half of the acceptance sentence. Every corpus `RectTube`
weldment piece (`part <Name>` with a `pieces:` block: cnc_router_r1
`BaseFrame`, tracks `weldment_frame` `MachineFrame`) now realizes to
real STEP end to end via `staged_build` -- a source-text weldment path
(`orchestrator/programs.py::_weldment_piece_programs`) recognizes each
literal `stock RectTube(W x H x T, l=L)` piece and emits a `blank`
outer solid (W x H face, extruded by L) + one centered `RectPocket`
cavity ((W-2T) x (H-2T) x (L-T), one wall-thickness floor -- the
single-cavity model `RectPocketOp` documents). `Plate` weldment pieces
ride the same path as plain blanks. Keyed `<part>.<piece>`, cavity-less
so `staged_build` realizes them, no hand-authored program. Census +
end-to-end STEP tests: `test_weldment_recttube_pieces_realize_real_
step`. Goldens re-reviewed: no diagnostic drift (the source path adds
geometry at realize time; the `check` obligation set is unchanged).

RESIDUAL (still escalated, F122/F123): the arc-profile extrusion half
is NOT closed. The one corpus arc-extrusion part is `saw_stock(
extrusion(BeamSection, l=820mm))` (cnc_router_r1 `GantryBeam`), whose
`BeamSection` walk closes through two `arc tangent` corner blends. The
arc REALIZER primitive landed (a `Sketch.arcs` -> b3d `RadiusArc` edge,
unit-tested) and takes an EXPLICIT arc endpoint (`ProfileArc.to`), but
NOTHING computes that endpoint: the closed polygon of a tangent-arc
walk is nonlinear in the bulge radius, which the Rust closure solve
(`close_walk`) explicitly defers as "a separate increment"
(`ClosureSegment.arc` docstring) -- `ArcGeometry` carries only
`bulge`/`join`, no radius or endpoint. Deriving it in Python would
duplicate the Rust closure the D205 escalation forbids duplicating.
So this is a real geometry increment (tangent-arc walk closure ->
arc endpoints), not source wiring; it is escalated (F123), never
invented around. `GantryBeam` stays honestly non-convertible
(`_STOCK_ESCALATED`) alongside `CarriagePlate` (non-literal
`rect(1.1*w, ...)` expression). WO-104 Status stays `in-progress`
until the arc-closure increment lands and the full acceptance
sentence (RectTube AND arc-extrusion) is honestly closed.
Spec: D211 (this WO owns the cycle's ONE bump, 28->29); D208/D209;
  charter 38 sec. 1.13; charter 30 (geometry lowering); the
  2026-07-11 escalations (RectTube/extrusion, session record);
  WO-62 (RealizedAssembly), WO-77 (removal-verb precedent for new
  FeatureOps), WO-97 (consumes SegmentLength::Bounded).

## Goal

One coordinated schema bump lands the four blocked shapes: a
rectangular interior pocket (RectTube stock), arc segments in
Sketch outlines (extrusion profiles), mate edges on
RealizedAssembly (real instruction ordering), and
SegmentLength::Bounded (WO-97's IR half).

## Deliverables

1. `FeatureOp::RectPocket` (schema + lowering + realizer
   interpretation via OCP box-cut): unblocks RectTube stock
   recognition -- extend the stock-recognition path (orchestrator/
   programs.py + the Rust side that owns it) so `saw_stock(
   rect_tube(...))` emits blank + RectPocket; cnc_router_r1
   BaseFrame (or the corpus's actual RectTube parts) gains real
   STEP geometry.
2. Arc sketch segments: `Sketch` outline grammar/IR accepts
   tangent arcs (the `arc tangent` profile walk); realizer
   promotes them to real edges; the extrusion parts (GantryBeam
   family) gain real geometry. Straight-line-only guards become
   arc-aware, not deleted.
3. `RealizedAssembly.mates`: typed mate edges (part a, part b,
   mate kind, dof consumed) emitted by the existing assembly
   solve (WO-62's mate solve already computes them -- expose,
   never re-derive); `mating_graph_hash` now hashes the exposed
   edges (document the compatibility note in the WO close-out).
4. `SegmentLength::Bounded { lo, hi, direction }` IR variant per
   D205's buildable half (removal.rs precedent) -- consumed by
   WO-97, inert until then (no behavior change this WO beyond
   carrying it).
5. SCHEMA_VERSION 28->29, `make schema` regeneration, goldens
   regenerated + diff-reviewed (no new error-level
   diagnostic_multiset rows), fixtures for each new shape
   (positive + negative), realizer unit tests (pocket volume,
   arc edge count), `make install` before `make check` noted for
   integrators.

## Acceptance criteria

- A RectTube stock part and an arc-profile extrusion part emit
  real STEP-derived geometry end to end (staged_build -> STEP in
  the artifact store).
- WO-96's instructions can read real mate edges (proven by one
  updated test on the WO-62 exemplar; full consumption is
  WO-100 D5).
- Exactly one schema bump; `make check` green.
