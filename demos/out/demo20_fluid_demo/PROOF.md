# PROOF: WO-144 fluids close-out -- burn-down finding + the espresso fallback's real dp discharge (D258.5/F152/F157)

- pipeline path: `regolith build --release` then `regolith ship` (real CLI, both projects) + the `diagram.moody` producer (`regolith.backends.drawings.producers.diagram_moody`) called directly on the espresso calc sheet's own discharged numbers.

## Primary target: small_office (F-WO144-1 finding)

`small_office/hydronics.fluo`'s `margin`/`balance` claims now ROUTE to real registered models (`fluids_dp_multipath@1`, `fluids_flow_imbalance@1`, WO-139/140/141) -- but the feldspar Hardy-Cross pack itself abstains: `hardy_cross: unsupported feature edge_kind:hx_segment`. `coil1`/`coil2` are `HxSegment` edges, a payload feature the pack's solver does not carry yet (a feldspar-side gap, not a lithos bridge gap; out of this WO's scope to add). Per the WO's own escalation clause this is FINDING F-WO144-1, and this demo falls back to the espresso story (D258 ruling 5) rather than faking a close.

`npsh` also cannot close: `registry(grundfos_ups32)` names a pump-curve record that does not exist anywhere in `stdlib/std.fluid/records/components.toml` -- a missing catalog record, never fabricated (D224.1).

### Waiver-basis honesty (F152): before -> after

Every remaining small_office hydronics waiver's basis was corrected to name its TRUE current reason (the old text was stale and, for `balance`/`npsh`, flatly false -- registered models exist now). No waiver count dropped (F-WO144-1 blocks it), but every basis that remains reads true, which is F152's actual bar:

| claim | old (stale) basis | new (true) basis |
|---|---|---|
| margin | fluids.dp_inputs_missing: the supply riser Pipe edge lacks density/dia... | WO-144 F152 update: the WO-139/140/141 chain now ROUTES this claim to the feldspar Hardy-C... |
| balance | no registered harness model for claim kind 'fluids.flow_imbalance'... | WO-144 F152 update: a registered model now exists (fluids_flow_imbalance@1, WO-141) and th... |
| npsh | no registered harness model for claim kind 'fluids.npsh_margin'... | WO-144 F152 update: a registered model exists (NpshMarginModel, WO-110) and the npsh chann... |

`regime`/`fill` are UNCHANGED and remain named residuals: F157 (design-log 2026-07-15-cycle-36.md) has landed the elec converter call-form routing only -- the `settles()`/ window-comparator claim-SHAPE lowering surface `regime`/ `fill` need is still an open, real job, not landed for fluids or any other track. Stated plainly, per the WO's own acceptance bar: this is a residual, not a discharge, and not silently narrowed to look closed.

## Fallback: espresso_machine's thermosiphon dp claim (the real win)

`thermosiphon.fluo`'s `dp: fluids.dp(riser_top -> group_in, ...) <= 2Pa` is a SINGLE-segment `Pipe` edge claim (no multipath solve needed) -- it discharges for real: `fluid_darcy_weisbach_dp@1`, value `0.226172 Pa`, margin `1.77383`, citation `White, Fluid Mechanics, 8th ed., sec. 6.6, Darcy-Weisbach`.

`supply_dp` (the brew_water.fluo multipath claim, D258 ruling 5's named espresso story) does NOT discharge: its `chamber` edge extracts realized CAD geometry (`edge_params:geom_extract`), a SECOND, distinct solver-unsupported feature -- not the same gap as F-WO144-1, named here rather than conflated with it. `npsh` in the espresso fixture stays waived too: the Ulka EX5 pump's NPSH_r curve is not vendor-published (a real data gap, D224.1, not a toolchain gap).

## The Moody figure

Rendered from the `dp` sheet's own discharged inputs: `friction_factor=0.03` (declared literal, this claim's own regime band asserts laminar flow, `Re in [50, 2e3]`). The laminar closed form is EXACT (`f = 64/Re`, White 8e sec. 6.4 -- the same citation the sheet carries), so `operating_re=2133.3` is the algebraic inverse of that closed form applied to the sheet's own `f`, not a measurement and not a fabrication. `eps_d_family=()`: laminar flow has zero roughness dependence, so no curve family is drawn.

Honest observation, not smoothed over: `2133.3` sits about 6.7% above this claim's own asserted laminar ceiling (`Re <= 2e3`). This WO's scope is waiver-basis text, not claim re-derivation, so the discrepancy is named here rather than reconciled.

**Drafting-audit residual (T-0056), ridden honestly**: `diagram.moody` sheets do not yet pass `assert_ship_ready` (INV-31) -- the shared `ChartGeometry` annotation layout was built for `optimize.trace`'s staircase side-labels, not a multi-series/log-scale chart, and this producer's annotations overlap under that layout (`tests/backends/test_diagram_moody.py::test_passes_the_drafting_audit`, xfail `strict=True`). This demo emits the sheet and states that residual plainly; it does not call `assert_ship_ready` as a gate here, and does not claim the sheet is ship-ready.

## Re-run

```
uv run python -m demos.demo20_fluid_demo
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `espresso_dp_sheet.json` | 1996 | `sha256:5a413c729f645d19cb2231e243e9f801e1a9c9f1f96f6adadc4497fbfaa6aaa3` |
| `moody_diagram.json` | 10632 | `sha256:51ffbd8341c82d2ac4212e308e40e2b8d06243a33dcb32cfb546bf4b2288022a` |
| `small_office_explain.txt` | 20149 | `sha256:0a87c6b372bb0a3e8f7424f343273c608280a2a1b1d2e7c85ec7f304f6badf2b` |
