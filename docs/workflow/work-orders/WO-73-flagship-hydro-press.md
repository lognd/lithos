# WO-73: flagship hydro_press_h30 (30-ton hydraulic press, built end-to-end)

Status: honest-partial (phase-A architecture + one real
section-search discharge landed this dispatch; feldspar weld/bolt
discharge verification, ram/platen realization, the continuous-dim
optimize, and ship/parity artifacts are residuals -- see ledger
below; D183's own sanctioned "out-of-budget agent closes
honest-partial and a continuation slice re-dispatches" posture)
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

## Ledger (this dispatch, 2026-07-10)

### Track choice: calcite for frame members, hematite for welds/bolts

Investigated before writing a line: `frame2d`/`section: free`/
`std.civil` names do not exist ANYWHERE in `docs/spec/hematite/`
(grepped clean) -- section search (`in registry(std.civil.w_shape)`,
the landed `optimize_discrete` engine, footbridge G1's real discharge,
WO-65 ledger) is calcite-only. `mech.weld_stress`/`FilletWeld`/
`mech.bolt.separation_margin` (the landed cnc_router/frame.hema and
dune_buggy/engine_top_end.hema precedents) have no calcite-side
equivalent -- calcite's declarative `member`/`civil.utilization` form
carries no weld/bolt-joint primitive. NO single track carries both
WO-73-required feldspar surfaces on one file. Sent as a coordinator
message mid-dispatch (missing-capability report) and recorded here as
wall W1. Resolution: `frame.calx` (calcite) carries the H-frame
MEMBERS (`Col_L`/`Col_R`: `std.civil.hss_square`; `Head`/`Base`:
`std.civil.w_shape`) sized by real section search; `corners.hema`
(hematite) carries the welded corner gussets and the head-plate
bolted joint as a small, separately-realized sub-assembly.

### D183 surface 1: frame member utilization + section search -- REAL, PROVEN

`frame.calx`'s `Head` member (`section: in registry(std.civil.
w_shape)`) resolves through the LANDED WO-65 engine end to end:
`tests/orchestrator/test_hydro_press_frame_resolve.py::
test_hydro_press_head_section_flips_to_a_real_discharged_verdict`
drives the real corpus file through `orchestrator.orchestrate.build`
(not a synthetic fixture, the footbridge-precedent recipe) and
asserts `Frame.Head.section = Head=w8x10`, `cause=optimize(
mass_per_length, trace=blake3:...)` -- winner + cause + trace in the
lockfile, exactly the WO's acceptance line. The load path: the ram's
266.9kN rated force enters as a bearing PRESSURE on a `RamPad` slab
member (26690kPa over a 0.01m2 contact pad, footbridge Deck's own
`Bearing(tributary=...)` idiom) rather than a direct point/line load
on `Head` -- see wall W4 below for why that path does not exist.

`Col_L`/`Col_R`/`Base` do NOT resolve this dispatch: `Base`'s own
reaction only arrives through the `Moment()` column transfers, which
`resolve_tributary_demand` does not walk (no Bearing transfer names
it) -- it defers `frame_load_untargeted`, proven honestly (not
fabricated) by `test_hydro_press_base_section_defers_honestly`.
`Col_L`/`Col_R` were not driven through the same probe this dispatch
(budget cut, not attempted) -- the SAME wall (no load path reaches
them via a Bearing transfer either) almost certainly applies; record
as a residual, do not assume a verdict either way.

`civil.bearing_pressure(F_L/F_R)` claims defer `no_frame_model`
(WO-48 deliverable 5's own documented pre-existing gap -- the same
residual footbridge/small_office/bus_shelter/pole_barn all carry,
verified by grep against `tests/orchestrator/test_frame_resolve.py`
sec. "no_frame_model"), not a new wall.

**W4 (new).** No landed path resolves a directly-targeted load on a
BEAM member at all: `crates/regolith-lower/src/frame_lower.rs::
load_entries` classifies a load's `LoadKind` as `Distributed` only
when its unit ends in `Pa`, but `python/regolith/orchestrator/
frame_resolve.py::member_udl_demand`'s DIRECT-load loop only accepts
`N/m`/`kN/m` (`_LINE_TO_N_PER_M`) for a directly-targeted load, and
`kind != "distributed"` short-circuits it regardless. No unit
satisfies both sides of that split -- a beam can only ever receive
resolvable demand through a `Bearing(tributary=...)` transfer from a
`kPa`-loaded source member (a footbridge Deck-shaped slab), never
directly. Not a schema/crates change (AD-22): worked around honestly
per-file with the `RamPad` slab + `Bearing` transfer above, same
idiom every calcite flagship already uses; recorded here as an
authoring-ergonomics/resolver-completeness gap for a future WO
(a `LoadKind::Point` variant already exists at the Rust/schema level,
`frame_lower.rs`'s own `else` branch, but NO python resolver code
path ever consumes it -- dead schema capability, not exercised
anywhere in the landed corpus either).

### D183 surface 2: fluorite hydraulic flownet -- AUTHORED, check-clean, NOT harness-verified

`hydraulics.fluo`'s `PressCircuit` (`Pump`/`CheckValve`/relief+
directional `Valve`/`Pipe` ram edge) parses and passes `regolith
check` clean (part of the whole-flagship 7-warning set, all in the
documented E0443/L0803/L0801-from-clause families). `require
Capacity.rated`, `require Safety.relief_holds`/`hammer` are DEMANDED,
none `waive`d anywhere in this flagship (grepped: zero `waive`/
`assume!` sites in the whole `hydro_press_h30/` tree). NOT run
through the harness this dispatch to confirm an actual discharge
verdict (vs. an indeterminate/deferred one) -- `fluorite`'s own
README already documents "lowering to obligations and solving remain
WO-32" as the track's general state; whether `PressCircuit`'s claims
concretely discharge or defer was not probed with the same rigor as
`frame.calx`'s section search. Residual: run the fluid-net harness
probe (mirroring this ledger's `frame_resolve` recipe) and record
discharged/deferred per claim.

### D183 surface 3: feldspar weld-group + bolted-joint discharge -- AUTHORED, NOT VERIFIED (wall)

`corners.hema`'s `CornerGusset.require Structural.weld_static`
(`mech.weld_stress` under `FilletWeld`) and `HeadPlate.require
Structural.clamp` (`mech.bolt.separation_margin`) are real, landed-
vocabulary claims (mirrors the cnc_router/frame.hema and dune_buggy/
engine_top_end.hema precedents exactly) and the file is `regolith
check`-clean. A quick `orchestrator.orchestrate.build` probe this
dispatch (BUILD tier, no frame/cost record paths) showed every
obligation deferring `unresolved_limit`/`unsupported_op` rather than
discharging -- NOT yet root-caused (budget cut): could be a real
missing model-registry entry for `mech.weld_stress`/`mech.bolt.
separation_margin` at this trust tier, or an authoring mistake in
this file's `trust:`/`require` block shape that a closer read of
`docs/spec/hematite/03-contracts-and-assemblies.md`'s `trust:`
grammar would resolve. Recorded as an open wall, NOT claimed as
"feldspar discharging" -- the WO's own acceptance line asks for
discharge WITH cited evidence, which this dispatch did not produce.
Continuation slice: root-cause the two deferrals, then add a
`test_hydro_press_corners_discharge.py` mirroring this ledger's frame
test.

### Residuals (not attempted this dispatch, budget cut)

- **Ram/platen realization.** `ram_platen.hema` stays phase-A
  contract-only (every `impl` is `= todo!`, printer_k1's own phase-A
  posture) -- geometry realization (the `Ram`/`Platen` parts actually
  cutting/machining) was not attempted.
- **One continuous dim optimized.** Not demonstrated this dispatch
  (WO-73 acceptance line 4). Candidate: `RamPad`'s tributary contact-
  pad dimension, or a `Col_L`/`Col_R` wall-thickness `in [lo, hi]
  minimize` continuous domain, once the load-path wall (W4) is closed
  for the columns too.
- **Ship artifacts (sheets + contract-graph, audit-clean).** The
  contract-graph sheet IS proven this dispatch (`tests/
  test_flagship_hydro_press_contract_graph.py`, mirroring printer
  k1's own recipe: non-trivial, deterministic, valid ASCII SVG,
  passing). Sheets/schedules and a full `ship --explain` audit-clean
  parity run were NOT attempted.
- **Parity accounting.** Not measured/ledgered this dispatch (WO-73
  acceptance line 3). A continuation slice should run the same
  `ship --explain` parity recipe WO-64's own ledger used.
- **`Col_L`/`Col_R` section-search verdicts.** Not probed (see D183
  surface 1 above) -- likely the same W4 wall, not confirmed.

### Fixed this dispatch (not a residual)

`ram_platen.hema` originally cited `AISI_4140_QT` and `AISI_1045`,
neither a real `std.materials` key (`tests/magnetite/test_stdlib.py::
test_corpus_bare_materials_resolve_against_std_materials` caught it
-- phantom material references). Corrected to `AISI_4140` (the
landed, non-QT record) and `S355` (already used elsewhere in this
flagship); both resolve, test green.

### What IS proven, concretely (do not re-litigate these)

- `regolith check` clean over `examples/flagships/hydro_press_h30/`
  (7 warnings, all in the documented E0443/L0803/L0801-from-clause
  families; `tests/test_corpus_clean.py -k flagships` passes).
- `Head`'s section search discharges for real: winner `w8x10`,
  `cause=optimize(mass_per_length, trace=blake3:...)`, proven by
  `tests/orchestrator/test_hydro_press_frame_resolve.py` (2 tests,
  both green) -- the WO's "second real section-search application."
- The contract-graph sheet renders, is deterministic, and is valid
  ASCII SVG (`tests/test_flagship_hydro_press_contract_graph.py`, 3
  tests, all green).
- Zero waivers anywhere in the flagship; the tonnage/pressure/relief
  claims are demanded, not waived (WO's own "none waived" line).

`make check` GREEN at close-out (full gate: fmt-check, lint,
typecheck, guard-core, schema-check, Rust tests, 1179 Python tests
passed / 4 skipped / 24 xfailed, 21 graphite tests passed) -- run
after the phantom-material fix above; the run before it caught that
exact defect, which is the gate doing its job.
