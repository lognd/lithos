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
| `calc/base_bolts__00a47be5c6d6.pdf` | 7171 | `sha256:37a79e666cdbafdff08b05d1b8e03cbdb3d4197eea197a95cfe2068e8b43b5c0` |
| `calc/calc_book.json` | 38421 | `sha256:4c8b0e4f6b9a377ff14900a99e85c0161859404089c30e6544fb59e354901215` |
| `calc/housing_deflection__52437cee0b1d.pdf` | 6772 | `sha256:9f9ec8093d9003c272cfcbe4f76c6f27d363d098c9d30d70a667ffa3c8665873` |
| `calc/j1_bearing__53ab3fcccae2.pdf` | 6779 | `sha256:891be80959f06368a716e2fbd75b1959f0e724844d27261865ce47d68191eb26` |
| `calc/j2_bearing__52437cee0b1d.pdf` | 6789 | `sha256:632d5e4030bb701874542ecddad26e78002655663de89f09ab732f34afb89910` |
| `calc/j3_bearing__aff6c1f5010f.pdf` | 6984 | `sha256:0839b630db1bab0712ffa97dca5a5031946bb89da8bb87fdf3663111cd79c61b` |
| `calc/makeable__13d6853d50c8.pdf` | 6093 | `sha256:b11091c5d6eb7fbb42b4c745b1bf2d471f751b09366e5033ab192c004a4125cc` |
| `calc/makeable__8063247841b6.pdf` | 6082 | `sha256:78ea0d289abbaaffdd0ca220bcb3183c1409d445e4b164350f57ef0a0f75eb4c` |
| `calc/makeable__bc46ac338ae7.pdf` | 6093 | `sha256:b18f6f85a42b12f2cf10169ae33f3048a820e4c0661c29907f49d642634143f5` |
| `calc/payload_deflection__7d65d819881c.pdf` | 7158 | `sha256:a991a26dfddd395f87c8e373f220fe12588ad61635de1ba951e79afded830746` |
| `calc/payload_deflection__aff6c1f5010f.pdf` | 7161 | `sha256:13cabcd9f3732a80039a1ae7eaecc6dcdeb8497b27d656001d16f72934bb9e35` |
