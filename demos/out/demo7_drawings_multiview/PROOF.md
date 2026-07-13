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
| `civil_small_office/drawings/drawings/Frame.dxf` | 3637 | `sha256:1f4aa5f10e057142554f1d0fc8cdf9681333b06f9be7c8a701a896df20331b10` |
| `civil_small_office/drawings/drawings/Frame.explain.txt` | 1728 | `sha256:ac7d225d3acc9d041a39f4d2bdb1383a0a1c80e1c09d777f3590fe6d7af9f8bc` |
| `civil_small_office/drawings/drawings/Frame.pdf` | 3703 | `sha256:0aa0ed9ff662277f1b7eaf6c0d6f97d82d093519046fbf09dbdce62a204301d7` |
| `civil_small_office/drawings/drawings/Frame.svg` | 4449 | `sha256:c1c1dfac047e34a43924ff43211f5c1556829e25aaee7fa130a4d1e72782bfb5` |
| `civil_small_office/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:99a19fa28524d3c917592a531192b8a4a72c38db9134975da1d37805eee181b6` |
| `civil_small_office/drawings/drawings/HeatingLoop.dxf` | 2349 | `sha256:a4792f225330d01d2c750db0c434855f8962bef6e5dc98425ad7277171e7b844` |
| `civil_small_office/drawings/drawings/HeatingLoop.explain.txt` | 924 | `sha256:2546fba3b38890d23401d6c3337b471a19279820d2a3a2392f7944e829952917` |
| `civil_small_office/drawings/drawings/HeatingLoop.pdf` | 2276 | `sha256:c57bf5445e59a9292790afe0ef6e85ce89a046bbdeae6bc5f60231ed284baf94` |
| `civil_small_office/drawings/drawings/HeatingLoop.svg` | 2509 | `sha256:0eb92726b9f79895746e60e902d83ce030292b7c75e02c44354dbf12e31a33ba` |
| `civil_small_office/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `civil_small_office/drawings/drawings/contract_graph.dxf` | 1476 | `sha256:89a2ee98e3fdc40b5e75f3284cc55c4ba37b9790ec835c4fba2c15f23cbb3b77` |
| `civil_small_office/drawings/drawings/contract_graph.explain.txt` | 959 | `sha256:baae11fe8abd776aa2c91195836211fc1e8097eab5a1f46f5da6b84e38b76dc3` |
| `civil_small_office/drawings/drawings/contract_graph.pdf` | 1191 | `sha256:f81dfa992a8e521b09019e30352d96bbc48370cac50179c976502c701594bb0c` |
| `civil_small_office/drawings/drawings/contract_graph.svg` | 1191 | `sha256:fe1025463e9707bcebd266044974cd79d8e19270aa6715de8c20f3a4d5b1b04e` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.drawing.json` | 48117 | `sha256:5263d3abb333b2a914abff5d041d531aeb0ce194cf69d30a3fa632bb8a07fadf` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.dxf` | 62528 | `sha256:5800ca5cfe8a6f3c74e6b9f0a869d23b34ba10580781ff9370cf0c53ca5a745f` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.explain.txt` | 975 | `sha256:5b2a574b00ae15d2b512570d54a7996af1ba7b2de143894e07c7031318135cfd` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.pdf` | 33690 | `sha256:54c5925e3e42880a10774d931cbd3e329b47f02d8c743efb774923abba1f5714` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.svg` | 72974 | `sha256:6b005e27234f5f699d5f2c171a919db26555c4d0d699b20abd229ddd0a3e557f` |
| `mech_printer_k1/drawings/drawings/PartCooling.drawing.json` | 1188 | `sha256:d3d182b2a70260379c9b67f5a7ef4cc2e81182fb5f121f84eec949f532a60083` |
| `mech_printer_k1/drawings/drawings/PartCooling.dxf` | 1872 | `sha256:46efd03414e27fa36ee46c9ca530632ad2c185ff6561279a64a479e2ae2b7473` |
| `mech_printer_k1/drawings/drawings/PartCooling.explain.txt` | 924 | `sha256:b7a4cddbdec8bcc82e7abf3b42af6bfd452cc5c2053b9473559f1b6617734ebe` |
| `mech_printer_k1/drawings/drawings/PartCooling.pdf` | 1569 | `sha256:73878e859eb13992b1369de959bc777ef969d1b27508e8cd25a9e6ba8afbd15e` |
| `mech_printer_k1/drawings/drawings/PartCooling.svg` | 1719 | `sha256:18465e83227b537be588a85d2ae1950fa6b3d510755a33ceea16e06a6b94932b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.drawing.json` | 8421 | `sha256:010c5d095430a803f20702674eed5c982a7d5fffd1f445ec54ed0afe6b95170b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.dxf` | 11262 | `sha256:42d0509364e6c5890edb163471ab03beea0cc4179469f5dfdfb43312b02a41e7` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.explain.txt` | 1023 | `sha256:ffa9f05b8babb6f4a83edc6c471e73a23a8d08c3cca79fdbbf08ed03fef4e473` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.pdf` | 6254 | `sha256:b9b51844627165ba877cd917d9249044c180d4c1a937c5b089d3f12fb86682bd` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.svg` | 12659 | `sha256:b955375d93b30e28e6e75e2f71fb31e7cad6942a53a2777d3d1a4fa4956c84fe` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.drawing.json` | 8425 | `sha256:3c6481a1eec2c0fd6849298fae0a0d0a89a39d91749e9d51ba70bac908337415` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.dxf` | 11265 | `sha256:673d703d53f9190bd04b3aa5924edb390c3dba2e0781642ad2f6e49542c6a72f` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.explain.txt` | 1031 | `sha256:67a57dfdfffc6134953bcd66c01f8976f111b4058caa0b78be582b7d4a1bd308` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.pdf` | 6257 | `sha256:78ff32cdb8b268d0f20a7fadee4fe941ed9bf4502b9a90aec70fbc719626cd15` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.svg` | 12662 | `sha256:b70ef3529939277a9823bbd6d63fd276e33a42406daad8981ae315903a1ab8c9` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.drawing.json` | 12075 | `sha256:5dde6f1c4766dab4d892de9e38049cfd5d588e4ebe61f2f263e2d3f7f0de3ff9` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.dxf` | 16165 | `sha256:aeacad5204430ecf78cd21f5e8c3bff4db8f3c7b5150d257b7f787858866e1d4` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.explain.txt` | 967 | `sha256:5a67f5b2e0dd6439d5abca11909359c7fddde0c6f3ffcb58696c83ee84bb1ba2` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.pdf` | 8871 | `sha256:10e34bfce59d023b4b36d2ecab6d78116be2f129cababde77c6ae1162cf16fc7` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.svg` | 18292 | `sha256:aa19380904776eabd12e8ea94020e212c4ebe0202656b22eb32782da8d8ca0e2` |
| `mech_printer_k1/drawings/drawings/contract_graph.drawing.json` | 10960 | `sha256:ebb6cd0367f64ae13f0b38ba6aab3f9ae7c3a076059649fb7bb145945cd579f1` |
| `mech_printer_k1/drawings/drawings/contract_graph.dxf` | 8905 | `sha256:abc8cb8294017c91cf7bf684dcaf227aa468d81c4b9e5e5414aec679f97742c6` |
| `mech_printer_k1/drawings/drawings/contract_graph.explain.txt` | 948 | `sha256:7c7a449c187b26e2c7f5712c828933f78db3debcfe6b61064d42f47751bb05ee` |
| `mech_printer_k1/drawings/drawings/contract_graph.pdf` | 10028 | `sha256:92cd0d6247c0dbe9461d3ec3975f03714b22d837eb63fcd34caade10b35c38bf` |
| `mech_printer_k1/drawings/drawings/contract_graph.svg` | 11939 | `sha256:958cd6bbf3f149b07804a4141e53d7adb770960f423d3635f82e164a1529bdce` |
