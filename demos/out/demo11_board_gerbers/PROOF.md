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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:43baff54d9acbd639368d35077bd7bfe068f8ca210a7863bd37e7ba58510ff51` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:0d0b9634d1ab14648b14235a9cb960ba9b0855eb2e93f81d9609c93fe3170668` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:43baff54d9acbd639368d35077bd7bfe068f8ca210a7863bd37e7ba58510ff51` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:e38a86def50db5309a156268677d21449f36877145b8035b9bf18910c63d22aa` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:839bae15bc9ba9848ca912ecfe433c0ce9e5db5621e0da6b4db467084baaab29` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:760fa94419003c0fffa3c89b911c1c735ea3d0bf978a0480e30de3619d1264a9` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:c4abdef1763031dc6572153ae39bcfc186904cc41212a412c3ea445cc9fef28d` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:0defbafd7eccf3d557836c879708d9d3d49e93e17887aca91d891dbcd5e2493f` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:333ff571bfc798fa630a76e507a0f8afea8755f826469c706b571c19c17b8faf` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:3da9a0da3e2505fecb781c9897a3013b891098d4a54119579cc40ced01c2cc61` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:c27f724b8324ac47e353e5c9da509cec14a87e413ffd1af82efa7e2b91e06f0e` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:839bae15bc9ba9848ca912ecfe433c0ce9e5db5621e0da6b4db467084baaab29` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:d1e8238d76e3f53dc76e5572c27284ce06ee7c875e8c3e7022bbd3d5659b79ed` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:18a9cff7a1cb7ccee7efa097f7648536d7674c557319e00625c6468aab757b54` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:a492ea5d5b4ee7e168f0deaa70a7b581f6ab81cf2febddb0a0b3930a05128da9` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:c404c5982ba94af62b8b3594391b86f4684d038bf63342157ac36782946657a2` |
| `boards/gerbers/board-F_Silkscreen.gto` | 16192 | `sha256:7b0201d1051f7e76598c7d652769eff96eea0e2499f23a65a31e34ff0722eaa7` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:839bae15bc9ba9848ca912ecfe433c0ce9e5db5621e0da6b4db467084baaab29` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:266d4be9499979b1e9a7f4ba22aeea20eaf3a9acd3e8aabdd763a2187826e684` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
