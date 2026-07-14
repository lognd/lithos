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
| `opt_trace_count.pdf` | 4966 | `sha256:1232e7366435af4b2db7436cf47c0ff176a7895f9ec7b9e703af5d3bafad0772` |
| `opt_trace_count.svg` | 7582 | `sha256:d986e9a28cded8ae75856be7c32bdb5c552d824ad7a7e3759dee0a4e2d376636` |
| `opt_trace_thickness.pdf` | 8080 | `sha256:377249a482323db8aa217de2f591efe36f3775a7e5149d3e38003b8d742c2c1f` |
| `opt_trace_thickness.svg` | 11899 | `sha256:4702112981c2a69977c850a7570b7ee0341904666cdecd340c7d0293f90998d7` |
| `regolith.lock` | 387 | `sha256:3bd90d09178253080551b41f538b0495c1646699d8af6ab3cbfa28a4cec089d8` |
| `ribbed_panel.glb` | 1988 | `sha256:7430155ff07ce940880a3cc706e9bdbf47c5a28224539d59d143e66dd6b14155` |
| `ribbed_panel.step` | 76298 | `sha256:52734108d9a31fbf5df970ad35182440c553b8483381ee72cc9af834022e6d2c` |
| `ribbed_panel.viewer.html` | 12128 | `sha256:1052e3159077692939cdcd3baca2867604a960f2449c2e8b45c5a3184462b264` |
| `ribbed_panel_drawing.pdf` | 2078 | `sha256:a31f02f4cad3052fd6d907d9a671027bd0d106e4e670b7e97f0568a3c4fa2f72` |
| `ribbed_panel_drawing.svg` | 3299 | `sha256:e800126e722dcb3d9271844648648275636d9f2bbc0406149f8185bf6582f0ff` |
