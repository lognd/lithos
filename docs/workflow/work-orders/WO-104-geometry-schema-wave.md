# WO-104 -- Geometry + schema wave: RectPocket, arc sketches, mate edges, bounded segments (SCHEMA 29)

Status: open
Language: Rust (regolith-oblig schema + regolith-lower) + Python
  (realizer/mech interpretation of the new ops)
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
