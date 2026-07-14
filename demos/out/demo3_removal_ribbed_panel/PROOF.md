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
| `opt_trace_count.pdf` | 6190 | `sha256:5a7ddaea3b48fa65fd723c59552ae39a544b250e5ddd02c52ad68110e0c2b475` |
| `opt_trace_count.svg` | 9564 | `sha256:00217af898fa7a9a829c05990102e7439f020ca912c528028998d08194e83b3e` |
| `opt_trace_thickness.pdf` | 9354 | `sha256:8c2571a073041c83d351bb120d5378f2da93a6d822efd6992f821ce7dda74d80` |
| `opt_trace_thickness.svg` | 13801 | `sha256:60abcbd7e6a2cb7492b3a07dc7c5ea3c0821c23d0017f03e6bc515841cb14273` |
| `regolith.lock` | 387 | `sha256:3bd90d09178253080551b41f538b0495c1646699d8af6ab3cbfa28a4cec089d8` |
| `ribbed_panel.glb` | 1988 | `sha256:7430155ff07ce940880a3cc706e9bdbf47c5a28224539d59d143e66dd6b14155` |
| `ribbed_panel.step` | 76298 | `sha256:52734108d9a31fbf5df970ad35182440c553b8483381ee72cc9af834022e6d2c` |
| `ribbed_panel.viewer.html` | 12128 | `sha256:1052e3159077692939cdcd3baca2867604a960f2449c2e8b45c5a3184462b264` |
| `ribbed_panel_drawing.pdf` | 3710 | `sha256:d61690097e246f268ea1d6e70a20a97abd4d700d4d0d2507da17a977d05070ac` |
| `ribbed_panel_drawing.svg` | 6432 | `sha256:368801a8528bf077b3ae3e6d0c5f6c675fcf684152618496dd60932b1f2f9f93` |
