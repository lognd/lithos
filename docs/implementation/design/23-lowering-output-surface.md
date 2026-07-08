# Lowering output surface (WO-29): producer-gap inventory + design charter

Status: NORMATIVE (cycle 19, WO-29 design pass, design-log
2026-07-06). Sections 1-4 are the factual gap inventory as of cycle 18
(master `b1ac9d8`); section 5's Q1-Q5 are now DECIDED (section 5a) and
bind the implementation half of WO-29. Section 5b records which
decisions this dispatch actually closed end-to-end vs. which hit a
further upstream wall and were cut back to WO-29's own follow-up (see
the WO-29 file's "Cuts recorded this cycle").

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
  continuations / `override` / `plan:` / `flip`. The elec behavioral
  bodies (`spec:` / `ports:` / converter / `on`-event) are RETIRED from
  this row: WO-36 typed them (`Field`/`CtorStmt`/`OnBlock`/`RegAssign`)
  and wired `regolith-lower::converter` to feed `ConverterGraph` from
  real `.cupr` source, un-xfailing the INV-16 end-to-end fixture.
- **Fluorite note (WO-32 D6):** the fluid track's `flownet` payload
  (fluorite/03) lowers with NO `OpaqueIsland` debt of its own -- every
  `.fluo` production (`medium`/`flownet`/`edges`/`states`/`require
  fluids.*`) was typed from WO-31 forward, so WO-32's flownet
  elaboration and payload-ref obligation emission landed straight
  against typed CST with no promotion step like Q4's above. The F96
  lesson (sec. 1: four consumers independently hit the same
  hand-built-fixture wall because the parser stayed ahead of the
  lowering passes) applied forward: fluorite's front end and its
  lowering passes shipped in the same generation (WO-31/WO-32), so no
  fifth wall to record here.

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

## 5. Design questions -- DECIDED (WO-29 deliverable 1, cycle 19)

### 5a. Decisions

- **Q1 -- EntityKind extension policy: first-class `Hole` / `Bend`
  variants, typed fields ride `Measures`.** Decided FOR first-class
  variants over a structured-`Other` scheme: `forall` domain
  dispatch (WO-28) needs a stable discriminant the query engine's
  `base_selector` matches on (`query.rs`), and `Other(String)` is a
  string comparison with no compile-time exhaustiveness -- the exact
  reason `Other` was documented as "pack-defined kinds" only, not the
  home for two domain kinds two consumers already name in their
  forward contracts. Typed fields (`position`, `diameter`,
  `edge_distance` for `Hole`; `radius`, `angle`, `line` for `Bend`)
  ride the EXISTING `Entity::measures` map (already the
  typed-by-predicate-registry mechanism, WO-08) under documented
  well-known keys, rather than new dedicated struct fields on
  `Entity`/`EntityKind`. Rationale: a new geometric attribute (e.g. a
  future `counterbore_depth`) becomes a new well-known measure key,
  not a schemars-breaking struct change and `SCHEMA_VERSION` bump --
  `Measures` was designed exactly for this extensibility (entity.rs
  doc comment: "String-keyed so packs extend it"). `Net` stays
  bare (no typed fields) per the existing inventory note; a future
  net-endpoint projection is a separate, not-yet-forward-contracted
  need and stays out of scope here.
- **Q2 -- Feature-program home: a new `BuildPayload` field, Rust
  authored.** Decided FOR a payload field
  (`BuildPayload::feature_programs: IndexMap<PartName,
  FeatureProgram>`) over a side artifact: AD-4 says consumers see
  ONLY the serialized payload, never a second channel, and a side
  artifact would need its own versioning/determinism story outside
  `payload_json()` (INV-10 already covers the whole payload, not a
  bolt-on file). Direction of truth per AD-5: the Rust
  `FeatureProgram` type (schemars-derived, `regolith-lower` or
  `regolith-api`) is authored; `SCHEMA_VERSION` bumps;
  `python/regolith/realizer/mech/schema.py::FeatureProgram` (today
  hand-written) becomes the GENERATED form under `_schema/`, with the
  realizer's existing hand-written type becoming, for one transition
  commit, the drift-check target, then deleted once WO-22's consumer
  imports the generated model directly.
