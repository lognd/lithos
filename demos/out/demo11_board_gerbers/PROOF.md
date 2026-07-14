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
| `boards/board.kicad_pcb` | 1055 | `sha256:2685ab67057d87e495c3e57d94d471061883dae2d642ad794fef97a78f9c1e3e` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:65d15dd3278f716085e6525da1505b2ae6fa7a4c532c5e221dbf771f93b993a9` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:9b2e98edfbfb3a43663211057fadf95783a078aaef58b056fce01fe7725a510a` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:f879fb68ad00bb3454b2fe55dd9a927a0868e44a79f515d4ac3b1035b8d99a1e` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:f3e58c7b2be3900fec887ce44f8b9614eda1761be30cebe64f823d35dce46dc3` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:efccdcb32fcdf3b1f4aad49b27ae200cd8ac712e6d571436f20896b131b04789` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:6958cffa0214a44953e144b2687797146d6f5d44c03d5b9f3b5c3d1ecd591fd3` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:929cb493e7bd5c15451f1996159cf6f964c0e6b8fdc0761fdad189bd93615938` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:6252116bdf02688838047c232aaf87fb203426e9f6600f8b3a0f1a3cfddb19c1` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:79a31c3ecf240d2669a206ca9c0eed374cbf01ba9f72b91313f992ed2e4bf746` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:24b978760f7562994fdddeba445388b366da9ce7a18f110f532078146db05845` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:abb2effd36e0eb23795adb3e4da8ee46a2348f735335d1af10176cc8bc175962` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:efccdcb32fcdf3b1f4aad49b27ae200cd8ac712e6d571436f20896b131b04789` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:5e022b344ce2cfcc54fea80c3f50f181098527ff7ad56a24ccace177fa2bd4bc` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:38fd5307fbf1e048e6b2942df791b8cd2349396aaa74b5964cb9e600d9471647` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:a42b49368b8106f5a0282b146aa9b064c2dd1109743ed0c3c809c6a5ce5dda73` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:5211503e81b08e1c0b4242b0c2b63f36de2694cbf12b338c7d6fa38868771b49` |
| `boards/gerbers/board-F_Silkscreen.gto` | 15772 | `sha256:3b7f15dc62734c64554fb5c09de77b96fc5cf7b2719d902e6ec4c073df8f2243` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:efccdcb32fcdf3b1f4aad49b27ae200cd8ac712e6d571436f20896b131b04789` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:5c0e964c0ff982472f3be25edee462cf2c92e835d0ef7418eb1837ef59fcc829` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
