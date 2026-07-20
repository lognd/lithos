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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:6998b37ca33e45d8dadbb5fb041f79c636a2ad1efe7f91829b326f1a2f2bd049` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:e50235abf5b40418360d0dfca157489559b7a5e45975c40fb047e376a204526b` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:6998b37ca33e45d8dadbb5fb041f79c636a2ad1efe7f91829b326f1a2f2bd049` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:ec75309b0d7b63cd12b795a456c28820267db53540c96329a6c87ba3cab4d0a1` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:7e965f8f371faccf760a5c628b21c09685bd992bad4dd541542e10de621ab8d0` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:e93c9d800a71e4c2a07cd0f4fda82ba40ed3dc10bf941c0cd38922f4b1850e7c` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:9f89d527358e716a7c6d9eadf40dfc0a02515cad367884df995eec064081c5c3` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:5ce21160045d66efab984703932868b986a9e43a453e3944784547630e50fcba` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:73fdcffc4b902ac18141b1a1f33c94be90273688a6f3a0598f0b37e8c3a714d3` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:63749ad1473186d505d85da187a4e73ae6b303d88649a5892ea8585dd9b7d65f` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:fdc330a011bd34f145936df3f91d072439bb4305c8cb4fc9f438c08a5301d994` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:7e965f8f371faccf760a5c628b21c09685bd992bad4dd541542e10de621ab8d0` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:c3729c9686595bc845c60cf5c47bbd7da46d2586c0333afa30c17ba80f725891` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:30a0aad794daf583da5b7f434530eaa83de151c9dc92714866c453bb6ef089bc` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:9d632f021192fc4763b2f4060d4bc43aaf97b4bcbed3d47d5270faa8992db732` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:2f9e30dfae6fddd618c63668912da53b571413b47d1e9db0dd6710a9d254bac4` |
| `boards/gerbers/board-F_Silkscreen.gto` | 16192 | `sha256:35abc4abcd061c8e39a11419b21aa02162938f2657227f7d2ccac5cd7b0fbb47` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:7e965f8f371faccf760a5c628b21c09685bd992bad4dd541542e10de621ab8d0` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:8bd0e60554384e6af5863d78a3e82f33df5298233cba4359926b5da559717f35` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
