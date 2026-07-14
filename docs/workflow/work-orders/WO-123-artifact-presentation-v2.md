# WO-123 -- Artifact presentation v2: professional sheet rendering (D238/AD-39, charter 41)

Status: honest-partial (landed 2026-07-14: renderer core v2, gating
  audit + INV-31, dimension entities, ruled tables, chart axes,
  labeled title block + provenance footer, calc typesetting,
  regenerated demos, guide section -- residuals in the close-out
  ledger below: F140 style-pack record home, F141 calc gating
  signature, F142 layered-diagram label collisions, F143
  continuation-sheet overflow)
Language: Python (backends/drawings renderer + style + audit,
  backends/calc.py sheet rendering, producers); no schema bump
  (D225/D239 -- presentation is emission-layer only).
Spec: charter 41 (NORMATIVE -- sections 1, 2, 4, 5 are this WO's
  contract); F135 (the evidence set your output must visibly fix);
  D238; AD-27 (one documentation IR); AD-36 (registry seam, style
  packs); AD-6/INV-10 (determinism -- no timestamps, byte-stable);
  regolith/13-invariants.md (INV-31 lands here WITH proof
  argument).

## Goal

Every sheet artifact regolith emits (mech/civil/fluid/elec
drawings, calc sheets, opt traces, BOM/cost/schedule sheets, SI
tables, reports) renders to charter 41's professional standard:
proper title block, real dimension entities, ruled tables, real
charts, measured placement with zero clipping/overlap -- and the
drafting audit becomes a gating check that would REFUSE today's
output.

## Deliverables

1. Sheet layout engine (renderer core): text measurement before
   placement; wrap / shrink-to-floor (never below min height) /
   continuation-sheet overflow; page frame + margins + zone marks;
   named-field title block (title, doc number, rev, scale, units,
   projection, sheet n/N, design short-hash, schema version, style
   pack id) with label/value typography per charter 41 sec. 1.
2. Dimension entities for drawings: extension lines, arrowheads,
   dimension text with units (tolerance where the payload carries
   one), view labels + per-view scale; the F135.1 floating-text
   dimensions are deleted, not restyled.
3. Ruled-table primitive shared by every table consumer (BOM,
   cost/schedule, SI, opt-trace candidates, calc inputs): header
   row, column alignment by type, units in headers. Pipe-delimited
   prose is removed from every renderer.
4. Chart primitive for opt traces (and any future series sheet):
   axes with ticks + unit-labeled titles, gridlines, legend,
   collision-free point annotation; winner marked on-chart
   (F135.2 fixed).
5. Calc sheet typesetting (backends/calc.py PDF path): Claim /
   Model / Inputs (ruled table with provenance pins) / Result
   (value, margin, verdict badge) / Evidence-chain footer sections
   per charter 41 sec. 2; content unchanged, layout new (F135.3
   fixed).
6. Drafting audit upgraded to GATING (ship path, all sheet
   families): clip detection, geometry-measured overlap detection,
   title-block field completeness, rendered min text height,
   table/chart discipline. Each F135 defect class gets a negative
   fixture the audit REFUSES with a named diagnostic. INV-31
   enters regolith/13-invariants.md with its proof argument in the
   SAME change.
7. Default style pack upgraded to the professional drafting look
   (faces, size scale, line weights, title-block geometry) --
   hash-pinned record data in std.style, the ONE home (no
   renderer hard-codes).
8. Goldens regenerated (never hand-edited) with the diff reviewed;
   docs: guide 21-reading-build-output.md gains a "reading the
   sheets" section; charter 41 cross-referenced.

## Acceptance

- The four F135 sheet defects are visibly gone in regenerated
  demo output (demo1 opt trace, demo3 drawing, demo15 calc
  sheets): no clipped text, no overlaps, real dimensions, real
  axes, ruled tables, complete labeled title blocks.
- The upgraded audit FAILS a checkout containing only the old
  renderer output (negative fixtures prove each rule bites).
- INV-31 in the invariant ledger with proof argument; audit gating
  in the ship path.
- Determinism: byte-identical across runs; no timestamps.
- `make check` green; `make demos` regenerates cleanly.
- COORDINATOR VISUAL PASS (D238.3): the coordinator renders and
  inspects your output at integration; "gorgeous" is granted by
  eye, and iteration requests are in-scope for this WO until
  granted.

