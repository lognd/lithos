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
| `boards/MainboardMcu.edit_model.json` | 232 | `sha256:938ba6547adec1530557fc45d5f96dd26aa445c569ae644b79786a23ea45ab60` |
| `boards/board.kicad_pcb` | 1055 | `sha256:3eab866a3c48a9f5289b880c682ad7acd415639108a6768463ebdd1766a900e4` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:5e57a9cfb7b5807cc04dcea93f0001ef8216cb38d61deded1017b15f9a95e1a2` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:41ced5b22d77c0ac3d54d04c5dcd8774852eefc0203b610f6cb02869a6654162` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:5e57a9cfb7b5807cc04dcea93f0001ef8216cb38d61deded1017b15f9a95e1a2` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:6148a2cf700f48f4430071e0bb61cb2820f6378b9ae5eb86cb881d8c9613cd59` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:7ef06f6620bbc316ac3ba497f3a91ccb3d215a978f4220e58664082dd34508a4` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:46d8f81a2f564386715f8f113b18b24e6174b40f8174064e23cc0f9744160410` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:b0822e7c59b8b8b3a1c88ad51fa21771c60779de520167ec8f41d26314d12c0d` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:ff200c6995f115bbe2904f97145199b0af3dcfe17abe1d1c69421f8068bd893d` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:cf342b3eb93a7eb97fe0112519806cec7b087016f1608745ffdc0afefcd1e98c` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:412f9b181c727f840e005a438ec458230439c90f2873181c9fcf0070a83373c1` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:5bd1fb426a922e94f44a67d50e24b8a104ad4b6b2ef9fcfb5d0f6333f150a9f8` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:7ef06f6620bbc316ac3ba497f3a91ccb3d215a978f4220e58664082dd34508a4` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:debe097d2a8def7d4e37734974c03fb89f701ac84564bc2a3bc1ab2c6a8bcb62` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:1c51be82a664d19af05cb3df78c6a9cfb128c6d0341dd5a50838d2c6d7f22cfb` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:2bc4a00c13abe20db17de5d2702617a0024ada6fa979ad67e579605cf24f5dbc` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:f39b352f79345a48c4dfb221ffb4221419648df40be49ef36a907d7917cdd2b1` |
| `boards/gerbers/board-F_Silkscreen.gto` | 13617 | `sha256:fc19a250e4338fc79acaf03ff4096b580ee18c0412e136844b5a9a6776cb1a38` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:7ef06f6620bbc316ac3ba497f3a91ccb3d215a978f4220e58664082dd34508a4` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:a3504cba95d34f58516295a65d91da14873e96da0729611dc3470b382fc3a38f` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
