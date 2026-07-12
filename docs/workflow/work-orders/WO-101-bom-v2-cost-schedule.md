# WO-101 -- Derived BOM v2 + cost and schedule sheets

Status: open
Language: Python (backends; read-side of payload/records/costing)
Spec: D208; charter 38 sec. 1.7/1.8; regolith/07 sec. 6 (backends
  never invent); AD-27 (schedules in scope); WO-54 (costing
  evidence + pins); WO-84/D192/D201 (record resolution);
  D204 (mass precedent honesty -- do NOT fake mass).

## Goal

The BOM derives from the design graph with real quantities, real
record-pinned part numbers, real mass where computable, and joined
cost columns; costing evidence and calcite/CAM schedules become
shipped sheets. The area-labeled-as-mass landmine dies.

## Deliverables

1. Derivation pass: one `derive_bom_rows(report)` that walks the
   payload -- assembly members (RealizedAssembly), entity DB
   parts, frame members (FramePayload + section/material pins),
   elec block instances (BlockRequirement/board entities),
   flownet fittings -- into typed rows {subject, kind, qty,
   record ref + pin hash where a record resolved, material,
   description}. Part numbers ONLY from pinned records or caller
   `AssemblyLine`s (which override/augment by subject key);
   a row with no record and no caller line ships with an
   explicit `unsourced` marker, never an invented number.
2. Real mass: density (material record) x volume (OCP volumetrics
   over the pinned STEP bytes) with both pins carried as
   provenance; where either input is missing the mass cell is
   honestly empty with a reason -- REMOVE the `mass_hint =
   area_mm2` field entirely (it is a correctness landmine; grep
   consumers and fix them in the same change).
3. Cost join: `BuildReport.cost_estimates` digests + record pins
   join onto matching rows as cost columns; totals row cites the
   profile. No estimate -> empty cell + reason.
4. Renderers (via WO-99's registry): bom.csv, bom.json,
   bom.pdf (DrawingModel table through the existing PDF
   renderer), bom.md. Deterministic ordering (subject key).
5. Cost sheet + schedule sheet producers: costing evidence ->
   cost summary sheet; calcite member schedule + CAM plan summary
   -> schedule sheets -- all ordinary DrawingModel tables through
   ordinary producers, preview-stamped like everything else.
6. Tests: derived BOM golden for cnc_router_r1 (real STEP mass
   for the 9 real-geometry parts) and timber_pavilion (frame
   member rows + schedule sheet); override/augment semantics;
   unsourced marker; determinism; docs: guide section + regolith/
   07 cross-reference note.

## Acceptance criteria

- cnc_router_r1 ships a BOM where BedPlate has a real mass with
  material + geometry provenance, and NO artifact anywhere emits
  `mass_hint` as an area.
- timber_pavilion ships a member schedule sheet; espresso ships a
  cost sheet from its existing costing evidence.
- `make check` green; goldens reviewed.
