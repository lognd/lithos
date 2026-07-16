# WO-156 -- timing closure v1: grounding `budget kind=timing` (D264)

Status: open (Depends: WO-145 [processors first slice -- the
  `Cited`/`CitedInterval`/`MeasCondition` models this WO's timing
  fields are authored under, and the `ti.mcu` MSP430FR5 family whose
  datasheet t_pd/t_su/t_h/t_co values are this WO's first real
  timing data] AND WO-155 [the sim gate -- a sibling, not a
  prerequisite in the data-flow sense, but D264 ruling 7 sequences
  this WO after both: after WO-145 for the citation carrier, after
  WO-155 because both gates share the E11xx code space and the
  INV-<N> ledger entry WO-154 drafted, and serializing avoids two
  agents touching the same invariant text concurrently]; the D256
  hash window MUST have merged)
Language: records (TOML, timing fields on logic/MCU record classes)
  + Rust (`regolith-lower` budget closure over the new contribution
  sources -- if the closure math needs new Rust beyond what
  `crates/regolith-ir/src/budget.rs:46`/`crates/regolith-lower/src/
  contracts.rs:9-12` already provide) + Python (`std.timing` harness
  model, calc-book timing table).
Spec: D264 rulings 2/6 (timing is a SIBLING gate, not a lookalike of
  functional sim -- verilator is explicitly NOT a timing source;
  `setup_slack`/`corners(all)` stay deferred per WO-154's ratified
  reopen criterion, v1 scopes to contribution-sum budgets the
  grammar already parses); `scratch_recon_cuprite_sim_gate.md` sec.
  4b (the two timing-data seams this WO implements: part records via
  WO-145's citation carrier, and routes via the WO-34 extraction
  seam + stackup Dk-derived v_p), sec. 4a second half (the budget-
  closure design: sum-of-interval contributions vs limit at the
  declared clock period, the tolerance-chain math shape
  `docs/spec/cuprite/04-structural-layer.md:246-249` already names);
  D257 (`Cited`/`CitedInterval`/`MeasCondition` models, WO-145's
  deliverable -- t_pd/t_su/t_h/t_co/f_max rows on `ti.mcu` records,
  each under a citation; this WO is the FIRST consumer proving the
  carrier is fit for a real closure, not just storage); charter 35
  rule 2 (the pre-layout-allocated / post-layout-re-discharged
  pattern for a budget, established for impedance -- this WO applies
  the SAME pattern to timing, not a new one) and charter 35's
  stackup `Dk` record field (the propagation-velocity source);
  `docs/spec/cuprite/04-structural-layer.md` sec. 5 (`budget <name>
  kind=timing:` container, already parses via
  `crates/regolith-syntax/src/parser.rs:257`; `close_budget`,
  `crates/regolith-ir/src/budget.rs:46`, already closes over literal
  declared contributions -- this WO's job is GROUNDING the
  contributions, not building the container); `E0432`
  (`crates/regolith-lower/src/contracts.rs:9-12`, the existing
  budget-cannot-close diagnostic, worst-contributor naming --
  REUSED verbatim as the timing-closure failure, no new diagnostic
  family per D264 ruling nothing-new-here); WO-154's ratified
  INV-<N> ledger entry (this WO discharges the (a)/(c) legs for the
  TIMING half specifically -- the sim half is WO-155/157's).

## Goal

A `budget <name> kind=timing:` closes for real against cited
datasheet timing values (part records, post-WO-145) and/or extracted
route lengths converted to propagation delay via a cited stackup
`v_p`, at a single worst-case corner, through the existing E0432
failure path -- with a calc-book timing-closure table rendering
every contribution's citation, sum, limit, slack, and verdict through
the one renderer.

## Deliverables

1. Timing fields on `ti.mcu` (and any other WO-145-landed) logic/MCU
   records: t_pd/t_su/t_h/t_co/f_max as `CitedInterval` values (per
   WO-145's shape: datasheet MIN/TYP/MAX with citation + a named
   `MeasCondition`), added under the SAME package (`stdlib/ti.mcu/`)
   WO-145 created -- this WO does not invent a new record home, it
   extends the one WO-145 landed. If WO-145's landed record family
   does not yet carry these fields, add them as a follow-on to that
   package with the SAME citation discipline (no uncited value).
2. `std.timing` harness model (Python): closes a `budget kind=timing`
   at the declared clock period (or interface window) by summing
   interval contributions (record-cited values + route-derived
   delays) against the limit, taking the PESSIMAL end of each cited
   interval (v1's single worst-case corner, per the reopen-criterion
   deferral WO-154 recorded) -- the same closed-form arithmetic
   `close_budget` already applies to literal declared contributions,
   now fed by grounded values instead of hand-typed numbers.
3. Route contribution: RealizedLayout-extracted trace lengths
   (already carried for `bus_length_match`, per
   `docs/spec/cuprite/04-structural-layer.md:193-196`) convert to
   delay via a cited propagation-velocity figure derived from the
   STACKUP record's `Dk` field (charter 35's `std.elec.stackups`),
   using the formula charter 35 already establishes for Dk-derived
   quantities. Pre-layout, the route's contribution is its budget-
   ALLOCATED share (the existing `allocate:` machinery); post-layout,
   the same budget re-discharges over the extracted length -- the
   exact pre/post-layout re-discharge pattern charter 35 rule 2
   established for impedance, applied here without modification to
   that pattern's shape.
