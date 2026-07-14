# Charter 41 -- Artifact presentation standard (AD-39)

Decided cycle 36 (D238, owner directive 2026-07-15; recon F135).
Machinery: WO-123 (rendering v2), WO-124 (fab-set completeness).
This charter is NORMATIVE for every renderer and every emitted
artifact family; it wins over the WO bodies it governs.

The bar, verbatim from the directive: every emitted artifact --
PDFs, drawings, gerbers, silkscreen, all of it -- is GORGEOUS,
professional, and as informational as possible. Proof is visual
(D238.3): the coordinator inspects rendered output at integration
and records acceptance in the design log.

## 1. Sheet grammar (all PDF/SVG sheet artifacts)

Every sheet artifact (drawings, calc sheets, opt traces, BOM/cost/
schedule sheets, SI tables, parity/audit reports) satisfies:

1. TITLE BLOCK: a ruled block of NAMED field cells -- title,
   document number, rev, scale, units, projection (mech views),
   sheet n/N, design content address (short), schema version,
   style pack id. Field LABELS render in a smaller caption face;
   values in the body face. No unlabeled text lines.
2. BORDER + ZONES: sheet border with margin per the style record;
   zone reference marks (A..; 1..) on drawings; page frame on
   report-style sheets.
3. TYPOGRAPHY SCALE: exactly the style pack's faces and the
   modular size scale (caption < body < subtitle < title); minimum
   rendered text height enforced; NO text below the minimum, ever.
4. NOTHING CLIPS, NOTHING OVERLAPS: every text run and mark is
   measured before placement; content that does not fit wraps,
   shrinks-to-floor (never below minimum height), or overflows to
   a continuation sheet -- it never crosses the page edge, another
   annotation, or the title block. This is INV-31, enforced by the
   gating drafting audit (sec. 4).
5. TABLES ARE TABLES: ruled header row + body rows with column
   alignment by type (text left, numbers right, units on the
   header) -- pipe-delimited prose is banned from every renderer.
6. CHARTS ARE CHARTS: axes with ticks and unit-labeled titles,
   gridlines at the minor emphasis level, a legend when more than
   one series, annotated points labeled without collision. A bare
   polyline is not a chart.

## 2. Informational density (D238.4)

More information, never less legibility:

- Mech drawings: real dimension entities (extension lines,
  arrowheads, dimension text with units and tolerance where the
  payload carries one), all realized principal dims, material +
  finish + mass (from the BOM truth) in the title block region,
  view labels + scale per view, notes block for claim-derived
  callouts (e.g. critical dims tied to claim ids).
- Calc sheets: typeset sections -- Claim (source text + anchor),
  Model (id, version, citation), Inputs (ruled table: symbol,
  value, units, provenance pin), Result (value, margin,
  verdict badge), Evidence chain (hashes, caption face). The
  existing content is already complete (F135); this is layout.
- Opt traces: objective vs candidate index chart with units, the
  winner marked ON the chart, the candidate table as a ruled
  table below (candidate, choice, objective, feasible, verdict).
- Every number printed traces to the payload/calc book/records --
  a renderer never computes new engineering numbers (D224
  extension); it formats what the truth surfaces carry.
- Provenance footer on every sheet: design content address, style
  pack, generator version. No wall-clock timestamps anywhere
  (determinism, AD-6/INV-10).

## 3. The fab set (boards; D238.2)

A shipped board emits the COMPLETE fabrication set, from both the
real-KiCad leg and the fake-KiCad tier (same file set, honest tier
labeling unchanged):

- Copper (all layers), soldermask F/B, paste F/B, SILKSCREEN F/B,
  edge cuts, courtyard, fab notes, margin, job file, drill
  (Excellon, plated + non-plated), drill map.
- Silkscreen carries: every refdes (collision-placed, min text
  height), polarity/pin-1 marks, connector channel labels (tap
  header channels when the debug profile is on, charter 40), and
  the board identity block: name, rev, design short-hash.
- The gerber job file lists every emitted layer; a layer in the
  job file that is not in the set (or vice versa) is a ship-path
  error.

## 4. Enforcement (gating, INV-31)

The drafting audit (`backends/drawings/audit.py`) is GATING in the
ship path for every sheet family and is upgraded until it actually
fails F135's evidence set:

- clip detection (any mark outside the printable frame),
- true overlap detection (geometry-measured, all annotation kinds,
  title block included),
- title-block field completeness (named fields, sec. 1.1),
- minimum text height (rendered, not requested),
- table/chart discipline (no raw delimiter prose; charts carry
  axes) -- rule additions land with the renderers that satisfy
  them.

Negative fixtures: deliberately-violating models are refused with
named diagnostics (regolith-diag values, AD-7). INV-31's proof
argument lands in `13-invariants.md` with WO-123.

## 5. Style packs

Everything visual (faces, sizes, line weights, emphasis levels,
title-block geometry) stays hash-pinned record data in the style
pack (`std.style`, AD-36) -- renderers read the pack, never
hard-code. The default pack is upgraded by WO-123 to a
professional drafting look (and remains the ONE home for it).

## 6. Proof of gorgeousness (D238.3)

Automated audits gate REGRESSIONS; a human eye grants the bar.
At each presentation WO's integration the coordinator renders the
package artifacts (PDF pages to raster, gerbers through a viewer,
silkscreen legibility at 1:1), inspects them, and records in the
design log: artifact hashes, what was inspected, verdict. A
presentation WO is not done without that record.
