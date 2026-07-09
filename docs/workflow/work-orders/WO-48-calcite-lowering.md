# WO-48: calcite lowering + `std.civil` reference packs

Status: todo
Depends: WO-47 (typed calcite CST), WO-45 (the stdlib home it adds
`std.civil` to), WO-28 engine remainder (the rule-pack format the
code packs are written in -- the egress/occupancy L2 checks do NOT
depend on it and may land first if WO-28 is still open; split the
dispatch on that seam). Pattern: WO-32 (fluorite lowering -- the
proven grammar->lowering->schema->corpus->docs slice sequence; use
the same D1..Dn split discipline from its close-out).
Language: Rust (`regolith-lower`, `regolith-ir`/`regolith-oblig`
schema) + Python (packs, orchestrator seam); one SCHEMA_VERSION
bump coordinated at dispatch.
Spec: docs/spec/calcite/03-lowering.md (post-WO-46, NORMATIVE),
00-architecture.md AD-25 (realized-IR growth rule) / AD-22
(one producer per fact), design-log 2026-07-08-cycle-26 D133/D135;
regolith/13 INV-15 (ledger conservation -- the load-path check's
family), INV-24 (release gate); the WO-32 close-out (the
FlownetPayload precedent every step mirrors).

## Goal

Calcite designs check and build for real: circulation/egress and
load-path L2 checks fire over the typed CST, calcite claims lower
to obligations, the frame IR exists as a realized-domain payload
(AD-25 growth rule), and `std.civil` ships the load-combination +
occupancy/egress reference content the corpus cites -- ending the
last phantom references.

## Deliverables

1. L2 static checks in the lowering passes per 03-lowering's
   definitions: egress (travel distance/exit width/dead-end over
   the circulation graph), occupancy arithmetic, load-path
   conservation on the AD-23 net (a load with no path to a
   foundation is a leak -- the INV-15 family, its own E-code
   block); honest-pass + deliberate-violation fixtures each.
2. Claim lowering: the 03-lowering claim-family table ->
   obligations with correct given/payload citation (the
   `push_fluid_obligations` precedent in `claims.rs`).
3. Frame IR: the 03-lowering field list as a schemars schema in
   `regolith-oblig` (kind string per the D96 vocabulary -- extend
   the kind table in design/20-solver-abstraction.md AND feldspar's
   09-model-integration sec. 4 in the same change, the
   `layout.realized` precedent); emission from the lowered member/
   connection/load data; content-addressed via the ONE encoder.
4. `std.civil` under `stdlib/` (WO-45's layout): load cases +
   combination sets, occupancy/egress tables, starter structural
   records; the reference building-code rule pack IF the WO-28
   format exists by then, else its package home + records with a
   `# TODO(WO-28)` marker (record the cut).
5. Closed-form structural harness models (the `harness/models/`
   precedent): beam utilization + deflection against the frame IR's
   members -- enough for the corpus's non-FEA claims; feldspar
   consumption of the frame IR is feldspar-side follow-up (note it
   in feldspar's TODO, do not implement there).
6. Goldens: calcite corpus enters the golden/obligation corpus;
   fluorite/hematite/cuprite goldens unchanged.
7. Docs: 03-lowering flipped planned->implemented per section;
   regolith/08 + design/23 gain the calcite rows (the fluid-track
   precedent); regolith/11 sec. 8 `std.civil` entry flipped.

## Acceptance criteria

- The five-design corpus: violations fire (each L2 check proven
  both ways), clean designs produce stable obligation goldens.
- Frame IR round-trips through the payload store and appears in
  `regolith debug ir`.
- Zero golden churn outside calcite; `make check` green; one
  SCHEMA_VERSION bump.

## Non-goals

- FEA/frame solving (feldspar-side); drawing/BIM export; detailing;
  scheduling/cost (charter sec. 7 non-goals stand).
- Realizer/backend for calcite beyond the frame IR emission
  (schedules backend is future WO-25-family work; note demand,
  do not build).
