# WO-77 -- Declared material-removal vocabulary (charter 34 phase 1)

Status: todo (file authored 2026-07-10 -- the queue had carried
  this WO as "file exists" in error; D200 records the vocabulary
  rulings the charter delegated to this WO's spec cycle)
Language: Rust (regolith-syntax claim-scope verbs, regolith-ir/
  -lower projection) + Python (realizer projections, DFM rows,
  coverage ledger) + corpus
Spec: toolchain/34-topology.md sec. 2 (the charter, NORMATIVE for
  intent); D200 (design-log 2026-07-10-cycle-33 -- the concrete
  vocabulary this WO implements); AD-17 (one claim-scope feature
  traversal); WO-51 (FeatureProgram producer), WO-22 (realizer +
  E0443 omission posture), WO-67 (coverage/named-skip posture);
  hematite/07 (feature-op grammar home).

## Goal

The honest erosion, phase 1: an author DECLARES a removal family
over a target region; the optimizer explores its parameters with
machinery that already exists; the feature chain realizes it; DFM
gates every candidate. No density fields, no synthesis -- pattern
vocabulary only.

## The vocabulary (D200 -- implement, escalate only on contradiction)

Four constructor VERBS in the existing `then:`-scope feature-call
form (the Bore/CBore/Pierce/Bend idiom -- NO new statement form;
parameters use the existing literal / `in [lo, hi]` / `in {a, b}`
slot forms the optimizer already consumes):

1. `Ribs(count, pitch, thickness, height?)` -- count int, pitch/
   thickness/height lengths; height optional (defaults to the
   target region's depth).
2. `PocketGrid(nx, ny, wall, floor, depth?)` -- nx/ny ints, wall/
   floor lengths, depth optional (defaults to through-depth minus
   floor).
3. `Shell(t)` -- wall thickness.
4. `Lattice(cell, density)` -- cell in a DISCRETE set (v1 set:
   `{gyroid, honeycomb, cubic}`), density a fraction in [0, 1].

Target region: exactly the existing claim-scope subject mechanism
every current feature verb uses -- no new targeting grammar.

## Deliverables

1. Grammar/claim-scope: the four verbs recognized by the ONE
   feature-call traversal (AD-17); malformed family params (wrong
   arity, wrong dimension, density outside [0,1], unknown cell
   name) = NEW constructive E-code (next free; E0450 is taken)
   naming the family's signature.
2. Lowering: each verb materializes an ordinary `FeatureOp` (the
   EXISTING IR shape -- kind/constructor/params; NO new IR fields,
   NO SCHEMA_VERSION bump; if the existing shape genuinely cannot
   carry a family, STOP and escalate rather than bump).
3. Realizer projections (Python interpreter): Ribs, Shell, and
   PocketGrid project into v1 geometry where build123d supports
   them; Lattice is an HONEST named omission (the E0443/W-warning
   posture + a coverage-ledger named skip: "lattice: no v1
   projection"). Coverage ledger rows for all four.
4. DFM tier rows (the manufacturability law, charter sec. 2): a
   rule-pack batch (the WO-28/std packs idiom) with per-family
   predicates -- min rib thickness vs process, pocket wall vs
   tool access, shell min t, lattice cell x process feasibility
   (subtractive processes cannot make an internal gyroid:
   INFEASIBLE, named). Fixture cases both ways per family.
5. Corpus: a fixture part (or a cnc_router_r1 part if one fits
   naturally) declaring `Ribs` with a bounded `count`/`thickness`
   and a mass-minimize objective -- the optimizer pins a winner
   through EXISTING machinery (`cause: optimize(...)`); a negative
   fixture for the new E-code (numbering checked against master at
   the end).
6. Docs: hematite/07's feature-op section gains the four verbs
   (track-header version bump); guide mention beside the existing
   feature-op examples; charter 34 sec. 2 gets a "landed" cross-
   reference (no rewriting of its text).

## Acceptance criteria

- The Ribs fixture builds: FeatureProgram carries the op, the
  optimizer pins count/thickness with a trace, DFM rows fire on
  an infeasible twin.
- Lattice declares, lowers, and skips HONESTLY (named skip in the
  coverage ledger; no fabricated geometry).
- No SCHEMA_VERSION bump; no corpus regression (zero
  lowered->deferred transitions); goldens regenerated via make
  targets.
- `make check` green.

## Dependencies

WO-51/22/67 (landed), WO-85/90 (landed -- the current parse base).
Phase 2 (density fields) stays gated on this WO + WO-76 + an owner
compute-budget check-in (charter sec. 3) -- NOT this dispatch.
