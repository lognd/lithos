# WO-12: Contract IR (L2)

Status: in-progress (role-kind + parameter matching now REAL: `Interface`
carries `role_kinds` + `params`, `Impl` carries `bound_kinds` + `params`;
`check_role_kind` does coverage + role-kind compatibility, `check_param_match`
does parameter kind + type/shape matching with free-variable pinning
allowed. CST extractors `Interface::from_decl` / `Impl::from_impl_stmt`
populate role kinds + params from the typed `roles:`/`params:`/`<params>`
structure and role bindings from the impl body's ctor statements. Tests:
matching impl passes, role-kind mismatch fails, param mismatch fails,
free-pin allowed, CST extraction. DEPENDENCY CUT: an impl binding's
entity KIND (`bound_kinds`) is not carried in the impl's own syntax --
it needs the entity DB (regolith-sem query resolution); the field +
matching logic are in place and unit-tested, populated end-to-end once
WO-19 lowering resolves bindings. The cross-boundary INV-13 fixture
stays xfail until that wiring lands.)
Depends: WO-05..10
Language: Rust (`regolith-ir`) -- see `00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: substrate/04 (all); hematite/03; cuprite/02 sec. 4a, cuprite/07 sec. D-E

## Goal

The implementation-free contract graph and its checks: the level where
a system verifies with zero artifacts.

## Deliverables

- IR nodes: `Frame`, `Interface` (roles, demands, promise slots with
  ValueSources, `spec:` as opaque island, `<params>` vs `params:`
  distinction), `Impl` (role bindings as queries, inline promise
  refinement -- narrowing-only check, `todo!`), `Mating` (named sides,
  align, dof removed/kept, couples, preload, effects as signature
  refs, capability, state claims), `SystemNode`/`AssemblyNode`
  (parts, boundary + `at=` datums, connect, budgets, reserves,
  targets, config variables with exposer namespacing).
- Ledgers: DOF/Gruebler (mech), driver/load + domain-crossing +
  flow ledger (elec) -- as one pluggable ledger interface with two
  domain packs.
- T1 conformance: role-kind by construction, parameter match (binding
  may pin a free variable), capability-vs-demand lookups (tables from
  WO-16; a static in-memory pack for tests).
- Budget arithmetic: interval sums vs limit, `E0432` naming worst
  contributors; `locked:` entries; reserve accounting for targets.
- Refinement checking (`refines` + inline): promises widen-only from
  base to refined consumer view... (direction per substrate/04:
  refined = tighter demands on self, stronger promises).
- Derived-structure handle table (elec): intent -> realized-entity
  namespace stubs so claims can reference `report.supply` pre-
  allocation (resolution defers; the reference form validates).

## Acceptance

- Contract-first test: an assembly of unbound interfaces + matings +
  boundary passes/fails its ledgers with zero parts (both a
  well-formed and an over-constrained case).
- Double-axial-fixation and unfed-flow scenarios produce E0420-family
  diagnostics.
- Impl promise WIDENING is rejected; narrowing accepted.
