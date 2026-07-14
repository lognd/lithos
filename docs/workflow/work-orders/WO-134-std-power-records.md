# WO-134 -- std.power records: apparatus, conductors, devices (charter 43; D250.1)

Status: open (independent -- no gates; dispatches first)
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
