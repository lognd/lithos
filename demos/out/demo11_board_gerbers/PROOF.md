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
| `boards/board.kicad_pcb` | 1055 | `sha256:98da74cad6ec4f2b5e1aa93eb620f3a4c3aae367d9962702e721a5c77c5b5714` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:7ea317653e0f2627dbb397d68ca9c2be21d4cbf5219402873d1d021a3f53e81b` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:dc8526eb84634e497d9210801592f9440279f3a1c7d42073feb6821d380257cd` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:7ea317653e0f2627dbb397d68ca9c2be21d4cbf5219402873d1d021a3f53e81b` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:50e5fd86eff1583447b6e9d5246abd170f20a831598407aa6477060d4631ebf9` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:80236ca1f494b055c998e7e1b7492fcb12e425f68cf74bfad8fb224bb916d50b` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:f76efb973bbf634d11b36e337ffe1fde1024ca215f9c092d8c8c0abbfe7514a0` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:d11691f839f82622d3dd3e59e71cb5add5f85ca9f654a6d9c7d879fb415a4fad` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:b2d9dc9fe6bedd89a75ca48c2ea0799767bd923934baa804e2e3a599a576118a` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:f9196a92bebb02d1403f2c4f3efaa32aa4eaf29f0acea7031b58947512c7a0fa` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:e3779d52f8e95c6987c39e8c6c152d4a6933566aea39a3f9516f4fd2b2111794` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:c19cebd52dc20ad6bd111b93fd923ab79e1c64465d490e9f81e2a6b4fbc620e6` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:80236ca1f494b055c998e7e1b7492fcb12e425f68cf74bfad8fb224bb916d50b` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:834a8e104bb5964e46cd1322dcac608146797efbcd42c209d462145f2cd1a642` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:207fe6f32469948d2441411b33a1cd66aef3e3bd74b42419bc579cb44f3e9a78` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:c5857b599d240aff874ac13596c247c38738e90cc04b0062e571f5c976082ab1` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:dcca40db38bdf959f33593fc3941dc804e54b532aeb358d22640526ab49d878b` |
| `boards/gerbers/board-F_Silkscreen.gto` | 13917 | `sha256:6cb9b7eb7aa99c4c554c9fa6a6d1554a45c6a11c3646b758a76fd72ff8fb9afe` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:80236ca1f494b055c998e7e1b7492fcb12e425f68cf74bfad8fb224bb916d50b` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:4cd0738a9aaf2b742f7efb1f2332500c09afcfe786c7674547b3051f6487df40` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
