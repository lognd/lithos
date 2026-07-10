# WO-71: flagship mainboard_mx (ATX-class board, built end-to-end)

Status: honest-partial (phase A+ elec chain built; real optimize,
real KiCad-outline tier, and the feldspar lumped-thermal VRM
discharge all demonstrated; netlist-tier circuit bodies and
board-layout-at-scale recorded as honest cuts/walls, not forced --
full ledger below)
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

## Ledger (this dispatch)

**Done.** `examples/flagships/mainboard_mx/` -- 5 sources
(`magnetite.toml`, `README.md`, `power_tree.cupr`, `mcu.cupr`,
`connectors.cupr`, `mainboard_mx.cupr` -- 6 files, 5 real sources +
manifest). `regolith check` over the whole flagship: 0 errors, 3
`todo!`-honest-deferral warnings (`Rail1V8`, `Rail1V1` in
`power_tree.cupr`; `BoardOutline` in `mcu.cupr`) -- matches the
declared-deferred-artifact count exactly, zero unexpected diagnostics,
zero waivers. `regolith fmt` is byte-idempotent on every file (its
"rewrote" log line fires unconditionally; verified via md5sum
before/after a second pass -- no content change). `examples/flagships`
was already in `tests/test_corpus_clean.py`'s `_CORPUS_ROOTS` (WO-64
D1); `mainboard_mx` rides the same clean-check gate with no test
change needed (`test_corpus_root_has_no_unexpected_warnings[examples/flagships]`
passes).

- Architecture (`power_tree.cupr`): `Rail5V`/`Rail3V3`/`Rail1V8`/
  `Rail1V1`, one `block` per rail (`buck_converter.cupr`'s `Buck`
  shape), each with `require Regulation` (ripple/transient) and a new
  `require Droop` claim (sag mask on load step) -- the per-rail droop
  budget this WO asked for. `Rail5V`/`Rail3V3` are `by select` over
  three named candidates each (D161 shape, `ebi_decode.cupr`
  precedent: candidate refs are diagnostics-only labels, no vendor
  declaration required at this tier). `Rail1V8`/`Rail1V1` are
  contract-only (`todo!`) -- not part of the select demonstration,
  honestly deferred.
- `mcu.cupr`: `MainboardMcu` board, `SomCarrier` port contract (EBI/
  PCIe/USB port families), `impl AddressDecodeGlue by select(nor_glue,
  cpld, mcu_chip_selects)` carried over VERBATIM from
  `examples/tracks/cuprite/ebi_decode.cupr` per the WO's explicit
  instruction to reuse it.
- `connectors.cupr`: `PowerInConn`, one `by circuit` realization with
  a single vendor part (`molex_8981`) -- the "connectors from
  std.elec" scope item; kept minimal (one connector, not a full
  harness) given the dispatch budget.
- `mainboard_mx.cupr`: top-level `system MainboardMx`, wires the tree
  end to end (`require Tree`: each rail's `vin` = its parent's `out`,
  closing 12V -> 5V -> {3.3V, 1.8V, 1.1V}), `budget wall_power` (locked
  per-rail watts that SUM to the 130W ceiling), two per-rail
  `budget rail_current_*` (D183 demonstration 1), `budget bom_cost`
  against `profiles.cost.prototype` (D183 demonstration 5), and the
  `policy: minimize mfg.cost(all)` line the optimize test's declared
  cost table reads.

**D183 demonstration 1 (multi-rail power tree, droop, budgets close):
DONE.** `power_tree.cupr` + `mainboard_mx.cupr` as above; `regolith
check` confirms the tree's `require Tree` equalities and both budgets
close with 0 diagnostics.

**D183 demonstration 2 (`by select` on >= 2 regulator stages, pinned
via real `regolith optimize`): DONE.**
`tests/test_wo71_mainboard_selects.py` (template:
`tests/test_wo56_ebi_decode.py`) drives the FULL D168 chain for real:
`regolith.compiler.check` over the real `.cupr` source ->
`BuildPayload.choice_points` (confirmed both `Rail5V.Rail5V` and
`Rail3V3.Rail3V3` land as real `ChoicePoint`s with their exact declared
candidate sets) -> `domains_from_choice_points` ->
`optimize_discrete` -> `winner_lock_row` (INV-21 `cause:
optimize(cost, trace=...)` pin). Both stages pass a policy-flip test
(reversing the declared cost table flips the winner) -- 5/5 tests
pass. `MainboardMcu.AddressDecodeGlue`'s select (carried from
`ebi_decode.cupr`) is a third real choice point in the same payload,
not separately re-tested (already covered by WO-56's own test against
the identical shape).

