# WO-19: Lowering pipeline (end-to-end assembly driver)

Status: in-progress (wired end-to-end + green; depth pass landed cycle
12 -- BE-2/BE-3/BE-5/BE-6 done; BE-4 monomorphization/INV-11 CUT CLOSED
this cycle -- use-site generics typed in WO-05, expanded in regolith-lower;
BE-9 rung-7 `waive` ladder + ledger landed -- pass 5b `regolith-lower::
waivers` builds the waiver ledger onto `payload.ledger`, INV-02/INV-12
un-xfailed, see TRIAGE BE-9; cycle 15 -- the orchestrator candidate/
discharge loop now reaches REAL verdicts: `orchestrator.translate`
recovers the comparator from a `require`-placeholder claim's `rhs`
(the core sets `op="require"` and carries `>= 6` in the predicate),
which was the true cause of `resolutions=0`/all-deferred discharge;
INV-03 + the reachable INV-26 defaults are now real, see TRIAGE C15)
Depends: WO-05..WO-13 (the libraries it wires), WO-18 (payload surface);
gates WO-15 golden corpus, the bulk of WO-17, WO-14 real inputs

> STATUS (cycle 11): the pipeline is wired end-to-end -- Session::check
> runs passes 1-5, Session::compile adds static discharge against a
> persisted `.regolith/` evidence cache, BuildPayload is typed, schema
> is at v2, `make check` green. Over examples/cubesat the pipeline
> lowers 40 obligations + snapshot records (real, deterministic --
> INV-10 holds; obligations rose 21 -> 40 after the parser
> sibling-ejection desync was fixed, recovering the previously-ejected
> `require` blocks -- see docs/audit/TRIAGE.md). Value sources in nested
> blocks are now reached, so resolutions are Cause-typed and non-empty
> (INV-21 activated); the count is low only because the corpus is
> literal-heavy. RECORDED PARTIAL (needs fuller WO-05 grammar, not a
> defect). The conforming corpus is now clean over cubesat -- parse
> noise was cut 984 -> 31 by treating unknown top-level declarations as
> opaque (not errors) and dropping the false global duplicate-name
> check (INV-18 is scope-aware), then 31 -> 0 on cubesat by fixing the
> comment-led-body desync (TRIAGE cycle 11). Residual corpus parse
> diagnostics (18, all in mech `.hem`) are unrelated domain-body opaque
> constructs (`walk`/`constraints`/`regions`), not top-level ejections.
> Closing this to `done` needs the residual grammar (value-sources ->
> resolutions, impl/for name attribution), per-subject INV-20 gating,
> and INV-11 monomorphization.
>
> DEPTH PASS (cycle 12): the parser now emits a typed CST (promoted
> domain constructs, `SubjectError`/`parse:0193` attribution, comment-led
> bodies), and the remaining WO-19 cuts the grammar now supports are
> implemented:
> - BE-2 (given: population): `claims.rs::given_for_decl` threads a
>   decl's `material`/`materials` fields and `loads:` block child lines
>   into `Given` from the typed `Field` tree. INV-1 mutation half is now
>   green (a material change re-keys the obligation). `TODO(BE-2)` gone.
> - BE-3 (per-subject INV-20 gating): `entities.rs::decl_is_poisoned`
>   drops any decl whose subtree carries a `SubjectError`/`Error` node at
>   pass 2 (the single choke point); clean siblings proceed. Shared by
>   entities/checks/contracts/claims so all passes agree.
> - BE-5 (structural Cause): `entities.rs::cause_from_value_source`
>   derives the `Cause` from the `ValueSource`/`CauseValue` node kind
>   (in[..]->Planner, derived->Obligation, allocated->Budget,
>   free/default->Dfm) instead of a text scan.
> - BE-6 (INV-13 obligations): `contracts.rs` collects `ConformanceEdge`s
>   for impl (top-level Decl + in-body `ImplStmt`), `by extern` linkage,
>   and import edges; `claims.rs` emits one `<upper> conforms <lower>`
>   obligation per edge. Corpus obligations rose (cubesat 40 -> 93,
>   gear_reducer 4 -> 15, buck_converter 4 -> 6; no drop).
> Golden deltas (REGOLITH_UPDATE_GOLDEN=1): obligations up as above;
> resolutions unchanged (2/0/0 -- corpus is literal-heavy; the Cause
> VALUES changed structurally but the count did not); snapshots/evidence
> unchanged; zero new diagnostics.
>
> BE-4 (INV-11 monomorphization) CUT CLOSED (this cycle): WO-05 now types
> generic USE-sites (`PatternOf<TappedHole<M3>>` -> `InstExpr`/
> `GenericArgs`, disambiguated from claim comparisons `a < b`), so
> `checks.rs::monomorphize` expands each generic declaration over its
> DISTINCT typed instantiations exactly once. Two totality guards fall
> out of the proof argument and are emitted as diagnostics (values): an
> instantiation whose arity does not match its declaration is an
> un-expandable point (E0504 GENERIC_ARITY_MISMATCH), and a generic
> declared and referenced nowhere is a dead generic (E0503 DEAD_GENERIC).
> Dead-generic detection uses a whole-compilation identifier census so a
> generic bound only through conformance/roles (name recurs) stays quiet;
> the conforming corpus emits ZERO monomorphization diagnostics and no
> obligation drop. `test_inv_11_monomorphization_totality.py` is now a
> real end-to-end fixture (un-xfailed): arity mismatch, dead generic, and
> a clean-expansion negative control. RESIDUAL (not INV-11): the
> per-instantiation static-CHECK bodies (numeric checks re-run at every
> expanded point) are future work once those checks have structured
> input; the expansion SET they will run over is now real. The INV-13
> discharge half (an impl contradicting its spec must FAIL equivalence)
> is Python-harness territory (AD-1), still xfail.
> OWNERSHIP/REGION/SYMMETRY POPULATION (cycle 13, INV-04/05/23 flipped):
> the pass-3 `ownership.rs` module lowers the now-typed `OwnershipStmt`/
> `RegionStmt`/`SymmetryStmt` nodes into real sem inputs -- a per-scope
> `BorrowTable` (role bindings + owned exclusion regions as standing
> borrows), `EntityKind::Region` entities with a `RegionPolicy`,
> `PredictedDelta.modifies`/`.regions_touched`, and an `OrbitTable` built
> by folding `pattern` contributions (new `OrbitTable::contribute`) and
> collapsing on `break`. Three diagnostics now flow to the facade over
> real source: a modify of a borrowed entity (E0302, bidirectional,
> INV-05), a route into an owned exclusion region (E0302, INV-23; a
> declared `join`/arbitration region is exempt), and an `any` over a
> broken/undeclared orbit (E0502, INV-04). `test_inv_04/05/23` are now
> real end-to-end fixtures (honest-pass + deliberate-violation each);
> INV-06 stays xfail (needs WO-08 query resolution + WO-10 scope-entry
> snapshots, not the parser). Golden deltas: none on the corpus
> (obligations/resolutions/snapshots/diagnostics unchanged; the corpus
> declares no conflicting ownership/region/symmetry), only the
> gear_reducer CST insta golden (a `flip about X` line, now typed).
> SYSTEM-NODE POPULATION (cycle 14, INV-07/08/15 flipped): pass 4
> (`contracts.rs`) now builds REAL `SystemNode`s instead of empty ones --
> `BoundaryEntry`/`Reserve`/`FlowEdge`/`Target` from each `system`/
> `assembly` decl's `boundary:`/`reserves:`/`flows:` blocks and its
> `target ... of <Sys>` decls, with target draws bound to reserves and
> child boundaries linked by `parts:` type reference. The three sound L2
> checks in the new `regolith-ir::system` module flow diagnostics to the
> facade: boundary subsumption (INV-07, E0407), reserve over-allocation
> (INV-08, E0432), the system-flow ledger (INV-15, E0420). Each is
> conservative (same-unit interval compare only; declared flow
> participants over-collected via a `name:` text scan so opaque-island
> intents never manufacture a false leak). `test_inv_07/08/15` are real
> end-to-end fixtures (honest-pass + deliberate-violation each). Golden
> deltas: NONE (the conforming corpus declares no boundary/reserve/flow
> violation, so it stays clean; obligations/resolutions/snapshots/
> diagnostics unchanged). INV-19 stays xfail with a revised reason (the
> promise-only contract surface holds by construction; its test needs
> escalation-edge lowering + a two-build harness, not SystemNode
> population).
> QUERY-RESOLUTION WIRING (cycle 15, INV-06/18 flipped): pass 3 gained a
> `query.rs` half that gives WO-08's `regolith-sem::query` engine its
> first caller. WO-05 types `feature`/`refer` as contextual `QueryStmt`
> single-line nodes; `query.rs` commits one `EntityKind::Other(<name>)`
> entity per `feature` into a per-declaration scope-entry `EntityDb`
> snapshot (`PredictedDelta::commit`) and resolves each `refer <name>` as
> a `.only` `Query` against it. Over/under-match is `E0301`
> (`AMBIGUOUS_SELECTION`, INV-18 reference determinism); each scope
> resolves only against its OWN committed snapshot, so a `refer` naming a
> sibling declaration's feature under-matches (INV-06 snapshot isolation).
> `test_inv_06`/`test_inv_18` are now real end-to-end fixtures (honest-pass
> + deliberate-violation each). Golden deltas: NONE (the corpus declares no
> `feature`/`refer`, so obligations/resolutions/snapshots/diagnostics and
> the insta/schema goldens are unchanged). RESIDUAL (not INV-06/18): the
> by-name entity identity is the WO-19 simplification, and the wider
> cardinality vocabulary (`.all`/`.any`/joins) stays unit-tested in
> `regolith-sem`.
> CONVERTER-GRAPH SEAM (INV-16 converter non-instantaneity): pass 3
> (`checks.rs`) now runs the continuous/discrete converter-graph
> acyclicity check via the new `regolith_sem::converter` module
> (`ConverterGraph` -> ZOH delta-by-type rule -> within-domain
> acyclicity -> `E0105 COMBINATIONAL_CYCLE`). The mechanism is SOUND and
> unit-tested in Rust (comparator-feeds-own-threshold legal; combinational
> cycle caught). It runs over an EMPTY graph today because the elec
> `spec:`/`ports:`/converter/`on`-event bodies are still `OpaqueIsland`
> after WO-05 (same posture as the stage-topology seam) -- trivially
> acyclic, real code, no stub. `test_inv_16` stays honest-xfail naming the
> true blocker (WO-05 elec behavioral-body promotion); un-xfail once WO-05
> types those bodies and this pass feeds them into `ConverterGraph`. No
> golden deltas (empty graph over the corpus). See docs/audit/TRIAGE.md.
Language: Rust (`regolith-lower`, NEW crate per AD-17; `regolith-api`
wiring; `regolith-oblig` schema additions; `regolith-py`/facade payload
surface refresh)
Spec: substrate/06 (execution ladder), substrate/07 sec. 2,
substrate/05, substrate/13 (INV-1/10/11/15/17/18/20/21/27);
`00-architecture.md` AD-17 (normative), AD-4/AD-5/AD-6/AD-8/AD-18

