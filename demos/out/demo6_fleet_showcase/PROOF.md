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

<<<<<<< HEAD
- `dist/index.md` (sha256 `sha256:be967fed4a15611bab5b9b2d0bfdce5db8a0563a16347d1dcc642481be99542d`) -- the release-gate stamp and the content-hashed listing of every artifact family.
=======
- `dist/index.md` (sha256 `sha256:b15b45aa9bb415b5d8ca230e48a5b9131fa9c26ab313ef721f7509574b939317`) -- the release-gate stamp and the content-hashed listing of every artifact family.
>>>>>>> wo123
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
| `dist/calc/bearing__0da4bbc23c21.pdf` | 5714 | `sha256:0933b0ba6d988164f68c229841e58a6bc66dc7782084b9200a360d0082491313` |
| `dist/calc/bom__236efcefb087.pdf` | 6873 | `sha256:49b8b0bdb10062acf26ecbde3da56abe92c5dc5833b4320c8ba8b9a252f383a1` |
| `dist/calc/calc_book.json` | 16760 | `sha256:2c0f202db65c37650601f772de0e1ea9764f3fbbfcae6b020402659cce01866e` |
| `dist/calc/construction__.pdf` | 6019 | `sha256:415cd93c72962549dff999c43d625239d9ab6a0426ba7fab430f90b0f00fb79a` |
| `dist/calc/deflect2__0da4bbc23c21.pdf` | 5794 | `sha256:21a12750cfc52cc533ab4d151d327c4633e8acedf4240787bc936c241f333614` |
| `dist/calc/strength_G2_AB___0da4bbc23c21.pdf` | 5772 | `sha256:166a805d04c71e1848b73011f0f8da1d1f18b12f880ed494c8fd9ee48279db69` |
| `dist/calc/strength_GR_AB___0da4bbc23c21.pdf` | 5774 | `sha256:c7209a49e6ad6deb2cf500f39a7b93f40a06af399a541a9111013bfd40029d25` |
| `dist/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `dist/drawings/drawings/Frame.dxf` | 4174 | `sha256:a8d525c365dd78b4b59c35cd643abbf41ba4713faed3dfd43efc7a083dd20625` |
| `dist/drawings/drawings/Frame.explain.txt` | 2507 | `sha256:3ede684f5bfe13df28afbcabe08764abc20d99858bf0f04ae62e90676bbf5e5f` |
| `dist/drawings/drawings/Frame.pdf` | 8771 | `sha256:17e058dfaa4aa0e87854d39f657d1dd08bfd3a5c3f89f90589e2319a4912c1d4` |
| `dist/drawings/drawings/Frame.svg` | 15328 | `sha256:ab64306fe9ea1be685cdb8e9be1650bc2bb4021306663f9f93aea9f0688c6157` |
| `dist/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:6a0121a37180f0f187175c12f1974b9cbae2526e27527b3caa3c02587a01d19e` |
| `dist/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `dist/drawings/drawings/HeatingLoop.explain.txt` | 1744 | `sha256:fa6f39a472c58d030c391bdc9e1598b58228012cc6dbf42e34ea9ed54f2cf186` |
| `dist/drawings/drawings/HeatingLoop.pdf` | 3649 | `sha256:57c1e73503f892081394c88c92a18081ab4e36df0d6b8d2d4b71dd7f41b89867` |
| `dist/drawings/drawings/HeatingLoop.svg` | 4819 | `sha256:4aeb4dd9664f7eb3e18537634c2662eafb1b53c1becdd4a67931d0ad559cd6f0` |
| `dist/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `dist/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `dist/drawings/drawings/contract_graph.explain.txt` | 1783 | `sha256:50ca4eed5b113c0aebc43cec10adc8c48d0631700a66f3299b3692441773d2b2` |
| `dist/drawings/drawings/contract_graph.pdf` | 2482 | `sha256:5a15ab47b18aced24784c51b6276c97e95d4e9d328890d6810714f5ed1e328d2` |
| `dist/drawings/drawings/contract_graph.svg` | 3359 | `sha256:8d1ba2212bea36cab95bdb3c5710194d6b591eff282f5452c161577dbebddd3b` |
| `dist/gate_summary.json` | 207 | `sha256:b9e5cf143ea623f49d73e617e86de503c1b1157f4fe620f6cb5e0abcf3997089` |
<<<<<<< HEAD
| `dist/index.md` | 3370 | `sha256:be967fed4a15611bab5b9b2d0bfdce5db8a0563a16347d1dcc642481be99542d` |
| `dist/manifest.json` | 6841 | `sha256:482689eab44bfbd4c12632b8223f10b226593ee15b9782eb67a65fbed5f5ad02` |
=======
| `dist/index.md` | 3331 | `sha256:b15b45aa9bb415b5d8ca230e48a5b9131fa9c26ab313ef721f7509574b939317` |
| `dist/manifest.json` | 6818 | `sha256:2e8e99d6de9e36a264302b9d2347f2f3f1267b34809f518d5a1e5977fb79e18c` |
>>>>>>> wo123
| `dist/parity_ledger.json` | 25867 | `sha256:c76a45b6f55a8af3ebe33bf036b155ff0f507dd06a7e3b604a5dd88311536b6e` |
