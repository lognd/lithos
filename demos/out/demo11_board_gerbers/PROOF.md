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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:f259677448d0710a72a801d7a6415b0dcd463dc301f9a23ff7c5b83f9fe35bd5` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:acc0f8b68f9841b17a237fbd724b1d68071700bb008f38f08476d87dffa945a8` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:f259677448d0710a72a801d7a6415b0dcd463dc301f9a23ff7c5b83f9fe35bd5` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:054afb3e233a1dad8633d1e23b3f5a6d4897908107f1e19e0b1707067eba5c65` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:1fe857ac7c5972819d2198eabaa8dfea8ccc32d82060ea50ff507e305b3ed389` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:506beb2ce1da0e0db66ebb48ed9585eedd6a7760987482d0f038003dee9d7fa3` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:4a1127f3bf26125950a69df633f4c1d2068803cb8bd65361d16e24ee2442636e` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:6f6b01d6c8ef1d4c87aa5296d1fb35391aa5a8f773441efb43e400a52630c23a` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:72f477907ee8331a2c0a42e39f261bcdf0ed142c4e50b48ca10803e8ba8e3882` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:305a3bd2b1882048dd765a45895ff0177a9d0ffe3d421081b8559ae8966721cd` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:84f843501a3bdc189bb836af17666039529875674852c5fad5b43dab4dd4f408` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:1fe857ac7c5972819d2198eabaa8dfea8ccc32d82060ea50ff507e305b3ed389` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:a66acd50e14e951cf4403c01779659ddf6c5c50facdbe240d0c61d4adc14f72d` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:c5dd03c38adaef0e167dcadd8917412c3da1c31493a2edbd93548da6ca1d819c` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:5c124f2753672ae7641db45c78ded3c8153c65495c3827a402b0a45417a3b4d2` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:1dea47eceecab550e3dd2745939f59de86a710170849bced79afab73a5a1c716` |
| `boards/gerbers/board-F_Silkscreen.gto` | 15772 | `sha256:77713327a0fbb29446ad5831813fb6dbaa159dcc92c91674ebbe6390020050c1` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:1fe857ac7c5972819d2198eabaa8dfea8ccc32d82060ea50ff507e305b3ed389` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:a5dc74c8dea343643258b6018c09db7c5d8f639f1a66c10f5643ee846589bfd8` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
