# WO-08: Query engine (static tier)

Status: done
Depends: WO-07
Language: Rust (`regolith-sem`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/05 sec. 2, 5; hematite/02 sec. 6; cuprite/07 sec. F

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

## Status note (FE-8 follow-up)

The static name/type resolution this WO owns gained a minimal L1
primitive in `regolith-sem::resolve` (`QuantityClass`, `classify_value`,
`field_classes`, `check_equality_ban`): given a declaration's field
table, it resolves a bare NAME operand's quantity class and completes
INV-17's `==` ban for the name-resolved case (`a == b`, both continuous)
that the syntactic `regolith-syntax` pass cannot decide (FE-8). Wired
into `lower.checks` and verified end-to-end through
`regolith.compiler.check`. Scope is deliberately narrow (a decl's own
directly-declared scalar fields); cross-decl/query-resolved operands
remain out of scope.

## Status note (INV-06/18 resolution wiring, cycle 15)

The query engine's `Query::resolve` (cardinality-typed resolution against
an entity-DB snapshot) gained its first real caller. WO-05 now types
`feature`/`refer` as contextual single-line `QueryStmt` nodes, and
`regolith-lower/src/query.rs` commits one entity per `feature` into a
per-declaration scope-entry snapshot and resolves each `refer <name>` as
a `.only` query against it. Over/under-match is `E0301`
(`AMBIGUOUS_SELECTION`, INV-18 reference determinism); because each scope
resolves only against its OWN committed snapshot, a `refer` naming a
sibling declaration's feature under-matches (INV-06 snapshot isolation).
`test_inv_06`/`test_inv_18` are now real end-to-end fixtures. The by-name
entity granularity is the WO-19 simplification (matching `ownership.rs`);
the wider cardinality vocabulary (`.all`/`.any`/joins, orbit `any`) stays
unit-tested in `regolith-sem::query`.

## Acceptance

- Table-driven tests: every query form in the examples corpus
  validates; deliberately ambiguous/over-matched queries produce the
  documented diagnostics with fixes.
- Orbit-split-then-`any` scenario matches hematite/02 sec. 1's comment
  (`ports.any` after `plug_port` = E0502).
