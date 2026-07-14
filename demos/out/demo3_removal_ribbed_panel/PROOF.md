# PROOF: removal-vocabulary bounded slots (ribbed_panel, WO-77)

- optimized quantity: **mass** (realized panel volume x density, measured by the real OCCT interpreter for EVERY candidate)
- domain: the `Ribs` op's planner-tagged bounded slots, read off the emitted FeatureProgram of `examples/tracks/hematite/ribbed_panel.hema` --
  - `RibbedPanel.lightening.count` in [4, 8]
  - `RibbedPanel.lightening.thickness` in [2mm, 5mm]
- winner: **count = 4 ribs**, **thickness = 3.970 mm** (fewest ribs at an interior thickness -- decided by the search over real realized mass under a stiffness floor, not an authored answer)
- cause rows (verbatim from `regolith.lock`):

```
RibbedPanel.lightening.count=4    cause: optimize(mass, trace=blake3:07f1921d90a84af426bbaef098c0c49c93c372519766396524332908c1f50992)
x=0.003970303111409936    cause: optimize(mass, trace=blake3:6e4b39ba0a7b6c257db833a2d6a5928f567d2307bb2732341d4076e0003ab270)
```

## Where a human SEES it

- `ribbed_panel.step` / `.glb` / `.viewer.html` -- the realized solid carrying the pinned 4 ribs; open the viewer offline to rotate it.
- `ribbed_panel_drawing.svg` / `.pdf` -- the part drawing whose dimensions carry provenance back to the pinned geometry.
- `opt_trace_count.svg/.pdf` (trace `blake3:07f1921d90a84af426bbaef098c0c49c93c372519766396524332908c1f50992`) and `opt_trace_thickness.svg/.pdf` (trace `blake3:6e4b39ba0a7b6c257db833a2d6a5928f567d2307bb2732341d4076e0003ab270`) -- the outer count search and the winning count's inner thickness search, each candidate's measured mass and the winner annotation.

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `opt_trace_count.pdf` | 6136 | `sha256:2055e35ab141fcc52256d97fbb2aea5cc9ace0fd803270ca4ba954338f4f25b0` |
| `opt_trace_count.svg` | 9564 | `sha256:645d45a43f714cdac9d2eb516493fc8fb70e080e6431c5974f0aa565dc052f21` |
| `opt_trace_thickness.pdf` | 9347 | `sha256:3dcef1cdfc6e49038814016d9b0dbee67015e1b2662015a8996fb966144a8552` |
| `opt_trace_thickness.svg` | 13877 | `sha256:be707a716baad54b732c929356ef2d9169426e1104065dccdae87a7a3c614884` |
| `regolith.lock` | 387 | `sha256:3bd90d09178253080551b41f538b0495c1646699d8af6ab3cbfa28a4cec089d8` |
| `ribbed_panel.glb` | 1988 | `sha256:7430155ff07ce940880a3cc706e9bdbf47c5a28224539d59d143e66dd6b14155` |
| `ribbed_panel.step` | 76298 | `sha256:52734108d9a31fbf5df970ad35182440c553b8483381ee72cc9af834022e6d2c` |
| `ribbed_panel.viewer.html` | 12128 | `sha256:1052e3159077692939cdcd3baca2867604a960f2449c2e8b45c5a3184462b264` |
| `ribbed_panel_drawing.pdf` | 3710 | `sha256:d61690097e246f268ea1d6e70a20a97abd4d700d4d0d2507da17a977d05070ac` |
| `ribbed_panel_drawing.svg` | 6432 | `sha256:368801a8528bf077b3ae3e6d0c5f6c675fcf684152618496dd60932b1f2f9f93` |
