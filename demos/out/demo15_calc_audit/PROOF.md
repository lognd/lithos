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
| `calc/base_bolts__00a47be5c6d6.pdf` | 4201 | `sha256:3bb94113c66c522881e6b497e5494d693c07937c492f12cdefb52a53be2f1b16` |
| `calc/calc_book.json` | 32865 | `sha256:d1ae1bfb411b9e202aa8075b7be607f234b384b73a8f0886ba8aa97853345b25` |
| `calc/housing_deflection__52437cee0b1d.pdf` | 4013 | `sha256:501921e718f1d22e241f1c19c8356f74d66cb4476be19c34d11b59523d156515` |
| `calc/j1_bearing__53ab3fcccae2.pdf` | 4016 | `sha256:2a23e52fb9e36abf8e19a3ff1f00eba4250d37975f8033aafde816e4519ae1a4` |
| `calc/j2_bearing__52437cee0b1d.pdf` | 4027 | `sha256:92c3d84c39ae3302b3a2949b32f4ad3bfa7819827b98843883d557384ceb4231` |
| `calc/j3_bearing__aff6c1f5010f.pdf` | 4223 | `sha256:42913d772587ffd6a53b4dfb9a1e162c672ee39e0a9d84f7fe3f9483bcc6a190` |
| `calc/makeable__13d6853d50c8.pdf` | 4190 | `sha256:75e312a08a0bd6a17b57178f91ee7cf625aae989ebb53a7455fc553db1e18ee5` |
| `calc/makeable__8063247841b6.pdf` | 4179 | `sha256:fd2a14a5ffc774607184d8bdfb0849b631fd2e2772b18b19fc5883d8d666b7c3` |
| `calc/makeable__bc46ac338ae7.pdf` | 4190 | `sha256:3179fef8b71b98c8a0d8cdc1c06eb2b0a0af0b0564f607636f87d181b77364c6` |
| `calc/payload_deflection__7d65d819881c.pdf` | 4188 | `sha256:e244ad96176397cd3774fed0a90ee2b9aa079ca0d2c6d16ff5e202430d6a2aac` |
| `calc/payload_deflection__aff6c1f5010f.pdf` | 4189 | `sha256:bccd0f735c84527956406d3daa6e00538d4b8f81d50a58accb13813eb189b77e` |
