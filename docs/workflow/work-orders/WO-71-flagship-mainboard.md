# WO-71: flagship mainboard_mx (ATX-class board, built end-to-end)

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

`examples/flagships/mainboard_mx/`: an ATX-class controller
mainboard (SoM-carrier posture is acceptable if it keeps the elec
chain honest). Architecture: multi-rail power tree (12V->5V->3.3V/
1.8V/1.1V) with per-rail current budgets and droop claims;
`by select` on at least two regulator stages (stdlib + declared
candidates); EBI/decode reuse; connectors from std.elec; costing
with a BOM-bearing profile. Drive the elec chain as far as the
LANDED realizers go (netlist/BlockRequirement; the KiCad
RealizedLayout tier where it runs) and record the layout-scale
walls honestly. Feldspar surfaces REQUIRED: lumped thermal
transient (VRM thermal claim) + any landed elec-adjacent model that
applies; name what does not exist. Optimization REQUIRED: the
regulator selects with a cost objective; one continuous dim
(e.g. copper pour/trace class via a declared discrete or bounded
slot) if the landed surface carries it -- else record the wall.

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
