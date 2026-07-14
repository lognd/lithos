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
| `boards/board.kicad_pcb` | 1055 | `sha256:f777c8e535ea5343eba0454687cabcb0386afc5fcf3f2af93f83c9e8fcb0f00d` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:8a0022eb3d9fd008ed91afc0339ec21b6255ff2e049e54fd5e24d8e96a33c098` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:5f77fac3d73e1c0742b26770933dead0fb6db91711c6540586ecf7f83c191f00` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:8a0022eb3d9fd008ed91afc0339ec21b6255ff2e049e54fd5e24d8e96a33c098` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:e80d3f0715072af033f98bab11c3d9bc5b021409692881197e5f8b0556487a46` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:cbc9cd16ab1af6134a2a8034328a836f6715758f3066842aeb8d317d0dea3e30` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:355e01485935e567306421bc3255fd6140a5fd4899a7dbd5c890c28602224132` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:118e2e415ddd40ef9ac08b31350199b006193e1225592f42aba11e27b27f7c55` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:8f622c57df23f0eac6fd96c99694f7fea5e39b2b4697da4fc53d7129fbf511ce` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:8f0b46c176fe8cfb360f0d8cbc8d689b7d05794ee80ec464e73eadb4ccc00103` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:83b746f7e7f1530831b02029193fc532e3b39194cedd1f37160a4037eab4e83a` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:1ec86523b3f4efec3bcc9489448f76938c963483e974b2367a1bef1fcae14ba3` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:cbc9cd16ab1af6134a2a8034328a836f6715758f3066842aeb8d317d0dea3e30` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:dd08255265e80d01a199644c29ed9a2a5fb831c264c4e5a76537b18927ba562a` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:31ceb81f1c259d8cbb0127e09ab925207c6b55861edd3100cd234304d84b0425` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:44e1ae995a5b439a5f4852973ad9753214a1722e7393ee43f4c1a0c771278dc9` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:3a2f0e8857b558472e36d90575cdad3198c5c8a07a8a9316654a4b1b1e4cbf7e` |
| `boards/gerbers/board-F_Silkscreen.gto` | 17541 | `sha256:ce694391dcc66061fb9676a0d825b0a6b771c42d805a4dbdc868379e93d423cd` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:cbc9cd16ab1af6134a2a8034328a836f6715758f3066842aeb8d317d0dea3e30` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:39080c7dcd9c8018b65cfa5bf33fd368d0241386e1083a2449ce477407cd1ab3` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
