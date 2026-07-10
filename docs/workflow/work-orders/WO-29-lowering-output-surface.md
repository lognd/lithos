# WO-29: Lowering output surface (typed IR for downstream consumers)

Status: DONE (deliverable 1 DONE cycle 19; deliverable 2 DONE
cycle 23 -- Q4(a) corrected to `then:` claim scopes (D125), domain
`Hole`/`Bend` entities materialized from the shared claim-scope walk
with typed measures, query-engine-reachable, goldens regenerated;
deliverables 3 (SCOPED, see cut note) + 5 DONE cycle 23; deliverable 4
(binding-requirement bridge) DONE 2026-07-08 -- source construct named
(architecture-resource `promises:`, NOT `budget:`; D126, cuprite/05
sec. 2 + regolith/10 sec. 1), parser promoted for comparison-valued
call keyword args, `regolith_ir::BlockRequirement` payload field
projected in Rust (SCHEMA_VERSION 7 -> 8), Python bridge screens raw
demands + derives candidates from magnetite records per the D90 split)
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
table), regolith/13 (INV-1/10/18/21); `../../spec/toolchain/00-architecture.md`
AD-4/AD-5/AD-6/AD-17/AD-18; design:
`../../spec/toolchain/23-lowering-output-surface.md` (gap inventory + design charter --
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
   settle Q1-Q5 of `../../spec/toolchain/23-lowering-output-surface.md`; record the
   decisions in that document (flipping it to normative) plus a dated
   design-log entry; add AD-22 to `../../spec/toolchain/00-architecture.md` if Q5 lands
   that way. No implementation leaf before its shape is decided here.
2. **Domain entity structuring** (unblocks the WO-28 engine
   remainder): extend `regolith-sem::EntityKind` per Q1 with the
   domain kinds rule packs quantify over (holes, bends; nets exist
   but carry no queryable fields) and populate them in
   `lower.entities` from the typed CST, including whatever Q4 parser
   promotions that requires (`../../spec/toolchain/grammar.ebnf` in lockstep, fuzz targets
   inherit). Every populated field a `forall` can project is typed,
   deterministic, and query-engine-reachable (WO-08); ambiguity stays
   E0301 data (INV-18).
   [The ELEC half (nets with queryable fields, board-domain
   entities) was this WO's recorded remainder -- CLOSED by WO-87
   (D198), 2026-07-10: `regolith-lower::board_entities` populates
   Instance/Net + the board-correctness domains from a board's
   declared topology, `Net` gained its `known_measure_keys`
   vocabulary, and the registry-records payload feeds record facts
   into rule eval.]
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
   (Python-side, magnetite records). The allocation loop itself stays
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
design-log `2026-07-06-cycle-19.md`), `../../spec/toolchain/23-lowering-output-surface.md`
flipped to normative, AD-22 added to `../../spec/toolchain/00-architecture.md`.

CORRECTION (2026-07-08, D125, owner-authorized): the cuts note below
names `parts:` per-line orbit constructors as the blocking parser
promotion for deliverables 2/3/4. This was factually wrong -- `parts:`
orbit lines instantiate sub-parts/assemblies, not hole/bend geometry
(see `../../spec/toolchain/23-lowering-output-surface.md` Q4(a) and
`../../design-log/2026-07-07-cycle-23.md` sec. E). The real blocking
promotion is `then:` claim-scope feature constructor calls
(`Bore(...)`, `PatternOf<...>(...)`, etc.), already partially walked
per-line by `crates/regolith-lower/src/claims.rs`. Every `parts:`
reference in the paragraphs below is historical record of the
cycle-19 dispatch's (incorrect) reasoning and is left verbatim; read
it as `then:` claim-scope constructors per this correction.

UPDATE (cycle 23): deliverable 2 is now DONE against the corrected
surface. `regolith-lower::claim_scope` is the shared `then:`
claim-scope walk (one traversal for deliverables 2/3/5);
`regolith-lower::entities::build_entities` now emits `Hole`/`Bend`
entities per feature constructor (`PatternOf<...>(n=N)` orbits
expand to N), with typed `diameter`/`depth`/`angle`/`radius`
measures projected under the Q1 well-known keys and reachable
through the WO-08 query engine (`holes`/`bends` base selector).
`EntityKind::from_constructor_word` is the one home for the
constructor-to-kind mapping. Corpus goldens regenerated
deliberately: only content-derived `snapshot_hashes` /
`obligation_keys` shifted (new entities re-key the scope snapshots);
zero new diagnostics, unchanged counts. No parser promotion was
needed after all -- the parser already structures `then:` ctor
lines as `CtorStmt` (the cycle-19 note's premise that they were
swallowed opaque was part of the same Q4(a) misreading D125
corrects).

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
`../../spec/toolchain/grammar.ebnf` update, fuzz-target coverage, then wiring
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

