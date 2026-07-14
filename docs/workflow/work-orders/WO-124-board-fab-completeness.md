# WO-124 -- Complete, professional board fab set: silkscreen, mask, paste, drill (D238.2/AD-39, charter 41 sec. 3)

Status: honest-partial -- every deliverable landed (fab-set
  completeness both legs, silkscreen identity + refdes labeling seam,
  completeness gate, docs, demo11 regenerated with the full set);
  named residuals: polarity marks and mask/paste/courtyard/drill
  CONTENT are evidence-backed absences (F136), the REV field reads
  N/A (F137) -- no schema bump, D239 not triggered -- and the
  coordinator visual pass (D238.3) is pending at integration by
  definition.
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

## Close-out ledger (2026-07-14)

**Landed:**

- D1 (real-KiCad leg): `_run_kicad_cli` (`backends/elec.py`) now
  passes `--layers` (the full charter 41 sec. 3 set, via
  `elec_fabset.kicad_layers_arg()`) to `pcb export gerbers`, and
  `--excellon-separate-th --generate-map --map-format gerberx2` to
  `pcb export drill`. `kicad-cli` auto-emits the `.gbrjob` job file
  once multiple layers are requested (verified on-host, kicad-cli
  10.0.4). Both layer-authoring tiers (`fake_kicad.py`,
  `kicad_wrapper.py`) gained the FULL standard KiCad layer table --
  the prior 3-layer table silently dropped every non-copper/non-Edge
  layer from a real-`kicad-cli` re-export (a real bug this WO fixes
  as a side effect of extending the layer list).
- D2 (silkscreen content, both legs): board-identity block (name +
  design short-hash from `netlist_hash`; `REV: N/A` -- F137) drawn
  as real `gr_text`/`PCB_TEXT` (real leg -- KiCad's own plotter
  renders genuine vector strokes) or a hand-rolled 3x5 stick font
  (fake leg, `elec_fabset._GerberWriter.text`). Refdes labeling seam
  built (`_placement_refdes_lines`, draws every
  `RealizedLayout.placements` entry) -- empty today (no fleet board
  has placements; F136 explains why polarity marks are out of
  reach). Connector channel labels: same seam, unexercised (no
  channel-carrying placement exists yet either).
- D3 (fake-KiCad tier): new `regolith.backends.elec_fabset` module --
  deterministic Gerber X2 + Excellon writer, replaces the prior
  `Err(tool_unavailable)` honest cut. Manifest-identical to the real
  leg (same relative paths under `gerbers/`/`drill/`).
- D4 (completeness check): `elec_fabset.check_fab_set_completeness`
  runs in `ElecBackend.produce` on BOTH legs' output before
  shipping; negative-tested against today's 4-layer set
  (`test_elec_fabset.py::test_check_fab_set_completeness_fails_on_
  todays_four_layer_output`).
- D5 (docs): `guide/15-board-correctness.md` sec. 6 (full-set table
  + named absences). demo11 NOT regenerated -- see F138.

**Named absences (D224, no schema bump, D239 not triggered):** F136
(pad-stack/courtyard/polarity data absent from `Placement`), F137
(no design-revision concept anywhere in the realized surface).

**Tests:** `tests/backends/test_elec.py` (8/8, including the real
`kicad-cli` round trip via `make kicad-link`) + new
`tests/backends/test_elec_fabset.py` (8/8). `make check`: see the
gate-record line below.

**Real-leg proof:** demo11 REGENERATED with the complete 19-file
`boards/` set (`--release` initially refused with 3 `elec.si.*`
`unmatched_call_path` deferrals -- the worktree venv lacked feldspar,
fixed per the dispatch remedy and recorded as F138). Self-verified by
parsing the shipped output: `F.Silkscreen` gerber carries 207 real
stroke (`D01`) segments from the plotted identity text; `board-
PTH.drl` is header-valid Excellon; `board.kicad_pcb` and the plotted
gerber both carry `MainboardMcu.outline <short-hash>` / `REV: N/A`.
A manual non-release `build`+`ship` of the same project double-proved
the leg before the venv fix.

**COORDINATOR VISUAL PASS (D238.3):** not yet recorded -- pending
integration; demo11's regenerated `dist/boards/` is the inspection
set (silkscreen legibility at 1:1, mask/paste sanity, drill map).
