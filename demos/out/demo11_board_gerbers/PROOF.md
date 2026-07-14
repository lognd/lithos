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
| `boards/board.kicad_pcb` | 946 | `sha256:bc691f1287554eeae4218f118ef21158f1d18f0dce9135d205a4a21c8bfab620` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:70d03a057724f995095e9496efacefc05086a1267ce5bfe2e4b99a5c50f3c004` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:3fe4e2a3eb99d076cab50c75f8099f52ff720cdd68dd713f6fae59b4ee7e08f8` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:aeeb372940d5ac73464ce61d2d34295def8dba5a261eb7995b0bde8a5ba137a5` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:39fa05216e6f18a45f5a510ac4d8743e2d97d7c21535dffd0d0ba0ce0160c765` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:3143701058c50f3c556e6eb9c17c5bba869545dfbe5cbacb416dad48d40731a0` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:5d5df5be65120feec8f4c646c5ec87784bbc009061aaaff786a8f392f1ced434` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:1f573400638fd51473a0483750dd9345101ed9d188ebf2cdfd0090c55e573f50` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:1d7bb10210c80a3611638c74716adaf8b07b9c5d7d11d55c2f7de8bbe0aaa629` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:8141f87b37f2609b6618756569aa7c44c04f5b51c80af602e7ff327d49ecd0c1` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:35093b55a0f78caaedcd987e7c10ac5b52a63b36855bbfa3d4ce772ea74fbdb1` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:e89c160321a37b9fb819ba91e530c33f5ddb976fe31af8f78c470c181012207f` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:3143701058c50f3c556e6eb9c17c5bba869545dfbe5cbacb416dad48d40731a0` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:e4ebaab82370648503a289a3840f381df7f443474fc1bb7ae401ba4911edb864` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:e58dcd4f288cb3b81ea9e20efb273a60617e8a527717f3c11889c3aca7c9221c` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:56907bc109bc76d9003275969419a91b5bc5ebeb5d4a8391e9e8456f1c3cb8e9` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:c79009198e8421565233937d77123d5ea984fb2cdad4500afec774abe2ddbd51` |
| `boards/gerbers/board-F_Silkscreen.gto` | 10578 | `sha256:068b2df06482e5054b34ea5b35a6658a25fbe9b33ae6732e9124288daeba8436` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:3143701058c50f3c556e6eb9c17c5bba869545dfbe5cbacb416dad48d40731a0` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:f23a86a303d3d39cb87d5470db1576bbf8b3c7bbfd86bbdef60bd09def43d779` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
