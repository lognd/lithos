# WO-75: flagship arm_a6 (6-DOF robot arm, built end-to-end)

Status: todo
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
