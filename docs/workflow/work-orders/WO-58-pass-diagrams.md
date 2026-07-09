# WO-58: pass-visualization diagram producers (bdf-shaped views)

Status: in-progress (deliverables 1/3/5/6/7 done; deliverable 2
ESCALATED, not implemented this dispatch -- see the ledger at the
bottom of this file; deliverable 4 gated on WO-55 per this file's own
header, not implemented this dispatch)
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

## Ledger (this dispatch: deliverables 1/2/3/5/6/7 assigned; 4 out of scope)

**Done.**

- D3 (deterministic mechanical layout): `regolith.backends.drawings.
  layout` (`layered_positions`, `standoff_ladder`) -- longest-path
  layering from predecessor edges (roots at layer 0), a 3-segment
  orthogonal route per edge, a fixed-step label ladder. No aesthetic
  search; a re-run with the same node/edge order is byte-identical
  (`TestLayoutHelper`, `tests/backends/test_drawings.py`).
- D1 (`diagram.elec_blocks`): `regolith.backends.drawings.producers.
  elec_blocks`, reading a `HarnessPayload` (WO-34 D99, already landed
  in `BuildPayload.harnesses`, no schema change). NAMED
  SIMPLIFICATION, not a cut: cuprite net MEMBERSHIP (which schematic
  net a `component.port` belongs to) is not exposed to any existing
  seam today -- this is WO-34's OWN escalation note verbatim
  (`docs/workflow/work-orders/WO-34-routed-runs.md`, the `E0306`
  section), re-confirmed here rather than re-litigated. This producer
  therefore reads a harness's RUN endpoints (real, landed, artifact-
  only data) as its block/port/net-like structure: one rectangle per
  distinct component referenced by a run endpoint, one port annotation
  per distinct pin, one orthogonal polyline per run. Chosen corpus
  design: `examples/tracks/cuprite/wiring_harness.cupr`'s `MainLoom`
  harness (4 blocks, 2 runs) -- the acceptance criterion's "one
  rectangle per block, one polyline per net" is asserted by entity
  count in `TestElecBlocksProducer.
  test_one_rectangle_per_block_one_polyline_per_net`.
- D5 (wiring): `DrawingSpec.track == "elec_blocks"` reads
  `BackendInputs.harnesses` (new field, `regolith.backends.framework`);
  `regolith.backends.ship.ship` derives `harnesses` straight from
  `report.final.payload_json`'s `"harnesses"` key (a `HarnessPayload`
  carries no `PayloadRef`, WO-34 D3's own note, so it never reaches
  `report.realized_inputs` the way geometry/layouts/flownets/frames
  do) with an explicit-argument override, mirroring the existing four
  maps' convention; `regolith ship --spec`'s `"drawings"` block accepts
  `"track": "elec_blocks"` with no further CLI plumbing (WO-50
  precedent: `build` already ignores the `"drawings"` block by design,
  so no `build` flag was needed either).
- D6 (quality): `elec_blocks` sheets pass the full WO-50 drafting-audit
  rule pack unmodified (`TestElecBlocksProducer.
  test_passes_the_drafting_audit`); "goldens" in this repo's own
  precedent for this backend are the deterministic in-code assertions
  `TestElecBlocksProducer`/`TestDrawingsBackend` add (there is no
  separate `tests/golden/` fixture directory for WO-50's own mech/
  fluid/civil producers either -- `test_deterministic_across_two_runs`
  is the golden). The renderer (`regolith.backends.drawings.renderer.
  render_svg` and siblings) is UNMODIFIED -- no Rust file changed, `git
  diff --stat -- crates/ python/regolith/_schema` is empty for this
  dispatch, verified before commit.
- D7 (docs): this ledger; `docs/guide/00-getting-started.md` sec.
  "7a. Verifying a lowering visually"; charter cross-refs already name
  WO-58 (`docs/spec/toolchain/29-interaction-surface.md` sec. 4,
  `00-architecture.md` AD-31) -- no charter edit was needed or made.

**Escalated, not implemented (AD-22).**

- D2 (`diagram.contract_graph`): BLOCKED on a real `BuildPayload`
  producer gap, not a DrawingModel schema gap (so this is NOT the
  D160/WO-55-folded case the WO header anticipated -- it is AD-22's
  more general rule: "a consumer that hits a producer gap escalates it
  ... rather than growing its own extraction path against internal
  compiler state"). Verified by reading `crates/regolith-api/src/
  session.rs`'s `BuildPayload` struct field-by-field (diagnostics,
  resolutions, obligations, snapshots, evidence, ledger,
  feature_programs, block_requirements, flownets, field_datums,
  harnesses, frames) end to end: none of `regolith-ir`'s own
  `Interface`/`Frame`/`Mating` node types (`crates/regolith-ir/src/
  nodes.rs`) is serialized into `BuildPayload` anywhere. `Obligation`/
  `Resolution`/`Claim` (the only other BuildPayload-reachable
  structures) carry no interface name, promise-slot count, or
  connection kind either -- `subject_ref` is a content hash, not a
  readable name. Building this sheet honestly needs a NEW
  `BuildPayload` field (e.g. a `ContractGraphPayload` summarizing
  interfaces/frames/matings by name, mirroring `FlownetPayload`'s
  precedent), which is a Rust `regolith-ir`/`regolith-api` change --
  out of this WO's own scope header ("Rust none expected (renderer
  unmodified)"). Recommended fold-in: a WO-29-shaped follow-up (the
  crate that already owns the lowering output surface, per
  `docs/spec/toolchain/00-architecture.md` sec. 22 AD-22's own naming
  convention for this exact situation), NOT WO-55 (that schema bump is
  for `OptimizationTrace`, an unrelated payload).

**Out of scope for this dispatch (per dispatch instructions, not this
WO's own gate).**

- D4 (`diagram.opt_trace`): gated on WO-55 per this file's own header;
  not attempted.
