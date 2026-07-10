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
stays xfail until that wiring lands.
SYSTEM NODES NOW REAL (cycle 14): `SystemNode` is populated from the
typed CST by `regolith-lower::contracts` -- `BoundaryEntry`/`Reserve`/
`FlowEdge`/`Target` built per `boundary:`/`reserves:`/`flows:` block and
`target ... of <Sys>` decl (draws bound to reserves; child boundaries
linked by `parts:` type reference). Three sound L2 checks in the new
`regolith-ir::system` module flow diagnostics to the facade: boundary
subsumption (INV-07, E0407 BOUNDARY_NOT_SUBSUMED), reserve
over-allocation (INV-08, E0432), and the system-flow ledger (INV-15,
E0420). Each check is conservative (interval-compares only in a shared
unit; over-collects declared flow participants so opaque-island intents
never yield a false leak). `test_inv_07/08/15` are real end-to-end
fixtures (honest-pass + deliberate-violation each); golden corpus
unchanged. REMAINING for done: matings/`connect` and interface
promise-slot bodies are still opaque islands (WO-05 grammar), so DOF/
driver ledgers over real matings and refinement narrowing are not yet
exercised end-to-end; INV-19 stays xfail (promise-only surface holds by
construction; its test needs escalation-edge lowering + a two-build
harness).)
REFINEMENT-BOUND EXTRACTION (cycle 33, WO-92): the recorded cut is
CLOSED in mechanism -- WO-26 D104 landed the both-scalar-bounds
extraction (`regolith-lower::claims::conformance_windows` ->
`given.loads` -> `translate._translate_conformance`), unit-tested end
to end. It fires only when BOTH the interface AND the impl BODY
re-declare a same-named scalar comparator field (`y: <= N`). The
corpus expresses conformance via generic-parameter instantiation +
geometric/role/`derived` promises instead, so no both-scalar-bound
pair occurs and the flagship conformance obligations stay honestly
`conformance_windows_unresolved` (genuinely unbounded, never a
fabricated window; see design-log F116). No further compiler work
without the OPEN owner decision F116 records.
Depends: WO-05..10
Language: Rust (`regolith-ir`) -- see `../../spec/toolchain/00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/04 (all); hematite/03; cuprite/02 sec. 4a, cuprite/07 sec. D-E

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
  base to refined consumer view... (direction per regolith/04:
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
