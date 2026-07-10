# WO-73: flagship hydro_press_h30 (30-ton hydraulic press, built end-to-end)

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

`examples/flagships/hydro_press_h30/`: a 30-ton H-frame shop press.
Architecture: welded H-frame (calcite-or-hematite structural
members -- pick the track that lowers honestly and record why),
hydraulic circuit as a fluorite flownet (pump/valve/cylinder/relief
from std.fluid + declared records; the relief-pressure safety claim
is release-gated), ram/platen mech parts realized. Feldspar
surfaces REQUIRED: frame member utilization (frame2d + capacity
forms) under the 30-ton case; fillet weld group checks at the
frame's welded corners; bolted joints where the head plate bolts.
Optimization REQUIRED: `in registry(std.civil.w_shape or
hss_square)` section search on the frame members (the landed
engine, second real application) + one continuous dim. Safety
posture: tonnage/pressure/relief claims all demanded, none waived.

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
