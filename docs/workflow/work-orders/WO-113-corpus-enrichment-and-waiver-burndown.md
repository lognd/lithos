# WO-113 -- Corpus data enrichment + waiver burn-down (Class D, fleet-wide)

Status: open
Language: corpus authoring (.hema/.cupr/.fluo/.calx + std.*
  records + memos); Python only for census tooling if needed.
Spec: D224 (the three authoring rules -- provenance, same-change
  burn-down, honest failures fix the DESIGN); D220 (terminal waiver
  classes); D216 (trust floors met or author-revised, never
  waived around); gates: WO-109/110/111/112 landed (the discharge
  channels must exist before inputs are worth declaring).

## Goal

Every claim whose model now exists and whose inputs a real
engineering drawing would carry gets those inputs DECLARED with
provenance, discharges for real, and loses its waiver in the same
change. The fleet census flips from 45/929 discharged/waived toward
majority-discharged, with the remaining waivers all in D220.2's
closed classes.

## Deliverables

1. Fleet-wide inputs pass, project by project (worked in dependency
   order: the seven zero-discharge projects first -- arm_a6,
   dune_buggy, mainboard_mx, printer_k1, reaction_wheel,
   regen_engine, uav_talon): declare the named missing inputs
   (bearing ratings from manufacturer tables as std.* records;
   loads/speeds/duty derived from already-declared design data
   with in-file derivations; datasheet citations otherwise).
   The arm_a6 `mech.bearing.l10_hours` set (c_rating, p_exponent,
   p_load, speed_rpm) is the type specimen.
2. Same-change burn-down: each real discharge deletes its waive
   block and regenerates the project memo; stale-waiver listings in
   ship output must be ZERO at the end (the gate lists them --
   an unmatched waiver left behind is debt, and the health
   consistency leg already checks memo/waiver integrity).
3. D224.3 design fixes: where real inputs yield VIOLATED, fix the
   DESIGN (resize, re-spec, pick the real part) with the rationale
   recorded in-file; every such fix is enumerated in the close-out.
4. Trust-floor pass per D216: floors met at tier where a certified
   channel exists; author-revised (per-claim, recorded rationale)
   where aspirational; NEVER memo-waived around.
5. Final: fleet evidence refresh (release build reports), census +
   goldens regenerated, per-project before/after discharge counts
   in the close-out ledger.

## Acceptance

- Zero projects discharge zero obligations.
- Every remaining waiver fleet-wide sits in a D220.2 class, and
  the close-out proves it by enumeration (the WO-117 census golden
  encodes it permanently).
- No fabricated values: spot-checkable provenance on every added
  datum; `make check` + fleet ship green.

## Escalation

A claim that cannot discharge because of a MODEL or MACHINERY gap
discovered here (not inputs) goes back to the coordinator as a
named residual -- never silently re-waived without a 2(c) F-number.
This WO is large: the coordinator may dispatch it in per-project
slices; each slice follows this file.

## RESUME (session checkpoint, worktree wo113-enrichment-campaign)

Commit 1 of the campaign landed: `cc7fe3f fix(cnc_router_r1): declare
Burin's real machine record, burn down stale Spoilboard waiver
(WO-113 F132.1)`. The mandatory first item (F132.1) is DONE: Burin's
own machine record (derived from machine.hema's declared axis
travels, D224.1(b)) replaces the WO-72 300x200mm placeholder in
records/cam.toml; the Spoilboard's stock is trimmed 830x530->830x520mm
(D224.3 design fix -- the honest Y-axis overhang the real machine
record exposed); the stale `makeable` waiver is deleted; the memo,
calc-book/audit goldens, and the cnc_router_r1 row of
tests/golden/data/fleet_census.json are regenerated and verified
(`regolith build --release`: release_ok=True, 0 violated, discharged
10->11; `pytest tests/golden -k cnc_router`: 8 passed).

NOT YET STARTED (everything else in the campaign order): arm_a6 (the
type specimen -- mech.bearing.l10_hours needs c_rating/p_exponent/
p_load/speed_rpm; add real SKF/NSK 6002/6004-class dynamic rating
records), then printer_k1, uav_talon, reaction_wheel, regen_engine,
dune_buggy, mainboard_mx (the seven zero-discharge projects); then
riscv_hart_rv1, sdr_transceiver, cubesat, espresso_machine,
hydro_press_h30, cnc_router_r1 (its REMAINING non-Spoilboard
deferrals -- the machine-level `makeable: manufacturable(all)` waiver
and the other named F126.1 label-kind gaps are Class B/C, out of
D224 scope, do not touch), small_office, timber_pavilion. Also
outstanding: the WO109-F3 six shadowing waivers (mainboard refclk x3,
riscv x3 -- delete + memo regen only, no new data needed since those
claims already discharge); cost profiles ([profiles.cost.*], 16
claims) against std.cost fixture-tier rates; the three fluid records
(water/glycol/coolant) per D224 provenance (only if genuinely
citable -- else stays deferred); the D216 trust-floor pass.

Working notes for the next agent: `regolith build <project> --release`
(from the worktree root, `.venv/bin/regolith`) is the fast per-project
check; regenerate per-project calc goldens with
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_calc_corpus.py -k
<project>`, then hand-patch that project's row in
tests/golden/data/fleet_census.json (discharged/accepted_deviation
counts) since that census golden is NOT auto-regenerated by the same
env var -- read the calc-book log line
(`regolith.backends.calc: calc book: <project> -- N discharged, M
accepted, ...`) for the correct numbers, then rerun
`pytest tests/golden -k <project>` to confirm green before committing.
Fleet-wide census/goldens get their FULL regen+review pass at the very
end (WO-113 deliverable 5 / WO-117), not per-project. After any Rust
change or fresh worktree session, `make install` then reinstall
feldspar (`uv pip install -e /home/logan/projects/feldspar --python
.venv/bin/python`) before any build.
