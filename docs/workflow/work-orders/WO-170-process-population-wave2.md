# WO-170 -- process population wave 2: PCB fab/assembly + perf-board + elec-install (D269 item 4)

Status: open (Depends: WO-168 [process record schema]; WO-169 need
  not be done first -- the two waves are independent data
  populations, both depending only on the schema)
Language: data (TOML/stdlib records), same convention as WO-169.
Spec: D269 item 4 (population order: "...then PCB assembly, then the
  long tail" -- this WO is that second step); process-research
  dossiers `procres/pcb.md` (PCB fab, SMT assembly, through-hole/wave
  solder, conformal coating, perf-board hand assembly) and `procres/
  elec_install.md` (branch-circuit practice, panel/service practice,
  conduit/raceway practice -- flagged in the rollup as a DIFFERENT
  COST-MODEL CATEGORY, design-practice not fabrication; keep that
  distinction in the record's own framing, do not force it into a
  fabrication-cost-driver shape it does not fit).

## Goal

Populate `std.process` records + DFM check-sets for: PCB fab, SMT
assembly, through-hole/wave solder, conformal coating, perf-board
hand assembly (WO-165's consumer), and the three elec-install
practice families (branch-circuit, panel/service, conduit/raceway --
WO-167's consumer).

## Deliverables

1. One `ProcessRecord` + `DfmCheckSet` per named process, citing the
   matching `procres/pcb.md`/`procres/elec_install.md` dossier entry.
   `elec_install`'s three entries note in the rollup that they are
   NOT merely spot-verified this pass but independently pre-existing
   LANDED work (std.power's WO-134/134B NEC/Eaton citations) --
   reuse those existing citations directly rather than re-sourcing;
   this wave's job for elec-install is to shape the ALREADY-CITED
   data into the `ProcessRecord`/`DfmCheckSet` contract, not to
   re-research it.
2. Perf-board hand-assembly record feeds WO-165's stub DFM check
   (WO-165 deliverable 5) with a real value.
3. PCB fab/assembly records feed the existing (already substantially
   real, per the recon dossier) KiCad two-tier realizer's DFM
   checking, if it does not already have a `std.process`-shaped
   record -- check first whether PCB DFM today (`harness/models/dfm/
   checks.py`) already sources its constants from a citable place; if
   so, this WO's job is to WRAP that existing sourced data into the
   new contract shape (WO-168), not duplicate it (NO DUPLICATION
   principle).

## Non-goals

- No new elec-install catalog content beyond what std.power already
  landed (same D250 sec. 3 gate WO-167 names).
- No long-tail families (WO-171).

## Acceptance

- Records exist for all six named process families, `provenance`
  populated honestly per each dossier entry's real posture.
- WO-165's perf-board capability registration and any existing PCB
  DFM check both reference these records (grep-checkable: no
  duplicate hard-coded constant remains alongside the new record for
  the same value).
- `make check` green.
</content>
