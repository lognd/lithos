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
| `cnc_router_r1/bom/bom.pdf` | 12039 | `sha256:acf9ed1c04ed925fbeaaf744b05baf73e94f3cd072f6db7cf847c46820e19155` |
| `timber_pavilion/cost/cost_summary.pdf` | 7574 | `sha256:67b958f830bdb9bcbc3556d0dcbac820d90e784aba9fc1a9a3fdf7ac2e89f061` |
| `timber_pavilion/cost/cost_summary.svg` | 11465 | `sha256:ea71ffbd62269d31c59c2bb0fc0f0dd7f3fb9aa8d808faafb613da2f757e9a0d` |
| `timber_pavilion/schedule/PavilionFrame.drawing.json` | 3192 | `sha256:3f3a81dd9e5f53145225a242b697ecdde8379168a0624382f93efbe4082e0795` |
| `timber_pavilion/schedule/PavilionFrame.dxf` | 3561 | `sha256:77a976896847b95136ca99dcb664170a2ce1f5ad6cddf4e55bedda2f064640f2` |
| `timber_pavilion/schedule/PavilionFrame.explain.txt` | 2573 | `sha256:9ffd22a72c31e08036c73178d8487e390c4ca360ed3dfed8601f63106b23775c` |
| `timber_pavilion/schedule/PavilionFrame.pdf` | 7146 | `sha256:d8b0cb1f314e03e3765afbaa09b2b1b0f7fd419145690e973b54e436927cb5ec` |
| `timber_pavilion/schedule/PavilionFrame.svg` | 12252 | `sha256:873a00393b293147996d7307eb42fd580defa28fa2bed66b7efa319d65e5e1e5` |