## Escalation

Content gaps (a sheet NEEDS information the payload does not
carry, e.g. tolerance fields) are ledgered as named findings
(placeholder F-numbers) -- never invent data at the renderer
(D224 extension, charter 41 sec. 2). Style-pack schema needs that
would touch wire schemas: STOP, escalate to the coordinator
(D239).

## Close-out ledger (2026-07-14, honest-partial)

Landed (all `make check` legs green; demos regenerate cleanly;
coordinator visual pass performed on demo1 opt trace / demo3
drawing / demo15 calc sheet renders):

1. Renderer core v2 (`backends/drawings/renderer.py`, ONE geometry
   home shared by SVG/PDF/DXF and the audit): deterministic
   conservative text measurement (`measure_text_width_mm`), greedy
   wrap + shrink-to-floor (`wrap_to_width`/`fit_text`, never below
   `min_text_height_mm`), anchor clamping so nothing crosses the
   printable frame.
2. Dimension entities (`DimensionGeometry`): extension line,
   dimension line, two-stroke arrowheads, value+unit(+tolerance)
   text clamped in-bounds -- the F135.1 floating-text dimensions
   are deleted, not restyled.
3. Ruled-table primitive (`TableLayout`): measured column widths,
   header row rule, per-column numeric right-alignment, widest-
   column wrap when the table would overflow the sheet width;
   pipe-delimited prose removed from every renderer AND banned by
   audit rule.
4. Chart primitive (`ChartGeometry`): axes with tick labels,
   gridlines, plotted series, captions clamped ON the chart with
   tick-row clearance (F135.2 fixed).
5. Calc sheet typesetting via the no-view content-area rule +
   ruled Calculation/Inputs tables with wrapped claim text
   (F135.3 fixed); content unchanged.
6. GATING drafting audit (D238.1/INV-31): four geometry-measured
   rules (`no-clipping`, `geometric-overlap`,
   `no-pipe-delimited-cells`, `dimension-in-bounds`) measuring the
   EXACT renderer geometry; `assert_ship_ready` refuses the ship
   with a named `drafting_audit_refused` BackendError from
   `DrawingsBackend.produce`; negative fixtures per F135 defect
   class in `tests/backends/test_audit.py`. INV-31 + proof
   argument in `docs/spec/regolith/13-invariants.md`.
7. Title block v2: named label/value field cells (TITLE, DWG NO.,
   REV, SCALE, SUBJECT, SHEET n/N) + provenance footer (design
   content address, schema version, style pack id). Style scale
   (caption/body/subtitle/title faces, line weights, table/chart/
   dimension constants) added to `StyleRecord` -- overridable data,
   no renderer hard-codes.
8. Producer fixes the gating audit forced: fluid P&ID edge labels
   ladder by RESOLVED anchor; projection fallback banner anchored
   at view origin.
9. Docs: guide/21-reading-build-output.md "Reading the sheets"
   section; regenerated demo outputs (PROOF.md/manifest.json).

Residuals (each named, none silently dropped):

- F140 (deliverable 7 residual): the professional style constants
  live in `StyleRecord`'s defaults, NOT yet as a hash-pinned
  std.style record pack. Landing the record home needs the AD-36
  record plumbing for style packs end-to-end; until then the ONE
  home is style.py's defaults (still no renderer hard-codes).
- F141 (deliverable 6 residual): `calc_package_files` returns a
  bare tuple, so calc sheets get a LOUD warning, not a hard
  refusal -- making them gating needs its signature to grow
  `Result[..., BackendError]` across every call site (ledgered in
  `backends/calc.py`).
- F142 (deliverable 6 residual): the `contract_graph` and
  `harness` diagram kinds have known dense-layout label collisions
  in the WO-58 layered-layout helper (observed: arm_a6 22-node
  contract graph; 4-block harness fixture) -- carved out of the
  gate (warn, not refuse) in `audit.py::_NON_GATING_SOURCE_KINDS`
  until the layout helper gives label kinds their own lanes.
- F143 (deliverable 1 residual): continuation-sheet overflow is
  not implemented; the wrap/shrink ladder covers every current
  producer's content (no sheet reaches the floor height and still
  overflows). A producer emitting more than a page of content
  reopens this.
