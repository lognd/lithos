# PROOF: derived BOM v2 (real masses) + cost sheet + member schedule

## 1. Derived BOM v2 with real masses (cnc_router_r1)

- pipeline path: `regolith build --release` + `regolith ship --spec ship.spec.json` -- the `bom/` family (csv/json/md/pdf) derives rows from the design graph (charter 38 sec. 1.7): 13 row(s) carry a REAL mass (std.materials density x OCP volume over the pinned STEP bytes) with `material_pin` + `geometry_pin` provenance columns.
- totals row (verbatim): `TOTAL,,,,,,,105444.098,,,,,,q25,`
- honesty: fittings with no record ship `UNSOURCED`; every empty mass/cost cell carries its reason column, never a fabricated number.

## 2. Member schedule (timber_pavilion)

- the shipped civil sheet `PavilionFrame.*` carries the `Member Schedule` table -- one row per frame member (id/role/length/section/material, sections + materials record-pinned) -- in PDF/SVG/DXF plus the machine-readable `.drawing.json` rows.

## 3. Cost sheet from real costing evidence (timber_pavilion)

- the release build persists a REAL `ItemizedEstimate` (`all/construction`, D147 costing evidence) into the discharge-time payload store; this demo resolves it via `regolith.backends.ship.resolve_cost_estimates` (the SAME channel `ship` threads into the BOM cost join) and renders the WO-101 deliverable-5 `cost_summary_sheet` producer to PDF + SVG.
- estimate grand total: 2449.50..3036.00 USD.
- WO115-F1 (named gap, not papered over): no fleet ship package today emits the `cost/` dist family (`index.md` says `cost/: absent` everywhere) -- `cost_summary_sheet` has no ship-side caller (WO-101 Status: in-progress), and the BOM cost JOIN columns stay honestly empty fleet-wide because no persisted estimate subject matches a BOM row subject (timber's estimate subject is `all`; cnc has none). The producer and the evidence above are both real; the dist wiring is the WO-101 residual.

## Re-run

```
uv run python -m demos.demo8_bom_cost_schedule
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `cnc_router_r1/bom/bom.csv` | 4067 | `sha256:ecf245fab734700267ee384277faba3c2d751fa54456a93ce6c90903aaff18d8` |
| `cnc_router_r1/bom/bom.json` | 9035 | `sha256:69610cdc0cf4fc33d1d6a03cc0382a37650893aee0d9ebacfac70059c0f3944d` |
| `cnc_router_r1/bom/bom.md` | 2992 | `sha256:e587d6844023c4017fdbaab04834a6ef3a7d5d831b9da2e99ef465b304b5e03a` |
| `cnc_router_r1/bom/bom.pdf` | 3120 | `sha256:d501a09398b291e6f9865e2563eb1cf34d87aeb64afa211b5b30aac8da5b96a5` |
| `timber_pavilion/cost/cost_summary.pdf` | 2410 | `sha256:63923fb58855d70b6f092eca5baea7f856123036a18e7479b3df8bd0db2b9c22` |
| `timber_pavilion/cost/cost_summary.svg` | 2413 | `sha256:f185e058d19eab300f89991737ad6925b41e1464d052834d3498217d922c78c0` |
| `timber_pavilion/schedule/PavilionFrame.drawing.json` | 3192 | `sha256:3f3a81dd9e5f53145225a242b697ecdde8379168a0624382f93efbe4082e0795` |
| `timber_pavilion/schedule/PavilionFrame.dxf` | 3024 | `sha256:afb27ad64798e61ea4112267f82385197b61f8f4391b4a33a5bbb285ee236610` |
| `timber_pavilion/schedule/PavilionFrame.explain.txt` | 1537 | `sha256:d4ead748a660443ac4525a6de02d9c5ea71f3965fe046c6091abb1531a2b2b43` |
| `timber_pavilion/schedule/PavilionFrame.pdf` | 2989 | `sha256:1ab122ae86dbdc4fd632cc251314273c0e30ec19dec2e17c3a92d0b7d8be6050` |
| `timber_pavilion/schedule/PavilionFrame.svg` | 3512 | `sha256:8100e1ace9a59c753f44f930049edcb2f5b2900f791cb87d3765106334d7ba5d` |
