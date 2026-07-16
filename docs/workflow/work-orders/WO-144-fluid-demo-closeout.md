# WO-144 -- fluid demo close-out: small_office waiver burn-down + demo pack (D258.5/F152/F157)

Status: open (Depends: WO-140, WO-141 [lithos half], WO-143 for the
  full dp/balance/npsh/Moody story; the regime/fill half of this WO
  additionally gates on the F157 claim-shape slice -- `TODO.md:170-174`,
  a pre-existing seed this WO does NOT re-propose or implement, only
  consumes if it has landed by this WO's dispatch time. If F157 has
  not landed, ship the dp/balance/npsh burn-down and name the
  regime/fill claims as a residual gated on F157, per the F152
  honesty bar -- do not fake the gate.)
Language: corpus authoring (fluorite fixture) + demo script + fleet
  census update. No toolchain changes -- gaps found here are
  FINDINGS, same discipline as WO-137.
Spec: D258 ruling 5 (the demo story: "size a building's hydronic
  heating loop and hand the reviewer a calc book" -- small_office
  discharges dp/balance/npsh for real, its calc sheet carries a Moody
  chart with the operating point plotted; fallback if the bridge
  slips is espresso brew-line dp with derived f); F152 (the honesty
  bar: a waiver count reduction is only real if every REMAINING
  waiver's basis is still true -- do not silently narrow a waiver's
  scope to make the count look better); F157 (the claim-shape slice
  the regime/fill half depends on); the demo-11/16/17 PROOF.md
  precedent (`demos/out/demo11_board_gerbers/PROOF.md`,
  `demos/out/demo16_doctor_config/PROOF.md`,
  `demos/out/demo17_physical_bringup_pack/PROOF.md`) -- this WO's
  demo run is committed the same way.

## Goal

`examples/flagships/small_office/hydronics.fluo`'s five currently-
waived claims (margin dp, flow balance, NPSH, regime, fill/settle;
lines 47-79) convert to real model-backed discharges wherever the
cycle-37 fluids stack (WO-138..143) makes that possible, and the
fleet gets a committed, provable demo run showing the before/after.

## Deliverables

1. Burn down small_office hydronics waivers:
   - dp (margin): discharges via WO-139 (derived friction factor)
     + WO-140 (component/fitting losses) + WO-138 (egw_60_40
     density/viscosity).
   - flow balance / mdot: discharges via WO-141's lithos-side pack
     bridge (feldspar Hardy-Cross), or names the exact residual if
     the bridge is not fully closed at this WO's dispatch time.
   - NPSH: discharges via the WO-138 pump-curve/NPSHr record + IF97
     pv(T) chain.
   - regime / fill(settle): discharge ONLY if F157 has landed by
     this WO's dispatch; otherwise recorded as a named residual
     gated on F157, per the Depends line above.
2. A demo script (extend `demos/demo15_calc_audit.py` or add a new
   `demo18_fluid_demo.py`, coordinator's call at dispatch time)
   running `regolith build --release` then `regolith ship` on
   small_office, walking the calc book to the dp sheet and its Moody
   figure (WO-143).
3. A committed demo run under `demos/out/<name>/` with a `PROOF.md`
   matching the demo-11/16/17 shape (what drove this, the discharge
   chain, before/after waiver table, provenance hashes).
4. Fleet census update: the waiver-count delta for small_office
   recorded honestly (F152) -- every REMAINING waiver (if any) still
   states its true basis, not a narrowed restatement designed to
   look smaller.
5. Fallback path (if WO-141's bridge has slipped at dispatch time):
   ship the espresso brew-line dp + NPSH story instead (derived f +
   Moody sheet only, from WO-138/139/143), and say explicitly in the
   close-out that this is the fallback, not the primary story.

## Out of scope

- Any new fluid record, model, or pack wiring -- this WO consumes
  WO-138..143's landed work, it does not add new physics.
- Re-implementing or re-scoping F157 -- if it has not landed, the
  regime/fill claims are a named residual, full stop.
- Any change to the small_office building/power corpus outside the
  fluorite hydronics fixture.

## Acceptance

- `regolith build --release examples/flagships/small_office` green,
  with the dp/balance/npsh claims (at minimum) showing model-backed
  discharge, not a memo waiver: `regolith ship --explain
  examples/flagships/small_office` shows a reduced waiver count
  against the pre-WO-144 baseline.
- Every waiver that REMAINS after this WO still names a true,
  currently-accurate basis -- checkable by diffing the waiver text
  before/after and confirming no waiver was narrowed without a
  matching capability landing (the F152 test).
- The Moody figure (WO-143) appears on the small_office dp calc
  sheet (or the espresso fallback's dp calc sheet) in the shipped
  output.
- A demo run is committed under `demos/out/<name>/` with a `PROOF.md`
  present, following the demo-11/16/17 structure (checkable: `ls
  demos/out/<name>/PROOF.md demos/out/<name>/manifest.json`).
- `make check` and `make health` green at the updated fleet census.
- The close-out states explicitly whether the regime/fill claims
  discharged (F157 landed) or remain a named residual (F157 not yet
  landed) -- one or the other, stated plainly, never left ambiguous.

## Escalation

If small_office's supply-riser chain still cannot close after
WO-138..143 land (an unforeseen gap none of those WOs covered),
that is a FINDING (F-WO144-n), not a silent scope cut -- ledger it
and fall back to the espresso demo per D258 ruling 5's named
fallback.
