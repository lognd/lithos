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

- `dist/index.md` (sha256 `sha256:4a52e3d8d0aef65dd6a45d3592b000935799e9945c2104088d94bedb1cc6f8d7`) -- the release-gate stamp and the content-hashed listing of every artifact family.
- `dist/drawings/` -- per-part SVG + PDF + DXF drawings.
- `dist/3d/` -- per-part GLB + offline viewer.
- `dist/bom/` -- the massed BOM (csv/json/md/pdf).
- `dist/gate_summary.json`, `dist/parity_ledger.json`, `dist/acceptance_ledger.json`, `dist/manifest.json` -- the signed release ledgers.

Every file above is content-addressed in this demo's `manifest.json` and re-verifiable with `regolith ship --verify`.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `dist/acceptance_ledger.json` | 10635 | `sha256:b8d97935993dc9466612c6af1233f983838231bb4d5f1c1bf0088d393871cdf6` |
| `dist/drawings/drawings/Frame.drawing.json` | 4195 | `sha256:eb9be17102a3aa3bd0eb6b2771dac595802a417bd0799be08fbddfc913f66799` |
| `dist/drawings/drawings/Frame.dxf` | 3646 | `sha256:1d69215e59c58ebf7856b4c8535f19ad90bafbdac6c9d2f61a0ee321856be579` |
| `dist/drawings/drawings/Frame.explain.txt` | 1728 | `sha256:7b540714eb2fd719ce0e326e07da352cb72c4ba9aab68ea8057e3580ce64d002` |
| `dist/drawings/drawings/Frame.pdf` | 3712 | `sha256:6fd825bb8629ffc2eba004064d87713b685a909ce1864ee1f247fb844ff1d914` |
| `dist/drawings/drawings/Frame.svg` | 4458 | `sha256:683dff6b09e946be0b779eb756de750b899ecf1dc55de7d3b95d35a6a2c4f753` |
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
| `dist/index.md` | 2464 | `sha256:4a52e3d8d0aef65dd6a45d3592b000935799e9945c2104088d94bedb1cc6f8d7` |
| `dist/manifest.json` | 5672 | `sha256:2f163a4bd74521cb2b6a4446e3ad653373fcb36d297a5deda8aa9df7878701b2` |
| `dist/parity_ledger.json` | 25867 | `sha256:fdfcc0261b5f4f9463271c50f68b68e394f5c96978a503e8bc918c25598b3852` |
