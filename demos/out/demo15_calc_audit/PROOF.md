# PROOF: calc book + audit index with real discharges, walked row by row (arm_a6)

- pipeline path: `regolith build --release` + `regolith ship --spec` over arm_a6; the shipped `calc/` family is kept verbatim (calc_book.json, audit_index.json, one PDF per discharged sheet) beside `acceptance_ledger.json`.
- EVERY-ROW WALK: all 54 obligations resolve to exactly one disposition -- 10 calc sheets (each with a rendered PDF, asserted on disk) + 44 accepted deviations (each content hash cross-linked into an acceptance-ledger match set, asserted), 0 violated, 0 deferred, 0 unexplained; the summary block reconciles with the rows.
- HASH CHAIN: every sheet's `chain.sheet_digest` was recomputed here INDEPENDENTLY (blake3 over the sheet's own canonical body, `local-blake3:` tag) and matches the shipped value; every sheet cites its discharge evidence hash; 7 sheet(s) carry record-pinned inputs surfaced in `chain.record_pins`.
- every value/margin/model/citation below is the REAL discharge's own (D224 enrichment: cited manufacturer ratings, ISO 281 exponents, VDI 2230 -- see each sheet's `inputs` provenance).

## The ten discharged sheets

| sheet | model | value | margin | citation |
|---|---|---|---|---|
| base_bolts::00a47be5c6d6 | bolted_joint_separation_vdi2230@1 | 14875.2 | 13383.7 | VDI 2230 joint-stiffness diagram, concen |
| housing_deflection::52437cee0b1d | beam_cantilever_deflection_eb@1 | 1.09232e-06 | 0.000198853 | uncited built-in |
| j1_bearing::53ab3fcccae2 | bearing_basic_rating_life_l10h@1 | 1.02221e+07 | 5.09104e+06 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| j2_bearing::52437cee0b1d | bearing_basic_rating_life_l10h@1 | 1.28925e+06 | 624623 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| j3_bearing::aff6c1f5010f | bearing_basic_rating_life_l10h@1 | 1.90556e+08 | 9.52628e+07 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| makeable::13d6853d50c8 | mfg_manufacturable_mill@1 | -0.8 | 0.8 | declared [[machine]]/[[tool]] record env |
| makeable::8063247841b6 | mfg_manufacturable_mill@1 | 0 | 0 | declared [[machine]]/[[tool]] record env |
| makeable::bc46ac338ae7 | mfg_manufacturable_mill@1 | -0.8 | 0.8 | declared [[machine]]/[[tool]] record env |
| payload_deflection::7d65d819881c | beam_cantilever_deflection_eb@1 | 5.60867e-05 | 0.00144111 | uncited built-in |
| payload_deflection::aff6c1f5010f | beam_cantilever_deflection_eb@1 | 3.61723e-05 | 0.00116202 | uncited built-in |

## Re-run

```
uv run python -m demos.demo15_calc_audit
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `acceptance_ledger.json` | 17227 | `sha256:b0f0c19e5bfb8372481af62a2eeaeef7a3a128746954f9802107c683842aaf24` |
| `calc/audit_index.json` | 19121 | `sha256:cd9b0061b612b6b62f925583979f9688fb9d7f2944518a35adcf91b8eff8cc52` |
| `calc/base_bolts__00a47be5c6d6.pdf` | 2256 | `sha256:679f4174829a3088297904976f586251cbe8a2d5d9ad4f16293793ced4b98734` |
| `calc/calc_book.json` | 32865 | `sha256:d1ae1bfb411b9e202aa8075b7be607f234b384b73a8f0886ba8aa97853345b25` |
| `calc/housing_deflection__52437cee0b1d.pdf` | 2284 | `sha256:bf5eb7866988d927b5e46c60bb364ee8e2f80258e04f5d4406f3efdbcf91a3d1` |
| `calc/j1_bearing__53ab3fcccae2.pdf` | 2231 | `sha256:5db34389005770877ae0b484f5803560be8ff1311052a0d19f89f9dc22fdfb0a` |
| `calc/j2_bearing__52437cee0b1d.pdf` | 2242 | `sha256:c8fc3499220e2798c9c32d5ed6760eb556ebe29ef2459f04b8ace61ef4b129d2` |
| `calc/j3_bearing__aff6c1f5010f.pdf` | 2302 | `sha256:c3a73d74d24e4e50e4a990d1eb2da79fee38ac67fd89923754bb455b3725b6a1` |
| `calc/makeable__13d6853d50c8.pdf` | 2197 | `sha256:4658d4f48e629a49039dd90e460ef8b0eee70cc6468ade399d41378513099193` |
| `calc/makeable__8063247841b6.pdf` | 2186 | `sha256:5771d59f692e0bc3498c445cb466eded00ab737db82cfe4b27949b3300c3928c` |
| `calc/makeable__bc46ac338ae7.pdf` | 2197 | `sha256:1798a978f1d806a4f0fafce79e4c26cb4fce5102af56fed26ca7911cd7a41e02` |
| `calc/payload_deflection__7d65d819881c.pdf` | 2294 | `sha256:40dc26c6a713e22d3b15a24436acff60b5ee2ad9692750f82f400bda365f57f8` |
| `calc/payload_deflection__aff6c1f5010f.pdf` | 2295 | `sha256:18ee6ae49b40ead92d986e1fe3db2ce1c783e794f7d4e23b4543e6b292111371` |