## Cuts recorded this cycle (dispatch, 2026-07-08, D345 branch)

Re-dispatched to close deliverables 3/4/5 against the D125-corrected
surface. Found (and used) a second instance of the SAME D125 pattern:
`connect:` block instance lines (`name: Ctor(a=.., b=..)`) parse
through the shared stmt-block grammar exactly like `then:` scope
constructor lines -- already a structured `Field`/`CallExpr`, not an
opaque island. No new CST production was needed for deliverable 5
either.

**Deliverable 5 (`connect` -> `Mating`) is DONE.** `claim_scope::
connect_calls_in_decl` (the same one-seam module as the `then:` walk)
lifts every connect-block instance line; `contracts.rs::
collect_mating_specs`/`connect_matings` resolve each instance against
its `mating <Name>:` declaration's `align`/`dof`/`effects` fields and
build a real `regolith_ir::Mating`, wired into `build_system_node` in
place of the WO-19-era `matings: Vec::new()` placeholder. The WO-23
rigid-statics feed (`solve_pass.rs`) already consumed this exact
shape (`align` = `at(x, y)` text, `dof_removed` = `fx`/`fy`/`mz`
labels, `effects` = `load(fx=.., ...)` entries) -- proven end to end
with a real fixture (`contracts.rs::
connect_mating_feeds_a_real_statics_reaction_from_source`). A
`pairwise(...) by <Mating>` orbit connection (seen in the corpus,
`examples/systems/cubesat/structure.hema`) is explicitly NOT promoted
(D91's two-sided `a=`/`b=` form only) and is skipped with a log
rather than guessed at -- a real, scoped follow-up if a future
consumer needs orbit-zip matings. The REAL corpus's `mating <Name>:`
declarations spell `align: a.frame = b.frame (contact)` and
`dof: removed=[all]` (not the `at(x,y)`/`fx,fy,mz` shape
`solve_pass.rs` parses), so the corpus's own statics feed still
no-ops today (as before) -- this is `solve_pass.rs`'s own documented
DATA FORMAT note, not a WO-29 gap; teaching it the richer align/dof
vocabulary is a `solve_pass.rs`-owned follow-up, out of this
dispatch's scope (deliverable 5 is the LOWERING, not the solve-input
vocabulary).

**Deliverable 3 (feature/stage program emission) is DONE, SCOPED.**
Per Q2 (D89): a new `BuildPayload` field
(`feature_programs: Vec<regolith_ir::FeatureProgram>`, schemars-
authored in `regolith_ir::feature_program`), `SCHEMA_VERSION` bumped
6 -> 7 (one bump), `make schema` regenerated
(`python/regolith/_schema/models.py` gets `FeatureProgram`/
`FeatureOp`/`ResolvedFeatureParam`), drift-check green. Population
reuses the SAME `then:` claim-scope walk deliverable 2's entity
projector reads (`claim_scope::feature_calls_in_decl` -- one
traversal, two consumers, per the Q4(a) corollary): each
`Bore`/`CBore`/`Pierce`/`Bend` constructor becomes a `FeatureOp` with
its well-known scalar measures, each Cause-tagged (INV-21) from the
value-source keyword vocabulary.

