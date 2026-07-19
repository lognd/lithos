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

- `dist/index.md` (sha256 `sha256:7db149b982eae352d92d69f028fb8c178eae73c7e71f6df40203903f2ee34d03`) -- the release-gate stamp and the content-hashed listing of every artifact family.
- `dist/drawings/` -- per-part SVG + PDF + DXF drawings.
- `dist/3d/` -- per-part GLB + offline viewer.
- `dist/bom/` -- the massed BOM (csv/json/md/pdf).
- `dist/gate_summary.json`, `dist/parity_ledger.json`, `dist/acceptance_ledger.json`, `dist/manifest.json` -- the signed release ledgers.

Every file above is content-addressed in this demo's `manifest.json` and re-verifiable with `regolith ship --verify`.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `dist/acceptance_ledger.json` | 11659 | `sha256:976011140c1b066788fc07175f1abd73261910f736bc21192b1a28a7ade3a4a4` |
| `dist/artifact_index.json` | 10732 | `sha256:72e5360307a41e31fcc28083f99e942d1e4b52ff85e38e906e4d375a84640f54` |
| `dist/calc/audit_index.json` | 8655 | `sha256:5cfe46fb19d8a991a1fe58e71fb70611bde1d188ddc27c209258acdff2cf9222` |
| `dist/calc/bearing__300d3d669aa3.pdf` | 6034 | `sha256:f0cee94357bbd37f8d4c24557a66bc059423020566bc8ce0fc8825cf67cfc340` |
| `dist/calc/bom__c11c49a454b8.pdf` | 6873 | `sha256:230a8412f977fcb993b38528adb7c0de1fa3ed185017a19f27e5a1940ad57f8c` |
| `dist/calc/calc_book.json` | 18063 | `sha256:63cde22061b3565e7a39d6182d2347c1e3c842587aded0964ec0844e3e538819` |
| `dist/calc/construction__.pdf` | 6033 | `sha256:c522af1313e45b7e84299349b3c12969d0b0a3fec61ee163ab10ba476964011d` |
| `dist/calc/deflect2__300d3d669aa3.pdf` | 6112 | `sha256:ec1b82700497e64cd91d2a546e3cf285d4cdf82edc368d1809e2840ea64a5c21` |
| `dist/calc/strength_G2_AB___300d3d669aa3.pdf` | 6090 | `sha256:e79d566c5898517d58b1295b95ec0885cc5e7cff45ff812fc868d0bf597b2a74` |
| `dist/calc/strength_GR_AB___300d3d669aa3.pdf` | 6092 | `sha256:0954651f62fbe7a1f3825bd93d695f1ce7a10b37d4361681bb71d5fca7a6040b` |
| `dist/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `dist/drawings/drawings/Frame.dxf` | 4174 | `sha256:a8d525c365dd78b4b59c35cd643abbf41ba4713faed3dfd43efc7a083dd20625` |
| `dist/drawings/drawings/Frame.explain.txt` | 2716 | `sha256:579b393afe33da04d84dabe523fe933a0ec0890d1aae2ddfe9ec277660743978` |
| `dist/drawings/drawings/Frame.pdf` | 8771 | `sha256:ed3bd6e0067be5df7d3606580c892a69c7ccffcbe124940f9cf7d5cd02c48f1e` |
| `dist/drawings/drawings/Frame.svg` | 15328 | `sha256:12e8ebeac8b8afe5edc8a2bd9dee73f6c78e95bd4a8b5b3e1762f035a9586dc5` |
| `dist/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:99982fd02eb84657153a2cd9089f8270ae4524ac0fd4ed3cb3c6bbd219d22664` |
| `dist/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `dist/drawings/drawings/HeatingLoop.explain.txt` | 1959 | `sha256:0cb5e96dd8eaaad23ba72d4bbb0ffd3ea5f33195c9630e7e8c772fdbc2f7804f` |
| `dist/drawings/drawings/HeatingLoop.pdf` | 3649 | `sha256:34a35d36aaf19aaff607810811f475e589da9308a205ce7c23760a0bec853d0c` |
| `dist/drawings/drawings/HeatingLoop.svg` | 4819 | `sha256:9385f80da11f4cc419fcfb5f4f6177194db0263b7a2136ae8038255a2aa2cbcc` |
| `dist/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `dist/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `dist/drawings/drawings/contract_graph.explain.txt` | 2001 | `sha256:dbee7dfcecce281cbc1158893c4387e0e99d814d099cd249d3881fc96c73a279` |
| `dist/drawings/drawings/contract_graph.pdf` | 2482 | `sha256:a50e754852e7d94515b547d12cbc30a3cb8ba60fd0492d80ec3e6acd3fb61a1e` |
| `dist/drawings/drawings/contract_graph.svg` | 3359 | `sha256:e2e6291b1f14fa491de9e5c2b5cfde282f9168a73ce2fca9f9cb6ebfc38777da` |
| `dist/gate_summary.json` | 207 | `sha256:b9e5cf143ea623f49d73e617e86de503c1b1157f4fe620f6cb5e0abcf3997089` |
| `dist/index.md` | 3569 | `sha256:7db149b982eae352d92d69f028fb8c178eae73c7e71f6df40203903f2ee34d03` |
| `dist/manifest.json` | 6975 | `sha256:afa6cfca64aed7fd88379a722184da4b68aa19057407a7f915105dd0a9c7a8f3` |
| `dist/parity_ledger.json` | 28939 | `sha256:304c091727d045b6656354f5b874f4a144a330560f2381fd4f8e1f7222223c3c` |
