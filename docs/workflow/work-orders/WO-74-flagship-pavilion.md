# WO-74: flagship timber_pavilion (civil pavilion, built end-to-end)

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

`examples/flagships/timber_pavilion/`: a 6x9m timber pavilion
(.calx, the calcite flagship). Architecture: grids/levels, post+
girder+purlin frame over `std.civil.timber_sawn` (loads DECLARED
with basis per D183 -- snow/wind derivation models are a recorded
residual; rung-1 assertions with source-position basis keep every
demand targetable), envelope (roof), circulation/egress discipline
checks as landed. Feldspar surfaces REQUIRED: frame2d +
utilization/deflection discharge over the declared loads (the
tributary path where Bearing transfers apply -- declare them).
Optimization REQUIRED: `in registry(std.civil.timber_sawn)` section
search on >= 2 member groups with the mass tie-breaker disclosed.
Artifacts REQUIRED: plan/section sheets + member schedule +
civil_takeoff cost estimate (the landed WO-50/54 civil legs),
audit-clean, golden-enrolled.

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
