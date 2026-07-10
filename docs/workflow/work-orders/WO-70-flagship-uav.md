# WO-70: flagship uav_talon (fixed-wing UAV, built end-to-end)

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

`examples/flagships/uav_talon/`: ~1.2m fixed-wing electric UAV.
Architecture: airframe (wing spar/boom/fuselage mech parts --
realize the spar/boom/ribs class parts to STEP), propulsion
(motor/ESC/prop as elec+mech contracts; `by select` over a declared
motor-class candidate list with a cost/mass policy), avionics board
boundary + harness, battery. Budgets: total mass, CG envelope
(location budget over part masses -- use the budget machinery
honestly; if CG-as-budget is inexpressible, THAT is a first-class
wall), wing loading, propulsion watts, flight-time energy. Feldspar
surfaces REQUIRED: spar bending/deflection under a declared
(basis-cited) gust load case; bolted/clamped joint check where the
boom mounts. Optimization REQUIRED: spar cap dims `in [lo, hi]
minimize` against deflection/stress feasibility; the motor select.

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
