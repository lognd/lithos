# WO-110 -- Built-in model depth + manufacturability channel (Class C, lithos half)

Status: open
Language: Python (harness/models/*, registry wiring); no schema
  bump (D225).
Spec: F130 Class C; D220 (models added, gates untouched); D223
  (split: solver-pack-shaped physics goes to feldspar/WO-111;
  closed-form checks a firm does on a pad land HERE as built-ins);
  charter 34 (removal/DFM machinery); existing model conventions
  (harness/models/ -- match bearing_life.py / beam_bending.py
  idiom: typed inputs, named deferrals, citation in docstring).

## Goal

Every Class C claim kind the fleet actually declares has a real
registered discharge channel with a citation and calibration test.
The census' "no registered model" residue shrinks to kinds that
genuinely have no closed form (those go to WO-111 or stay 2(c)
exclusions).

## Deliverables (survey first -- enumerate the fleet's undischarged
call forms after WO-109 routing, then land the set; the list below
is the known floor)

1. `manufacturable(<process>)` discharge channel: the 40 `makeable:`
   claims evaluate against realized geometry through the existing
   cam/DFM family (charter 34 packs; mill/turn/print/cut process
   envelopes): tool access, min feature vs tool, depth-to-dia,
   stock-fit -- discharging where the realized part passes, VIOLATED
   where it genuinely fails (then the DESIGN gets fixed per D224.3),
   deferring with named inputs where geometry/process data is
   absent.
2. Shaft/rotor critical speed (`crit_speed:` family) -- Rayleigh/
   Dunkerley closed form, cited.
3. Torsion + combined-stress checks for shaft claims (`twist:`) --
   cited closed forms.
4. NPSH available-vs-required check (`npsh:` fluid claims).
5. Label kind `cost`: route to the WO-54/101 costing surface --
   a cost claim compares the estimator's number against the
   declared bound (the estimate machinery exists; this is the
   claim-facing adapter).
6. Label kind `jitter` and the elec residue: adapters onto the
   existing buck/SI/link-budget model family where the call form
   matches; honest named deferral where the physics is
   board-level (goes to the 2(c) ledger).
7. Every new model: docstring citation (textbook/standard,
   editioned), calibration test against a published worked example,
   deferral tests for each missing-input branch.

## Acceptance

- Each landed model discharges (or honestly VIOLATES) at least one
  real fleet claim end-to-end at release tier, demonstrated in the
  WO close-out with build-report evidence.
- No fleet claim defers "no registered harness model" for a kind
  this WO landed.
- `make check` green; census + goldens regenerated and reviewed.

## Escalation

Physics needing real numerics (FEA, modal, fatigue spectra) is
feldspar-shaped: hand it to WO-111 in the close-out, do not
approximate it into a built-in. Schema needs escalate per D225.
