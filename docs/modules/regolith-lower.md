# regolith-lower

The pass-pipeline driver (AD-17, `docs/spec/toolchain/00-architecture.md`
sec. 17): parsed source -> entity DB snapshots -> semantic checks ->
contract IR -> content-addressed obligations -> (compile only) static
discharge. A PURE function of source text -- no IO, no rendering, and
it never returns `Err`; a failing build is diagnostics in the output
(AD-7). All IO (file discovery/read, evidence-cache load/store) stays
in `regolith-api::Session`; the ONE diagnostic renderer stays invoked
from `regolith-api`. Regolith reference:
`docs/spec/regolith/06-execution-model.md`,
`docs/spec/regolith/07-claims-and-evidence.md` sec. 2.

This doc covers the crate's top-level entry points
(`crates/regolith-lower/src/lib.rs`) plus one section per pass
submodule below, added as the T-0002 sweep continues crate-by-crate.

## Pipeline entry points

<a id="join-physical-lines"></a>
### `join_physical_lines`

Rejoins a CST node's text into one line: each physical line has its
trailing `#` comment stripped, then all lines are joined with a single
space. Text-level scanners across this crate (net member tuples, rule
`demand:`/`advise:` values, stage `process=(...)` kwargs) read a
field/statement's spelled RHS off raw node text rather than a fully
structured value node (the grammar only partially structures
parenthesized argument lists, AD-3's lossless-degrade stance). Those
values can legally wrap across physical lines inside a balanced
`(`/`[`, so a naive `text.lines().next()` scanner silently drops every
continuation line with no diagnostic (this was F151, a false-pass
mechanism). ONE home for the join so every such scanner shares it
(NO DUPLICATION).

<a id="parse-sources"></a>
### `parse_sources`

Parses every `SourceFile` into a `ParsedFile`, preserving the caller's
order (`Session::discover_files` already sorts for determinism, AD-6;
this pass does not re-sort). The first stage both `lower` and
`lower_and_discharge` share.

<a id="lower"></a>
### `lower`

Runs passes 1-5 (`parse` through `lower.claims`): the `check()`
pipeline. Always materializes a full `LowerOutput`; never `Err`. Takes
the orchestrator-resolved `RealizedInputs` (WO-42 deliverable 3,
AD-25/D128) -- resolving a digest against the WO-30 store is the
caller's IO, done before this function is ever called (AD-17).

<a id="lower-with-lint-config"></a>
### `lower_with_lint_config`

Same as [`lower`](#lower), but promotes/silences `Lint`-family
diagnostics per a `regolith_diag::LintConfig` (WO-40 deliverable 4:
`magnetite.toml [lints]`, `deny` -> `Error`) at the very end of the
batch, in the ONE place (`regolith_diag::apply_lint_config`) severity
changes.

<a id="lower-and-discharge"></a>
### `lower_and_discharge`

Runs passes 1-6 (adds `lower.discharge`): the `compile()` pipeline.
Consults and updates an `EvidenceCache` for the statically
dischargeable toy subset (WO-13); a second call over the same sources
hits the cache. `registry_version` is the harness model-registry
version (Python-side, AD-1), folded into every evidence-cache key so a
model upgrade forces re-verification (BE-1/INV-1).

<a id="lower-and-discharge-with-lint-config"></a>
### `lower_and_discharge_with_lint_config`

Same as [`lower_and_discharge`](#lower-and-discharge), with the WO-40
`[lints]` promotion step (see
[`lower_with_lint_config`](#lower-with-lint-config)).

## Pass submodules

<a id="block-requirement"></a>
### `block_requirement`

Pass 3c (WO-29 deliverable 4): the binding-requirement bridge payload
field. Projects each `.cupr` `architecture for <Computer>:` declaration's
abstract resource blocks (`resources:`/`memories:`/`peripherals:`
entries) into `regolith_ir::BlockRequirement` records, reading the raw
capability demand off each entry's `promises:` keyword argument. Source
construct: cuprite/05 sec. 2 and regolith/10 sec. 1's `interface
promises`/`interface demands` rows, not the `budget` row.

<a id="board-entities"></a>
### `board_entities`

The board entity-population pass (WO-87, D198): declared-topology
extraction for a `board` decl, committing elec structural entities
(`EntityKind::Instance`/`Net`) and derived board-correctness domains the
`std.board_correctness` packs (WO-79, charter 36) quantify over. Per
D198, this pass reads only what the source spells (`then:` vendor
instances, `nets:` membership tuples, `straps:` bindings) plus the
registry-records payload (`crate::registry`) for record facts; it never
computes placement/routing-aware topology.

<a id="calcite"></a>
### `calcite`

Pass 3d (WO-47 deliverable 4, WO-48 slice A): the calcite civil net
disciplines. Runs the front-end-decidable circulation and load-path
compile checks (calcite/03 sec. 3) over every parsed `.calx` file's
typed `CirculationDecl`/`StructureDecl` AST, riding the same AD-23 net
core (`regolith_sem::net_core`) the elec/fluid disciplines use --
`CirculationDiscipline` wired to E0204, `LoadPathDiscipline` wired to
E0208. WO-48 slice A adds the reachability/declaration checks named as
a WO-47 scope cut.

<a id="checks"></a>
### `checks`

Pass 3: semantic checks over lowered entities (ownership,
stages/scopes, profile DOF ledgers, symmetry orbits). Regolith
reference: `docs/spec/regolith/05` sec. 3/5, `docs/spec/regolith/06`.
WO-19's per-decl entity granularity does not yet populate
`PredictedDelta`/`BorrowTable`/`StageGraph`/`Walk` inputs, so this pass
runs each checker over the currently-empty structured inputs it does
have; real diagnostics start flowing the moment a later WO structures
more grammar, with no pipeline change needed.

<a id="claim-scope"></a>
### `claim_scope`

The ONE `then:` claim-scope walk (WO-29 Q4(a) corrected, deliverable 2;
shared by passes 2/3/5 per the design corollary -- NO DUPLICATION,
AD-17). A `then:` scope holds feature constructor lines
(`pilot = Bore(dia 28mm, ...)`), each structured by the parser as a
`SyntaxKind::CtorStmt`. `feature_calls_in_decl` yields one `FeatureCall`
per constructor call; `parts:` orbit lines (sub-part instantiation) are
explicitly NOT this walk's job (`../design/23-lowering-output-surface.md`
Q4(a)).

<a id="contracts"></a>
### `contracts`

Pass 4: structured contract IR (interfaces, budgets) plus conformance
checks. Regolith reference: `docs/spec/regolith/04-contracts.md`. Only
the structured surface WO-05 exposes is lowered: an `interface` decl's
own name (its `roles:`/`promises:`/`spec:` bodies are opaque islands,
recorded as skipped); a decl's structured `budget name: limit`
statements become `regolith_ir` `Budget`s and are checked with
`close_budget` when the limit is a literal quantity.

<a id="converter"></a>
### `converter`

Pass 3 (converter-graph half): build the continuous/discrete converter
graph (INV-16) from typed elec behavioral bodies and run the
within-domain acyclicity check. Regolith reference:
`docs/spec/cuprite/03-behavioral-layer.md` sec. 1/1a (event-bounded
hybrid semantics, ZOH delta-by-type rule), `docs/spec/regolith/13`
INV-16. Feeds typed `ports:`/`spec:`/`OnBlock`/`RegAssign` nodes into
`regolith_sem::converter`, which previously had no real caller.

<a id="discharge"></a>
### `discharge`

Pass 6: static discharge of the WO-13 toy closed-form subset plus the
WO-23 L2 stiffness-network tier, cached by obligation content hash.
Regolith reference: `docs/spec/regolith/07` (evidence, margin rule),
`docs/spec/hematite/03-contracts-and-assemblies.md` sec. 4 item 3. Two
static models are wired end-to-end: the toy `value + eps <= limit`
margin rule (`model_id = "toy_budget_sum"`) and the L2 lumped stiffness
network (`model_id = "l2_stiffness_network"`) behind
`mech.stiffness(<node>) >= <limit>` claims.

<a id="entities"></a>
### `entities`

Pass 2: AST -> declaration table -> per-scope `EntityDb` snapshots.
Regolith reference: `docs/spec/regolith/05` sec. 1/3,
`docs/spec/regolith/13` INV-18 (ambiguity is data), INV-21 (every
non-literal slot carries a `Cause`). One scope per top-level `Decl`
(its name); a duplicate declaration name is `E0301` data, not a panic.
Only the structured subset (`Field`/`CtorStmt`) is walked -- everything
else is an `OpaqueIsland` and contributes no entities.

<a id="extract"></a>
### `extract`

The routed-geometry extraction seam (WO-32 deliverable 2; D99/F102).
ONE module that reads a realized-geometry record and, for a path/role
selector, produces the typed hydraulic parameters fluorite lowering
needs -- flow areas, length, bend angles/radii, roughness class,
elevation change -- plus wall compliance and the Korteweg wave speed.
This is the shared seam WO-34 (wire runs) also reads. Purity (AD-17):
a pure function of its inputs, no IO.

<a id="feature-program"></a>
### `feature_program`

Pass `lower.programs` (WO-29 deliverable 3, completed by WO-51): the
feature/stage program payload, built from the same `then:` claim-scope
walk (`claim_scope::feature_calls_in_decl` -- one traversal, two
consumers, AD-17). Per D150/D151/D152 it adds the typed sketch payload
per referenced profile, a named `E0443` warning for every `then:` op
with no v1 projection (never a silent truncation), and `flow_paths`
derived from the feature-op chain.

<a id="flownet-lower"></a>
### `flownet_lower`

Pass 3d (WO-32 deliverable 3): fluorite flownet elaboration. Walks
every parsed `.fluo` file's typed `flownet` AST (fluorite/03 sec. 1-2)
into an in-memory `FlownetPayload`: nodes, the reference datum, one
`FlowEdge` per declared edge, and symbolic state domains. Hydraulic
parameters for `from=` edges are extracted through the shared
`crate::extract::extract_path` seam. Purity (AD-17): this pass reads
no IO; the orchestrator resolves realized inputs before calling in.

<a id="fluid"></a>
### `fluid`

Three subnet checks: the two front-end-decidable ones (imposer
presence, terminal joining) plus, as of WO-49, the FOPEN-1
medium-mismatch check -- decidable at this layer because its binding
surface (`impl FluidPort<medium=...>`, fluorite/02 sec. 2) is pure AST.
The wall-compliance checks (fluorite/03) still need WO-32
realized-geometry data and are not decidable here (see the WO-31
handoff note).

<a id="frame-lower"></a>
### `frame_lower`

Pass 3d (WO-48 deliverable 3): calcite `frame` payload elaboration.
Walks every parsed `.calx` file's typed `structure` AST (calcite/02
sec. 6) into an in-memory `FramePayload` (calcite/03 sec. 4): joints
synthesized from member anchors and declared supports, members with
role/geometry/section/material, supports, literal load entries, and
the require group's combination-set ref. Purity (AD-17): reads no IO;
section/material refs are name-only pins resolved elsewhere.

<a id="harness-lower"></a>
### `harness_lower`

WO-34 deliverable 2: cuprite `harness:` elaboration (D99). Walks every
parsed file's typed `harness` AST into a `HarnessLowerReport` carrying
one `HarnessPayload` per harness. A run's `along <structural refs>`
path is extracted through the same shared `crate::extract::extract_path`
seam `flownet_lower` uses -- never a second copy. A `route: free` run
lowers with an unresolved length (INV-21: no fabricated value).

<a id="lints"></a>
### `lints`

Pass: v1 style/advisory lints (WO-40 deliverable 2), Warning severity
by default, over `regolith-diag`'s `Lint` code family. Runs inside the
same pipeline every other pass runs in (AD-24: CLI and LSP see
identical results by construction). Regolith reference:
`docs/spec/toolchain/24-developer-tooling.md` sec. 5. v1 covers three
of the six named lints (`unused_import`, `retired_vocabulary_usage`,
`todo_assume_inventory`); the other three need a cross-file
usage/scope graph this pass does not have yet.

<a id="output"></a>
### `output`

The pipeline's input/output surface: source files in, parsed files and
the assembled build payload out. Regolith reference:
`docs/spec/regolith/06`, `docs/spec/regolith/07` sec. 2. `LowerOutput`
is the pure-Rust, no-IO shape `regolith-api` wraps into `BuildPayload`
(AD-17).

<a id="ownership"></a>
### `ownership`

Pass 3 (ownership / region / symmetry half): flow the now-typed
`OwnershipStmt`/`RegionStmt`/`SymmetryStmt` CST nodes into the
`regolith-sem` mechanisms that were implemented and unit-tested but had
no caller feeding real parsed input. Regolith reference:
`docs/spec/regolith/05-ownership-and-queries.md` sec. 3/5,
`docs/spec/regolith/13` INV-4 (symmetry soundness), INV-5 (ownership
finality), INV-23 (region exclusivity). Per declaration scope it builds
a `BorrowTable` + `EntityKind::Region` entities + an `OrbitTable` and
runs the sem checks.

<a id="power"></a>
### `power`

Pass 3e (WO-132): the cuprite power-distribution net discipline
(charter toolchain/43-power-distribution.md secs. 1-2, D248/AD-42).
Runs the front-end-decidable power discipline checks over every
parsed `.cupr` file's typed `PowerDecl` AST, riding the same AD-23 net
core (`regolith_sem::net_core`) the elec/fluid/calcite disciplines use
-- `net_core::PowerDiscipline` wired to E0212 (at least one source
imposer per subnet). Rules 2-4 (undeclared parallel source paths,
unprotected ampacity transitions, load reachability -- E0213/E0214/
E0215) are hand-written directed graph walks over the `feeders:` edge
list, the same scope split `calcite.rs` uses for its own reachability
checks (imposer-counting stays a `NetDiscipline` plugin; edge walks
live here). The apparatus vocabulary (`service`, `generator`,
`transformer`, `switchgear`, `panelboard`, `mcc`, `feeder`, `busway`,
`breaker`, `fuse`, `relay`, `motor`, `load`) needed no new grammar:
each is an ordinary constructor name used as a `feeders:` edge's
value, exactly like fluorite's `Pipe`/`Valve`/`Pump`.

`emit_power_payloads` (WO-133 deliverable 2, coordinator adjudication
F-WO133-1): CST -> `PowerNetPayload` emission. Buses/loads read their
declared per-item properties (`PowerDecl::bus_items`/`load_items`,
`regolith_syntax`); branches read each `feeders:` edge's apparatus
kwargs (`kva`, `pct_z`, `length`, `frame`, ...). The schema stayed
FROZEN (D272 spent): a REQUIRED field (`Bus.nominal_voltage`/`phases`,
`Load.connected_kva`, `Transformer.kva`, `Feeder.length`,
`ProtectiveDevice.frame`) with no declared source refuses emission for
the WHOLE net (E0217, `POWER_PAYLOAD_FIELD_UNRESOLVED`) rather than
fabricating a value (D250.3 exactly) -- mirrors this module's own
E0212-E0216 "refuse, never guess" posture. `check_cross_standard_mix`
(E0216, `POWER_CROSS_STANDARD_MIX`, D255) flags a bus touched by
apparatus edges declaring disagreeing `std=` standard families.

<a id="query"></a>
### `query`

Pass 3 (query-resolution half): resolve `refer <name>` references
against each declaration scope's committed entity-DB snapshot (WO-08
semantics, INV-06/18). Regolith reference:
`docs/spec/regolith/05-ownership-and-queries.md` sec. 2/5,
`docs/spec/regolith/13` INV-6 (snapshot isolation), INV-18 (reference
determinism). Feeds real, parsed references into `Query::resolve`
against a per-scope snapshot; by-name granularity matches `ownership.rs`.

<a id="realized-input"></a>
### `realized_input`

The realized-IR input channel (WO-42 deliverable 3, AD-25/D128).
`lower()`/`lower_and_discharge()` are pure functions of (sources,
realized-IR inputs): the orchestrator resolves realized-domain IR
digests against the WO-30 content store and hands the resolved bytes in
here, preserving AD-17 purity. This module is the pure data carrier
only; resolving a digest to bytes is the caller's IO, done before
`lower()` is ever called.

<a id="registry"></a>
### `registry`

The registry-records payload (WO-87, D198): loaded record fields
reaching the Rust rule engine through the existing WO-42 realized-input
channel as a `kind: "registry.records"` payload. Python's magnetite
`RecordStore` is the ONE record loader (the one-loader law, D198); this
module deserializes that payload and never reads TOML or does IO --
the payload is an input to lowering like any realized IR.

<a id="removal"></a>
### `removal`

The declared material-removal vocabulary (charter 34 phase 1,
D200/WO-77): the ONE home for the four family constructors' parameter
signatures, slot-form parsing, and constructive validation. Both
consumers of the AD-17 claim-scope traversal -- the `lower.programs`
projection (`feature_program.rs`) and the entity projector
(`entities.rs`) -- read family parameters through this module, so an
emitted `FeatureOp` and the rule-pack entity that quantifies over it
can never disagree. Slot forms are exactly the existing value-slot
vocabulary (D200).

<a id="rule-engine"></a>
### `rule_engine`

The WO-28 rule-pack engine core: pack index, attachment resolution,
the binding environment, and the deliberately-narrow demand evaluator
shared by every consumer -- `resolves:` eager resolution (`entities.rs`),
static-rule evaluation (`rules.rs`, E0601/E0604), rule-obligation
lowering (`claims/rule.rs`), and the `rules test|try` CLI runners
(`regolith-api`). Regolith reference:
`docs/implementation/design/21-rule-packs.md` (D-B/D-C/D-E),
hematite/02 sec. 10, AD-21.

<a id="rules"></a>
### `rules`

Rule-pack static checks (WO-28 partial): the checks that need only the
typed `RuleDecl` CST plus the `EntityKind` measure vocabulary, not full
query-engine matching or demand-expression evaluation. Regolith
reference: `docs/spec/toolchain/21-rule-packs.md` sec. 3 (E06xx
family), design doc D-C (union composition, collision is an error),
D-E (a predicate referencing an unprovided fact is a compile error,
E0603). Emits `RULE_NAME_COLLISION` (E0602) over attached rule packs in
file-then-source order (AD-6 determinism).

<a id="solve-pass"></a>
### `solve_pass`

Pass 5b (WO-23): rigid statics over each system node's matings,
feeding computed reaction envelopes into obligations' `given.loads` so
promise obligations carry real computed loads, not declared-only ones.
Regolith reference: `docs/spec/hematite/03-contracts-and-assemblies.md`
sec. 4 item 2, `docs/spec/hematite/05-lowering.md` (L2 solves). The
solve itself lives in `regolith_ir::solve::statics` (AD-1); this pass
only extracts the problem from the contract graph and folds results
into the obligations.

<a id="waivers"></a>
### `waivers`

Pass 5b: `waive ...:` blocks -> the waiver ledger + honesty checks.
Regolith reference: `docs/spec/regolith/12-overrides-and-hints.md` sec.
3 (the rung-7 `waive` construct) and `docs/spec/regolith/13` INV-2
(ladder safety), INV-12 (waiver honesty). Runs AFTER claim lowering so
it can match each declared waiver against the obligations the pipeline
actually emitted; produces a `WaiverRecord` only for a matched
obligation (INV-2 realized structurally, never a bare acceptance of an
unmatched name).

<a id="claims"></a>
### `claims` (module cluster: `claims/mod.rs`, `common`, `comparison`, `compute`, `conformance`, `cost`, `fluid`, `frame`, `plan`, `require`, `rule`)

Pass 5: `RequireClaim` -> `Claim` -> `Obligation`, one per claim line;
one `SnapshotRecord` per committed entity scope. Regolith reference:
`docs/spec/regolith/07-claims-and-evidence.md` sec. 2,
`docs/spec/regolith/13` INV-1 (obligation-key sensitivity). Each
`RequireClaim` group's `Field` line becomes one `Obligation`;
`subject_ref` is the enclosing declaration's `EntityDb::snapshot_hash()`
(AD-18). The submodules split this pass by claim kind: `common`/
`comparison` hold shared predicate-scanning helpers; `compute` builds
`ClaimForm::Compute` obligations (WO-33 D98); `conformance` builds the
EOPEN-15 demand-implication obligation; `cost` lowers `mfg.cost(...)`
claims (WO-54); `fluid` elaborates flownets into `kind: flownet`
obligations; `frame` covers the 03-lowering sec. 5 frame-payload claim
forms (WO-48); `plan` covers the five `cam.*` claim kinds (WO-67/69);
`require` lowers a general `require` group's comparison/`within`
predicates (WO-33 D98 deliverable 3); `rule` builds one obligation per
attached rule-pack match (WO-28).
