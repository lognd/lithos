# WO-72: flagship cnc_router_r1 (CNC router, built end-to-end)

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

`examples/flagships/cnc_router_r1/`: a 600x600mm-class CNC router.
Architecture: frame + gantry (realize the plate/extrusion parts;
the gantry as a RealizedAssembly), spindle mount, motion (std.motion
leadscrews/rails/steppers), controller boundary + harness. Feldspar
surfaces REQUIRED: frame2d stiffness/deflection on the gantry beam
under a declared cutting-force case; bolted-joint checks on the
gantry joints; bearing life on the rail/leadscrew bearings
(ISO 281 over std.bearings-shaped ratings). Optimization REQUIRED:
gantry plate/beam dims minimized against the deflection claim
through the staged evaluator. CAM SELF-HOSTING REQUIRED: at least
one of its own realized plate parts carries `plan: extern(...)`
G-code verified by std.cam end-to-end (the WO-69 chain) -- the
machine's parts are checked for manufacturability on a machine
class from std.machines.

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
