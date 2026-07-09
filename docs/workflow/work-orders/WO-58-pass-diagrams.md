# WO-58: pass-visualization diagram producers (bdf-shaped views)

Status: todo
Depends: WO-50 (DrawingModel + SVG renderer, landed; the fluid P&ID
is the payload-derived template). Deliverable 4 (trace sheet) gates
on WO-55's schema merging -- if dispatched before that, deliver 1-3
and record 4 as the gated slice in the ledger. NO SCHEMA_VERSION
bump (D160): a proven DrawingModel field gap is ESCALATED per AD-22
for folding into WO-55's single bump, never bumped here.
Language: Python (backend producers, layout heuristics, goldens);
Rust none expected (renderer unmodified).
Spec: docs/spec/toolchain/29-interaction-surface.md sec. 1.6
(NORMATIVE), 25-drawings-and-artifacts.md (the one-IR doctrine,
determinism, audit), 00-architecture.md AD-27/AD-31, design-log
2026-07-09-cycle-30 D165.

## Goal

Lower passes become human-verifiable sheets: an elec structural
block diagram (blocks/ports/nets -- the bdf-shaped view), an L2
contract-graph sheet, and (post-WO-55) an optimization trajectory
sheet -- all DrawingModel through the existing SVG renderer,
deterministic, golden-enrolled.

## Deliverables

1. **`diagram.elec_blocks`** producer: from the lowered elec
   payload surfaces (blocks, ports, net membership as landed by
   WO-29/WO-34 payloads -- artifact-only inputs, AD-22), emit a
   DrawingModel diagram sheet: block rectangles with port stubs,
   net polylines, names as annotations; symbol geometry from
   records where the WO-50 symbol-record seam provides it, plain
   rectangles otherwise (record which).
2. **`diagram.contract_graph`** producer: from BuildPayload L2
   surfaces (frames, interfaces, connections): node-and-edge sheet
   with interface names, promise-slot counts, connection kinds as
   edge labels.
3. **Deterministic mechanical layout** (shared helper, ONE home in
   the backends package): layered DAG placement (longest-path
   layering, in-layer order = source order -- AD-6), orthogonal
   edge routing on a grid, standoff ladders for labels. No
   aesthetic search; byte-identical across runs by construction.
4. **`diagram.opt_trace`** producer (GATED on WO-55 merge): from an
   `OptimizationTrace` payload: candidate table (schedule-style
   `tables`) + convergence polyline (objective vs evaluation
   index), winner highlighted via annotation. Every number cites
   the trace digest (charter-25 provenance rule).
5. **Wiring**: ship-spec blocks + `regolith ship`/`build` flags per
   the WO-50 precedent; producers discovered through the existing
   backend seam (AD-26 kind=backend).
6. **Quality**: the applicable WO-50 drafting-audit rules run over
   these sheets (title block completeness, no overlapping
   annotations, text height); goldens (DrawingModel JSON + SVG)
   for: one corpus cuprite design's block diagram, one
   multi-artifact corpus design's contract graph.
7. **Docs**: charter cross-refs, guide section ("verifying a
   lowering visually"), WO ledger.

## Acceptance criteria

- Both wave-A sheets byte-identical across two runs; goldens
  enrolled; `make snapshots` reviews them.
- The block diagram of the chosen cuprite corpus design visibly
  matches its source structure (reviewed against the design's
  block/net list in the test by counting entities: one rectangle
  per block, one polyline per net -- structural assertions, not
  pixel taste).
- Renderer unmodified (diff-asserted) OR the escalation note filed
  and folded per AD-22/D160.
- Sheets pass the drafting-audit rules they are subject to; every
  rendered number/name carries provenance (schema-required).
- `make check` green; Status flipped (with deliverable 4's gate
  state named) in this change.
