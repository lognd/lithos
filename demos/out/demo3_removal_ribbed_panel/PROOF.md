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
| `opt_trace_count.pdf` | 6190 | `sha256:cd8cf5463026b745bfa9d6c02327f0883b191b738ce816353dcf0dce198bfbb6` |
| `opt_trace_count.svg` | 9564 | `sha256:22f9e665925227d75f826e6778a3ef03c056cfa7521c691d4206f3d63163bb93` |
| `opt_trace_thickness.pdf` | 9354 | `sha256:71e2e92890a4e0ead10acc910ef12162a0baf5722d31c017b17c4ddfddb3af16` |
| `opt_trace_thickness.svg` | 13801 | `sha256:55deb94a7dcb33909b0ce3a21312f2a3e8aa38e20127d8ea9bcbd41a43a86f2f` |
| `regolith.lock` | 387 | `sha256:3bd90d09178253080551b41f538b0495c1646699d8af6ab3cbfa28a4cec089d8` |
| `ribbed_panel.glb` | 1988 | `sha256:7430155ff07ce940880a3cc706e9bdbf47c5a28224539d59d143e66dd6b14155` |
| `ribbed_panel.step` | 76298 | `sha256:52734108d9a31fbf5df970ad35182440c553b8483381ee72cc9af834022e6d2c` |
| `ribbed_panel.viewer.html` | 12128 | `sha256:1052e3159077692939cdcd3baca2867604a960f2449c2e8b45c5a3184462b264` |
| `ribbed_panel_drawing.pdf` | 3710 | `sha256:4ad6041263340fc95f8451283eaf612a99888a28932dc4f54227b5d00d954169` |
| `ribbed_panel_drawing.svg` | 6432 | `sha256:38365b706d11095b21a906a79fd8a017c03b1d4d548833015cb67a2f4bad7182` |