4. E0432 wiring end to end for the timing case: a budget that cannot
   close names its worst contributors (existing `budget.rs:46`
   behavior) using the now-real cited/extracted contributions rather
   than literals.
5. Calc-book timing-closure table (through the ONE renderer, AD-7/
   charter 41; the SI sheet is the direct precedent per
   `docs/spec/toolchain/35-signal-integrity.md` rule 5): path/budget
   name, each contribution with its citation (record page or
   extracted length + v_p formula), sum, limit, slack, verdict.
6. WO-154's INV-<N> proof argument, timing half: this WO's close-out
   states explicitly which of legs (a)/(c) it discharges for timing
   subjects (a clocked subject with no timing budget is a named
   absence -- though the TOTALITY sweep proving zero silent rows is
   WO-157's; this WO proves the per-budget grounding leg, (a)-shaped:
   every closed timing budget's evidence traces to a citation or an
   extracted length, never a bare literal).
7. Tests: a `std.timing` unit test closes a budget over
   `ti.mcu`-cited t_pd/t_su values at a stated clock period and
   verifies the slack/verdict arithmetic; a route-derived contribution
   test verifies the Dk-to-v_p-to-delay conversion against a hand-
   computed value; an E0432 negative fixture proves a budget that
   cannot close names the right worst contributor; a rendering test
   proves the timing table appears on the calc book with citations
   visible.

## Out of scope

- `setup_slack(...)`/`corners(all)` language surface -- named
  deferral, reopen criterion already recorded by WO-154; this WO
  scopes strictly to contribution-sum budgets at a single worst-case
  corner.
- Deriving timing facts from simulation -- explicitly NOT a source
  (verilator is functional/untimed); this WO's two sources are part
  records and routes, full stop.
- The functional sim gate itself -- WO-155/157, a sibling.
- Fleet corpus adoption (declaring real timing budgets for
  riscv_hart_rv1 etc., burning waiver rows) -- WO-157.
- Any second manufacturer package beyond what WO-145 landed.
- The coverage-sweep TOTALITY proof (zero silent absent-timing rows
  across the fleet) -- WO-157's enforcing change; this WO proves the
  grounding leg only.

## Acceptance

- `uv run pytest tests -k std_timing -q` green: budget closure over
  cited `ti.mcu` values, route-derived delay conversion, E0432
  negative fixture, calc-book rendering test.
- A grep/test proves every timing contribution in the new tests
  traces to a `Cited`/`CitedInterval` value or an extracted-length +
  cited `v_p` -- no bare literal contribution in the new test
  fixtures (mirrors WO-145's "uncited value unrepresentable" bar,
  applied at the consumer).
- The calc-book timing table's rendering test asserts citations are
  visible in the rendered output (not just present in the underlying
  model) -- a reviewer-checkable snapshot or field assertion.
- `docs/spec/regolith/13-invariants.md`'s INV-<N> entry (WO-154's
  draft) is updated in this WO's close-out to record which proof
  legs this WO discharges for the timing half, in the SAME change as
  the code (house law: new guarantees need a proof argument in the
  same change).
- `make check` green.

## Escalation

If the stackup `Dk`-to-`v_p` formula charter 35 establishes does not
already cover the frequency range or dielectric type a real timing
budget needs, escalate to the coordinator (a new closed-form
derivation is a spec decision, not an implementation-time
invention) rather than approximating silently.
