# WO-101 -- Derived BOM v2 + cost and schedule sheets

Status: in-progress

## Close-out ledger (cycle 34, D210)

LANDED (green: ruff + ty + 178 backend tests + 18 new WO-101 tests):
- Deliverable 1 -- `regolith.backends.bom.derive_bom_rows`: derives typed
  rows from mech parts / assembly members / frame members / elec blocks /
  flownet fittings; caller `AssemblyLine`s override + augment by subject
  key; `unsourced` marker where no record and no line. Part numbers never
  invented.
- Deliverable 2 -- REAL mass = std.materials density x realized volume,
  material pin (`<key>@rev`) + geometry pin (STEP hash) carried; honest
  empty cell + reason where an input is missing. The `mass_hint = area_mm2`
  field is REMOVED from `mech.py` and its consumers fixed (D204/D210).
- Deliverable 3 -- cost join: `ItemizedEstimate` totals + profile cite
  join onto rows by subject; no estimate -> empty cell + reason.
- Deliverable 4 -- renderers bom.csv/json/md/pdf via the WO-99
  `RendererRegistry` under the `bom` `over` family (pdf through the
  existing `DrawingModel` PDF renderer); deterministic (subject key).
- Deliverable 5 -- `cost_schedule.cost_summary_sheet` +
  `member_schedule_sheet` (ordinary `DrawingModel` tables).
- Deliverable 6 (partial) -- focused unit tests: real STEP-part mass +
  provenance, unsourced, override/augment, determinism, cost join,
  four-format emission, no-mass_hint, material-record load, cost/schedule
  sheets. Docs: guide 20 BOM section + regolith/07 sec. 6 cross-ref.
- Wiring: `regolith ship` builds the `bom` backend (CLI
  `_bom_backend_from_spec`) with project std.materials records.

RESIDUAL (D210; WO-shaped follow-ons, none blocking the shipped core):
- ship-time cost-estimate threading (resolve `report.cost_estimates`
  digests from the payload store into the backend; currently empty ->
  honest empty cost cells);
- CAM plan summary schedule (no backend-facing plan payload yet);
- three-corpus end-to-end ship goldens (cnc_router_r1 / timber_pavilion /
  espresso). Status stays `in-progress` until these land.

ESCALATION: D210 records the volume-source decision (pinned topology
volume vs ship-time STEP re-import) against the INV-10/AD-6 determinism
guarantee.

## Work order


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
