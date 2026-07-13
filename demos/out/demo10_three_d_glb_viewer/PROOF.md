# PROOF: deterministic GLB + standalone offline viewer.html (charter 38 sec. 1.6)

- pipeline path: `regolith build --release` + `regolith ship --spec ship.spec.json` over cnc_router_r1; the shipped `3d/` family is kept verbatim (no bespoke 3D driver).
- 14 GLB(s), one per realized part, each verified to open with the `glTF` binary magic; fixed tessellation parameters, sorted buffers, no timestamps (charter 38 sec. 1.6) -- re-running this demo end to end reproduces the hashes below byte-identically.
- 14 viewer(s), each verified STANDALONE on the shipped bytes: the GLB payload is embedded inline as base64 (`atob` decode), and the file contains zero external requests (no `http(s)://`, no CDN script/link tags, no `fetch`/XHR). Open any `*.viewer.html` below by double-clicking it -- it renders with no server and no network.

## Re-run

```
uv run python -m demos.demo10_three_d_glb_viewer
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `3d/3d/BaseFrame.cross_b.glb` | 1128 | `sha256:02be5162c98665d8e12055fac6a31b1cb64a3cee287ff60d3a47f0f76093ea41` |
| `3d/3d/BaseFrame.cross_b.viewer.html` | 10992 | `sha256:06818fd90cf7640e17bc9734c09cdc9d3e9cc865dcb1f3ebd64fad3f1c44aed1` |
| `3d/3d/BaseFrame.cross_f.glb` | 1128 | `sha256:995b3667defa7ec97a10e332f7a983eee17cd4e756ff171708adace192735639` |
| `3d/3d/BaseFrame.cross_f.viewer.html` | 10992 | `sha256:a7a3b377cb094c085b16ce24b1d121ae9f516dded04c6209362be707364f40e9` |
| `3d/3d/BaseFrame.cross_m.glb` | 1128 | `sha256:b2055033abd1da4c82ae677122400b80ba36765a6e36f13bbc23c9e15ae4bc2d` |
| `3d/3d/BaseFrame.cross_m.viewer.html` | 10992 | `sha256:39280f0f3a8a50ca7788d112b0c81922150f1fb33876298b0ceae52d9cc098a0` |
| `3d/3d/BaseFrame.rail_l.glb` | 1128 | `sha256:8e4bcf986dd8f255d8db932cff43d485b0e8fe5af52d5fbcc3d3ba28f3f17f28` |
| `3d/3d/BaseFrame.rail_l.viewer.html` | 10990 | `sha256:bc7b01fb1188976489c7b4c106c829ff7f6df8d1cec0fe44bd0d666336c75064` |
| `3d/3d/BaseFrame.rail_r.glb` | 1128 | `sha256:b845b29c5ac7789d28d39cdbd504712a2a011a0a4511617454740e55aae2ae7c` |
| `3d/3d/BaseFrame.rail_r.viewer.html` | 10990 | `sha256:b9b58765727ac44059090e73e9eb9e742ce4f1163013158ec992d8e549e89473` |
| `3d/3d/BaseFrame.upright_l.glb` | 840 | `sha256:e43a86f2c53ac85e2f0598afcd5b21643eeb5aea166c905d84ccac250dcdde7c` |
| `3d/3d/BaseFrame.upright_l.viewer.html` | 10612 | `sha256:b51ef1c509f2b8eb1e4201e82fe9ca5b724ad49b616ef80ab0c8d65222f502b1` |
| `3d/3d/BaseFrame.upright_r.glb` | 840 | `sha256:601f009bc8dfccab79123e9641782dc2c9348f33da32b90c62ab335d95b04d61` |
| `3d/3d/BaseFrame.upright_r.viewer.html` | 10612 | `sha256:41519523d188c19e719d85402e8bc0a6078f61a32e613f9af47830d4f6341309` |
| `3d/3d/BedPlate.body.glb` | 832 | `sha256:503b8b203c921aad448ea518c6f7af7903688f9b3bdb83c24f8510dfc7890496` |
| `3d/3d/BedPlate.body.viewer.html` | 10592 | `sha256:6beb5551006b469d98d436631c5ec914bdb11b997346dfde13408aa07898432b` |
| `3d/3d/GantryBeam.body.glb` | 2208 | `sha256:cda60934a00d4485103dd27e8e9738ab91149f77dbc479aeafcc8e553be65b2f` |
| `3d/3d/GantryBeam.body.viewer.html` | 12428 | `sha256:35a4a91f16fcc5ff223074f4a93eb884c761d93d7b12983de12fd1c59cb2ce3b` |
| `3d/3d/IdlerBearingPlate.body.glb` | 840 | `sha256:ce72db76401002149e44a7505bf40be72ed7b7ec1bfcc7337e814b9cdec1344f` |
| `3d/3d/IdlerBearingPlate.body.viewer.html` | 10618 | `sha256:63311b471f90ee66d1792e043b787946e94e760310b9c1164bcb55641775623e` |
| `3d/3d/MotorPlate.body.glb` | 832 | `sha256:aaa136bedf276509a7d13ced88a70ed04e8289dc3961d61d5348a8dc6efa30be` |
| `3d/3d/MotorPlate.body.viewer.html` | 10596 | `sha256:06b43e571d5ca23fb01dab15dd38206d87ee3eafa0bf51f09316af28664babb9` |
| `3d/3d/SidePlate.body.glb` | 836 | `sha256:20f58e4dd8fcfcca13bfdaa8943eb3d48366fa8be5ca31dc3e9236750d84db92` |
| `3d/3d/SidePlate.body.viewer.html` | 10598 | `sha256:1e94f981170c2099acc6388f575f675fd835212b8aaf7faaecc8790413314bc3` |
| `3d/3d/SpindleMount.body.glb` | 836 | `sha256:4d1e47d1ffe96156338a955a5c409e986da33fd8e25cd4f43abed8a17e4e9ac0` |
| `3d/3d/SpindleMount.body.viewer.html` | 10604 | `sha256:ee7b67db159811938e3ab05bcdd6b1beb87e54381efe4577025708a2df831aa7` |
| `3d/3d/Spoilboard.body.glb` | 836 | `sha256:ec196ecbbd66aab91be17bdb14612aee997182e340e757e1213c6819adb33e02` |
| `3d/3d/Spoilboard.body.viewer.html` | 10600 | `sha256:0f5bfdde28395462c6865af2b78bc43a1367e2cf07cfdfdf1b02beafddabe1eb` |
