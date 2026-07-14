# WO-123 -- Artifact presentation v2: professional sheet rendering (D238/AD-39, charter 41)

Status: open
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
