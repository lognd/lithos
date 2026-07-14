# WO-136 -- Sited equipment: the cuprite-calcite tandem (D249/AD-42, charter 43 sec. 4)

Status: open (gated on WO-132/133; wants WO-134's masses/footprints)
Language: Rust (the containment/clearance claim lowering) + Python
  (routing + the civil seam). No schema bump expected -- civil's
  bearing/space machinery EXISTS; report before bumping.
Spec: charter 43 sec. 4 (NORMATIVE); AD-42; D249;
  regolith/10-domain-binding.md (cross-domain composition -- this WO
  is its sharpest test); D102 (typed containment machinery -- reuse,
  do not reinvent); calcite/03 (spaces, load paths); the EXISTING
  `civil.bearing_pressure` + embedment claim kinds (WO-48/WO-85 --
  reuse them; a transformer's mass on a slab is not a new claim).

## Goal

An item of power apparatus is declared ONCE and is simultaneously an
electrical artifact and a physical one: its mass lands on a calcite
slab, its footprint plus its NEC 110.26 working clearance occupies a
calcite space, and its heat is a load on the room -- checked, not
assumed.

## Deliverables

1. Apparatus siting: a declared apparatus binds to a calcite space/
   slab (the existing contract/mating machinery -- one declaration,
   roles in two domains).
2. MASS -> `civil.bearing_pressure` through the EXISTING claim kind
   and the existing frame/footing chain (WO-48's resolution). No new
   claim kind; prove a transformer's pad loading discharges.
3. `elec.power.working_clearance(<apparatus>)`: the NEW claim kind
   whose SUBJECT is electrical and whose EVIDENCE is architectural --
   footprint + NEC 110.26 working depth/width/headroom, checked as
   spatial containment (D102's machinery) against the calcite space
   that contains it. Cite the NEC article + edition (D250.1).
4. Egress from the working space -> the existing calcite circulation
   claim (reuse).
5. Heat rejection -> a declared thermal load on the room where a
   fluorite/HVAC surface exists; an honest named absence otherwise
   (never a silent zero).
6. Failures are DIAGNOSTICS, not warnings: a transformer that fits
   only if its door cannot open is a design ERROR (charter 43 sec. 4).

## Acceptance

- A transformer sited in a calcite electrical room discharges its
  bearing_pressure through the existing civil chain AND its
  working_clearance against the room's real geometry.
- A deliberately-undersized room FAILS working_clearance with a named
  diagnostic naming the shortfall (mm, and which face).
- No new schema; `make check` + `make health` green.

## Escalation

If the cross-domain binding needs a contract-model change, STOP and
report -- this WO is the TEST of `regolith/10-domain-binding.md`, and
if the model does not hold, that finding is more valuable than a
workaround (record it as F-WO136-n with the exact wall).
