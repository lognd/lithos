# mainboard_mx -- ATX-class controller mainboard (flagship, WO-71)

SoM-carrier posture (D183 row: acceptable posture "if it keeps the
elec chain honest" -- this flagship exercises the DENSE elec chain,
not a from-scratch SoC bringup).

Envelope-target givens (each is a literal the parity report's
attention list will show -- correct and honest per AD-33, not a
derived value):

- ATX-class outline, <= 305mm x 244mm (`mainboard_mx.cupr` boundary).
- 12V system input (`connectors.cupr` `PowerInConn`).
- Multi-rail power tree: 12V -> 5V -> {3.3V, 1.8V, 1.1V}
  (`power_tree.cupr`).
- Single SoM-carrier compute boundary (`mcu.cupr` `MainboardMcu`).

## Files

- `magnetite.toml` -- manifest, BOM-bearing cost profile
  (`profiles.cost.prototype`/`default`, D147 shape).
- `power_tree.cupr` -- the multi-rail power tree: `Rail5V`/`Rail3V3`
  `by select` over named candidates (D161 shape); `Rail1V8`/`Rail1V1`
  contract-only (`todo!`, honest deferral).
- `mcu.cupr` -- `MainboardMcu` board: SoM carrier port contract +
  the EBI/decode `by select` reuse (`ebi_decode.cupr` D161 shape,
  verbatim-carried candidate set).
- `connectors.cupr` -- `PowerInConn`, the 12V input connector,
  realized `by circuit` with one vendor part.
- `mainboard_mx.cupr` -- top-level integration: power-tree wiring,
  per-rail current + wall-power budgets that sum and close, BOM cost
  budget, policy line the optimize test's cost objective reads.

## Demonstrations (D183) and where they live

1. Multi-rail power tree + droop budgets that sum and close at L2:
   `power_tree.cupr` (`require Droop` per rail) + `mainboard_mx.cupr`
   (`require Tree`, `budget wall_power`/`rail_current_*`).
2. `by select` on >= 2 regulator stages, pinned via a real
   `regolith optimize` run with a cost objective: `Rail5V`/`Rail3V3`
   in `power_tree.cupr`; the pin + trace live in
   `tests/test_wo71_mainboard_selects.py`.
3. Elec chain driven as far as the landed realizers go: see the WO
   ledger -- BlockRequirement/netlist tier vs. the KiCad
   RealizedLayout tier (wall recorded if the latter does not run in
   this environment).
4. Feldspar lumped thermal transient discharging a VRM thermal claim:
   `tests/test_wo71_mainboard_vrm_thermal.py`, model-direct against
   feldspar's `heat.transient.duty_cycle_peak_temperature` (the
   lithos-side claim form is a recorded continuation slice -- see the
   WO ledger).
5. Costing with a BOM-bearing profile: `magnetite.toml`
   `profiles.cost.prototype` + `mainboard_mx.cupr`'s `budget bom_cost`.
6. Ship artifacts: contract-graph sheet, deterministic, audit-clean
   (`tests/test_flagship_mainboard_contract_graph.py`; the
   `elec_blocks` diagram is a recorded continuation slice).

See `docs/workflow/work-orders/WO-71-flagship-mainboard.md` for the
full ledger, walls, and parity accounting.
