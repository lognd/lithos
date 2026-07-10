# WO-74: flagship timber_pavilion (civil pavilion, built end-to-end)

Status: honest-partial (2026-07-10 dispatch; full ledger below)
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

## Ledger (this dispatch, 2026-07-10)

### Checklist

- [x] `examples/flagships/timber_pavilion/{site,program,frame}.calx`
      authored (calcite structure/program/frame split).
- [x] `magnetite.toml` + `README.md`.
- [x] `regolith check` clean whole-project (`obligations=6,
      diagnostics=0`).
- [x] Corpus-enrolled: `tests/golden/test_golden_corpus.py` (T0
      check-tier golden) and `tests/golden/test_deferral_corpus.py`
      (translate-tier deferral golden), both generated and green.
- [x] Feldspar surfaces DEMONSTRATED: `civil.utilization` AND
      `mech.deflection` discharge with real evidence
      (`beam_utilization_interaction`/`beam_simple_span_deflection_
      udl`) over G1, via `orchestrate.build` at `BuildTier.BUILD`
      (`tests/orchestrator/test_wo74_pavilion_frame.py`).
- [x] Optimization DEMONSTRATED: G1 and G2 each run an independent
      `in registry(std.civil.timber_sawn)` section search
      (`search_free_section`/`optimize_discrete`), each producing a
      `frame_lock_rows` entry with `cause: optimize(mass_per_length,
      trace=blake3:...)` -- the WO-74 ">= 2 member groups" ask, over
      the REAL (mid-dispatch-widened, 11-candidate) family, mass
      tie-breaker disclosed in the trace.