SCOPE NOTE (found, not invented around): this WO's own acceptance
fixture, `examples/tracks/hematite/sheet_bracket.hema`, constructs its
`Blank`/`Pierce`/`Bend` features against a `profile BracketFlat`
`walk:` body -- sketch/profile geometry (outline points, in-plane hole
centers) that is a SEPARATE, still-opaque surface (WO-11's Walk ->
SketchClosure question, an explicit WO-29 non-goal, listed in this
file's own "Non-goals" section). `regolith-lower`'s current structured
surface can populate scalar feature parameters (diameter/depth/angle/
radius) but cannot populate a `Sketch` (real outline/hole-center
geometry) without that promotion landing first. This means the
literal acceptance criterion ("yields a feature program the EXISTING
WO-22 interpreter accepts and realizes to STEP") is NOT met this
cycle -- the real, schema-versioned producer infrastructure Q2
decided on is in place and tested, but wiring it to
`regolith.realizer.mech.schema.FeatureProgram`'s full contract (real
`Sketch`/`Point2` shapes) is the next dispatch's job once WO-11's
surface is promoted. Recorded here rather than faked with invented
geometry.

**Deliverable 4 (binding-requirement bridge) is NOT DONE this
cycle -- a genuine mapping ambiguity, escalated rather than
invented.** Q3 (D90) decided the SPLIT (Rust emits raw
`BlockRequirement`-shaped capability demands; Python derives the
`ComponentCandidate` screening table from magnetite registry records)
but did not name WHICH structured lowering-output field a block's
`min_capabilities` demand should be projected from. Investigated:
`ContractGraph::budgets` (`contracts.rs`) is the closest existing
structured surface (`budget name: limit` statements already lowered
to `regolith_ir::Budget`), but it is populated as a single FLAT pool
across the whole build with NO owning-declaration attribution --
`build_contract_ir`'s budget loop pushes into `out.budgets` with no
subject/decl-name field, so there is today no sound way to group a
budget statement back to the `.cupr` block it demands FOR without
guessing (e.g. assuming "the enclosing decl" -- which the code
doesn't currently track at that loop iteration either, though it
could be added). Rather than invent a mapping this WO's design pass
never decided (Q3 named the RUST/PYTHON split, not the SOURCE
FIELD), this is escalated for the next dispatch: either (a) extend
`Budget`/`ContractGraph` to carry the owning declaration name (a
small, mechanical change) and treat each block's budgets as its
`min_capabilities` demand, or (b) if `budget:` statements are NOT the
intended capability-demand vocabulary (they read as ceilings the
block itself must not exceed, not demands ON a supplied component),
identify the actual cuprite/elec source construct WO-24's
`BlockRequirement` was forward-authored against and confirm it
against `docs/spec/regolith/10-domain-binding.md`/cuprite/05 before
implementing. The Python-side candidate-table derivation (magnetite
`RecordStore` records -> `ComponentCandidate`) is also unwired,
gated on the same question (a `ComponentCandidate.capabilities` map
needs to know which record-body fields are capability amounts, and
`magnetite/records.py::Record.body` is still opaque/untyped in Python
per its own docstring -- "the concrete record bodies are parsed by
the Rust front-end like any source").

ADDENDUM (2026-07-08, owner-authorized investigation pass -- D4 now
DONE, see the RESOLUTION note at the end): the source construct IS
unambiguously named in the specs; the only thing missing was a parser
production for the shape it lives in, which this dispatch then built.
The investigation finding is left verbatim below as the record of how
the construct was identified.

- `budget:` is confirmed NOT the right vocabulary. `docs/spec/regolith/
  10-domain-binding.md` sec. 1 rows `budget` ("error budget, power
  budget, timing budget, noise budget" -- closure-arithmetic
  ceilings) and `interface demands` / `interface promises` ("max
  load capacitance... " vs "drive strength, timing..." -- per-block
  capability matching) as DISTINCT regolith concepts. `docs/spec/cuprite/
  09-hdl-coverage.md` sec. 1 (SV interfaces / modports row) names
  "cuprite interfaces + roles (regolith/04 contracts)" as the
  mechanism carrying "CONTRACTS (promises/demands with evidence)" --
  this is a second, independent citation for the same answer.
- The construct WO-24's `BlockRequirement` was forward-authored
  against is `docs/spec/cuprite/05-computer-track.md` sec. 2: an
  `architecture for <Computer>:` decl's `resources:`/`memories:`/
  `peripherals:` sub-blocks, each entry a stdlib block contract
  (`executor`, `memory`, `mover`, `fabric`) carrying a `promises:`
  keyword argument (e.g. `cpu0: executor(promises: >= 20Mops f32
  sustained)`, `examples/systems/cubesat/kestrel.cupr` lines 165-177).
  cuprite/05 sec. 2 names these explicitly: "Execution resources are
  abstract blocks with promises" -- matched at `bind` time against a
  candidate `vendor(...)` record's own capability table, i.e. exactly
  WO-24's "screened by capability arithmetic" component-binding step.
- BUT this construct is NOT structurally lowered today, and not for
  the `parts:`/`then:` reason D125 already corrected -- a DIFFERENT,
  narrower gap. Checked the real CST
  (`crates/regolith-syntax/tests/snapshots/
  snapshots__cst@examples_systems_cubesat_kestrel_cupr.snap`, lines
  2096-2230): `architecture`'s body already parses generically into
  `Field`/`CallExpr`/`ArgList` nodes (`resources:` -> `cpu0:` ->
  `CallExpr(executor, ArgList(NameRef(promises)))`), but the
  `promises: >= 20Mops f32 sustained` VALUE inside the call's arg
  list is not itself parseable -- the parser has no grammar for a
  comparison-bearing keyword-argument value inside a `CallExpr`
  `ArgList`, so it bails to an `OpaqueIsland` right after the
  `promises` token (confirmed for all four resource/memory entries in
  the fixture). `regolith-ir::nodes::Interface` already has a
  `promises: Vec<PromiseSlot>` field with a real extraction path
  (`sub_block_fields(decl.syntax(), "promises")`) for the SEPARATE
  `interface X: promises:` indented-block form used by roles/pads/
  bores -- that mechanism does not apply here because `architecture`'s
  promises are inline call kwargs, not an indented sub-block, and
  `crates/regolith-lower/src/contracts.rs`/`claims.rs` have no
  `architecture`/`resources`/CallExpr-kwarg walk today (grepped,
  zero hits).
- Net: closing D4 needs a grammar/parser promotion (typed
  comparison-valued kwargs inside `CallExpr` `ArgList`s, or a
  dedicated `resources:`-entry CST shape) BEFORE either a
  `BlockRequirement` Rust projection or a Python `ComponentCandidate`
  derivation can be written against real data -- the same class of
  "larger than a same-dispatch addendum" prerequisite this WO already
  named for the `parts:`/`then:` promotions (D91), not a small
  mechanical field addition. NOT implemented this pass; recommend the
  next dispatch scope a `architecture`-resource-promises parser
  promotion explicitly (grammar.ebnf update, fuzz coverage, then wire
  `regolith-lower` to emit a `BlockRequirement`-shaped IR node keyed
  by the owning resource name, only after which the Python
  `ComponentCandidate` derivation from magnetite `RecordStore` records
  can be typed against it).

RESOLUTION (2026-07-08, owner-authorized -- D4 DONE, design-log D126):
the recommended promotion above was executed this same dispatch.
1. Parser: `name: <value>` keyword arguments inside a `CallExpr`
   `ArgList` now structure into a typed `KeywordArg` CST node
   (`crates/regolith-syntax`, `grammar.ebnf` + a fuzz-corpus seed in
   lockstep); the kestrel.cupr CST golden regenerated, zero new
   diagnostics. The comparison-bearing bound is a structured
   `UnaryExpr`/`BinExpr`; trailing qualifier residue (`f32 sustained`)
   sweeps to a bounded opaque island so the arg list stays balanced.
2. Rust: `regolith-lower::block_requirement` walks each
   `architecture for ...:` decl's `resources:`/`memories:`/
   `peripherals:` entries and emits a schema-versioned
   `regolith_ir::BlockRequirement { owner, block, contract, demands }`
   into a new `block_requirements` `BuildPayload` field. RAW demands
   only (spelled comparator + value text), the same raw-text discipline
   deliverable 3 uses. `SCHEMA_VERSION` bumped 7 -> 8 (one bump),
   `make schema` regenerated; goldens re-keyed (schema-version folds
   into every content address -- counts + diagnostics unchanged).
3. Python: `regolith.realizer.elec.bridge` screens the raw demands into
   the numeric WO-24 `BlockRequirement` and derives `ComponentCandidate`s
   from magnetite `RecordStore` records (typed `Record.capabilities` slice
   added). D90 split honored: Rust emits raw demands, Python screens.
   Only `>=`/`>` demands become minimums (the candidate>=minimum
   direction WO-24's `_satisfies` models); `<=`/`==`/`<` ceilings are
   logged + skipped, not force-fit. This un-gates WO-24's bridge cut:
   an end-to-end test drives raw payload -> screening models -> the
   existing allocation search to a bound pin with no hand-built
   requirement fixture.

## Non-goals (stay in their owning WOs)

- Rule evaluation, `resolves:`, E0601/E0603/E0604, reference packs,
  `rules test|try` (WO-28); realizer geometry/binding logic (WO-22 /
  WO-24); allocation-search internals (orchestrator, done).
- Elec behavioral bodies + INV-16 `ConverterGraph` feed -- the
  separate WO-05-residual item rides WO-24's next slice, not this WO.
- Walk constraint-surface typing / Walk -> SketchClosure (WO-11
  surface question, WO-23's other cut).
- Realized-fact discharge, manufacturing outputs (WO-25).
