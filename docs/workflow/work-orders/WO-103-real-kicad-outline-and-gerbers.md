# WO-103 -- Real board outlines into real KiCad + gerber export

Status: open
Language: Python (realizer/elec + backends/elec; toolenv-gated)
Spec: D208; charter 38 sec. 1.10; AD-25; WO-24/25 (real-KiCad
  wrapper + backend framework); the 2026-07-11 fake-KiCad tier
  (realizer/elec/fake_kicad.py) -- its "real leg is never faked"
  law is UNCHANGED; toolenv doctrine (D191.3).

## Goal

The real KiCad wrapper draws the DESIGN'S board outline (the 50mm
placeholder square dies) and `kicad-cli` exports real gerbers/
drill/pick-place on hosts where toolenv resolves KiCad (the
reference host has kicad-cli 10.0.4 -- prove it for real).

## Deliverables

1. Outline threading: the same `BoardOutlineSpec` geometry the
   fake tier already renders (mainboard_mx 305x244mm Edge.Cuts)
   feeds `kicad_wrapper.py`'s board construction; kill
   `_PLACEHOLDER_OUTLINE_MM`. Non-rect outlines: whatever the
   spec shape carries today (rect w/d) -- do not invent a richer
   outline language; escalate if a corpus design needs one.
2. Real export leg: `ElecBackend` runs `kicad-cli pcb export
   gerbers|drill|pos` against the realized board where toolenv
   resolves a real KiCad; outputs land in the package `boards/`
   family beside the `.kicad_pcb`. The fake tier remains the
   deterministic CI leg, stamped `generator regolith-fake-kicad`
   as today; gate real-leg tests with the toolenv probe (skip
   with the install hint, never fail on tool absence).
3. Honesty: the board status stamp ("unrouted") stays truthful;
   routing is NOT this WO (no autoroute fabrication). Gerbers of
   an unrouted-but-real-outline board are legitimate fab-shape
   evidence and are labeled as such in the index.
4. Tests: unit (outline geometry in the generated s-expr,
   both legs byte-compared where deterministic); integration on
   the real leg behind the toolenv gate (mainboard_mx outline
   rect present in exported Edge.Cuts gerber); regression: fake
   tier byte-identical to current goldens; docs: guide 18
   external-tools section update.

## Acceptance criteria

- mainboard_mx ships `boards/` with a 305x244 real-KiCad board
  file (real leg) or the fake-tier equivalent (CI), each honestly
  stamped; on the reference host the gerber set exists and names
  the real outline.
- No placeholder-square constant remains; `make check` green.
