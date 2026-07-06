# hematite Implementation Roadmap

> Spec 0.13. Phases are cumulative; each ends with a shippable artifact.

## Phase A -- spec hardening (no code)

1. Write 5-10 real parts and 2 assemblies in target syntax (sheet-metal
   bracket, machined housing, weldment, molded clip, the torch igniter),
   deliberately stressing scopes, queries, stages, setups, impls, and
   matings. Awkwardness = design bugs; feed them back into the spec.
2. Define the quantity core schema precisely (serialization included).
3. Define the entity DB schema and the query grammar (EBNF), including
   the walk grammar for profiles.
4. Define the obligation/evidence schema (serialization format).

## Phase B -- static core (first shippable: a linter)

5. Constraint graph + entity DB data structures (Python).
6. Parser for a minimal subset: one part, primitives, Extrude/Pocket/
   Fillet, queries, `then:` scopes.
7. Query validation, ownership/borrow checking, monomorphized checks,
   symmetry orbits, DOF ledger, capability/fit lookups -- all
   geometry-free. **`hematite check` works before any geometry kernel
   exists.**

## Phase C -- geometry vertical slice

8. Feature IR -> CadQuery/Build123d -> STEP export.
9. Post-geometry verification pass (confirm static topology predictions).
10. One eager DFM rule pack: sheet metal (closed-form, well-documented).

## Phase D -- contracts

11. Interfaces, impl conformance T1/T2, matings.
12. One assembly end-to-end: ledger + rigid statics + a bolted joint's
    analytical state claims via a hand-rolled mini-harness with 3-4 model
    nodes (joint diagram, beam, Lame).

## Phase E -- the boundary, for real

13. Obligation/evidence serialization; harness as a separate process.
14. Orchestrator with caching + lockfile.
15. Eager DFM resolution of `free`; lazy loop with sensitivity hooks
    stubbed.

## Later

Rust migration of hot paths - sketch solver integration (OPEN-5
residue; language surface closed, D65) - kinematics model packs (v2;
OPEN-3 closed for v1, D64) - statistical allocation pack + capability
distributions (OPEN-2 closed, D63) - UI - the elec track converging on
the shared regolith implementation (see `../cuprite/08-open-questions.md`
on sequencing).
