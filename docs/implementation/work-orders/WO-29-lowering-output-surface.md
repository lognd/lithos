# WO-29: Lowering output surface (typed IR for downstream consumers)

Status: in-progress (deliverable 1 DONE cycle 19 -- D88-D92 decided,
`../design/23-lowering-output-surface.md` normative, AD-22 landed, EntityKind
extension query-reachable; deliverables 2-5 + the two D91 parser
promotions REMAIN, fully scoped below and in the cuts note --
re-dispatch this WO, do not open a new one)
Depends: WO-19 (the pipeline this extends), WO-05 (only the residual
promotions design Q4 selects); GATES the end-to-end halves of WO-22
and WO-24, the WO-28 engine remainder (deliverables 3-8), and
WO-23's `connect` -> `Mating` cut. Sequenced BEFORE any further
realizer / rule-pack dispatch (design-log D87).
Language: Rust (`regolith-lower` passes, `regolith-sem` entity kinds,
`regolith-syntax` residue per Q4, `regolith-oblig`/`regolith-api`
schema surface); Python (regenerated `_schema/`, the orchestrator-side
binding bridge, facade updates)
Spec: regolith/07 sec. 2 (lowering) + sec. 7 (allocation search),
hematite/05 (stage pipeline), cuprite/04 + 06 (structural lowering
table), regolith/13 (INV-1/10/18/21); `../00-architecture.md`
AD-4/AD-5/AD-6/AD-17/AD-18; design:
`../design/23-lowering-output-surface.md` (gap inventory + design charter --
deliverable 1 below makes it normative for this WO)

## Goal

Close the one producer gap behind four recorded consumer cuts (F96):
`regolith-lower` emits the typed IR its PATH TO SHIP consumers
already wrote forward contracts for -- a feature/stage program for
the mech realizer, a binding-requirement projection for the elec
realizer, structured domain entities for rule-pack `forall` domains,
and `Mating` construction for the L2 statics feed -- so downstream
work orders prove their infrastructure against live compiled designs
instead of hand-built fixtures. One producer, schema-versioned, per
AD-17: no consumer grows a private path into the compiler.

## Deliverables

1. **Design pass FIRST** (dispatch-protocol escalation path, the
   WO-28 spec-cycle precedent): survey the three consumer forward
   contracts and the `Mating` feed against today's `BuildPayload`;
   settle Q1-Q5 of `../design/23-lowering-output-surface.md`; record the
   decisions in that document (flipping it to normative) plus a dated
   design-log entry; add AD-22 to `../00-architecture.md` if Q5 lands
   that way. No implementation leaf before its shape is decided here.
2. **Domain entity structuring** (unblocks the WO-28 engine
   remainder): extend `regolith-sem::EntityKind` per Q1 with the
   domain kinds rule packs quantify over (holes, bends; nets exist
   but carry no queryable fields) and populate them in
   `lower.entities` from the typed CST, including whatever Q4 parser
   promotions that requires (`../grammar.ebnf` in lockstep, fuzz targets
   inherit). Every populated field a `forall` can project is typed,
   deterministic, and query-engine-reachable (WO-08); ambiguity stays
   E0301 data (INV-18).
3. **Feature/stage program emission** (unblocks WO-22 end to end): a
   serialized, deterministic feature program per part in the build
   output -- stages/setups and feature ops with resolved parameters
   and Cause-typed resolutions (INV-21) -- satisfying the
   `regolith.realizer.mech.schema.FeatureProgram` forward contract
   per Q2's direction-of-truth decision (Rust schemars source,
   `SCHEMA_VERSION` bump, `make schema` regenerated, drift check
   green). Wire `regolith.realizer.mech.pack.register` in as the
   consumer per WO-22 cut 1's reopen criterion.
4. **Binding-requirement bridge** (unblocks WO-24 end to end):
   extraction from a real lowered `.cupr` build into
   `BlockRequirement` / `ComponentCandidate` inputs -- per-block
   capability demands projected from lowered entities/claims
   (Rust-side per Q3) plus the registry-candidate table derivation
   (Python-side, quarry records). The allocation loop itself stays
   orchestrator-owned and untouched (regolith/07 sec. 7).
