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

- `dist/index.md` (sha256 `sha256:a4062d33670827cc6fde07603524a15db8ca31af324330ea52d35142da6d6e44`) -- the release-gate stamp and the content-hashed listing of every artifact family.
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
| `dist/calc/bearing__0da4bbc23c21.pdf` | 5720 | `sha256:cb46a13adbb5c159935cc25e4bfd540d21a33e77695cd0f63daa8c715c7c4b33` |
| `dist/calc/bom__236efcefb087.pdf` | 6873 | `sha256:a8ac8187d7622796d06a07b1c5a30ebb1cf7c8932b7dafbf0648bb26ba58b4f3` |
| `dist/calc/calc_book.json` | 16907 | `sha256:66247a0a7160a28fadc070a431b348318258298f231c923bac2fb9fd32cd98e5` |
| `dist/calc/construction__.pdf` | 6019 | `sha256:6dd5448872c314db20d02386065fa50d43a754404913670571cd4c29692809d4` |
| `dist/calc/deflect2__0da4bbc23c21.pdf` | 5800 | `sha256:54064482fe138b05b9312a7930970a41ce542f05faa9009bd307e5d6468ac45e` |
| `dist/calc/strength_G2_AB___0da4bbc23c21.pdf` | 5778 | `sha256:2be46fa5450728efe1a6a99e979d93821b3063c990fe5d56d0da9fdc703d07a5` |
| `dist/calc/strength_GR_AB___0da4bbc23c21.pdf` | 5780 | `sha256:7bcff7a7c5d220dbbf16ce32e908e7f807f55680b457a1ffe62752a336960019` |
| `dist/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `dist/drawings/drawings/Frame.dxf` | 4174 | `sha256:a8d525c365dd78b4b59c35cd643abbf41ba4713faed3dfd43efc7a083dd20625` |
| `dist/drawings/drawings/Frame.explain.txt` | 2716 | `sha256:579b393afe33da04d84dabe523fe933a0ec0890d1aae2ddfe9ec277660743978` |
| `dist/drawings/drawings/Frame.pdf` | 8771 | `sha256:17e058dfaa4aa0e87854d39f657d1dd08bfd3a5c3f89f90589e2319a4912c1d4` |
| `dist/drawings/drawings/Frame.svg` | 15328 | `sha256:ab64306fe9ea1be685cdb8e9be1650bc2bb4021306663f9f93aea9f0688c6157` |
| `dist/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:6a0121a37180f0f187175c12f1974b9cbae2526e27527b3caa3c02587a01d19e` |
| `dist/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `dist/drawings/drawings/HeatingLoop.explain.txt` | 1959 | `sha256:0cb5e96dd8eaaad23ba72d4bbb0ffd3ea5f33195c9630e7e8c772fdbc2f7804f` |
| `dist/drawings/drawings/HeatingLoop.pdf` | 3649 | `sha256:57c1e73503f892081394c88c92a18081ab4e36df0d6b8d2d4b71dd7f41b89867` |
| `dist/drawings/drawings/HeatingLoop.svg` | 4819 | `sha256:4aeb4dd9664f7eb3e18537634c2662eafb1b53c1becdd4a67931d0ad559cd6f0` |
| `dist/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `dist/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `dist/drawings/drawings/contract_graph.explain.txt` | 2001 | `sha256:dbee7dfcecce281cbc1158893c4387e0e99d814d099cd249d3881fc96c73a279` |
| `dist/drawings/drawings/contract_graph.pdf` | 2482 | `sha256:5a15ab47b18aced24784c51b6276c97e95d4e9d328890d6810714f5ed1e328d2` |
| `dist/drawings/drawings/contract_graph.svg` | 3359 | `sha256:8d1ba2212bea36cab95bdb3c5710194d6b591eff282f5452c161577dbebddd3b` |
| `dist/gate_summary.json` | 207 | `sha256:b9e5cf143ea623f49d73e617e86de503c1b1157f4fe620f6cb5e0abcf3997089` |
| `dist/index.md` | 3331 | `sha256:a4062d33670827cc6fde07603524a15db8ca31af324330ea52d35142da6d6e44` |
| `dist/manifest.json` | 6818 | `sha256:a0dd1484b1b4f39d88a0cef7b850052fbf459941702a66fdae86545d6e7b5599` |
| `dist/parity_ledger.json` | 25867 | `sha256:c76a45b6f55a8af3ebe33bf036b155ff0f507dd06a7e3b604a5dd88311536b6e` |