- [ ] Ship artifacts (plan/section sheets, member schedule,
      `civil_takeoff` cost estimate) -- NOT REALIZED this dispatch.
      `python/regolith/orchestrator/costing.py`'s `cost_civil_
      takeoff` estimator (WO-54) is landed and unit-tested
      (`tests/harness/test_cost_estimators.py`) but wiring it to this
      flagship's `[profiles.cost.construction]` end to end, plus a
      civil plan/section sheet backend analogous to
      `tests/test_flagship_printer_sheets.py`'s mech part-sheet
      pattern, was not attempted -- ran out of budget after the
      frame-chain wall-hunting below consumed the bulk of this
      dispatch. Recorded as the honest residual, not forced.
- [x] Parity/walls: every wall below cites its repro + spec section.
- [x] `make check` green (1228 passed, 4 skipped, 24 xfailed;
      graphite's own 21 passed).
- [x] Status flipped (honest-partial, this ledger).

### Walls (escalated live via SendMessage to the coordinator; also
recorded here per the ledger-wall discipline)

1. **Cross-file `grid`/`level` zero-length** (found first, refined
   twice). The landed frame lowering computed `length: 0` for a
   member whose `grid`/`level` declarations lived in a DIFFERENT file
   than the `member from (...) to (...)` consuming them --
   reproduced against the LANDED `examples/systems/small_office`
   corpus too (same split, not a WO-74 authoring bug), and NOT about
   multi-axis grids (a monolithic single-file repro with a two-axis
   grid computed correct nonzero lengths). Workaround shipped this
   dispatch: `grid`/`level` co-located in `frame.calx`, `site.calx`
   kept to `site: boundary/soil` truth only. **Coordinator ack
   (2026-07-10, later in this dispatch): the real fix landed on
   master** (project-wide grid/level position table, build-tier
   tripwire added) -- the co-located shape was KEPT rather than
   reworked back to the split shape, per the coordinator's explicit
   "do not rework finished goldens for aesthetics" instruction; the
   split-file shape is legal again for any FOLLOW-UP flagship.
2. **Two-axis row/column grid unverified.** Because of wall 1, this
   frame models ONE representative 3m bay (single grid axis) rather
   than the full two-axis (`frames` x `width`) plan -- the same "one
   frame line shown, repeats per grid line" scoping `pole_barn.calx`
   already establishes as precedent. Now that wall 1 has a real fix
   on master, a follow-up could restore the full two-axis plan and
   re-verify; not done here (budget).
3. **`kN/m` direct `on [...]` loads silently vanish.** `member_udl_
   demand`'s direct-load loop recognizes only already-linear units;
   every real corpus `on [...]` load is `kPa`-only. A `kN/m` `on
   [...]` line parses (`check` stays `diagnostics=0`) but is simply
   ABSENT from the lowered `FramePayload.loads` array downstream --
   verified by instrumenting `frame_resolve._length_m`/`member_udl_
   demand` and diffing the lowered payload with and without the
   line. Not fixed (crates/regolith-lower territory, AD-22
   escalation); documented in `frame.calx`'s header and worked around
   by keeping the purlin `role: slab`/fixed-section/pressure-only
   (footbridge's `Deck` shape), never `role: beam` with a bare
   line-load demand.
4. **A `column` has no resolvable demand in the landed harness**
   (axial demand pinned at 0, WO-48 deliverable 5 scope) --
   `resolve_member` requires a `member_udl_demand` hit (direct load
   OR resolvable `Bearing` tributary) before EVEN a section search
   can run, regardless of claim form. Posts stay fixed-section; a
   two-candidate post search was tried and abandoned (trivially
   "feasible" for both candidates, no real gate, not a useful
   demonstration) in favor of two REAL, demand-gated girder searches.
5. **`civil.utilization(<Structure>.members.all, ...)` cannot
   discharge once ANY member of the structure lacks a resolvable
   demand** (walls 3+4 mean the purlin and posts always lack one) --
   no real corpus example was found that discharges this aggregate
   form over a mixed-role membership; `frame.calx` uses the OTHER
   form `translate.py` supports, a per-member subject
   (`civil.utilization(G1, under=combo)` /
   `civil.utilization(G2, under=combo)`), an honest narrowing to the
   two members that DO resolve a real demand.
6. **`civil.embedment` is not a registered claim form** at all in
   `translate.py` (only `civil.utilization`, `mech.deflection`,
   `civil.story_drift`, `civil.bearing_pressure`, `mech.first_mode`
   are recognized) -- `pole_barn.calx`'s `frost: civil.embedment(...)`
   line is track/aspirational content, never landed. Omitted from
   `require Structure` rather than authored as an unrecognized claim.
   Coordinator ack: queued as a cycle-33 design item, not WO-74's to
   fix.
7. **`std.civil.timber_sawn` was a 2-candidate family** at dispatch
   start (thin section-search domain); widened to 11 dressed sawn
   sizes mid-dispatch by a separate agent (coordinator ack). This
   flagship's goldens/tests were generated/re-run AFTER the widening
   landed, over the real 11-candidate domain (G1/G2 both currently
   win `sawn_38x235`, subject to change if the family widens further
   -- the tests assert only that a real winner from the real family
   landed, not a pinned size, to avoid a golden bump on every
   toolchain-side registry change).

### Parity / measured accounting

- `regolith check examples/flagships/timber_pavilion`:
  `diagnostics=0, obligations=6, resolutions=0` -- clean.
- `orchestrate.build(..., BuildTier.BUILD, frame_record_paths=
  ("stdlib",))`: 6 obligations total -- 2 discharged (`civil.
  utilization` on G1, `mech.deflection` on G1; G2's own utilization
  obligation similarly discharges, see the test), 2
  `conformance_windows_unresolved` (WO-12 cut, unrelated to this
  flagship), 1 `no_frame_model` (`civil.bearing_pressure`, WO-48
  deliverable 5 scope), 0 fabricated/silent passes. No report
  errors, no waivers.
- Ship-artifact parity (sheets/schedule/takeoff) is UNMEASURED --
  the residual above; the WO-74 acceptance shape's "zero report
  errors/waivers" bar is met for everything that WAS attempted.

### Per-site disposition summary

| site | disposition |
|---|---|
| structure (grids/levels/members/transfers/loads) | DONE, real |
| feldspar discharge (utilization/deflection) | DONE, real, over G1 (G2 mirrors) |
| section search (>= 2 groups, mass tie-breaker) | DONE, real, G1+G2 over the widened 11-candidate family |
| circulation/egress | DONE (`civil.travel_distance` claim authored; check-clean) |
| ship artifacts (sheets/schedule/civil_takeoff) | NOT DONE -- honest residual, follow-up WO scope |
| civil.embedment/frost | OMITTED -- unregistered claim form, cycle-33 design item |
| two-axis grid plan | DEFERRED to a follow-up (wall 1's fix now landed; wall 2 no longer forced, just not re-attempted) |
