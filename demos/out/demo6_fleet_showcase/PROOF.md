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

- `dist/index.md` (sha256 `sha256:be967fed4a15611bab5b9b2d0bfdce5db8a0563a16347d1dcc642481be99542d`) -- the release-gate stamp and the content-hashed listing of every artifact family.
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
| `dist/calc/bearing__0da4bbc23c21.pdf` | 3811 | `sha256:8dd2e73f321c39d52f153e2ea1a470cd56e3a0290e6518a234863cd20716bfdb` |
| `dist/calc/bom__236efcefb087.pdf` | 4962 | `sha256:2d3038c4116cd3758f338fe920bd650274576c1f8978592f848463427b583a9a` |
| `dist/calc/calc_book.json` | 16652 | `sha256:67d1e576a9f9b77f968ff0bf8e6dbb6ccb5122caa89bd19b9958ab1aec4fd74d` |
| `dist/calc/construction__.pdf` | 4219 | `sha256:3a2b2e67ae528bdea592af12fd89d37549624de3d7201055b504e423b29ab544` |
| `dist/calc/deflect2__0da4bbc23c21.pdf` | 3891 | `sha256:567c4726d0d0bb8a4dff592bd0bb9fed68a97e900650414842c73a2e8eb7cc08` |
| `dist/calc/strength_G2_AB___0da4bbc23c21.pdf` | 3869 | `sha256:6b22956575453eabc42abcb3a77e13dc9054a518ff6fff974a37cca73ae71168` |
| `dist/calc/strength_GR_AB___0da4bbc23c21.pdf` | 3871 | `sha256:86938a2146b78b777788e95ab1851c36df3c623c272b8401eef1f8b45018fbb8` |
| `dist/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `dist/drawings/drawings/Frame.dxf` | 4174 | `sha256:a8d525c365dd78b4b59c35cd643abbf41ba4713faed3dfd43efc7a083dd20625` |
| `dist/drawings/drawings/Frame.explain.txt` | 2350 | `sha256:caa79f35e037728f335d24293b91385d656589068987a52a92a4460f2d5d8417` |
| `dist/drawings/drawings/Frame.pdf` | 7209 | `sha256:8262858cc24272e2654c3bd64ab607327a78ba2049cc956479ff34e5210a7601` |
| `dist/drawings/drawings/Frame.svg` | 11675 | `sha256:ae491721a14bbd7ae04afc5b68c2339ce8477fd5f7eb322c85f2671129f51cc6` |
| `dist/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:6a0121a37180f0f187175c12f1974b9cbae2526e27527b3caa3c02587a01d19e` |
| `dist/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `dist/drawings/drawings/HeatingLoop.explain.txt` | 1581 | `sha256:151be6b1b30bf9be67060ac92e4c60f772ac446b3b7b10ebc69e5a87dd653e82` |
| `dist/drawings/drawings/HeatingLoop.pdf` | 2829 | `sha256:f6e1a89c4f6fcdaf270ebe98e8e21f3dd55c9656a281c48be0eca633e5094b52` |
| `dist/drawings/drawings/HeatingLoop.svg` | 3484 | `sha256:0524374a94969a083925187d9a7ff3fab025394b69501f185d541149a522c02c` |
| `dist/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `dist/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `dist/drawings/drawings/contract_graph.explain.txt` | 1617 | `sha256:a146c358c127913d56815a24dd6997c6af8f26a8e9592d2cae2ac65887473a59` |
| `dist/drawings/drawings/contract_graph.pdf` | 1651 | `sha256:66c1078a3bbbbb777708672ce3480a91b8e662a96ae1464d616518c29efd6368` |
| `dist/drawings/drawings/contract_graph.svg` | 2013 | `sha256:27c869df4781b2ba476d07090b3c87cb00984ac58074928344b0b565b208158f` |
| `dist/gate_summary.json` | 207 | `sha256:b9e5cf143ea623f49d73e617e86de503c1b1157f4fe620f6cb5e0abcf3997089` |
| `dist/index.md` | 3370 | `sha256:be967fed4a15611bab5b9b2d0bfdce5db8a0563a16347d1dcc642481be99542d` |
| `dist/manifest.json` | 6841 | `sha256:482689eab44bfbd4c12632b8223f10b226593ee15b9782eb67a65fbed5f5ad02` |
| `dist/parity_ledger.json` | 25867 | `sha256:c76a45b6f55a8af3ebe33bf036b155ff0f507dd06a7e3b604a5dd88311536b6e` |