## Goal

WO-07..13 landed as standalone, tested libraries with no caller. This
WO builds the one assembly driver (AD-17): parsed source -> entity DB
snapshots -> semantic checks -> contract IR -> content-addressed
obligations -> (compile only) static discharge, populating every
`BuildPayload` field so `check`/`compile` return real data and the
golden corpus and invariant suite have something to bite on.

## Deliverables

1. Crate `crates/regolith-lower/` per AD-17: pure (no IO, no `Err`),
   `lower(sources) -> LowerOutput` and
   `lower_and_discharge(sources, &mut cache) -> LowerOutput`; one
   `tracing` span per pass (`parse`, `lower.entities`, `lower.checks`,
   `lower.contracts`, `lower.claims`, `lower.discharge`); per-subject
   INV-20 gating; deterministic order everywhere (sorted file order,
   source decl order, blessed collections only).
2. Pass 2 (`entities.rs`): AST -> declaration table (imports + name
   resolution; ambiguity is E0301 data, INV-18) -> per-scope
   `EntityDb` snapshots via `PredictedDelta::commit`; every defaulted
   value becomes a `regolith_qty::Resolution` (Cause-typed, INV-21).
3. Pass 3 (`checks.rs`): monomorphization expansion (INV-11), then
   queries, ownership/borrows, stages/scopes, profile DOF ledgers,
   symmetry orbit table -- each producing diagnostics (values).
