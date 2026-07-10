# Research: JLCPCB controlled-impedance stackups (WO-78 deliverable-1 sources)

Retrieved 2026-07-10 from the fab's own published impedance page:
https://jlcpcb.com/impedance ("Controlled Impedance PCB Layer
Stackup - JLCPCB"). This is the citable source for the
`std.elec.stackups` records (AD-34 sourcing law: document = the
fab's published stackup page, retrieved date above; community
tier -- fab-published, not independently measured by this
project). Values transcribed verbatim; record authors must not
"improve" them.

## Material dielectric constants (as published)

| material           | Dk   |
|--------------------|------|
| 7628 prepreg       | 4.4  |
| 3313 prepreg       | 4.1  |
| 1080 prepreg       | 3.91 |
| 2116 prepreg       | 4.16 |
| core (FR-4)        | 4.6  |
| solder mask        | 3.8  |

## 4-layer stackups (1.6mm class, outer copper 0.035mm, inner 0.0152mm)

| name             | outer prepreg        | core     |
|------------------|----------------------|----------|
| JLC04161H-7628   | 7628 0.2104mm        | 1.065mm  |
| JLC04161H-3313   | 3313 0.0994mm        | 1.265mm  |
| JLC04161H-1080   | 1080 0.0764mm        | 1.265mm  |
| JLC04161H-2116   | 2116 0.1164mm        | 1.265mm  |
| JLC04161H-7628A  | 7628 0.218 + 1080 0.0764 | 0.865mm |
| JLC04161H-3313A  | 3313 0.107 + 3313 0.0994 | 1.065mm |

(Further variants B..F exist on the page -- multi-prepreg stacks
with 0.15..0.7mm cores; transcribe from the source if a record
needs them.)

## 6-layer stackups (outer copper 0.035mm)

| name             | outer prepreg   | L2/L4 cores | middle          |
|------------------|-----------------|-------------|-----------------|
| JLC06161H-3313   | 3313 0.0994mm   | 0.55mm      | 2116 0.1088mm   |
| JLC06161H-7628   | 7628 0.2104mm   | 0.4mm       | 7628 0.2028mm   |
| JLC06161H-1080   | 1080 0.0764mm   | 0.55mm      | 7628 0.2104mm   |

## Record-authoring notes

- Cite each record: `evidence = { method = "catalog", trust_tier =
  "community", reference = "JLCPCB Controlled Impedance PCB Layer
  Stackup, jlcpcb.com/impedance, retrieved 2026-07-10;
  <stackup name> row" }`.
- The fab publishes Dk per MATERIAL, not per frequency; the SI
  models' accuracy bands (feldspar WO-25) already carry the
  honesty margin -- do not invent Df or frequency dependence the
  source does not state.
- 2-layer boards: JLCPCB's standard 2-layer is 1.6mm FR-4, outer
  copper 0.035mm, single core -- adequate for a 2-layer record
  citing the same page; microstrip-only (no stripline reference
  plane pair).