- **Q3 -- Binding-bridge split: Rust emits raw per-block capability
  demands, Python derives the candidate table.** Rust-side
  (`regolith-lower`, pure per AD-17's "no IO" rule): project
  `BlockRequirement`-shaped capability demands from lowered entities
  and claims into a new `BuildPayload` field -- deterministic,
  Cause-tagged where a demand traces to a resolved value source
  (INV-21). Python-side (orchestrator): derive `ComponentCandidate`
  screening tables from magnetite registry records, because registry
  lookup is I/O (reading `magnetite.toml`-resolved package data) and
  `regolith-lower` is a pure function of source text with no IO
  (AD-17) -- pushing registry I/O into the compiler would violate the
  same rule that keeps `regolith-lower` deterministic and testable.
  The allocation loop itself is untouched, orchestrator-owned
  (regolith/07 sec. 7), on both counts.
- **Q4 -- Parser residue: promote exactly two opaque forms, no
  more.** CORRECTED 2026-07-08 (see design-log addendum): of the
  WO-05 `OpaqueIsland` residue list (sec. 2), only two items are
  load-bearing for this WO's four consumer contracts:
  (a) `then:` claim-scope feature constructors (`Bore(...)`,
  `CBore(...)`, `Pierce(...)`, `PatternOf<...>(...)`, etc.), needed
  so deliverable 2 can materialize N `Hole`/`Bend` entities per
  constructed feature instead of the current one-entity-per-
  declaration granularity, and (b) `connect` arrow-line endpoints,
  needed for deliverable 5's `Mating` construction. `parts:` per-line
  orbit constructors (`n x Thing(...)`) are NOT part of this
  promotion: they instantiate sub-parts/assemblies (e.g.
  `examples/systems/cubesat/structure.hema`'s `rails: 4 x Rail`), not
  hole/bend geometry, and already carry a count/type structure
  `build_entities` can read without a new CST production. Explicitly
  NOT promoted here (stay opaque,
  each already has a named owner): `flows:` arrows (elec structural,
  rides WO-24's own next slice per its recorded cut), walk
  constraint text (WO-11's Walk -> SketchClosure surface question,
  WO-23's OTHER cut, not this one), `margin` / multi-line claim
  continuations / `override` / `plan:` / `flip` (no consumer forward
  contract names them), and the elec behavioral bodies (`spec:` /
  `ports:` / converter / `on`-event -- the separate WO-05-residual
  item, unchanged).
- **Q4(a) corollary -- ONE claim-scope walk, shared.** Deliverables
  2 (domain entity structuring), 3 (feature/stage program emission),
  and 5 (`connect` -> `Mating`) all read the same `then:` claim-scope
  CST once promoted; per NO DUPLICATION and AD-17 (one assembly seam)
  they MUST share a single walk over claim-scope constructor calls in
  `regolith-lower`, not grow three independent traversals. The walk
  lives beside `crates/regolith-lower/src/claims.rs` (the existing
  per-claim-line pass already visits `decl.claims()`); it is extended
  to also recognize constructor call syntax inside a claim scope
  (`Bore(...)`, `PatternOf<...>(...)`, etc.) and to hand each
  recognized call to whichever consumer-specific projector needs it
  (entity population for deliverable 2, feature-op emission for
  deliverable 3). `connect` endpoint promotion (deliverable 5, Q4(b))
  is a separate CST production (arrow-line syntax, not a claim scope)
  and does not share this particular walk, but stays in the same
  module for the same one-seam reason.
- **Q5 -- Yes, AD-22.** The one-producer principle already governed
  four independent WOs' behavior by convention (each one discovered
  it and self-enforced by recording a cut instead of inventing a
  side channel); leaving it implicit invites a fifth WO to
  re-discover it the hard way. Added as `../00-architecture.md` AD-22:
  "downstream consumers bind only to schema-versioned lowering
  output; a consumer's forward-authored contract type is a SPEC for
  what the payload must carry, promoted into the payload verbatim or
  regenerated from it -- it is never grown into its own path into
  `EntityDb`/CST/registry state."

### 5b. What this dispatch actually closed vs. cut

Per the dispatch protocol's escalation rule (design decisions are not
implementation completeness): Q1-Q5 above are the SHAPE decisions and
bind all future work on this surface, regardless of how much of the
implementation this single WO dispatch finishes. See the WO-29 file's
own "Cuts recorded this cycle" for exactly which deliverables landed
end-to-end this cycle and which hit the Q4(a) `then:`-claim-scope
promotion as a genuine further parser wall (the same class of wall
WO-23/WO-28 hit before this WO existed) and were cut back rather
than faked.

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
