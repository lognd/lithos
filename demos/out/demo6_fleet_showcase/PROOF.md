# PROOF: full regolith ship package with a live optimize pin (small_office)

- optimized quantity: **mass_per_length** -- small_office's steel members declared `section: in registry(std.civil.w_shape)`, sized by the WO-65 free-section search during `build --release`, here inside a FULL release package
- domain: the flagship's free-section `std.civil.w_shape` members
- winner + cause rows (verbatim from the shipped `build/regolith.lock`):

```
Frame.G2_AB.section = G2_AB=w16x40         cause: optimize(mass_per_length, trace=blake3:4ba1a9fd9da6d2d00a077d666acc3e10386dfe72fc165aed64e3b427a59fb9e8)
Frame.GR_AB.section = GR_AB=w8x10         cause: optimize(mass_per_length, trace=blake3:789f78a770613ba081251f3d9df05a53f8a274eff3c8df12d0e2e0f0c1b646bd)
```

## The full package a human opens

This is the complete `regolith ship` dist tree, produced by the real two-command flow (`build --release` then `ship`):

- `dist/index.md` (sha256 `sha256:40fb3d4d8556fb3abc38d25ee84c78104902864b2444335b4dfaa205f6dd36a3`) -- the release-gate stamp and the content-hashed listing of every artifact family.
- `dist/drawings/` -- per-part SVG + PDF + DXF drawings.
- `dist/3d/` -- per-part GLB + offline viewer.
- `dist/bom/` -- the massed BOM (csv/json/md/pdf).
- `dist/gate_summary.json`, `dist/parity_ledger.json`, `dist/acceptance_ledger.json`, `dist/manifest.json` -- the signed release ledgers.

Every file above is content-addressed in this demo's `manifest.json` and re-verifiable with `regolith ship --verify`.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `dist/acceptance_ledger.json` | 10635 | `sha256:ff26c85963afaac43a6924a16e20e2bd7fdefbbba626b42a722b593a8774950c` |
| `dist/calc/audit_index.json` | 8655 | `sha256:db28f59f4f84ae0f5ca3784410236aac6a137ac9ca38480b611708a48b5d4193` |
| `dist/calc/bearing__0da4bbc23c21.pdf` | 2000 | `sha256:5c4f8f528eaea40b5c4a13da056c40fa38b23b6e74e78c72b777bc0851185e41` |
| `dist/calc/bom__236efcefb087.pdf` | 2467 | `sha256:2fa5b4ea73315acf35c0ca4cf4a322533db186739f37bdd7db15c2f9ad1b9dc3` |
| `dist/calc/calc_book.json` | 16652 | `sha256:67d1e576a9f9b77f968ff0bf8e6dbb6ccb5122caa89bd19b9958ab1aec4fd74d` |
| `dist/calc/construction__.pdf` | 2132 | `sha256:2508771bf9a8e0666f4eaa8de44798e5e149605224fbbca44afa196125411944` |
| `dist/calc/deflect2__0da4bbc23c21.pdf` | 2080 | `sha256:8f64ac338862cb72a259b8077e2e815aae1360c6767ee915c88f54f64ef2cf69` |
| `dist/calc/strength_G2_AB___0da4bbc23c21.pdf` | 2058 | `sha256:bebce44a4889dcfada440fc90aca96642dd2ddc92cf9a831801a1ba726be9bf1` |
| `dist/calc/strength_GR_AB___0da4bbc23c21.pdf` | 2060 | `sha256:2b3b576bf0c3a79069199cc3b7f414184ae06a67bf029ead84d471f5cf9b44a7` |
| `dist/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `dist/drawings/drawings/Frame.dxf` | 3637 | `sha256:1f4aa5f10e057142554f1d0fc8cdf9681333b06f9be7c8a701a896df20331b10` |
| `dist/drawings/drawings/Frame.explain.txt` | 1728 | `sha256:ac7d225d3acc9d041a39f4d2bdb1383a0a1c80e1c09d777f3590fe6d7af9f8bc` |
| `dist/drawings/drawings/Frame.pdf` | 3703 | `sha256:0aa0ed9ff662277f1b7eaf6c0d6f97d82d093519046fbf09dbdce62a204301d7` |
| `dist/drawings/drawings/Frame.svg` | 4449 | `sha256:c1c1dfac047e34a43924ff43211f5c1556829e25aaee7fa130a4d1e72782bfb5` |
| `dist/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:99a19fa28524d3c917592a531192b8a4a72c38db9134975da1d37805eee181b6` |
| `dist/drawings/drawings/HeatingLoop.dxf` | 2349 | `sha256:a4792f225330d01d2c750db0c434855f8962bef6e5dc98425ad7277171e7b844` |
| `dist/drawings/drawings/HeatingLoop.explain.txt` | 924 | `sha256:2546fba3b38890d23401d6c3337b471a19279820d2a3a2392f7944e829952917` |
| `dist/drawings/drawings/HeatingLoop.pdf` | 2276 | `sha256:c57bf5445e59a9292790afe0ef6e85ce89a046bbdeae6bc5f60231ed284baf94` |
| `dist/drawings/drawings/HeatingLoop.svg` | 2509 | `sha256:0eb92726b9f79895746e60e902d83ce030292b7c75e02c44354dbf12e31a33ba` |
| `dist/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `dist/drawings/drawings/contract_graph.dxf` | 1476 | `sha256:89a2ee98e3fdc40b5e75f3284cc55c4ba37b9790ec835c4fba2c15f23cbb3b77` |
| `dist/drawings/drawings/contract_graph.explain.txt` | 959 | `sha256:baae11fe8abd776aa2c91195836211fc1e8097eab5a1f46f5da6b84e38b76dc3` |
| `dist/drawings/drawings/contract_graph.pdf` | 1191 | `sha256:f81dfa992a8e521b09019e30352d96bbc48370cac50179c976502c701594bb0c` |
| `dist/drawings/drawings/contract_graph.svg` | 1191 | `sha256:fe1025463e9707bcebd266044974cd79d8e19270aa6715de8c20f3a4d5b1b04e` |
| `dist/gate_summary.json` | 207 | `sha256:b9e5cf143ea623f49d73e617e86de503c1b1157f4fe620f6cb5e0abcf3997089` |
| `dist/index.md` | 3370 | `sha256:40fb3d4d8556fb3abc38d25ee84c78104902864b2444335b4dfaa205f6dd36a3` |
| `dist/manifest.json` | 6841 | `sha256:85bc305f740548548cc277dda64ce12428da474bad36aab5c7fcacab19d60927` |
| `dist/parity_ledger.json` | 25867 | `sha256:c76a45b6f55a8af3ebe33bf036b155ff0f507dd06a7e3b604a5dd88311536b6e` |
