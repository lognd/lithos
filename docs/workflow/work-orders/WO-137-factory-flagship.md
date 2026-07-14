# WO-137 -- The factory flagship: a real plant, power + building together (charter 43; the acceptance test of AD-42)

Status: open (gated on WO-132..136)
Language: corpus authoring (cuprite power + calcite building) +
  demos. No toolchain changes -- gaps you hit are FINDINGS (that is
  what a flagship is for), never in-scope fixes.
Spec: charter 43 (all of it, sec. 5 especially); AD-42; D248/D249/
  D250; charter 31 (the flagship program + parity bar); guide 27
  (authoring for discharge); D224/D250 (every record cited or
  honestly refused).

## Goal

A large factory: utility service -> substation transformer ->
switchgear -> MCCs -> motor loads, inside a REAL calcite building
with a real electrical room -- shipped through the full pipeline, and
proving that the power system and the building were designed as ONE
design, not two.

## Deliverables

1. `examples/flagships/factory_p1/` (per D188/D242, flagships/ is
   where new machine-scale builds go): the plant's power system in
   cuprite + its building in calcite, cross-bound per WO-136.
2. Real declared inputs with real provenance (D250.3): the utility's
   available fault current and X/R DECLARED as a cited datum (a
   stated utility-letter value, recorded as such) -- or, if you
   choose to demonstrate the honest path, LEFT UNDECLARED so the
   fault/withstand/arc-flash claims DEFER by name. Do at least one
   of each somewhere in the plant so BOTH behaviors are proven.
3. Claims across the whole chain: demand load, voltage drop, ampacity,
   fault current, withstand, transformer loading, motor start dip,
   coordination, working clearance, bearing pressure (the
   transformer on its pad), grounding.
4. Full ship: census + calc book (every power sheet carrying the
   D250.2 statement) + drawings (one-line diagram if the drawing
   surface can express it; if not, that is a FINDING) + the fleet
   bar.
5. Fleet enrollment; demo18 "the factory" proof pack cross-linking
   the electrical claims to the architectural evidence.

## Acceptance

- factory_p1 ships release-clean; every waiver in a D220.2 closed
  class; the arc-flash claim either discharges through feldspar's
  certified solver or DEFERS honestly -- it is never discharged by a
  screening estimate (this is the acceptance test of D250.4).
- Every power calc sheet carries the "this is not a stamped study"
  statement (D250.2).
- The working_clearance + bearing_pressure claims discharge against
  the REAL calcite room -- the tandem is proven, not asserted.
- `make check` + `make health` green at the new fleet size.

## Escalation

Every language/model/drawing gap the plant hits is a FINDING
(F-WO137-n) -- author around it honestly and ledger it. A flagship's
job is to find the walls, not to hide them. In particular: if the
one-line diagram cannot be expressed by the drawing surface, say so
loudly; a power design without a one-line is not a deliverable an
electrical engineer would accept, and that gap should drive the next
cycle.
