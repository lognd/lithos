# WO-103 -- Real board outlines into real KiCad + gerber export

Status: done (cycle 34)
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

## Close-out ledger (cycle 34)

Landed GREEN (`make check` exit 0: cargo fmt/clippy, ruff, ty,
guard-core, schema-check, rust tests, 1577 py tests, 21 graphite) on
the reference host with the real leg EXERCISED (kicad-cli 10.0.4 at
/usr/bin/kicad-cli, pcbnew linked; the `-m kicad` tier ran REAL, 7
passed).

DONE:
- D1 Outline threading: `LayoutRequest` gains required
  `outline_w_mm`/`outline_d_mm` (gt=0, no placeholder default) -- the
  ONE outline-geometry source BOTH legs read. The real wrapper
  (`kicad_wrapper.py`) draws the caller's w x d rect on `Edge.Cuts`
  via real pcbnew; `_PLACEHOLDER_OUTLINE_MM` is deleted (repo-wide
  grep clean). The fake tier reads the same request fields
  (`run_fake_layout` dropped its duplicate w_mm/d_mm kwargs;
  `ElecBoardInputs` dropped its duplicate outline fields). Non-rect
  outlines NOT invented -- the spec shape today is rect w/d only
  (charter 38 sec. 1.10's own cut).
- D2 Real export leg: `ElecBackend` kicad-cli gerbers/drill/pos
  export runs against the DESIGN-outlined board; proven on-host end
  to end (mainboard_mx 305x244 -> real pcbnew board -> 31 emitted
  files; `board-Edge_Cuts.gm1` traces X305000000/Y-244000000 in
  FSLAX46 mm format = the exact 305.000000mm x 244.000000mm
  profile). Outputs land in the package `boards/` family beside the
  pinned `board.kicad_pcb` (the ship CLI registers the backend under
  the `boards` key; the spec BLOCK stays `"elec"`), plus a
  backend-derived `board_status.json`. Toolenv gating unchanged:
  absence is a skip with the install hint, never a failure.
- D3 Honesty: status stays "unrouted" on both legs (DERIVED from
  `RealizedLayout.routed_segments`, never asserted; no routing
  fabricated -- routing remains out of scope); fake tier still stamps
  `generator regolith-fake-kicad`; the package index's boards-family
  line surfaces the backend's own label ("unrouted -- fab-shape
  evidence: real board outline, no routing performed").
- D4 Tests: outline fields exercised in every LayoutRequest site;
  new `-m kicad` integration test
  (`test_real_wrapper_draws_the_mainboard_mx_outline_and_exports_gerbers`)
  asserts the 305/244 coordinates in the exported Edge.Cuts gerber;
  fake-tier regression bar held -- the committed mainboard_mx pinned
  artifact (sha256:ad019d5a...) is byte-identical to what the tier
  emits today (`_kicad_pcb_text` untouched). Guide 18 kicad-cli
  entry documents the real-outline behavior.

RESIDUAL (named, not dropped):
- Non-rect outlines: the spec shape stays rect w/d (charter 38
  sec. 1.10's own cut); escalate via a design-log entry when a
  corpus design needs a richer outline language.
- The fleet-wide release gate over the boards family (every corpus
  member shipping green) is WO-106's acceptance, not re-proven here.
