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
| `opt_trace_count.pdf` | 2201 | `sha256:4ff5f1e16996961f5259014594cdc740d8733518029670c556d994ba643049ce` |
| `opt_trace_count.svg` | 2505 | `sha256:53ecb991b489426587d68c1f5352ef6751983f6979eab760a481e9f1daa247b2` |
| `opt_trace_thickness.pdf` | 3654 | `sha256:291ca8923bdec6483eef36a5d8e5f2b24f92883bae3e8f96ce9f6ad29b084b29` |
| `opt_trace_thickness.svg` | 4459 | `sha256:1e3b71c3cb5e45399b96dcde7df9c28e3059978c8a04b5403401f6849e190ae6` |
| `regolith.lock` | 387 | `sha256:3bd90d09178253080551b41f538b0495c1646699d8af6ab3cbfa28a4cec089d8` |
| `ribbed_panel.glb` | 1988 | `sha256:7430155ff07ce940880a3cc706e9bdbf47c5a28224539d59d143e66dd6b14155` |
| `ribbed_panel.step` | 76298 | `sha256:52734108d9a31fbf5df970ad35182440c553b8483381ee72cc9af834022e6d2c` |
| `ribbed_panel.viewer.html` | 12128 | `sha256:1052e3159077692939cdcd3baca2867604a960f2449c2e8b45c5a3184462b264` |
| `ribbed_panel_drawing.pdf` | 1277 | `sha256:9a93e3473600c082d99de487167f361f5da135426d9712937dbbd340a33efd9d` |
| `ribbed_panel_drawing.svg` | 1658 | `sha256:47284b514074a2a6cb96e8e1fc4f1efc937f3c11663de4aa8506b7f309f28a95` |
