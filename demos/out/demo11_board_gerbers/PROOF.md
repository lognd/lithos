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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:bcac0406b79d52d7f39580e8ee699e33ca76e0af6d2dbd7cb9a78085b3f4711e` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:782d1fd8072909f1e3d4c5297e785d30139c00f4b940a0739f77aa71efd2c781` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:bcac0406b79d52d7f39580e8ee699e33ca76e0af6d2dbd7cb9a78085b3f4711e` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:b71515b33c958a336c046ee64d0884cfef7fa6389ea740dcca8a2453e81ccb5c` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:4c07de30b98359fb764a20ba3c5fe47576997fd4baec0d594f62fcae4064c455` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:57cf9f053f44cdc9d34bcd6321d0be71cdf3d44bbda840f84928606b0e278a9c` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:0341eb9385bfd6c00a2dd9164df6c1852defed853fac281906737892800abe04` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:2c09c282c07a4723c0b096629d6eab6c519f179338c2a0ad0834583b28938942` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:9fce1a8484e18614f809fc77cc52edd638ac0f92cc7df0380b06a8896bda824c` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:e46e33608b0e75d0b8df4ddbbc483597a3e3206be03d43a31f2358721ad916c3` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:b440e413391f87e14792e6a23fc69fa89318c0ac7c7d68981ba6d17f18d819cd` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:4c07de30b98359fb764a20ba3c5fe47576997fd4baec0d594f62fcae4064c455` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:8ad33d4b2e72eb972f7eef6f09f527e86022e215dc9131dbf787a4cabbff1bcb` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:5add3f1fbd6a1cfea50ab50d77e8198a859435365c92f6d2488839669a731daa` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:672a2ec9f069b7d3f0cffbc933ab0b35c1a71f4882944666b67362c7414da1c7` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:1deebc40ca3d27aec95378e815e67645d35bbcd7d9e1b2fb15119cb5d16e0c35` |
| `boards/gerbers/board-F_Silkscreen.gto` | 17541 | `sha256:14e828625aa2df2a2c18461d4bd1ce17c5b6272039d2a1777543ccc24e2f68b1` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:4c07de30b98359fb764a20ba3c5fe47576997fd4baec0d594f62fcae4064c455` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:a87dd4701416cbc4a99bd1e9ec2d96010f5118ea4aa91aae650eb9c23c2f3ae7` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