**D183 demonstration 3 (elec chain as far as the landed realizers go):
DONE, further than expected -- recorded honestly.** The
BlockRequirement/netlist tier is not exercised by this dispatch (no
`impl ... by circuit` body was written for the rail blocks -- they are
`by select`, which is diagnostics-only at L1/L2 and produces no
netlist to lower; `PowerInConn`'s one `by circuit` body is the only
netlist-bearing artifact and is too small to be a meaningful
BlockRequirement demonstration on its own). WALL: a netlist-bearing
regulator circuit body (mirroring `buck_converter.cupr`'s `impl Buck
by circuit`) was in scope but cut for dispatch-budget reasons; the
`by select` diagnostics-only shape was prioritized per the WO's own
"select on >= 2 stages" wording. The KiCad RealizedLayout tier DOES
run in this environment: `real_kicad_available()` returns `True`
(`kicad-cli` on PATH, `pcbnew` importable via `make install`'s
`kicad-link`, verified after a fresh `git merge master` + `make
install`), and `tests/realizer/elec/test_kicad_real.py`'s 4
`-m kicad` tests pass live (not skipped) -- a real `pcbnew.BOARD` is
built, saved, and DRC'd clean, and round-trips through
`RealizedLayout`/`PayloadStore`. This is the SAME generic realizer
`printer_k1`/WO-24 already exercise (board-outline-agnostic); no new
mainboard-specific KiCad test was needed or added. No board-outline
geometry for `mainboard_mx.MainboardMcu.outline` was fed through it in
this dispatch (the `BoardOutline` impl is still `todo!`) -- feeding a
real outline through the real layout tier for THIS flagship
specifically is the natural continuation slice.

**D183 demonstration 4 (feldspar lumped thermal transient discharging
a VRM thermal claim): DEMONSTRATED-WITH-NOTE (upgraded mid-dispatch
from a wall).** The wall below was real when hit and was escalated
immediately; the coordinator confirmed the lumped-thermal-transient
tier then MERGED on feldspar main during this dispatch (feldspar
WO-24 dispatch 5: namespace `heat.transient`, directions
`step_temperature` / `time_to_threshold` /
`duty_cycle_peak_temperature`, caller-asserted Biot rejected >= 0.1).
`tests/test_wo71_mainboard_vrm_thermal.py` now discharges the VRM
claim MODEL-DIRECT (the coordinator-sanctioned route): the board's
declared numbers -- P = 3.0W (`Rail5V`'s `dissipation <= 3.0W`
promise, power_tree.cupr), T_amb = 45degC (`MainboardMx` boundary
upper corner, mainboard_mx.cupr), asserted VRM givens R_th = 20 K/W,
C_th = 5 J/K, t_on/t_off = 10s/20s, Bi = 0.05 -- fed into
`heat.transient.duty_cycle_peak_temperature` yield T_peak ~= 67 degC
against the 125 degC junction class limit: verdict discharged, ~58 K
margin, cross-checked against the direction's own documented closed
form, plus the memo's duty->1 limiting case (105 degC, still under
the limit) and a Bi = 0.5 rejection proving the gate. Module skips
when `feldspar` is not installed (same posture as
`tests/packs/test_feldspar_conformance.py`); it was installed
non-editable and run for real in this dispatch (3/3 pass). NOTE
(the "-with-note"): the lithos-side claim FORM
(`thermo.junction_temperature_transient` /
`thermo.junction_temperature_duty_cycle`, parallel to the landed
steady `thermo.junction_temperature` in
`regolith.harness.models.lumped_thermal`) is not yet wired, so no
`.cupr` claim names this discharge -- wiring that claim form and
routing it through the pack is the recorded continuation slice.
Original wall record kept verbatim below for history: feldspar
main (READ-ONLY, checked out at `../feldspar`) has NO landed lumped-
thermal-transient solver: `feldspar/python/feldspar/library/heat.py`'s
own module docstring states the WO-20 close-out explicitly CUT
"transient lumped/Heisler, natural convection, boiling/condensation,
radiation networks, LMTD/effectiveness-NTU heat exchangers" -- only
1-D steady conduction/convection resistance networks and Dittus-
Boelter forced convection landed. The one electrically-isomorphic
landed model (`feldspar.elec.solver`'s `elec.ngspice.rc_step`
direction, WO-17: a real `.tran` ngspice deck, `elec.rc.vf/
resistance/capacitance/time -> elec.rc.vc`, which is the standard
V<->T, R<->R_th, C<->C_th thermal-RC analogy and WOULD discharge a
VRM thermal claim under that analogy) requires the `ngspice` binary,
which is ABSENT in this dispatch's environment (`which ngspice` exits
1 -> `ToolMissing`, the documented fail-closed path
`tests/unit/test_elec_ngspice.py` already covers on the feldspar side).
Both routes are genuinely unavailable here, not merely unused: the
dedicated solver does not exist upstream, and the isomorphic one lacks
its tool. Spec citations: WO-20 close-out cut note (feldspar-side);
this WO's own instruction to "name what does not exist rather than
forcing" (WO-71 body, D183 row). No VRM thermal claim was written into
`power_tree.cupr` since nothing in the landed toolchain could discharge
it honestly.

**D183 demonstration 5 (costing, BOM-bearing profile): DONE.**
`magnetite.toml`'s `profiles.cost.prototype`
(`quantity`/`labor`/`pricing`/`markup`, D147 shape) +
`mainboard_mx.cupr`'s `budget bom_cost: ... require: mfg.cost(all,
profile=prototype) <= 220USD`. `regolith build
examples/flagships/mainboard_mx` (real build, not a synthetic
harness) logs `costing: context loaded (profiles=['prototype'],
default=prototype, cli=None, as_of=2026-07-10)` -- the landed
estimator surface genuinely reads the profile. All 31 obligations
land `deferred`/`no matching model` (honest: this flagship's rail
blocks are `by select`/`todo!`, not `by circuit` bodies with resolved
component BOMs) -- `discharged=0 unresolved=31`, `build: clean`,
matching WO-64's own contract-first-tier expectation (nothing forced).

**D183 demonstration 6 (ship artifacts, elec_blocks + contract-graph,
deterministic, audit-clean): PARTIAL, contract-graph done, elec_blocks
not attempted.** `tests/test_flagship_mainboard_contract_graph.py`
(template: `tests/test_flagship_printer_contract_graph.py`) drives the
real `regolith check` payload's `ContractGraphPayload` through the
WO-61 producer: deterministic across two runs (byte-identical model +
SVG), ASCII-valid SVG, one symbol per node / one polyline set per edge,
readable (non-hash) names, drafting-audit pass-or-honest-xfail -- 6/6
tests pass. The node count is genuinely small (1 node, `BoardOutline`)
because this is a pure-cuprite flagship with only one declared
interface -- recorded as a scope note in the test itself, not a bug
(printer_k1's larger graph comes from its mixed hematite/cuprite
interface set). An `elec_blocks` diagram (WO-71 body doesn't name it
explicitly but D183's exhibit list mentions it as a possible ship
artifact) was NOT attempted this dispatch -- cut for budget, a
continuation-slice candidate.

## Parity accounting

Every value in `power_tree.cupr`/`mcu.cupr`/`connectors.cupr`/
`mainboard_mx.cupr` is either a literal envelope-target given (README,
each cited to its exact file position, AD-33 discipline) or a
declared spec/require claim -- no derived numbers that lack a stated
basis. `todo!` count = 3, matching the L0803 warning count exactly
(the same invariant WO-64's ledger checks). Zero `waive` statements.
Zero unexpected diagnostics beyond the two documented families
(honest-deferral + the pre-existing generic-exception L0801 false
positive already carved out project-wide). The one attention-list item
NOT literal-sourced is the `MainboardMcu` port list's `params:
ebi_rate` domain (`[10MHz, 100MHz]`), which is impl-chosen per
`ControllerMcu`'s own precedent in `printer_k1/controller.cupr` --
consistent with that flagship's existing parity treatment, not a new
gap.

## Escalation round-trip

The feldspar lumped-thermal-transient gap (WO-20 close-out cut) was
escalated to the dispatching conversation the moment it was
confirmed (AD-22 discipline: gaps escalate, never get forced
through). The escalation WORKED mid-dispatch: the tier merged on
feldspar main (feldspar WO-24 dispatch 5) and demonstration 4 was
upgraded from wall to demonstrated-with-note above -- the walls-
drive-toolchain-growth loop F111 describes, observed live.

## Continuation-slice candidates (not done, explicitly cut)

1. A netlist-bearing `impl ... by circuit` body for at least one rail
   (e.g. `Rail5V`), to exercise the BlockRequirement/netlist tier this
   dispatch skipped in favor of the `by select` shape.
2. Feed `MainboardMcu.outline`'s real geometry through
   `run_real_layout` (the tier is proven live; only this flagship's
   own outline was not yet piped through it).
3. Wire the lithos-side transient thermal claim form
   (`thermo.junction_temperature_transient` /
   `thermo.junction_temperature_duty_cycle`, parallel to the landed
   steady `thermo.junction_temperature` in
   `regolith.harness.models.lumped_thermal`) so a `.cupr` claim in
   `power_tree.cupr` routes through the pack to the now-landed
   feldspar `heat.transient` directions (demonstration 4's note).
4. An `elec_blocks` ship diagram alongside the contract-graph sheet.
5. `Rail1V8`/`Rail1V1` circuit realization (currently `todo!`).
