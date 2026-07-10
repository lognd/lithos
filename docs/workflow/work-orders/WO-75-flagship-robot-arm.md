# WO-75: flagship arm_a6 (6-DOF robot arm, built end-to-end)

Status: honest-partial (deliverables 1-4 demonstrated; deliverable 5
ship artifacts NOT attempted this dispatch; see ledger)
Depends: the landed cycle-30/31 toolchain (SCHEMA_VERSION 25); NO
schema bump, NO crates/ changes (AD-22: escalate gaps into the
ledger). Template: WO-64's A->C arc and ledger discipline -- read
its FULL ledger first; this WO inherits its acceptance shape.
Language: corpus authoring + records refs + tests; Python only for
test/golden enrollment.
Spec: 31-flagships.md (NORMATIVE) + design-log 2026-07-10-cycle-32
D183 (this flagship's row names its REQUIRED surfaces); AD-33/D170
(parity bar); the track guides.

## Scope highlights

`examples/flagships/arm_a6/`: a 6-DOF desktop robot arm (~600mm
reach). Architecture: links (realize the machined/printed link
parts; >= 1 joint sub-assembly as a RealizedAssembly), joints
(std.bearings + std.motion steppers/belts via records), controller
boundary + harness, payload spec. THE DELIBERATE WALL HUNT: motion
(joint envelopes, reach, collision-over-motion) is a charter-30
non-goal awaiting exactly this evidence -- author the motion-shaped
claims you WANT (reach envelope, joint torque vs payload at named
poses) and record precisely where the static toolchain stops
(pose-parameterized claims may only be expressible as per-pose
declared cases -- do that for >= 3 named poses, rung-1 basis, so
torque claims stay dischargeable). Feldspar surfaces REQUIRED:
bearing life on >= 2 joints; bolted joints at the base; link
deflection under the payload case. Optimization REQUIRED: link
section dims minimized against deflection; `by select` on the
joint-2 gearbox/belt reduction candidates.

## Acceptance shape (inherited from WO-64 + D183)

- `regolith check` clean whole-project; corpus-enrolled (the
  flagships root is already in _CORPUS_ROOTS); contract-graph sheet
  golden.
- The D183-required surfaces DEMONSTRATED: real `regolith optimize`
  runs pinning with cause+trace; the named feldspar model families
  discharging with cited evidence; ship artifacts (sheets/schedules
  as applicable) deterministic and audit-clean.
- Parity accounting measured and ledgered (attention fully
  accounted; zero report errors/waivers); every todo!/wall recorded
  per-site with spec citations.
- `make check` green; Status flipped to done-or-honest-partial with
  the full ledger.

## Ledger (this dispatch, 2026-07-10)

`examples/flagships/arm_a6/` (9 corpus files + `README.md`):
`contracts.hema`, `base.hema` (J1 yaw realized, `J1YawAssembly`),
`joint2.hema` (J2 shoulder realized, `ShoulderJointAssembly` -- THE
required RealizedAssembly), `link1.hema`/`link2.hema` (upper
arm/forearm, J3 elbow, both carrying an `in [lo,hi] minimize` section
dim), `wrist.hema` (J4-J6, contract-only), `controller.cupr`,
`harness.cupr`, `arm_a6.cupr` (the top-level system + THE MOTION WALL
HUNT). `regolith check` over the whole project: `build ok=True`, zero
errors (only lint-tier `L0801`/`E0443` warnings, the same classes
`printer_k1` already carries). Corpus-enrolled via the existing
`_CORPUS_ROOTS` flagships entry (`tests/test_corpus_clean.py`, no
change needed).

**Demonstrations** (`tests/orchestrator/test_wo75_arm_a6.py`, 7
tests, all passing):
- Deliverable 1 (>= 1 joint sub-assembly realized): `joint2.hema`'s
  `ShoulderJointAssembly` (4 parts: housing, retainer, motor_bracket,
  upper_arm) solves with no loop residual, STEP-exports
  deterministically, mass = sum of parts -- the WO-64
  `test_wo64_xy_gantry_assembly.py` idiom (hand-declared `AssemblyDef`
  mirroring the source; `regolith-lower` still emits no numeric
  mate-graph payload from `connect:`/`align:`, unchanged since WO-64).
- Deliverable 3 (feldspar): base bolted joint
  (`mech.bolt.joint_separation`) discharged via
  `BoltedJointModel.estimate()` directly (WO-64 phase-C model-direct
  precedent) -- WALL W2 below. Bearing life (`mech.bearing.l10_hours`)
  on J1/J2/J3 is declared as honest claim intent in the corpus but NOT
  discharged -- WALL W1 below (no harness model exists at all). Link
  deflection under the payload case (`mech.deflection`, a LANDED,
  live-wired model -- confirmed by `printer_k1.xy_gantry.hema`'s own
  clean check) discharges for real through `regolith check` itself on
  both `link1.hema`/`link2.hema`.
- Deliverable 4 (optimize + select): `link1.hema`'s
  `UpperArmSection.b` and `link2.hema`'s `ForearmSection.b`
  (continuous `in [lo,hi] minimize`) both pin via
  `optimize_continuous_golden_section` at their lower bound (mass-
  monotonic, matching WO-64's own `bed.hema`/`xy_gantry.hema`
  recipe); `joint2.hema`'s `MotorBracket.JointReduction by
  select(belt_3to1, planetary_5to1, planetary_8to1)` pins via
  `optimize_discrete` under a torque-feasibility-aware cost table
  (only `planetary_8to1` clears POSE_REACH -- see W4).
- Deliverable 2 (THE MOTION WALL HUNT, charter
  `30-geometry-lowering.md` sec. 3's "Kinematic motion" non-goal
  reopen evidence): `arm_a6.cupr`'s `require MotionWallHunt` section,
  3 named poses (POSE_HOME, POSE_REACH, POSE_LOAD) as declared rung-1
  cases, per-pose joint moment literals with static lever-arm
  arithmetic shown in-line, each checked against the joint's
  motor-class holding torque times its reduction. Recorded, per
  claim, precisely where a real kinematics layer takes over: (a)
  sweeping the FULL travel envelope (not 3 samples) needs a
  continuous joint-angle parameter + a Jacobian-based torque model;
  (b) dynamic/inertial torque needs a rigid-body dynamics model this
  repo does not have; (c) reach-envelope collision-over-motion needs
  swept-volume geometry, not the nominal placed-assembly solve WO-62
  landed. This is the D183-mandated reopen-evidence gathering, not a
  simulation attempt.

**Walls** (full discussion + citations in `README.md`'s own walls
list; summarized here):
- **W1**: no `mech.bearing.l10_hours` harness model exists in this
  repo at all (feldspar's own WO-24 ISO 281 landed solver-side only).
  Declared as honest intent on J1/J2/J3; not discharged.
- **W2**: `mech.bolt.joint_separation` has a landed model
  (`bolted_joint.py`) but no `translate.py` routing yet (a separate
  wiring dispatch is landing the fix on another branch, per the
  coordinator's cycle-32 heads-up). Discharged model-direct instead
  (see deliverable 3 above).
- **W3** (deliberate cut, not blocking): the wrist (J4-J6) is
  contract-only (`wrist.hema`, `= todo!`) -- D183's required depth is
  fully met at J1-J3; the wrist is a residual for a follow-up WO.
- **W4** (the wall hunt's own quantitative payoff): at this
  flagship's declared reach/payload class, only the most capable `by
  select` candidate (`planetary_8to1`) clears POSE_REACH's static
  torque -- the cheaper candidates this same file declares do not.
  Exactly the reopen evidence charter 30 asks for.
- **W5**: J3 needed a FIXED 4x reduction (not a second `by select`
  choice point, AD-22 in-scope surfaces only) to clear POSE_LOAD.
- **W6** (ship artifacts, deliverable 5): NOT attempted this
  dispatch -- `printer_k1`'s own phase-C ledger already establishes
  no `.hema`/`.cupr` source in this repo reaches full CLI `ship
  --release` with realized geometry wired through yet; a
  direct-producer sheet/contract-graph demonstration
  (`printer_k1`'s `test_flagship_printer_sheets.py`/
  `test_flagship_printer_contract_graph.py` idiom) is scoped out for
  time -- a residual for a follow-up slice, not silently dropped.
- **W7** (parity accounting): NOT run this dispatch (time budget) --
  `regolith ship --explain`'s attention-list/parity report over
  `arm_a6` is a residual, same shape as W6.
- **Process note**: `make check`'s FULL suite (fmt, clippy, the
  whole Rust + Python test matrix) was NOT run this dispatch (time
  budget) -- only `regolith.compiler.check` over the new corpus (build
  ok=True, no errors), `tests/test_corpus_clean.py -k arm_a6`, and the
  new `tests/orchestrator/test_wo75_arm_a6.py` (7/7 passing) were
  verified. No `crates/` or schema changes were made, so the scope of
  what could regress is narrow (new corpus + one new test file), but
  this is recorded honestly rather than asserted clean.
