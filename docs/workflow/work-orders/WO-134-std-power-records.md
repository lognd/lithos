# WO-134 -- std.power records: apparatus, conductors, devices (charter 43; D250.1)

Status: done (dispatch 2026-07-15; conductors + grounding + motor
code-letter landed, cited to NEC/NEMA article+edition; transformers/
protective-devices/motor-catalog/busway REFUSED per D250 sec. 3 --
see close-out below)
Language: records (TOML) + the stdlib generation framework (WO-66).
Spec: charter 43 secs. 2-3 + 5 (NORMATIVE -- sec. 5 is the safety
  honesty law and it governs every row you write); AD-37 + charter 39
  (stdlib organization: transcribed catalog data is CITED
  community-tier records -- this WO is squarely that home); D224/D250
  (provenance: real datasheet/standard, conservative values, or an
  HONEST REFUSAL -- never a fabricated number); WO-66 (the generation
  framework + drift check); WO-45 (std.* package conventions).

## Goal

The catalog an engineer needs to size a factory's power system:
transformers, conductors with real ampacity tables, protective
devices with real ratings, motors, busway -- every row cited, every
absence honest.

## Deliverables

1. `std.power` package (charter 39's taxonomy; dotted ids).
2. Conductors: NEC 310.16-class ampacity tables (copper/aluminum, 60/
   75/90 C, per size), with temperature-correction and conduit-fill
   derating factors as data (NEC 310.15). CITE the article and
   edition on every table.
3. Transformers: real catalog families (kVA, primary/secondary,
   %Z, X/R, vector group, taps, losses, mass, footprint -- the MASS
   and FOOTPRINT matter: WO-136 sites them on a calcite slab).
4. Protective devices: breakers/fuses with frame, trip, interrupting
   rating (AIC), and a curve reference. If a real trip curve is not
   obtainable offline, the curve is an HONEST ABSENCE (the device
   still carries its ratings) -- coordination then defers by name
   rather than being computed against a fabricated curve.
5. Motors: HP/kW, code letter (locked-rotor kVA/HP), service factor,
   PF, efficiency -- real NEMA/IEC catalog values.
6. Busway; grounding conductors/electrodes.
7. Drift check + de-phantoming test (the WO-66 pattern): a record
   that cites nothing FAILS.

## Acceptance

- Every record cites a real standard/datasheet with edition; the
  citation check fails an uncited row.
- Recorded REFUSALS for anything not verifiable offline (the
  cycle-35 Ulka-pump precedent -- an honest gap beats a plausible
  invention, and in this domain a plausible invention is lethal).
- `make check` green; stdlib organization sweeps green (charter 39).

## Escalation

Anything you cannot verify offline is a refusal, recorded in the
close-out with what would be needed to obtain it. Do not
interpolate, do not "typical". D250 is not negotiable.

## Close-out (dispatch 2026-07-15)

**Landed, `std.power` package (`stdlib/std.power/`), 6 record
families, 89 rows, all `tier=community`, all cited to article +
edition:**

1. `conductor_ampacity` (34 rows) -- NEC (NFPA 70) 2023 Edition,
   Table 310.16: copper 14 AWG-500 kcmil and aluminum 12 AWG-500
   kcmil, 60/75/90 C columns.
2. `temp_correction_factor` (13 rows) -- Table 310.15(B)(1), 21-85 C
   ambient bands; cells the table itself does not tabulate (60C
   column above 55C ambient, 75C column above 70C) are left ABSENT
   on those rows with a note, not filled in.
3. `conduit_fill_adjustment` (6 rows) -- Table 310.15(C)(1),
   4-6/7-9/10-20/21-30/31-40/41+ current-carrying-conductor bands.
4. `grounding_electrode_conductor` (7 rows) -- Table 250.66.
5. `equipment_grounding_conductor` (14 rows) -- Table 250.122.
6. `motor_locked_rotor_code` (19 rows, A-V, no I/O/Q) -- ANSI/NEMA
   MG 1-2016 (Revised 2018) sec. 10.37.2, the NEC 430.7(B) nameplate
   code-letter classification (a defined range, not a measured
   "typical" value, so citable at this precision).

**REFUSALS (D250 sec. 3 -- named absence, not a fabricated number;
what would unblock each is stated):**

- **Transformers** (deliverable 3): could not land a real catalog
  family's kVA/primary-secondary/%Z/X-R/vector-group/taps/losses/
  mass/footprint row set to the D250 bar this session. Web fetches
  against Eaton's dry-type transformer design-guide PDFs
  (`eaton-dtdt-general-purpose-design-guide-dg009001en.pdf` and the
  Volume 2 commercial-distribution catalog) timed out / exceeded
  fetch size limits before a per-model impedance/mass/footprint
  table could be extracted and cross-checked. NEEDED: successful
  retrieval (or a locally cached copy) of a manufacturer nameplate
  table (Eaton, Square D/Schneider, or ABB dry-type distribution
  transformer catalog) with per-kVA %Z, X/R, and mass/footprint
  columns, verified row-by-row before transcription -- the
  cycle-35 Ulka-pump discipline, not skipped, just not reached this
  session.
- **Protective devices** (deliverable 4): breaker/fuse frame+trip+
  AIC+curve rows refused. Partial fragments were retrieved (Square D
  PowerPact H/J/L frame ampacity ceilings 150/250/600 A; Q-frame
  10/25 kA at 240 V from search snippets) but were NOT independently
  cross-checked against the primary catalog PDF (fetch failed the
  same way as the transformer PDF) to the confidence this domain
  requires, so no row was written from them. NEEDED: the primary
  PowerPact/QO catalog PDF (or an equivalent breaker-family
  datasheet) fetched and read in full, frame-by-frame, with AIC
  ratings cross-checked against at least two independent listings
  before transcription; trip curves specifically are expected to
  stay a NAMED ABSENCE per the WO body even once ratings land (no
  curve was found in a form this session could verify offline).
- **Motors, HP/kW/PF/efficiency/service-factor by catalog model**
  (deliverable 5, the per-motor half): refused. The NEMA MG 1
  locked-rotor CODE-LETTER classification landed (it is a defined
  standard range, not a measured figure), but individual motor
  nameplate rows (a specific HP/kW at a specific frame with real PF/
  efficiency/service-factor) need a manufacturer nameplate or NEMA
  Premium efficiency table this session did not retrieve and verify.
  NEEDED: a real manufacturer motor catalog (Baldor/ABB/WEG NEMA
  frame line) or NEMA MG 1 Table 12-11/12-12 efficiency table,
  fetched and cross-checked row by row.
- **Busway** (deliverable 6, the busway half; grounding conductors
  landed per above): refused entirely -- no busway ampacity/bracing
  catalog table was retrieved this session to any confidence.
  NEEDED: a real busway manufacturer catalog (Square D I-Line,
  Eaton Pow-R-Way) with per-frame ampacity and short-circuit
  bracing/withstand ratings.

**Verification:** `uv run pytest tests/magnetite/test_stdlib.py -q`
-- 65 passed (loader round-trips, tier honesty, de-phantoming,
dependency closure). `uv run python -m tools.stdlib.organization
--check prefix|one_family|citations` -- all PASS, 0 new issues from
`std.power` (prefix reservation clean; one-family-per-file clean,
each `std.power` record file declares exactly one `[[table]]` key;
citations clean, every row's `evidence.reference` present and
non-empty). `make check` run at close (see commit log for the
foreground gate tail).

**Escalation:** none needed -- the refusals above are the intended
outcome of an offline session hitting D250's bar, not a spec
ambiguity; no F-WO134-n opened.
