# PROOF: calc book + audit index with real discharges, walked row by row (arm_a6)

- pipeline path: `regolith build --release` + `regolith ship --spec` over arm_a6; the shipped `calc/` family is kept verbatim (calc_book.json, audit_index.json, one PDF per discharged sheet) beside `acceptance_ledger.json`.
- EVERY-ROW WALK: all 54 obligations resolve to exactly one disposition -- 10 calc sheets (each with a rendered PDF, asserted on disk) + 44 accepted deviations (each content hash cross-linked into an acceptance-ledger match set, asserted), 0 violated, 0 deferred, 0 unexplained; the summary block reconciles with the rows.
- HASH CHAIN: every sheet's `chain.sheet_digest` was recomputed here INDEPENDENTLY (blake3 over the sheet's own canonical body, `local-blake3:` tag) and matches the shipped value; every sheet cites its discharge evidence hash; 7 sheet(s) carry record-pinned inputs surfaced in `chain.record_pins`.
- every value/margin/model/citation below is the REAL discharge's own (D224 enrichment: cited manufacturer ratings, ISO 281 exponents, VDI 2230 -- see each sheet's `inputs` provenance).

## The ten discharged sheets

| sheet | model | value | margin | citation |
|---|---|---|---|---|
| base_bolts::52576b2ef524 | bolted_joint_separation_vdi2230@1 | 14875.2 | 13383.7 | VDI 2230 joint-stiffness diagram, concen |
| housing_deflection::b9f09cfa67c4 | beam_cantilever_deflection_eb@1 | 1.09232e-06 | 0.000198853 | uncited built-in |
| j1_bearing::49ecee58d1c9 | bearing_basic_rating_life_l10h@1 | 1.02221e+07 | 5.09104e+06 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| j2_bearing::b9f09cfa67c4 | bearing_basic_rating_life_l10h@1 | 1.28925e+06 | 624623 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| j3_bearing::ef1d76cd7518 | bearing_basic_rating_life_l10h@1 | 1.90556e+08 | 9.52628e+07 | ISO 281:2007 sec. 6.2, basic (L10) ratin |
| makeable::09207c26be84 | mfg_manufacturable_mill@1 | -0.8 | 0.8 | declared [[machine]]/[[tool]] record env |
| makeable::17597b36ecbd | mfg_manufacturable_mill@1 | 0 | 0 | declared [[machine]]/[[tool]] record env |
| makeable::7edc9b53202d | mfg_manufacturable_mill@1 | -0.8 | 0.8 | declared [[machine]]/[[tool]] record env |
| payload_deflection::d6bb9d908029 | beam_cantilever_deflection_eb@1 | 5.60867e-05 | 0.00144111 | uncited built-in |
| payload_deflection::ef1d76cd7518 | beam_cantilever_deflection_eb@1 | 3.61723e-05 | 0.00116202 | uncited built-in |

## Re-run

```
uv run python -m demos.demo15_calc_audit
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `acceptance_ledger.json` | 17227 | `sha256:1d37b78d13777d628722469a013cdaaa6c0d64d01b0436e9b4d2d97d1af205c0` |
| `calc/audit_index.json` | 19121 | `sha256:0e0518e5f0921b7d528f35c1da9a03f2604a9a5fec2043066680f0e4ce12aaaa` |
| `calc/base_bolts__52576b2ef524.pdf` | 7192 | `sha256:7172b7b0582436c4a973fa0181bf47803310196dd8ac21c615661839899c1225` |
| `calc/calc_book.json` | 39281 | `sha256:6326271923007c578ad240e1cb075bd3286b3240b5068456b402c69d23089d1a` |
| `calc/housing_deflection__b9f09cfa67c4.pdf` | 6789 | `sha256:2c72777f5685a15859455f4edb6b16b4c0a4796eb2fac483aa0e108d3fa14950` |
| `calc/j1_bearing__49ecee58d1c9.pdf` | 6791 | `sha256:b836956051411779966f2febb971ab96bd87f3b00563e20d20af37be66bb82c0` |
| `calc/j2_bearing__b9f09cfa67c4.pdf` | 6801 | `sha256:8f63836701215f610706a03646fd08ec173e58f70ce8132698a89bd0519a8e4a` |
| `calc/j3_bearing__ef1d76cd7518.pdf` | 6996 | `sha256:fd3ffcff79c5a3f5e7b6374fa4aab2c4842e205d41e642fb4ef87c804e4818de` |
| `calc/makeable__09207c26be84.pdf` | 6099 | `sha256:758c5ca9d76c196bcd19ae0f38db7de2c6223139dcfcab27a4148ae15384d70e` |
| `calc/makeable__17597b36ecbd.pdf` | 6088 | `sha256:8ed7823db975088121b63936e2a62b5d4c64e661603cb36b2960c639e56f6ea0` |
| `calc/makeable__7edc9b53202d.pdf` | 6099 | `sha256:ea5704f429c3fa2daf0fbe241f0ab1abb39cc636c91605137ab6873291bf7a6b` |
| `calc/payload_deflection__d6bb9d908029.pdf` | 7178 | `sha256:0f8ab63ddd38455f011ffa4d1215429defc3aa62009893e16e9ba856d6902867` |
| `calc/payload_deflection__ef1d76cd7518.pdf` | 7181 | `sha256:8fb7b786602117a1d9f17af86ed1c49620e413ef08770630903770704b886c86` |
