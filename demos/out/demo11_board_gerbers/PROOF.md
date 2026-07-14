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
| `boards/drill/board-NPTH-drl_map.gbr` | 3730 | `sha256:1381e5af1ccaea4aedc8e275b88238d7b9217fae705c62f6acd26011da99afba` |
| `boards/drill/board-NPTH.drl` | 306 | `sha256:18b32a104b74c0c6597683248060c268d885a058a202bfee3e2220b216cff1cc` |
| `boards/drill/board-PTH-drl_map.gbr` | 3730 | `sha256:1381e5af1ccaea4aedc8e275b88238d7b9217fae705c62f6acd26011da99afba` |
| `boards/drill/board-PTH.drl` | 302 | `sha256:cd0ce8cbde97824a674d782c06b4371cb1582fb923b869213a6b7973448c6876` |
| `boards/gerbers/board-B_Courtyard.gbr` | 465 | `sha256:cea110d8bc0bba9be11a5d3092ade22e04524c2c7fadb8d46bf9cf13d9111a4e` |
| `boards/gerbers/board-B_Cu.gbl` | 496 | `sha256:c99046c0d36a0a19ccbeb704ef61e796dbbf574aebdacb9bfe3ca25cb2c6dbfb` |
| `boards/gerbers/board-B_Fab.gbr` | 474 | `sha256:c5b5f695994413741dde71ee7646b198f7330b6db543d7468335d1a803ea6878` |
| `boards/gerbers/board-B_Mask.gbs` | 497 | `sha256:97c2df9f2e16891af8e99063a6491ea8d36e76147910855ee611f23d32e2de3b` |
| `boards/gerbers/board-B_Paste.gbp` | 492 | `sha256:e4aafe1f350f734ec65d50edd892bfd3ca51faa24ce709a8feacce6661d4a551` |
| `boards/gerbers/board-B_Silkscreen.gbo` | 493 | `sha256:0bda726e1db4d8e33418249f5f99e9d0145b670ff2c0024c63e6cb6e7e51cc6d` |
| `boards/gerbers/board-Edge_Cuts.gm1` | 601 | `sha256:f32b71129790ee6b3fdad61b0262483484d9fce5b8dba186d194b4e8655f84f9` |
| `boards/gerbers/board-F_Courtyard.gbr` | 465 | `sha256:cea110d8bc0bba9be11a5d3092ade22e04524c2c7fadb8d46bf9cf13d9111a4e` |
| `boards/gerbers/board-F_Cu.gtl` | 496 | `sha256:7cd2e7b5b75d3774eeee0d3002068cc4de46acd57d0625ba0a519cdcab1fd227` |
| `boards/gerbers/board-F_Fab.gbr` | 474 | `sha256:e1c433107d64d808f761d1ad6d0ddcb720c9f43830c76b4603547067ef914ee6` |
| `boards/gerbers/board-F_Mask.gts` | 497 | `sha256:cb79be0b2bffded3866507c43b17dbcf123707bc4ee4b618ef3de6b5b08dadaa` |
| `boards/gerbers/board-F_Paste.gtp` | 492 | `sha256:cfd5db74e6fb1b2d4fce3665de59a783930cef6c66e50cab833038299dd42e2e` |
| `boards/gerbers/board-F_Silkscreen.gto` | 10578 | `sha256:f3abe897723c1185851b9543dbe0255b336290870d3a0d8e20f9449cf1766d79` |
| `boards/gerbers/board-Margin.gbr` | 465 | `sha256:cea110d8bc0bba9be11a5d3092ade22e04524c2c7fadb8d46bf9cf13d9111a4e` |
| `boards/gerbers/board-job.gbrjob` | 2718 | `sha256:1b85118dc60c299c736225eeab5b845e3592c773e4d1d74feaa3a4b6d09800af` |
| `boards/panel.json` | 27 | `sha256:a94af1c626d8f5bca70082a6be2744dd0287250b3e97a166f1bc92c4c119a3e4` |
| `boards/pos/positions.csv` | 35 | `sha256:7565b037b9375e5a5070ba77a93488768c56409db7c519ace55cc83bb2f74819` |
