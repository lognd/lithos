# uav_talon -- flagship, the fixed-wing electric UAV

WO-70: the WO-64 A->C arc in one dispatch (contract-first
architecture -> realize what the landed toolchain supports ->
optimize -> discharge -> ship artifacts + parity accounting), per
`docs/workflow/design-log/2026-07-10-cycle-32.md` D183's row for this
flagship.

## Envelope targets (asserted givens)

Literals with a cited source position (the parity report's own
attention-list entry, AD-33: attribution not optimality) -- same
posture as `printer_k1/README.md`'s own envelope targets.

- **~1.2m wingspan class, 0.24 m2 planform area**, asserted in
  `uav_talon.cupr` (`UavTalon.boundary.wingspan`/`wing_area`). Source:
  `docs/workflow/work-orders/WO-70-flagship-uav.md` ("~1.2m fixed-wing
  electric UAV").
- **3S (11.1V nominal) electric propulsion**, asserted in
  `avionics.cupr`/`propulsion.cupr` (`vin: supply(in, [10.5V,
  12.6V])`).
- **Gust load case: CS-23/MIL-HDBK-5J discrete gust, 15 m/s vertical
  at cruise**, asserted in `airframe.hema` (`WingSpar.boundary.
  gust_v`) -- a light-UAV-class conservative envelope, cited in the
  file header and in `tests/harness/test_wo70_uav_talon_discharge.py`.

## File map

| file | track | contract |
|---|---|---|
| `contracts.hema` | hematite | shared project-local mech interfaces (spar/boom/motor/battery/card mounts) |
| `airframe.hema` | hematite | wing spar (realized, optimize + feldspar beam) + boom clamp (realized, feldspar bolted joint) + fuselage/skin (contract only) |
| `avionics.cupr` | cuprite | flight-controller board port contract |
| `propulsion.cupr` | cuprite | motor/ESC `by select` motor-class choice |
| `battery.hema` | hematite | battery pack contract (bay mount) |
| `harness.cupr` | cuprite | avionics/propulsion wiring (declared runs) |
| `uav_talon.cupr` | cuprite | the top-level `system`: budgets, boundary, claims, matings |

## D183 required demonstrations (this dispatch)

1. **`regolith optimize`**: `tests/orchestrator/test_wo70_uav_talon_optimize.py`
   -- `airframe.hema`'s `WingSpar.SparCapFlat.b = in [3mm, 8mm]
   minimize` pinned via golden-section continuous optimize (winner
   near 3mm, `LockRow.cause = optimize(...)`); `propulsion.cupr`'s
   `PropulsionEsc.impl MotorClass by select(bl_2814_900kv,
   bl_3520_650kv, bl_4020_450kv)` pinned via the `ebi_decode` discrete
   recipe against the flagship's real `choice_points` payload, under a
   declared cost/mass policy.
2. **Feldspar discharging**: `tests/harness/test_wo70_uav_talon_discharge.py`
   -- `WingSpar`'s bending/deflection under the declared gust case
   (`beam_bending.BeamBendingModel`, `mech.beam.cantilever_deflection`)
   and `BoomClamp`'s bolted joint separation check
   (`bolted_joint.BoltedJointModel`, `mech.bolt.joint_separation`,
   VDI 2230), both `discharged`.
3. **Ship artifacts**: `tests/test_flagship_uav_talon_sheets.py`
   (part sheets for `WingSpar`/`BoomClamp` + the avionics harness
   block diagram, deterministic, audit-clean) and
   `tests/test_flagship_uav_talon_contract_graph.py` (the whole-machine
   contract graph, deterministic, audit-passing or honestly xfailed
   per the WO-64 layout-depth precedent).

## Walls list

The governing spec citation for each lives in ONE place (not
duplicated here): the ledger section of
`docs/workflow/work-orders/WO-70-flagship-uav.md`.

- **W1**: no composite (carbon-fiber layup) material family exists in
  `std.materials` -- `Fuselage`/`WingSkin` honestly substitute
  `AL6061_T6`.
- **W2**: CG-as-budget is inexpressible -- no location/moment-arm
  `kind=` exists in the budget-math set (D49); wing loading is
  expressed as a `require` ratio claim instead, and no CG budget is
  attempted (recorded, not invented).
- **W3**: no LiPo cell/pack record exists in `std.elec`/
  `std.materials` -- `BatteryPack` stays `impl ... = todo!`.
- **W4**: no RC servo/receiver record exists in `std.elec` --
  control-surface servos and the RC receiver are not modeled this
  dispatch; `harness.cupr` only wires the two parts that ARE declared
  (`fc`, `esc`).
- **W5** (soft, inherited from `printer_k1`): the `connect:` ->
  numeric `AssemblyDef` solve gap (`regolith-lower` emits no mate-graph
  payload from `align:` clauses yet) means no full assembly solve is
  proven this dispatch beyond the two independently realized parts.