5. **`connect` -> `Mating` lowering** (closes WO-23's recorded cut):
   lower typed `connect` statements to real `regolith-ir` `Mating`
   values so the rigid-statics reaction solve runs from source;
   computed envelope loads keep landing in obligation `given.loads`
   (INV-1 re-key already proven by WO-23).
6. **Docs, goldens, cross-references in the same change**: payload
   schema docs updated; golden corpus deltas regenerated deliberately
   and explained (new emission over the conforming corpus must not
   add diagnostics); the reopen-criterion notes in WO-22 / WO-24 /
   WO-28 / WO-23 flipped from "blocked on WO-29" to done as each
   consumer seam is wired; TODO.md ledger updated.

## Acceptance

- `regolith build` over `examples/tracks/hematite/sheet_bracket.hema` (and the
  corpus parts inside WO-22's v1 feature set) yields a feature
  program the EXISTING WO-22 interpreter accepts and realizes to
  STEP -- WO-22's blocked acceptance half becomes checkable without
  modifying the interpreter's logic.
- A live compiled Kestrel board (`examples/systems/cubesat/`) yields
  `BlockRequirement` / `ComponentCandidate` inputs that drive WO-24's
  EXISTING allocation search to a bound netlist with no hand-built
  fixture in the loop.
- A `forall <var> in <query>` smoke fixture enumerates real holes (or
  bends) over a corpus part through the WO-08 query engine with typed
  field projection -- proving the domain the WO-28 engine remainder
  will evaluate over (rule evaluation itself stays WO-28).
- A `connect`-carrying fixture produces `Mating` values and computed
  reactions from source (WO-23's by-construction proof becomes an
  end-to-end one).
- Determinism: double build byte-identical on `payload_json()`
  (INV-10); every resolved parameter carries a `Cause` (INV-21);
  `make schema` idempotent, drift check green.
- `make check` green; golden deltas explained in the change; every
  cross-referenced WO file's blocker note updated truthfully (done or
  still-blocked, never silently dropped).

## Cuts recorded this cycle (dispatch, cycle 19)

Deliverable 1 (the design pass) is DONE: Q1-Q5 decided (D88-D92,
design-log `2026-07-06-cycle-19.md`), `../design/23-lowering-output-surface.md`
flipped to normative, AD-22 added to `../00-architecture.md`.

CORRECTION (2026-07-08, D125, owner-authorized): the cuts note below
names `parts:` per-line orbit constructors as the blocking parser
promotion for deliverables 2/3/4. This was factually wrong -- `parts:`
orbit lines instantiate sub-parts/assemblies, not hole/bend geometry
(see `../design/23-lowering-output-surface.md` Q4(a) and
`../../design-log/2026-07-07-cycle-23.md` sec. E). The real blocking
promotion is `then:` claim-scope feature constructor calls
(`Bore(...)`, `PatternOf<...>(...)`, etc.), already partially walked
per-line by `crates/regolith-lower/src/claims.rs`. Every `parts:`
reference in the paragraphs below is historical record of the
cycle-19 dispatch's (incorrect) reasoning and is left verbatim; read
it as `then:` claim-scope constructors per this correction.

Deliverable 2 (domain entity structuring) is PARTIAL: the `EntityKind`
extension itself landed (`Hole`/`Bend` first-class variants in
`regolith-sem::entity`, well-known measure keys documented;
`regolith-sem::query::base_selector` maps `holes`/`hole` and
`bends`/`bend` so the WO-08 query engine can dispatch on them today).
NOT done: populating them in `lower.entities` from real `.hema`
source. `crates/regolith-lower/src/entities.rs::build_entities`
currently lowers exactly ONE `Entity` per top-level `Decl` (see its
doc comment: "WO-19's simplified per-decl granularity"); a `parts:`
block's per-line orbit constructors (`n x Thing(...)`) are today
swallowed whole as one `OpaqueIsland` per declaration, not structured
into typed per-line CST nodes. Giving the parser a typed `parts:`
per-line production (a new CST node in `regolith-syntax`, a
`../grammar.ebnf` update, fuzz-target coverage, then wiring
`build_entities` to walk it and emit N `Hole`/`Bend` entities per
line with resolved `position`/`diameter`/`edge_distance` or
`radius`/`angle`/`line` measures) is itself the same class of
upstream wall WO-23 and WO-28 each hit independently before this WO
existed. It is a real, scoped, well-understood piece of work (Q4/D91
already named it precisely as the ONE parser promotion this
deliverable needs) but is larger than a same-dispatch addendum can
responsibly close alongside deliverables 3-5, which share the
identical prerequisite. Recorded here rather than faked; a follow-up
dispatch can pick it up directly from D91's scoping with no
rediscovery needed.

Deliverables 3 (feature/stage program emission), 4 (binding-
requirement bridge), and 5 (`connect` -> `Mating`) are NOT DONE this
cycle: each depends on the same `parts:`-line (3, 4) or `connect`-
line (5) parser promotion as deliverable 2, so none could be wired
end-to-end without it. Their PAYLOAD SHAPES are decided (D89 feature
program as a new `BuildPayload` field; D90 the Rust/Python binding-
bridge split; D91 `connect` endpoint promotion scoped) and are ready
for the next dispatch to implement against directly.

Deliverable 6 (docs/goldens/cross-references) is PARTIAL: the design
doc and design-log are updated (this cycle's real work); the
reopen-criterion notes in WO-22/WO-23/WO-24/WO-28 are updated
TRUTHFULLY (not flipped to "done" -- each now says design-decided but
still-blocked on the parser promotion, with a pointer to this cut
note). No golden corpus deltas are expected or included since no new
emission landed on the corpus-facing surface (the `EntityKind`
addition is additive to an enum already exhaustively matched with a
final `Other(String)` arm pattern in the one place it is matched
narrowly, `regolith-sem::query::base_selector`, which now has explicit
arms for the two new kinds -- `cargo build`/`cargo test` verified
green, no corpus diagnostic change). `TODO.md` is intentionally left
untouched per the close-out contract (coordinator updates the ledger
on integration).

## Non-goals (stay in their owning WOs)

- Rule evaluation, `resolves:`, E0601/E0603/E0604, reference packs,
  `rules test|try` (WO-28); realizer geometry/binding logic (WO-22 /
  WO-24); allocation-search internals (orchestrator, done).
- Elec behavioral bodies + INV-16 `ConverterGraph` feed -- the
  separate WO-05-residual item rides WO-24's next slice, not this WO.
- Walk constraint-surface typing / Walk -> SketchClosure (WO-11
  surface question, WO-23's other cut).
- Realized-fact discharge, manufacturing outputs (WO-25).
