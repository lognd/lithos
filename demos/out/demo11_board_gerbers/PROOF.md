# PROOF: real KiCad gerber set from the mainboard_mx BoardOutline

- feature proven: the shipped `boards/` manufacturing family (charter 38 sec. 1.10) -- gerber set, excellon drill file, pick-and-place CSV, the pinned `board.kicad_pcb`, the elec BOM (the spec's four vendor parts), and `panel.json`, all from the design's own declared 305x244mm BoardOutline.
- pipeline path: `regolith build --release --spec` (the elec leg realizes the board; the spec pins `deterministic: true` so the fake-KiCad tier writes the outline-only board, stamped `(generator regolith-fake-kicad)`) then `regolith ship --build --spec` (the ElecBackend resolves the pinned bytes and drives REAL `kicad-cli pcb export` -- kicad-cli 10.0.4 via toolenv on this host).
- 15 gerber layer(s), verified to carry the real KiCad generation header.
- honesty labels: `board_status.json` says `unrouted -- fab-shape evidence: real board outline, no routing performed` (asserted above; never a fabricated routed claim). The real kicad-cli exports embed `TF.CreationDate` timestamps, so every `gerbers/`, `drill/`, `pos/` row below is marked deterministic=False -- the fake tier remains the deterministic CI leg, exactly as charter 38 stamps it. Re-running this demo refreshes exactly those rows' hashes in `manifest.json` (the labeled churn); every deterministic row reproduces byte-identically.

## Re-run

```
uv run python -m demos.demo11_board_gerbers
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `boards/board.kicad_pcb` | 1055 | `sha256:2685ab67057d87e495c3e57d94d471061883dae2d642ad794fef97a78f9c1e3e` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:85387e570886d8f9fcfa75a196d7e6bee0460c72dc660f7cea86ec1e7150fb82` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:fe8275f305646960d3ec8a419d6d0cc1cb8625c4583bd9e82ca7ddf4a37bff9e` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:85387e570886d8f9fcfa75a196d7e6bee0460c72dc660f7cea86ec1e7150fb82` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:0e27b8423e0dd07aa3c56f7a7d821ff7fab10e5f60a758ed0773d4ae3c07444f` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:f7ce47ecce148cf4a290d04348e3b833dc631dcd6490ac8ede0404edf63c120c` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:92b252227df9996f569951574f3f350c6220dff305aef64f027a46882aa5caac` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:a8cde50cbe517d250bb2f5aca3cdd144db6dee729486f6e7c90b7fce2f4d0b15` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:773c0db0130b65e5d4f58c4394bd56b6117ea62afe4e9b7d66e449ee75c3a849` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:184aab5ddf9b509ddd33d8b050e7f3c1c055aab5f61c549465c36d5aedf22311` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:82849c81929a61814edb4d76150e386a28a946e5c72453f1c9aeffe609930553` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:4b83ecc9aabcf505cef81176925c10215d64f1188f9d0494a536b510ce6d50b0` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:f7ce47ecce148cf4a290d04348e3b833dc631dcd6490ac8ede0404edf63c120c` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:091f852d2e61a0adc11efbfd73f188609812c009204c745bbc23df1da3ec11e7` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:2422b821c0497e0897a2b399c2054acd80206fa74e793461b6340275263c4df2` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:982a709c43e0b5c9a2ee671734ef02d7119658b2ee3f6154a90cd29b99561979` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:cf8b8ff2dfab93dd986046f35f4be803aea5b39b40e37703310e755d79d53238` |
| `boards/gerbers/board-F_Silkscreen.gto` | 15772 | `sha256:5b0ebe65875298e35d18aa99e55bda308bde9b36469c630310f5ae349bd20d09` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:f7ce47ecce148cf4a290d04348e3b833dc631dcd6490ac8ede0404edf63c120c` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:b5576ef69e5a611ba2e79078ddc105942bd124a124cdfcf48c361e714550fb33` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
