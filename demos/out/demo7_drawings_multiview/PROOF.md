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
| `civil_small_office/drawings/drawings/Frame.explain.txt` | 2507 | `sha256:3ede684f5bfe13df28afbcabe08764abc20d99858bf0f04ae62e90676bbf5e5f` |
| `civil_small_office/drawings/drawings/Frame.pdf` | 8771 | `sha256:17e058dfaa4aa0e87854d39f657d1dd08bfd3a5c3f89f90589e2319a4912c1d4` |
| `civil_small_office/drawings/drawings/Frame.svg` | 15328 | `sha256:ab64306fe9ea1be685cdb8e9be1650bc2bb4021306663f9f93aea9f0688c6157` |
| `civil_small_office/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:6a0121a37180f0f187175c12f1974b9cbae2526e27527b3caa3c02587a01d19e` |
| `civil_small_office/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `civil_small_office/drawings/drawings/HeatingLoop.explain.txt` | 1744 | `sha256:fa6f39a472c58d030c391bdc9e1598b58228012cc6dbf42e34ea9ed54f2cf186` |
| `civil_small_office/drawings/drawings/HeatingLoop.pdf` | 3649 | `sha256:57c1e73503f892081394c88c92a18081ab4e36df0d6b8d2d4b71dd7f41b89867` |
| `civil_small_office/drawings/drawings/HeatingLoop.svg` | 4819 | `sha256:4aeb4dd9664f7eb3e18537634c2662eafb1b53c1becdd4a67931d0ad559cd6f0` |
| `civil_small_office/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `civil_small_office/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `civil_small_office/drawings/drawings/contract_graph.explain.txt` | 1783 | `sha256:50ca4eed5b113c0aebc43cec10adc8c48d0631700a66f3299b3692441773d2b2` |
| `civil_small_office/drawings/drawings/contract_graph.pdf` | 2482 | `sha256:5a15ab47b18aced24784c51b6276c97e95d4e9d328890d6810714f5ed1e328d2` |
| `civil_small_office/drawings/drawings/contract_graph.svg` | 3359 | `sha256:8d1ba2212bea36cab95bdb3c5710194d6b591eff282f5452c161577dbebddd3b` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.drawing.json` | 48117 | `sha256:5263d3abb333b2a914abff5d041d531aeb0ce194cf69d30a3fa632bb8a07fadf` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.dxf` | 62542 | `sha256:71682a7e1861f90c8905ddc9bd73821e095a62cc599fa95550d693e6a8f247f1` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.explain.txt` | 1809 | `sha256:074506a611c86e2139234536615f10f9594045792f6cd92d577a8a23f46272c5` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.pdf` | 35129 | `sha256:1a8e59a7bc57d0b3b7f5625c8d891583547c2a97861911b97c73cb7517a56bb3` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.svg` | 75449 | `sha256:f0e9922a8ebfe9716c66b4f96b955587aad8a4456617594ea8dbb2c253ef23e3` |
| `mech_printer_k1/drawings/drawings/PartCooling.drawing.json` | 1188 | `sha256:d8666b184b6bbe024cb0eb0cec83ac368d9c5b44674d155efcb3fbba1206f07a` |
| `mech_printer_k1/drawings/drawings/PartCooling.dxf` | 2399 | `sha256:5a19ca8d427bd27139586acf7f7b317559661c54f3493ee4ee1048e06781c77e` |
| `mech_printer_k1/drawings/drawings/PartCooling.explain.txt` | 1744 | `sha256:85bb82effaae3f06b3f297dbb94c0db5dbc6beb2fcfc48b3f6c4f6e0bdd8aaf8` |
| `mech_printer_k1/drawings/drawings/PartCooling.pdf` | 2848 | `sha256:14db06a1f61dda61af62b555d8e6d5584107511864a024d2cb5c7b123a500ca1` |
| `mech_printer_k1/drawings/drawings/PartCooling.svg` | 3875 | `sha256:e5fa05492a82efbad373da0f9642e1477180c07e0b240d3d1863371c07442d63` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.drawing.json` | 8421 | `sha256:010c5d095430a803f20702674eed5c982a7d5fffd1f445ec54ed0afe6b95170b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.dxf` | 11723 | `sha256:47728b5f16e2d4a195ec91c2826b93453b88fd5ac28bb32c012e9f2fa75ad7d8` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.explain.txt` | 1887 | `sha256:f254e63f822855d83194daa29139b72932c1e7187ae7536754f9f0f301e48eef` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.pdf` | 7693 | `sha256:e5e262a469b51382772271756280e55e0e69f24f7c98d3b29ecb757489ba72cf` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.svg` | 15134 | `sha256:d118e702741d6016e505727aeea4d533b698a1dcf2ea87a90cfb67801f7295b6` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.drawing.json` | 8425 | `sha256:3c6481a1eec2c0fd6849298fae0a0d0a89a39d91749e9d51ba70bac908337415` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.dxf` | 11726 | `sha256:b55c2776f83bd4eabb0bb66c69fd0f3cc682399dff25e1171f3f31c3cbdc753b` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.explain.txt` | 1900 | `sha256:501f7e0fbe3f716865e429f3cc52a7c9136d48a74f21d32be4b467e4965507e1` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.pdf` | 7696 | `sha256:8580a28b3d81330382afc884889032608e9e0950c3a85f28b68393779332efe6` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.svg` | 15137 | `sha256:3817e62ed9bdf7a3b4b9be8fd2a73adf4e5a5035d762a85aea7bfe3e763b13d2` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.drawing.json` | 12075 | `sha256:5dde6f1c4766dab4d892de9e38049cfd5d588e4ebe61f2f263e2d3f7f0de3ff9` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.dxf` | 16583 | `sha256:e4e7e55707867830f585bafaa6c616a8552c82c2791a65ea45aac5573852ae5d` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.explain.txt` | 1796 | `sha256:8ec7badcd9eeed5f9b968ad8ac3227860e284ac4f4bcc7308296ea45ccc30d3e` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.pdf` | 10311 | `sha256:46233c01100a5ddcd13d3a443cd24fe2766e836f70ce7d86a1298d6dd8c59c18` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.svg` | 20767 | `sha256:328172dc27de3748aef62e88f593f1079fdcca09144d0150f4675d9f08d8aa04` |
| `mech_printer_k1/drawings/drawings/contract_graph.drawing.json` | 10960 | `sha256:ebb6cd0367f64ae13f0b38ba6aab3f9ae7c3a076059649fb7bb145945cd579f1` |
| `mech_printer_k1/drawings/drawings/contract_graph.dxf` | 9438 | `sha256:37390d3fa307d8efa9b80be1612212038a3d99060e7b2158550b479a2c4b42c4` |
| `mech_printer_k1/drawings/drawings/contract_graph.explain.txt` | 1780 | `sha256:a3be07859656301387512c1fccca43f4e29eaf219b9067d1871523183f75983d` |
| `mech_printer_k1/drawings/drawings/contract_graph.pdf` | 11320 | `sha256:7ce690cd42cab612387f0d89edefae1d246ae16854cd0ed00012df7b9987579c` |
| `mech_printer_k1/drawings/drawings/contract_graph.svg` | 14131 | `sha256:362ffd190e4fea5ba402aeaaf0f8485229b736e2386c6ba072d8a018ae52bcb9` |
