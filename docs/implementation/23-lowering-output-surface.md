# Lowering output surface (WO-29): producer-gap inventory + design charter

Status: GAP INVENTORY -- sections 1-4 are factual and current as of
cycle 18 (master `b1ac9d8`); the design questions in section 5 are
OPEN. WO-29's opening design pass settles them, records the decisions
here plus a dated design-log entry, and flips this document to
normative for the implementation half -- the same lifecycle
`20-solver-abstraction.md` had for WO-20/21.

## 1. The pattern (why this document exists)

All four work orders dispatched since wave 1 delivered real, tested
infrastructure but had to prove it against HAND-BUILT FIXTURES
instead of live compiled designs, because `regolith-lower` does not
yet emit the typed IR each consumer needs (design-log F96):

| WO (commit) | What landed | Proven against | Missing producer |
|---|---|---|---|
| WO-23 (`82d9ce7`) | statics / stiffness / sketch solvers in `regolith-ir::solve` | IR built by construction | `connect` -> `Mating` lowering (opaque-island residue) |
| WO-28 engine (`08bafd5`) | E06xx registry + E0602 collision pass | typed `RuleDecl` CST only | domain entities (holes / bends / nets) for rule `forall` domains |
| WO-22 (`b1ac9d8`) | `FeatureProgram` IR, build123d/OCCT interpreter, STEP export, model pack | hand-built `FeatureProgram` fixtures | feature/stage program emission in `BuildPayload` |
| WO-24 (`1d69e33`) | allocation-search binding, netlist, KiCad adapter | hand-built Kestrel-shaped fixture | lowering-output -> `BlockRequirement` / `ComponentCandidate` bridge |

This is ONE gap with four symptoms. WO-19 wired the pipeline through
the static-core payload (diagnostics, resolutions, obligations,
snapshots, evidence, ledger) and every invariant went green against
that surface -- but the PATH TO SHIP consumers (realizers, rule
engine, allocation search) need richer typed IR that no lowering pass
emits yet. Each downstream agent independently found the same wall,
correctly refused to invent a workaround (the dispatch protocol's
escalation rule working as intended), and recorded the cut. WO-29
closes the gap once, centrally, instead of letting each consumer grow
a private path into the compiler.

## 2. What the output surface carries today

- `crates/regolith-api/src/session.rs::BuildPayload`: `diagnostics`,
  `resolutions`, `obligations`, `snapshots`, `evidence`, `ledger` --
  no stage/feature structure, no capability/requirement projection.
- `crates/regolith-sem/src/entity.rs::EntityKind`: `Face` / `Edge` /
  `Vertex` / `Net` / `Instance` / `Port` / `Region` /
  `Other(String)` -- no hole/bend domain kinds; the `Other` escape
  hatch is unstructured (no typed fields for a query to project).
- `OpaqueIsland` residue (tracked WO-05 cuts): `parts` per-line orbit
  constructors (`n x Thing`), `flows:` arrow lines (typed block,
  untyped edge), walk constraint text, `margin` / multi-line claim
  continuations / `override` / `plan:` / `flip`; plus the elec
  behavioral bodies (`spec:` / `ports:` / converter / `on`-event --
  those stay with the separate WO-05-residual item, see sec. 6).

## 3. Consumer forward contracts (already written, waiting)

1. **Mech realizer** (WO-22 cut 1):
   `python/regolith/realizer/mech/schema.py::FeatureProgram` --
   stages of resolved feature ops in SI metres, content-hashed.
   Consumer entry: `regolith.realizer.mech.pack.register`.
2. **Elec realizer** (WO-24 cut 2):
   `python/regolith/realizer/elec/binding.py::BlockRequirement` /
   `ComponentCandidate` -- block capability demands + screened
   registry candidates feeding the orchestrator-owned allocation
   search (regolith/07 sec. 7).
3. **Rule packs** (WO-28 cut 1): `forall <var> in <query>` must
   enumerate real domain entities (holes, bends, nets and their
   fields) through the WO-08 query engine.
4. **L2 statics** (WO-23 close-out cut): `regolith-ir` `Mating`
   construction from typed `connect` statements, so the reaction
   solve runs from source rather than by construction.

## 4. Constraints (normative, existing -- not up for redesign)

- **AD-4**: consumers see ONLY the serialized payload, never the CST.
- **AD-5/AD-18**: any new payload IR is schemars-single-sourced
  Rust-side, `SCHEMA_VERSION`-bumped, `make schema` regenerated (the
  Python forward contracts of sec. 3 become generated or verified
  against generated schema, not hand-maintained forever).
- **AD-6/INV-10**: deterministic emission (source order, blessed
  collections); double build byte-identical.
- **INV-21**: every resolved feature/binding parameter carries a
  Cause; **INV-1**: anything folded into an obligation's givens
  re-keys it.
- **AD-17**: `regolith-lower` is the ONE assembly seam. No second
  path into `EntityDb` -- the exact reason the WO-28 agent refused to
  build rule-pack-only entity structuring.

## 5. Open design questions (WO-29 deliverable 1 settles these)

Escalation, not invention: each answer lands in this document plus a
dated design-log entry before the corresponding implementation leaf.

- **Q1 -- EntityKind extension policy.** First-class `Hole` / `Bend`
  variants vs a disciplined structured-`Other` scheme; and which
  typed fields (position, diameter, edge distance, bend radius, net
  endpoints...) the query engine exposes to `forall` projections.
- **Q2 -- Feature-program home.** A `BuildPayload` field vs a
  per-part artifact record; and the AD-5 direction of truth (the Rust
  type is authored, the Python `FeatureProgram` regenerates from it
  -- the current hand-written forward contract becomes the drift
  check, then the generated form).
- **Q3 -- Binding-bridge split.** What is emitted Rust-side
  (per-block capability demands projected from lowered entities and
  claims) vs derived Python-side (registry candidate tables via
  quarry); the orchestrator owns the allocation loop either way.
- **Q4 -- Parser residue actually needed.** Which tracked WO-05
  opaque cuts block which emission; promote ONLY what a consumer
  needs (`grammar.ebnf` in lockstep, fuzz targets inherit).
- **Q5 -- Whether the one-producer principle gets AD-22** in
  `00-architecture.md` (downstream consumers bind only to
  schema-versioned lowering output; consumer-authored forward
  contracts are promoted into the payload, never grown into side
  channels).

## 6. Non-goals

- The consumers themselves: rule evaluation semantics, realizer
  geometry/binding logic, allocation search -- those stay in
  WO-28/WO-22/WO-24.
- Elec behavioral bodies + INV-16 (`ConverterGraph` feed): the
  separate WO-05-residual item (TODO.md sec. 7), cross-referenced,
  not absorbed.
- Walk constraint-surface typing beyond what Q4 pulls in: the
  Walk -> SketchClosure bridge is WO-11's typed constraint surface
  (WO-23's other cut), a language-surface question, not an emission
  one.
- Realized-fact discharge and everything post-realization (WO-25).
