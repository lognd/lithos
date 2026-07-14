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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:a60c15140bafd5bdbf813d79486f3fc94a77224a37bef93acfd8407742cb1720` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:a838a52865f8c58ddb00bfb1b178753f8f0d0c45082028059ed5f03bd7df79ef` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:a60c15140bafd5bdbf813d79486f3fc94a77224a37bef93acfd8407742cb1720` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:0dad637aed89ff0cc66d19dee3e62eb1b346a11c101fe3f3364dd228d54f68e8` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:46582aab223513da3589c2ccafe701adb2794dae1694b4019b0abee968e769d5` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:5393fed040b21c869440eeca233eeecf8eb957478be60499a162641f434a36d1` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:daaa1f476fa812a8ff596eee2b4d05ff8f2473c6ae48564303bf6ea2544e8545` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:8f46af719a21c0d8d2a2491b64e10349d41ec9f55730f8cd16d8c173d71aa755` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:8357db0fe20f17558d084c9d8c8d85579acd7f6df63e52963bd42f3f15f1f969` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:3cb2eab540ee178e1e36eb1b99ba2c3ec55bc493c0c28607c6b1dc768c161476` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:c844cba281f13b633a023f2a7880342d9d80e68fa503a1077b31f4fa0c0e85e2` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:46582aab223513da3589c2ccafe701adb2794dae1694b4019b0abee968e769d5` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:af1ac7641621566b5268d3cf1282f4c33e0a57b2ae46653dcf52b9a65927d008` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:3b192c0eee5ae4d40e6d991d88b3cae302d2fa13f87a1808938e20cc2914b305` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:01d870de9fa851696bb02a0dbc9526fc22dec9b17aa095626eb3773aaa96b49f` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:a2cc8e120990207778471964f41765e329a28a0cf25567d3303c8e25d0fc02ba` |
| `boards/gerbers/board-F_Silkscreen.gto` | 15772 | `sha256:d9242794bd769635a2ec6d324c65407826d5e2a53f997343796d5f7abbf3f61b` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:46582aab223513da3589c2ccafe701adb2794dae1694b4019b0abee968e769d5` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:6bb2db4549f3c2961baba6c5c18ce7508099cd9b61b45616efe20e0eb3cdcf10` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
