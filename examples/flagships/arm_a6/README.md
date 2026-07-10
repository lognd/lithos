# arm_a6 -- flagship-5, the 6-DOF desktop robot arm

WO-75 (D183). ~600mm reach class, 300g payload class. Phase A->C in
one dispatch, mirroring WO-64's own arc: contract-first architecture,
J1-J3 realized (base yaw, the shoulder joint sub-assembly, elbow),
J4-J6 (wrist) declared at contract altitude only, optimize + select,
feldspar discharge (mixed: some live, some model-direct/deferred --
see the walls list), the motion wall hunt.

## Envelope targets (asserted givens)

- **Reach class: ~600mm** (`arm_a6.cupr`'s `boundary.reach`): base
  0mm + upper arm 300mm (`link1.hema`) + forearm 250mm (`link2.hema`)
  + wrist/tool offset 50mm = 600mm.
- **Payload class: 300g** (`arm_a6.cupr`'s `boundary.payload_mass`).
- **24V-class stepper drive, 6 axes** (`controller.cupr`'s
  `ControllerMcu`, one step/dir/en triple per joint).

## File map

| file | track | contract |
|---|---|---|
| `contracts.hema` | hematite | shared project-local mech interfaces (`JointBore`/`JointMotorMount`/`LinkFlange`/`JointReduction`/`BaseFoot`) |
| `base.hema` | hematite | `BasePlate` + `Turret`, J1 (yaw) realized, `J1YawAssembly` |
| `joint2.hema` | hematite | the REALIZED shoulder joint sub-assembly (J2): housing, retainer, motor bracket, `by select` reduction, `ShoulderJointAssembly` |
| `link1.hema` | hematite | `UpperArm` (J2 output link), elbow pivot, optimize target |
| `link2.hema` | hematite | `Forearm` (J3 output link), fixed 4x reduction, optimize target |
| `wrist.hema` | hematite | `WristBase`, J4-J6 contract-only (honest cut, WALL W3) |
| `controller.cupr` | cuprite | 6-axis stepper driver board port contract |
| `harness.cupr` | cuprite | 6 joint motor runs |
| `arm_a6.cupr` | cuprite | the top-level `system`: budgets, boundary, mates, THE MOTION WALL HUNT |

## Walls list

Each with its governing spec citation (this WO's ledger,
`docs/workflow/work-orders/WO-75-flagship-robot-arm.md`, has the full
discussion):

- **W1**: no `mech.bearing.l10_hours` harness model exists in this
  repo at all (feldspar's own WO-24 ISO 281 landed on the solver
  side; no `python/regolith/harness/models/bearing_life.py` registers
  it here). Declared as honest claim intent on J1/J2/J3
  (`base.hema`/`joint2.hema`/`link2.hema`); not discharged this
  dispatch.
- **W2**: `mech.bolt.joint_separation` has a landed model
  (`bolted_joint.py`, VDI 2230) but `regolith.orchestrator.translate`
  does not route it end to end yet (a separate wiring dispatch is
  landing the fix on another branch, per the coordinator's cycle-32
  heads-up). Discharged here via the WO-64 phase-C model-direct
  precedent: `tests/orchestrator/test_wo75_arm_a6.py::
  test_base_bolted_joint_separation_margin_model_direct`.
- **W3** (deliberate scope cut, not blocking): the wrist (J4 roll/J5
  pitch/J6 yaw) is declared at contract altitude only
  (`wrist.hema`'s `WristBase`, `impl ... = todo!`) rather than
  realized to the same depth as J1-J3 -- D183's required depth (>= 1
  realized joint sub-assembly, the motion wall hunt, feldspar +
  optimize + select) is fully met at J1-J3; the wrist axes are a
  recorded residual for a follow-up WO, not a silent gap.
- **W4** (the motion wall hunt's own quantitative payoff): at this
  flagship's own reach/payload class, J2's cheaper `by select`
  candidates (`belt_3to1`, `planetary_5to1`) do NOT clear the
  POSE_REACH static torque case; only `planetary_8to1` does
  (`arm_a6.cupr`'s `MotionWallHunt` section has the full arithmetic).
  This is exactly the reopen evidence charter `30-geometry-lowering
  .md` sec. 3's "Kinematic motion" non-goal asks a flagship to
  gather: real torque sizing needs the full travel envelope, not 3
  sampled poses.
- **W5**: J3 (elbow) is direct-drive in the WO's original framing but
  needed a FIXED 4x reduction to clear POSE_LOAD -- recorded rather
  than silently added as a second `by select` choice point (only J2's
  reduction is in-WO-scope per D183; AD-22 gaps escalate, not
  invent).
- **W6** (ship artifacts, D183 deliverable 5): NOT attempted this
  dispatch (honest-partial). `printer_k1`'s own phase-C ledger
  already establishes that no `.hema`/`.cupr` source in this repo
  reaches full CLI `ship --release` with realized geometry wired
  through yet (`tests/backends/test_ship.py`'s documented wall); a
  direct-producer sheet/contract-graph demonstration
  (`printer_k1`'s own `test_flagship_printer_sheets.py`/
  `test_flagship_printer_contract_graph.py` idiom) was scoped out of
  this dispatch for time -- left as a residual for a follow-up slice.
