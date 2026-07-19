# PROOF: projected multi-view drawing sheets (mech + civil), charter 38 sec. 1.5

- pipeline path: `regolith build --release <project>` then `regolith ship <project> --build ... --spec ship.spec.json` (the real two-command release flow; no bespoke drawing driver) -- the drawings/ family is the sheet set charter 38 sec. 1.5 describes: OCP/OCCT hidden-line projections of the pinned STEP bytes for mech, the pinned FramePayload for civil.
- mech: printer_k1 (`printer_k1`), 30 file(s) under `drawings/`.
- civil: small_office (`small_office`), 15 file(s) under `drawings/` (the plan/section sheet, `Frame.*`).
- formats present per sheet: `.svg`, `.pdf`, `.dxf`, `.drawing.json` (the pre-render IR), `.explain.txt` (human-readable derivation note).
- determinism: svg/pdf/dxf/drawing.json/explain.txt are all deterministic renderers (fixed deflection parameters, sorted output, ryu floats, charter 38 sec. 1.5); re-running this demo reproduces byte-identical hashes below.

## Re-run

```
uv run python -m demos.demo7_drawings_multiview
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `civil_small_office/drawings/drawings/Frame.drawing.json` | 4186 | `sha256:0246cdf7433761b4fee893ad37a6eb89dccdd12d39181b77803d6823ba3361e3` |
| `civil_small_office/drawings/drawings/Frame.dxf` | 4174 | `sha256:a8d525c365dd78b4b59c35cd643abbf41ba4713faed3dfd43efc7a083dd20625` |
| `civil_small_office/drawings/drawings/Frame.explain.txt` | 2716 | `sha256:579b393afe33da04d84dabe523fe933a0ec0890d1aae2ddfe9ec277660743978` |
| `civil_small_office/drawings/drawings/Frame.pdf` | 8771 | `sha256:ed3bd6e0067be5df7d3606580c892a69c7ccffcbe124940f9cf7d5cd02c48f1e` |
| `civil_small_office/drawings/drawings/Frame.svg` | 15328 | `sha256:12e8ebeac8b8afe5edc8a2bd9dee73f6c78e95bd4a8b5b3e1762f035a9586dc5` |
| `civil_small_office/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:99982fd02eb84657153a2cd9089f8270ae4524ac0fd4ed3cb3c6bbd219d22664` |
| `civil_small_office/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `civil_small_office/drawings/drawings/HeatingLoop.explain.txt` | 1959 | `sha256:0cb5e96dd8eaaad23ba72d4bbb0ffd3ea5f33195c9630e7e8c772fdbc2f7804f` |
| `civil_small_office/drawings/drawings/HeatingLoop.pdf` | 3649 | `sha256:34a35d36aaf19aaff607810811f475e589da9308a205ce7c23760a0bec853d0c` |
| `civil_small_office/drawings/drawings/HeatingLoop.svg` | 4819 | `sha256:9385f80da11f4cc419fcfb5f4f6177194db0263b7a2136ae8038255a2aa2cbcc` |
| `civil_small_office/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `civil_small_office/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `civil_small_office/drawings/drawings/contract_graph.explain.txt` | 2001 | `sha256:dbee7dfcecce281cbc1158893c4387e0e99d814d099cd249d3881fc96c73a279` |
| `civil_small_office/drawings/drawings/contract_graph.pdf` | 2482 | `sha256:a50e754852e7d94515b547d12cbc30a3cb8ba60fd0492d80ec3e6acd3fb61a1e` |
| `civil_small_office/drawings/drawings/contract_graph.svg` | 3359 | `sha256:e2e6291b1f14fa491de9e5c2b5cfde282f9168a73ce2fca9f9cb6ebfc38777da` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.drawing.json` | 48117 | `sha256:5263d3abb333b2a914abff5d041d531aeb0ce194cf69d30a3fa632bb8a07fadf` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.dxf` | 62542 | `sha256:71682a7e1861f90c8905ddc9bd73821e095a62cc599fa95550d693e6a8f247f1` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.explain.txt` | 2029 | `sha256:32f0d3cd72ac39bd6d886840b6121a863126cf2aa78c308dc072baf0d679fdfa` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.pdf` | 35129 | `sha256:5257f6fbc8eb45a05132c6fed09b834e22b0729c1f44ff57e3911d3d54a91c56` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.svg` | 75449 | `sha256:97a7cd12f69365ae4bdf5f522fd23b31def1c9688650105dc5253c7aa86676fc` |
| `mech_printer_k1/drawings/drawings/PartCooling.drawing.json` | 1188 | `sha256:8204054169acc63b3f9eb9f5f11818ec8548c9fd4a20366cf53c7a644faeaf9e` |
| `mech_printer_k1/drawings/drawings/PartCooling.dxf` | 2399 | `sha256:5a19ca8d427bd27139586acf7f7b317559661c54f3493ee4ee1048e06781c77e` |
| `mech_printer_k1/drawings/drawings/PartCooling.explain.txt` | 1959 | `sha256:cdd5f7c86b4af69868480ea05a45aee222584a51bed35c6c924409a9db17b2c4` |
| `mech_printer_k1/drawings/drawings/PartCooling.pdf` | 2848 | `sha256:86e174627227654c155843e243a41990797e3ed071fd6c2c3572cf59bf2b213a` |
| `mech_printer_k1/drawings/drawings/PartCooling.svg` | 3875 | `sha256:239224c19efbb70f3d72d9c68b45bb21e8aae0063733b55e239c23f2cf0a3bc6` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.drawing.json` | 8421 | `sha256:010c5d095430a803f20702674eed5c982a7d5fffd1f445ec54ed0afe6b95170b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.dxf` | 11723 | `sha256:47728b5f16e2d4a195ec91c2826b93453b88fd5ac28bb32c012e9f2fa75ad7d8` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.explain.txt` | 2113 | `sha256:8fd1d5bf68227dd0bb7698b916768c02967b8d09cc115ff1cd7e759383b62611` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.pdf` | 7693 | `sha256:53f3510e8cbb7185523b36102ec30a30f2d9e6b55372db815c47bcefa8b6795b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.svg` | 15134 | `sha256:e0c1bf8182ad49d317dfcb163dbea55194503faa4f3131ed8031972386d369fd` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.drawing.json` | 8425 | `sha256:3c6481a1eec2c0fd6849298fae0a0d0a89a39d91749e9d51ba70bac908337415` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.dxf` | 11726 | `sha256:b55c2776f83bd4eabb0bb66c69fd0f3cc682399dff25e1171f3f31c3cbdc753b` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.explain.txt` | 2127 | `sha256:9b3d7804c8e23b9ebd97f1cbae493c59d30d5afc0b74f0bb77dd473b2b63fd27` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.pdf` | 7696 | `sha256:3dfe8f493534b3c23d97ed054c4b006c054f40e7cf4e837aac83dbeeb3803ca5` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.svg` | 15137 | `sha256:1204a282eeb83ec8ad49116e787121ae33daf39c2f23d7c1ed93b24969a401a0` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.drawing.json` | 12075 | `sha256:5dde6f1c4766dab4d892de9e38049cfd5d588e4ebe61f2f263e2d3f7f0de3ff9` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.dxf` | 16583 | `sha256:e4e7e55707867830f585bafaa6c616a8552c82c2791a65ea45aac5573852ae5d` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.explain.txt` | 2015 | `sha256:939c435c30cd33808c1c06e73ba0809443d061b175dff4b950fa27038b29d88c` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.pdf` | 10311 | `sha256:630c4cbf37a6655075ae5beed42b868c2b49ccdba92316c6af597a05d5385e2e` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.svg` | 20767 | `sha256:c1b813b324d214d652574801e24b73e7dc6052544efb9e391a1dcc598723c54b` |
| `mech_printer_k1/drawings/drawings/contract_graph.drawing.json` | 10960 | `sha256:ebb6cd0367f64ae13f0b38ba6aab3f9ae7c3a076059649fb7bb145945cd579f1` |
| `mech_printer_k1/drawings/drawings/contract_graph.dxf` | 9438 | `sha256:37390d3fa307d8efa9b80be1612212038a3d99060e7b2158550b479a2c4b42c4` |
| `mech_printer_k1/drawings/drawings/contract_graph.explain.txt` | 1998 | `sha256:00c97924f6c9fefaa09c9a8de1e8e6cd96cab11d30385e6b745d638a5c77ee6f` |
| `mech_printer_k1/drawings/drawings/contract_graph.pdf` | 11320 | `sha256:ab88975fff4d122b3eb8cd8291c3e03e4ac6a1a49beef282bf27092f0eb276de` |
| `mech_printer_k1/drawings/drawings/contract_graph.svg` | 14131 | `sha256:4f50359b0b9a3d704fe5692f694511efd9cce375129edf84ccde584794729a5b` |
