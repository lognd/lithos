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
| `civil_small_office/drawings/drawings/Frame.explain.txt` | 2350 | `sha256:caa79f35e037728f335d24293b91385d656589068987a52a92a4460f2d5d8417` |
| `civil_small_office/drawings/drawings/Frame.pdf` | 7209 | `sha256:8262858cc24272e2654c3bd64ab607327a78ba2049cc956479ff34e5210a7601` |
| `civil_small_office/drawings/drawings/Frame.svg` | 11675 | `sha256:ae491721a14bbd7ae04afc5b68c2339ce8477fd5f7eb322c85f2671129f51cc6` |
| `civil_small_office/drawings/drawings/HeatingLoop.drawing.json` | 1959 | `sha256:6a0121a37180f0f187175c12f1974b9cbae2526e27527b3caa3c02587a01d19e` |
| `civil_small_office/drawings/drawings/HeatingLoop.dxf` | 2867 | `sha256:bfa6c4946a70b8acc77631e2f1f55ed8c39a29a1833f6d579c38f5d594ffaa52` |
| `civil_small_office/drawings/drawings/HeatingLoop.explain.txt` | 1581 | `sha256:151be6b1b30bf9be67060ac92e4c60f772ac446b3b7b10ebc69e5a87dd653e82` |
| `civil_small_office/drawings/drawings/HeatingLoop.pdf` | 2829 | `sha256:f6e1a89c4f6fcdaf270ebe98e8e21f3dd55c9656a281c48be0eca633e5094b52` |
| `civil_small_office/drawings/drawings/HeatingLoop.svg` | 3484 | `sha256:0524374a94969a083925187d9a7ff3fab025394b69501f185d541149a522c02c` |
| `civil_small_office/drawings/drawings/contract_graph.drawing.json` | 757 | `sha256:39044d4570a12a66423293724e2c9a3f75b98914e7b25e5d3fcebe0158e61845` |
| `civil_small_office/drawings/drawings/contract_graph.dxf` | 2012 | `sha256:f42bf437dfb7eec9f2dfbac4fa800d13bda9968665e49d9f506269c0187b57e4` |
| `civil_small_office/drawings/drawings/contract_graph.explain.txt` | 1617 | `sha256:a146c358c127913d56815a24dd6997c6af8f26a8e9592d2cae2ac65887473a59` |
| `civil_small_office/drawings/drawings/contract_graph.pdf` | 1651 | `sha256:66c1078a3bbbbb777708672ce3480a91b8e662a96ae1464d616518c29efd6368` |
| `civil_small_office/drawings/drawings/contract_graph.svg` | 2013 | `sha256:27c869df4781b2ba476d07090b3c87cb00984ac58074928344b0b565b208158f` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.drawing.json` | 48117 | `sha256:5263d3abb333b2a914abff5d041d531aeb0ce194cf69d30a3fa632bb8a07fadf` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.dxf` | 62542 | `sha256:71682a7e1861f90c8905ddc9bd73821e095a62cc599fa95550d693e6a8f247f1` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.explain.txt` | 1641 | `sha256:b9bd71850655605a84695a8336133624336b015d94b3c690329d0cd4865dc3d9` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.pdf` | 34149 | `sha256:16a867e15d8bf64aa656bee567ad04e026a352acf04bbf923b7e8d1ed0a4b7a8` |
| `mech_printer_k1/drawings/drawings/BedCarriage.body.svg` | 73795 | `sha256:fb4886538802661e36e78705997a4e404e334c2cc698a57fb3b0a5220ca1cf90` |
| `mech_printer_k1/drawings/drawings/PartCooling.drawing.json` | 1188 | `sha256:d8666b184b6bbe024cb0eb0cec83ac368d9c5b44674d155efcb3fbba1206f07a` |
| `mech_printer_k1/drawings/drawings/PartCooling.dxf` | 2399 | `sha256:5a19ca8d427bd27139586acf7f7b317559661c54f3493ee4ee1048e06781c77e` |
| `mech_printer_k1/drawings/drawings/PartCooling.explain.txt` | 1581 | `sha256:167f444e1cbcc04f17b507d9435d453e2ebef57d53077eaa526e926602ea2b98` |
| `mech_printer_k1/drawings/drawings/PartCooling.pdf` | 2028 | `sha256:f9b88891a163a3cd3bdbc8e9f585ee5ffe9590c29bc5cb43b57ddfce6143f0f1` |
| `mech_printer_k1/drawings/drawings/PartCooling.svg` | 2540 | `sha256:3a35f5f6a3dd519ea7e93fd55acb1ac25679d5c591a37bd53f1a302d64a61912` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.drawing.json` | 8421 | `sha256:010c5d095430a803f20702674eed5c982a7d5fffd1f445ec54ed0afe6b95170b` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.dxf` | 11723 | `sha256:47728b5f16e2d4a195ec91c2826b93453b88fd5ac28bb32c012e9f2fa75ad7d8` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.explain.txt` | 1713 | `sha256:09b446ad176791b48147b86e6e25573fbf620364a9f5fe204613284080f91eea` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.pdf` | 6713 | `sha256:cefb21592691b9bea6e47c0d2dbbc69a6e16f2b0fb25fe191831496daa477196` |
| `mech_printer_k1/drawings/drawings/XRailBracketLeft.blank.svg` | 13480 | `sha256:12edf98d8e81ac7c6d8df39455e7aae63236e71fe77637062ebf46ea5afcfeee` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.drawing.json` | 8425 | `sha256:3c6481a1eec2c0fd6849298fae0a0d0a89a39d91749e9d51ba70bac908337415` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.dxf` | 11726 | `sha256:b55c2776f83bd4eabb0bb66c69fd0f3cc682399dff25e1171f3f31c3cbdc753b` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.explain.txt` | 1725 | `sha256:b598b5f015366991e3f8ad44a64485be6686ef7ec339fb2f730c1ae79c3b9a0c` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.pdf` | 6716 | `sha256:89a8c135025bdd465d6c64e1de3ae45095b23f321acd500a6ff4ae113a393823` |
| `mech_printer_k1/drawings/drawings/XRailBracketRight.blank.svg` | 13483 | `sha256:7c3e3b93bb9a2adf6ef99e1bf51e017f6cf00b75ea59f5912c6abb8a6a8165c3` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.drawing.json` | 12075 | `sha256:5dde6f1c4766dab4d892de9e38049cfd5d588e4ebe61f2f263e2d3f7f0de3ff9` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.dxf` | 16583 | `sha256:e4e7e55707867830f585bafaa6c616a8552c82c2791a65ea45aac5573852ae5d` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.explain.txt` | 1629 | `sha256:87f1590b94d3c5161eef19aa6bc9c449945ea8bf09f0869af4a03e016ad6516d` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.pdf` | 9330 | `sha256:907b44132127106525e3fbc494dea771b1fb166db30003193f33bdddb4d8c058` |
| `mech_printer_k1/drawings/drawings/YCarriage.blank.svg` | 19113 | `sha256:e604caa589c76399443de0762efe2dee39611f762bce7640c17ad671b273a9f1` |
| `mech_printer_k1/drawings/drawings/contract_graph.drawing.json` | 10960 | `sha256:ebb6cd0367f64ae13f0b38ba6aab3f9ae7c3a076059649fb7bb145945cd579f1` |
| `mech_printer_k1/drawings/drawings/contract_graph.dxf` | 9438 | `sha256:37390d3fa307d8efa9b80be1612212038a3d99060e7b2158550b479a2c4b42c4` |
| `mech_printer_k1/drawings/drawings/contract_graph.explain.txt` | 1614 | `sha256:0cf50605d7251f7f07d47d003a5d8e5ee228af4a70251479e5bf81b75916014d` |
| `mech_printer_k1/drawings/drawings/contract_graph.pdf` | 10488 | `sha256:20080e146b9f8d6b43f6b78f3943bb416c05c6c27038a3833f4b796afe937c0d` |
| `mech_printer_k1/drawings/drawings/contract_graph.svg` | 12785 | `sha256:d1b3fa69e1e7b7562d8f7f880576b4f871ab3b720a99f97e84c568a2422e93f5` |
