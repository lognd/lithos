# WO-124 -- Complete, professional board fab set: silkscreen, mask, paste, drill (D238.2/AD-39, charter 41 sec. 3)

Status: open
Language: Python (realizer/elec incl. fake_kicad tier,
  backends/elec.py exporter); no schema bump (D225/D239) -- if a
  silkscreen/placement need genuinely requires a payload slot,
  STOP and escalate (D239 bundles any bump with WO112-F4).
Spec: charter 41 sec. 3 (NORMATIVE fab-set contract); F135.4 (the
  evidence gap); D238; AD-36 (boards family, honest tier
  labeling); WO-103 close-out (real Edge.Cuts precedent);
  guide 15-board-correctness.md + 18-external-tools.md (toolenv
  kicad-cli resolution).

## Goal

A shipped board's gerber set is complete and fab-house-ready from
BOTH legs (real kicad-cli where toolenv resolves it, the
fake-KiCad tier otherwise): copper, soldermask F/B, paste F/B,
silkscreen F/B carrying refdes + polarity + board identity, edge
cuts, courtyard, fab notes, margin, job file, Excellon drill
(plated + non-plated) + drill map -- today's set (F135.4) stops at
copper/courtyard/edge/margin with no drill file in the shipped
package.

## Deliverables

1. Real-KiCad leg: extend the kicad-cli export invocation set to
   plot mask/paste/silkscreen F+B and fab layers, and to generate
   Excellon drill + map; the job file lists every emitted layer.
2. Silkscreen CONTENT (both legs): every refdes placed
   collision-free at charter 41 min text height beside its
   footprint; polarity/pin-1 marks for polarized parts; the board
   identity block (name, rev, design short-hash) on F.Silkscreen;
   connector channel labels where the placement carries them (the
   charter 40 tap header rides this hook later -- build the
   labeling seam, not the tap logic).
3. Fake-KiCad tier: emits the SAME file set with honest tier
   labeling unchanged -- deterministic minimal-but-valid gerber
   bodies (mask apertures from pad stacks, silkscreen text as
   strokes, drill from through-hole pad stacks). The two legs'
   file MANIFESTS are identical; bytes may differ (tier-labeled).
4. Set-completeness check in the ship path: job file vs emitted
   files vs charter 41 sec. 3 list -- a missing/extra layer is a
   named error, not a warning.
5. Package index + boards family docs updated (guide
   15-board-correctness.md gains the full-set table); demo11
   regenerated.

## Acceptance

- demo11's shipped gerber directory contains the complete charter
  41 sec. 3 set; the job file enumerates it; the completeness
  check would fail today's four-layer output (negative test).
- Real-leg proof on-host where kicad-cli resolves (it does on this
  host): plot succeeds, silkscreen contains refdes + identity
  text; fake-tier proof everywhere (unit + golden tests).
- Determinism both legs; goldens regenerated with reviewed diffs;
  `make check` green.
- COORDINATOR VISUAL PASS (D238.3): rendered gerber inspection
  (silkscreen legibility, mask/paste sanity, drill map) at
  integration; iteration in-scope until granted.

## Escalation

If placement data (footprint courtyards, pad stacks, polarized
flags) is missing from the realized surface for some fleet board,
emit the honest named absence per element and ledger a finding
(placeholder F-number) -- never fabricate geometry (D224). Schema
needs: STOP, coordinator adjudicates (D239).