4. Pass 4 (`contracts.rs`): contract IR construction + Mech/Elec
   ledgers + `close_budget` + conformance checks (INV-13/15).
5. Pass 5 (`claims.rs`): `RequireClaim` -> `Claim` -> one `Obligation`
   per sweep point; `subject_ref` = canonical snapshot hash (AD-18);
   hashes via `Obligation::content_hash` (INV-1 keys).
6. Pass 6 (`discharge.rs`): the WO-13 toy closed-form subset via
   `decide_margin` + `EvidenceCache`; cache hit on second run.
7. `regolith-api` wiring: `Session::check` = passes 1-5,
   `Session::compile` = 1-6 with cache IO in `Session` (`.regolith/`,
   `CacheCorrupt` on corruption); `BuildPayload` becomes typed
   (`Vec<Resolution>`, `Vec<Obligation>`, `Vec<SnapshotRecord>`, new
   `evidence: Vec<Evidence>`).
8. Schema surface: `SnapshotRecord` added to `regolith-oblig`;
   `Resolution`/`Cause` gain `JsonSchema` and join `export_schemas`;
   `SCHEMA_VERSION` bumped; `make schema` regenerated; `_core.pyi`,
   native getters, and facade updated; WO-18's cut deliverable 6
   (obligation-hash round-trip across the FFI) implemented.

