# WO-111 -- feldspar model growth: the WO-24 remainder + Class C solver half

Status: open
Language: feldspar repo (its own conventions: Rust core + Python
  pack, calibration-first); lithos side only pack-exposure wiring.
Spec: D223; feldspar WO-24 (welds, bearing life, fatigue, drive
  sizing, Roark -- the honest not-attempted remainder); feldspar
  WO-11/WO-27 precedents (signed certified discharge end-to-end);
  lithos 20-solver-abstraction.md sec. 7 (the pack contract);
  D220/D224 (no fabricated anything).

## Goal

The solver-pack physics the fleet's claims actually need exists in
feldspar, calibrated against published worked examples, exposed
through the pack contract so lithos claims discharge at certified-
capable tier.

## Deliverables

1. Weld group static strength (fillet/butt, treating the weld as a
   line -- Blodgett/Shigley cited) -- the frame corpus (cnc_router
   BaseFrame, weldment_frame) declares welded joints.
2. Bearing life depth: L10 with load-zone/application factors
   (the lithos built-in covers the basic rating life; the pack owns
   anything beyond closed-form) -- only if a fleet claim needs it;
   otherwise record not-needed.
3. Fatigue: Goodman/Gerber mean-stress + Marin-factor endurance
   estimate for steel shafts/members, stress-life, cited.
4. Drive sizing: motor/torque/inertia reflected-load checks
   (printer/cnc/arm axes declare motion claims).
5. Thermal transient: lumped-capacitance step response (the
   cycle-26 lumped_thermal built-in is steady-state).
6. Roark completion: the plate/shell cases the corpus touches
   (flat plate uniform load -- espresso/hydro panels).
7. Each model: calibration test vs a published worked example
   (source + edition + example number in the test), pack manifest
   exposure, and a lithos-side round-trip proof (one real fleet
   claim reaches it and yields a real margin) -- coordinate the
   lithos exposure commit with the coordinator.
8. Survey step 0: diff the fleet's undischarged claim kinds (after
   WO-109) against feldspar's 19+ exposed models; land what is
   needed, record what is not.

## Acceptance

- feldspar `make check` (its own gates) green; calibration tests
  pass; feldspar main pushed at green.
- At least one lithos fleet claim per landed model family
  discharges end-to-end through the pack channel (build-report
  evidence in the close-out).

## Escalation

Anything needing lithos schema/lowering changes escalates to the
coordinator (WO-112's territory). No lithos waiver edits here.
