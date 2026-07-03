# WO-08: Query engine (static tier)

Status: todo
Depends: WO-07
Language: Rust (`decl-sem`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/05 sec. 2, 5; mech/02 sec. 6; elec/07 sec. F

## Goal

Method-chain queries: static validation (names, kinds, operand types,
cardinality) on the pre-realization IR, symbolic resolution against
entity-DB snapshots.

## Deliverables

- Query AST from WO-05 islands: `.where(pred=...)`, `.all/.only/.any`,
  `.nearest(datum)`, `at_intersection(a, b)`, `&` joins,
  `.instances`, `.bits`, bus ranges `[i .. j]`, `.as_datum()`.
- Predicate registry per domain (declared, not hard-coded): predicate
  name -> operand types -> entity kinds it applies to.
- Cardinality typing: `Entity` / `Set[Entity; n]` / `Set[Entity]`;
  consumers declare what they accept; mismatch = E0301-family with
  the matched-entity table in the diagnostic.
- `.any` orbit check against the current symmetry group (E0502 with
  pinning suggestions on broken orbits); canonical-representative
  selection recorded for the lockfile (WO-14 consumes).
- Cross-owner selection without a join = E03xx.

## Acceptance

- Table-driven tests: every query form in the examples corpus
  validates; deliberately ambiguous/over-matched queries produce the
  documented diagnostics with fixes.
- Orbit-split-then-`any` scenario matches mech/02 sec. 1's comment
  (`ports.any` after `plug_port` = E0502).