## Acceptance

- `Session::check` over `examples/cubesat/` returns non-empty
  obligations, resolutions, and snapshot records; every resolution
  carries a `Cause` (INV-21); double build is byte-identical on
  `payload_json()` (INV-10).
- `compile()` differs from `check()` by evidence: first compile
  discharges the toy subset, second compile hits the cache (WO-13's
  acceptance, now end-to-end).
- INV-20 fixture: a file with a parse/L1 error produces zero
  later-pass span records for that file (observable via pass logging).
- INV-27 fixture: a golden example split across two files joined by
  an import yields identical verdicts, resolutions, obligation keys,
  and snapshot hashes.
- INV-1 fixture: mutating each obligation key component (claim,
  subject, given, record hash) changes the content hash (cache miss).
- `make schema` idempotent, drift check green, ty --strict green;
  `make check` green; every `todo!("STUB WO-19")` gone and its
  `#[ignore]`d tests un-ignored before Status flips to done.

## Implementation notes

Module layout and public stub signatures for `crates/regolith-lower/`
are specified in the cycle-11 design log (Fable architect escalation,
AD-17/AD-18). The crate is scaffolded architecture-first per the stub
convention: types + module layout + `#[ignore]`d tests land, then the
six pass bodies. Decision 2 (AD-18 canonical-encoder move to
`regolith_util::canon`) must land BEFORE WO-19 records any golden
hashes -- migrating `EntityDb::snapshot_hash` changes snapshot values,
and nothing durable pins the old ones yet.
