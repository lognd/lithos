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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:e8222ce6855ca46fbf242ea28fcef62e894ec7139d8b3c14f1eff2d26c1b0f06` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:61abe4b03b6f4febf904f4923c1a120fa714389a53a678aa195c1b22aa31b776` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:e8222ce6855ca46fbf242ea28fcef62e894ec7139d8b3c14f1eff2d26c1b0f06` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:100537fce295d8d2b0c49e35aba85cef6a54d52ab728e23e4fd7ba232fe6df44` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:e79926456953cef301f9be788a092cc67a0fbcbe4570789aaf3d59726585d6de` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:3a540d565415deb61faef5f08465a431678ed7033fdb2a429f4b56355b71241f` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:86299fd1c34ca765df3528084cbf9b7ae5ca3f972554f396841fa549f0697412` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:8685e4cde3757b0f030333983f8a2eeaa36ff0c4456c890189fa8b4a560eb543` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:10d2b859fdc840629b1f851197e372904ddf734d0a742b3c55b0185fd5b2b262` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:35e6ce51a083386bf9beea8006146a0e32a42174a595d23a93f9851037a86175` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:5c8db4824ab716ee1608d7148087c629b17255195fe731ee6522081fd77321ce` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:e79926456953cef301f9be788a092cc67a0fbcbe4570789aaf3d59726585d6de` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:17bc4dcb04f61fe991a3b5d59bdb30561d64e93a7370c9164608f2ebe4ee599d` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:77b0b0358618fccca9e83aa6321ced27cdfc1bb62d068c1184ab24e90cf051f8` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:32e6d64f6a6e1a9d32726cd905866d1ad6420b02a55944413f0c5bc5cc12c115` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:c9acd00b0de1e6490036284fc0fa18c11ad233825296155cdeab255020435b3e` |
| `boards/gerbers/board-F_Silkscreen.gto` | 10578 | `sha256:efb60bafa396ad4319908e5c498ccbe777e98bb7e80e30a07ec5d80423ad2794` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:e79926456953cef301f9be788a092cc67a0fbcbe4570789aaf3d59726585d6de` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:f7bf8d46628b2e5aad7f9e2922c2b1d18528d8d4c7aea3c8b6c1b156f3c5b190` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
