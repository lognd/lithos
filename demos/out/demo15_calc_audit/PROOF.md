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
| `calc/base_bolts__00a47be5c6d6.pdf` | 7189 | `sha256:419132825d56718cab62780da3fc9757ca3d134b182d23c1d79fe9be6af89ba1` |
| `calc/calc_book.json` | 39231 | `sha256:2babc86c878b5081809acf8702d67abf445a2b8c522a8ab5e267e29459d08364` |
| `calc/housing_deflection__52437cee0b1d.pdf` | 6790 | `sha256:9d5626f1f790796e88b6370bccd5faf0a772535b91d82ee0ba939a922e7f89e1` |
| `calc/j1_bearing__53ab3fcccae2.pdf` | 6791 | `sha256:b0c6101b8e85d8d2cf99be587947ceb23387ee166515317314d3e88109acd12c` |
| `calc/j2_bearing__52437cee0b1d.pdf` | 6801 | `sha256:2b3f99490538d366d49cb20aaa934e71b889f0015e6f47c0e7023b3ec215b62c` |
| `calc/j3_bearing__aff6c1f5010f.pdf` | 6996 | `sha256:20b763e7fbe33291aedfa7876ff2a012f2abe81e07bee945f31b766fde7d1d5f` |
| `calc/makeable__13d6853d50c8.pdf` | 6099 | `sha256:3456f250b7128f7b01b2e4e0282a085fc9305e023ee22f9d728fed6c8214c50a` |
| `calc/makeable__8063247841b6.pdf` | 6088 | `sha256:de72d6946af4423fa1b64b87c389604a301fff75ea8f01451fe2b56f64ed96bb` |
| `calc/makeable__bc46ac338ae7.pdf` | 6099 | `sha256:9b721c7c216a5eacd21084545c63e8c09fbad930525494d853860331e08a86f5` |
| `calc/payload_deflection__7d65d819881c.pdf` | 7179 | `sha256:7bf41b8254e4ea05754f4aeed62ef02aee22a6c334b6f7093a2324846ecee15d` |
| `calc/payload_deflection__aff6c1f5010f.pdf` | 7182 | `sha256:b5ea8c754af289ecc0c7f0703b20deca13a9342e75f1714fe7403fec892cbbe0` |
