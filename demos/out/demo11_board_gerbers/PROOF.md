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
| `boards/drill/board.drl` | 304 | `sha256:445c764b3009179f2abb5d5311a2465f24a3614e8c8ec76b9662f9467850de13` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:eaaad2942ff08bec030f3aa10898a70a9376ce2ac570ce2f20bfa95b75a32123` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:a4df5b0ac37b8bf224b7224d07a238b260717937f2c715cad916383c786d85a7` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:8330a97cab41627a59f43d417293d29b7ee4e0deb08ca3a68c28e48d08d64ad8` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:eaaad2942ff08bec030f3aa10898a70a9376ce2ac570ce2f20bfa95b75a32123` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:3b5dd4fe102c7ec443c48e6eb5864177dceac950d10bb4a67c8a5f01f291c6df` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:eaaad2942ff08bec030f3aa10898a70a9376ce2ac570ce2f20bfa95b75a32123` |
| `boards/gerbers/board-job.gbrjob` | 1299 | `sha256:448161f8cb9a9d469baa60dd62f826f02d38c0651a905f03b60e9b47c5c369d5` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
