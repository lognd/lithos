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
| `boards/board.kicad_pcb` | 1055 | `sha256:b4e001be1ebd940891ce54d0a079131d17a1d6142a344b98b995411dc0476cf0` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:3ccc99549ee43502fe04d0caa6566ff1a11eb56cf0c880e5b79be8cc915c3221` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:2b9bccf84e31d165c5efc2dddc492bf81a8f337eb5ba41d0f66ac5ea6065ae3e` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:3ccc99549ee43502fe04d0caa6566ff1a11eb56cf0c880e5b79be8cc915c3221` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:fe075f7076d2ff6a030697c6e0f9f395066ba9c2e7eec2b8554a1a042d0f1275` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:33ed0970e9c1694f7552b5f628281b933448a97febf73214516077aaba96e7e6` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:6a262f7d99211957fbb7f1c77393f77016ef431c99c4fe878c4c6c5ac3a7f80c` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:2c562f54c89170050d805a0fcce7a8ee29252c0b5203e0c34f0b7d12bc51cefa` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:a88112ebc484e4052499d30323cec6c9a425d372d2e370809a37da37b997b33a` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:943e2d66c7d82450cabebd4e94c0f71450556fdcee93bd610ec9ca54d2ec1090` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:1bc8d382e267b50cdd785915b46a7c4a94e02802842642031eab4f07f040f3ce` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:ed42bcaf102036112c8a41700ebcbc54b32dbfc2331b0f916fabe7937f77df81` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:33ed0970e9c1694f7552b5f628281b933448a97febf73214516077aaba96e7e6` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:64f498e947f5a29c96aa52b84fead9fb71ff34720c84476edcba22887a716418` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:fa513c3c55e71b081500d182c0b978c65595da58cc86d4d6688dd63cfc1954ae` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:d4a2217c1ffdb3c4cac29f372ae793967684af4471fa5de659c0e2132847870d` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:ea415c35b52f2c7370d3baf0ec8816dcc6f48a2db63544748da99cbbe70c893f` |
| `boards/gerbers/board-F_Silkscreen.gto` | 16192 | `sha256:64c092c29388b3a9a0264d75a9ec54ca85a9b5abd5cb5af30088c58021312c77` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:33ed0970e9c1694f7552b5f628281b933448a97febf73214516077aaba96e7e6` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:6905f70b81a72d34cbe4a71d029948214b743a5eac00e66d0910e12bd89e169b` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
