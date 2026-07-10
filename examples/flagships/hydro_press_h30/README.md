# hydro_press_h30 -- flagship, 30-ton H-frame shop press

WO-73 (design-log 2026-07-10-cycle-32 D183, wave 2). Built end-to-end
per the WO-64 A->C template in one dispatch arc; see the WO file's
ledger for phase status and honest-partial residuals.

## Machine-class targets (asserted givens, AD-33 attribution)

- **30 short ton (266.9kN) rated tonnage class**, asserted in
  `frame.calx` (`ram:` load), `corners.hema` (`press_reaction`), and
  `hydraulics.fluo` (`Capacity.rated` / `Safety.relief_holds`) --
  a literal cited machine-class target, not a derived value.
- **21MPa rated line pressure / 24MPa relief set / 27MPa burst
  margin**, the H30-class gear pump + relief circuit.
- **700mm column spacing x 1.4m daylight**, the H-frame envelope.

## Track choice: calcite for the frame, hematite for welds/bolts

`frame.calx` carries the H-frame MEMBERS (two HSS-square columns,
two W-shape beams) because calcite is the only landed track with
`section: in registry(...)` search (footbridge G1's real discharge
precedent, WO-65 ledger) -- hematite has no section-search
vocabulary. `corners.hema` carries the welded corner gussets
(`FilletWeld` + `mech.weld_stress`, the cnc_router/frame.hema
precedent) and the head-plate bolted joint (`mech.bolt.
separation_margin`, the dune_buggy/engine_top_end.hema precedent),
because calcite has no weld/bolt-joint claim vocabulary. No single
track carries both required feldspar surfaces on one file -- recorded
as WO-73 ledger wall W1 and flagged mid-dispatch.

## File map

| file | track | contract |
|---|---|---|
| `frame.calx` | calcite | H-frame members, section search, utilization + deflection under the 30-ton case |
| `corners.hema` | hematite | welded corner gussets (weld-group check) + head-plate bolted joint (bolt separation-margin check) |
| `ram_platen.hema` | hematite | ram + platen contract-only mounts (phase A) |
| `hydraulics.fluo` | fluorite | pump/relief/directional-valve/ram circuit; the release-gated relief-pressure safety claim |
| `hydro_press_h30.cupr` | cuprite (top) | machine-scale budgets, cross-track composition, restated safety claims |

See the WO-73 ledger (`docs/workflow/work-orders/WO-73-flagship-hydro-press.md`)
for the full walls table, optimizer-pin evidence, and parity accounting.
