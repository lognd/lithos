# PROOF: real KiCad gerber set from the mainboard_mx BoardOutline

- feature proven: the shipped `boards/` manufacturing family (charter 38 sec. 1.10) -- gerber set, excellon drill file, pick-and-place CSV, the pinned `board.kicad_pcb`, the elec BOM (the spec's four vendor parts), and `panel.json`, all from the design's own declared 305x244mm BoardOutline.
- pipeline path: `regolith build --release --spec` (the elec leg realizes the board; the spec pins `deterministic: true` so the fake-KiCad tier writes the outline-only board, stamped `(generator regolith-fake-kicad)`) then `regolith ship --build --spec` (the ElecBackend resolves the pinned bytes and drives REAL `kicad-cli pcb export` -- kicad-cli 10.0.4 via toolenv on this host).
- 7 gerber layer(s), verified to carry the real KiCad generation header.
- honesty labels: `board_status.json` says `unrouted -- fab-shape evidence: real board outline, no routing performed` (asserted above; never a fabricated routed claim). The real kicad-cli exports embed `TF.CreationDate` timestamps, so every `gerbers/`, `drill/`, `pos/` row below is marked deterministic=False -- the fake tier remains the deterministic CI leg, exactly as charter 38 stamps it. Re-running this demo refreshes exactly those rows' hashes in `manifest.json` (the labeled churn); every deterministic row reproduces byte-identically.

## Re-run

```
uv run python -m demos.demo11_board_gerbers
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `boards/board.kicad_pcb` | 262 | `sha256:da1c2e447954d4d943bdade029a93825764d90252168322daff3ffc0e820c4a4` |
| `boards/board_status.json` | 104 | `sha256:dfe745f6733c6b7d5f870e0b0ff8d4a52818239a391d19b0841ad8c84626a200` |
| `boards/bom.csv` | 318 | `sha256:9cbc9375a84d1c5c67104bcc1a715c53dd397d0f6aa643bff343fce98a656ad3` |
| `boards/drill/board.drl` | 304 | `sha256:51ffe4da67d85bb32d8a7094ec487720164e2dc52c05e854beb4e840a741b4eb` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:48a37210344d4de570a06c2d9d6af8c51490cb59511f142700ad991a2cac47ef` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:7241b56b39b4d5bd95f179a1a14b10d0badc179f7ce3145a7aa01a679747015c` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:429e37026184290a33068c7a81698f9947663ba8dca45f2ec53eaa753c811aac` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:48a37210344d4de570a06c2d9d6af8c51490cb59511f142700ad991a2cac47ef` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:e1d68597c9f25cdd6c51aadd34b820282037bf1e938a13f3b51511380b6806da` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:48a37210344d4de570a06c2d9d6af8c51490cb59511f142700ad991a2cac47ef` |
| `boards/gerbers/board-job.gbrjob` | 1299 | `sha256:d5a2b19df28c1ad45a529b76ec8a62444e3f316ebf09a1f09ee5bacf2a8458bf` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
