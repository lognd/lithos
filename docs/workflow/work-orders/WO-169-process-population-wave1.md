# WO-169 -- process population wave 1: EDM + heat-treat + stamping + grinding + shot-peen (D269 item 4)

Status: open (Depends: WO-168 [process record schema])
Language: data (TOML/stdlib records) + Python (any record-loader
  glue, following the existing `stdlib/std.*/records/` + `magnetite.
  toml` package convention -- mirror `std.materials`/`std.fasteners`/
  `std.tooling`'s existing layout exactly, do not invent a new
  package layout).
Spec: `docs/workflow/design-log/2026-07-19-cycle-38.md` D269 item 4
  (population order: EDM + heat-treat + stamping first -- the
  die-set program's consumers); the process-research dossiers
  (session scratchpad `procres/heat_treatment.md`, `procres/
  subtractive.md` sec. wire-EDM/sinker-EDM/grinding entries,
  `procres/sheet.md` sec. stamping/press-brake entries, `procres/
  surface.md` sec. shot-peening entry) -- THE reference pack; every
  record this WO adds must trace to a specific dossier entry, cited
  the same way the dossier itself cites (do not re-derive numbers
  from memory when a dossier entry already did the sourcing work).

## Goal

Populate `std.process` records + DFM check-sets (WO-168's schema) for
the five families D268's die-set program (WO-166) consumes: wire EDM,
heat treatment (anneal, normalize, quench+temper, case-harden,
nitride, stress-relieve, induction-harden, austemper/martemper,
solution-treat-age), stamping/press-brake, grinding, and shot-peening
(the recast-layer remediation step WO-166 slice c names as optional).

## Deliverables

1. One `ProcessRecord` + `DfmCheckSet` per named process
   (enumerate: wire_edm, sinker_edm if the dossier's entry is cheap
   to include alongside wire_edm -- name explicitly if deferred;
   anneal, normalize, quench_temper, case_harden, nitride,
   stress_relieve, induction_harden, austemper_martemper,
   solution_treat_age; press_brake_bend, stamping/blanking; grinding;
   shot_peening), each with `provenance` populated per the actual
   dossier finding for that entry -- the rollup's own count says this
   family is disproportionately `pd_gov`-anchored (MIL-H-6875 for the
   heat-treat entries specifically): USE that real anchor where the
   dossier names it, do not downgrade a real citation to `gek` out of
   caution, and do not upgrade a `gek` entry to look cited.
2. Punch-die clearance and AGMA/ISO-class table needs: NAMED REFUSAL
   per the dossier's own finding (Machinery's Handbook/ASM Sheet Metal
   Forming Handbook class tables) -- the record still lands, with the
   specific clearance-percent-of-thickness figure either cited to a
   real public-domain source if the dossier found one, or refused by
   name with a note on what a future owner-sourced update would need.
3. DFM checks consumed by WO-166: at minimum, a real (non-stub)
   "punch-die clearance within process envelope" check and a
   "press-tonnage within process envelope" check, wired to real
   `ProcessRecord.size_limits`/`cost_drivers` fields, not invented
   constants.
4. Capability registration update: WO-166's die-set `RealizerCapability`
   (once it exists) points its `process_records`/`dfm_checks` at
   these real records instead of stubs.

## Non-goals

- No population beyond the five named families (PCB/perf-board is
  WO-170; the long tail is WO-171).
- No re-deriving of dossier numbers -- if a needed value is not in
  the dossier, that is a named gap for this WO's close-out, not a
  license to estimate.

## Acceptance

- `stdlib/std.process/records/` (or wherever WO-168's convention
  lands) contains one file per named process, each with `provenance`
  set and a citation matching a real dossier entry (grep-checkable:
  each record's citation string appears in the corresponding
  `procres/*.md` dossier file).
- WO-166's die-set capability registration (once WO-166 lands) passes
  WO-164's refusal rule using THESE records, not stubs.
- `make check` green.
</content>
