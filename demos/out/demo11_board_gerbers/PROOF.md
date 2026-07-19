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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:0a89e700dbd2d54b322b954ffadfe793ff073e1eb4681daddb1a6c30d37db509` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:476d0005d95214cc24758722eb0c5aac9740783dddd408b6078a061eb857cc95` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:0a89e700dbd2d54b322b954ffadfe793ff073e1eb4681daddb1a6c30d37db509` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:e6a012fb9a1ba0166ed2b0939731b33d74921cb5482d056fd465d704b9b9f931` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:01c2d8a066493d3ad90a52b5b100275c4fd89d2171a88330247ea92b024bb8e8` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:1983e80a44a00c292e0bb71d132d837dbdb4e68152ef344233983a65825e9138` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:106589b22cc3b086647f934dc40fa0bb423e360d4660933c03ad316d2ce99eb2` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:90edb5ff790377e9dc54bdb10bff24094b68a38118545b3947137c4df2430ebb` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:f64eb6eba076323ec3435a3ce64c0f7c4c3d4721886bdef7684e50366801a312` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:621bdc6f6e299214fc2579d38a99ccd9991de3e2f0cdc296e7d1edca0526d7ed` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:227b10626937b2f54d6d3af2c1b668b71dd7de23b90755e177650590843f16c8` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:01c2d8a066493d3ad90a52b5b100275c4fd89d2171a88330247ea92b024bb8e8` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:73b6ad48e6a629a3e8418ad416b5f6e8c8f33dd725c60b8e09ce4924062857fb` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:d57f89cc1dfeacd4d3f5c725ea21c44b8d48142204436059a2c41b78a08307cb` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:b7307f53ab5726b0bf64bb3015c407ad6bb9774bb4104d46ed63e2dc591c02dc` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:8c62c84ee45234d48c9bf89fb9bf0d5c57e323dc8c93331e001a26268d921886` |
| `boards/gerbers/board-F_Silkscreen.gto` | 16192 | `sha256:362501573356cdd3d3283e2fbc60b4f0539f6b25e47dbe5d299dbdb9c3df8b22` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:01c2d8a066493d3ad90a52b5b100275c4fd89d2171a88330247ea92b024bb8e8` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:1e45a4b98156ef970abbc147c4d98f23019991827373d96788f1c453f76070bf` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
