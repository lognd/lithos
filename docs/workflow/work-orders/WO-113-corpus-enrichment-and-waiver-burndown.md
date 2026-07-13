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
