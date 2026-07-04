# Audit triage (cycle 11)

Disposition of the spec-conformance findings in this directory
(`frontend-conformance.md`, `backend-conformance.md`). Fixed items
landed with tests; deferred items carry greppable `TODO(<id>)` markers
at the code site.

## Fixed (this cycle, with regression tests)

- **BE-1 (HIGH, INV-1)** -- the evidence-cache key now folds the harness
  model-registry version (`Obligation::evidence_cache_key`), threaded
  from Python (`harness.MODEL_REGISTRY_VERSION`) through
  `compiler.compile` -> `_core.CoreSession.compile` ->
  `Session::compile` -> `lower_and_discharge` -> `discharge_static`.
  A model upgrade (version bump) changes every key, so stale evidence is
  never reused; the obligation's version-free `content_hash` (JSON
  interchange identity) is unchanged, so goldens do not drift. Tests:
  `obligation::tests::evidence_cache_key_is_sensitive_to_registry_version`,
  `discharge::tests::model_registry_bump_invalidates_cached_evidence`,
  `discharge::tests::same_registry_version_is_a_cache_hit`, and
  `test_ffi_bridge.py::test_compile_threads_registry_version_across_the_ffi`.

- **FE-5 (HIGH-ish, wrong result)** -- offset-unit tolerances no longer
  apply the absolute +273.15 offset (`convert_delta`, scale-only for
  deltas). Test: `interval::tests::plus_minus_offset_unit_tolerance_is_a_delta_not_absolute`.
- **FE-2 (MEDIUM, INV-21)** -- the `Cause` enum now carries all eight
  INV-21 provenance kinds (added `Extern`, `DerivedIntent`, `Policy`).
  Test: `resolution::tests::all_eight_inv21_causes_render_and_round_trip`.
- **Parser sibling-ejection desync (HIGH, lost obligations)** -- FIXED.
  Root cause: the layout pass does not shift the indent stack for blank
  or comment lines, so a body's `Indent` token can be separated from its
  header by `Newline`/`Comment` trivia (as in `kestrel.cupr`'s
  comment-led `intents:` body). `enter_body_block` and
  `parse_value_and_tail` tested for the body `Indent` after skipping only
  `Whitespace`, so a comment-led body was never entered: it ejected to
  the parent level and its `Indent`/`Dedent` pair desynced the layout
  stack, cascading `parse:0092` errors and dropping the ejected `require`
  blocks (their obligations never lowered). Fix: `enter_body_block` now
  looks PAST `Whitespace`/`Comment`/`Newline` trivia (without consuming
  it) to the body `Indent`, opening the block iff one follows;
  `parse_value_and_tail` delegates to it. Cubesat parse diagnostics
  31 -> 0; whole corpus 79 -> 18 (residual 18 are unrelated mech
  domain-body opaque constructs -- `walk`/`constraints`/`regions`);
  cubesat obligations 21 -> 40 (recovered from the previously-ejected
  `require` blocks). Regression tests:
  `parser::tests::comment_before_body_does_not_eject_the_block` and
  `parser::tests::kestrel_intents_body_retains_require_blocks`; goldens
  `cubesat`/`buck_converter`/`gear_reducer` regenerated.

- **Residual 18 mech parse diagnostics (HIGH-ish, ejected siblings)**
  -- FIXED. The 18 residual `.hem` diagnostics were NOT domain-body
  opaque payloads (as this file previously characterized them) but
  bracket-continuation desyncs: the layout pass did no implicit line
  joining, so a multi-line `()`/`[]` call/interval/import argument list
  emitted spurious INDENT/DEDENT that ejected following siblings
  (`require`/`waive`/`assembly`) to the file top level as
  UNEXPECTED_TOKEN. Fix: `layout.rs::emit_rest_of_line` now tracks
  bracket depth and joins bracketed physical lines into one logical
  line (Python-style), 18 -> 4. The last 4 (`sheet_bracket.hem`) were a
  comment-led machining body ejected by `parse_opaque_stmt`'s
  hand-rolled indent check; promoting `stage`/`setup`/`impl`/`connect`/
  `parts`/`zones`/`boundary`/`flows`/`walk` and policy rules to typed
  CST nodes that use the shared comment-aware `enter_body` closed it,
  4 -> 0. Whole corpus now parses with ZERO parse diagnostics.
  Subject-attributed recovery (`E0193` MALFORMED_IN_BODY on a stray
  in-body closing bracket, attributed to the enclosing decl subject)
  landed alongside, unblocking INV-20 per-subject gating downstream.
  Regression tests in `parser.rs`
  (`examples_have_no_parse_diagnostics`, `promoted_constructs_are_typed_nodes`,
  `stage_impl_and_comment_led_body_are_structured`,
  `walk_body_and_generics_are_typed`,
  `malformed_in_body_stmt_is_attributed_to_subject`).

- **FE-1 (HIGH, INV-17)** -- logarithmic-unit views (substrate/02
  sec. 5a) are now a `regolith-qty` module (`log.rs`): `dB`/`dBc`/`dBi`
  (ratio) and `dBm`/`dBW`/`dBuV` (referenced) view stored-linear
  quantities, with the one sum-reference legality check
  (`log_sum_reference`). `regolith-syntax::checks` wires it at L1, so
  `dBm + dBm` dies with `E0104` (ILLEGAL_LOG_SUM) while `dBm + dBi - dB`
  is a legal power. Tests: `log::tests::{two_referenced_powers_is_illegal,
  link_budget_sum_is_a_power, difference_of_references_is_a_ratio,
  uncancelled_subtracted_reference_is_illegal, linear_db_round_trip,
  sum_legality_is_commutative_in_operand_order,
  view_is_strictly_monotone_so_corners_commute}` and
  `checks::tests::{two_reference_log_sum_is_flagged,
  link_budget_log_sum_is_clean, reference_difference_log_sum_is_clean}`.
- **FE-6 (MEDIUM, INV-9/AD-6)** -- `Interval::new` outward-rounds a
  cross-unit-converted bound (lower down, upper up) and
  `Interval::contains` widens a cross-unit probe by one ULP, so a value
  at the exact converted boundary is never falsely excluded. Test:
  `interval::tests::cross_unit_boundary_value_is_still_contained`.
- **FE-3 (MEDIUM, ASCII enforcement)** -- the layout pass now rejects
  every non-ASCII character in source with `E0194` NON_ASCII_SOURCE
  (batch-emitted up front, like the tab check, at the lexical boundary
  per AD-3/AD-12); a non-ASCII byte was previously swept into an opaque
  island with no error. Tests: `layout::tests::non_ascii_byte_is_rejected`
  and `layout::tests::pure_ascii_source_has_no_non_ascii_diagnostic`.
- **FE-4 (MEDIUM, unit exponents)** -- `Unit::parse_atom` now accepts a
  trailing integer exponent suffix (`m2`, `s2`, `mm3`), so
  `Unit::parse_expr("W/m2")` and `"kg/s2"` resolve to the right
  dimension (substrate/02 sec. 1 heat_flux); an exponent on an offset
  unit is `OffsetInAlgebra`. The `parse_expr` docstring's false
  multi-operator `kg.m/s2` example was corrected to working
  single-operator forms (multi-operator stays the WO-05 hook). Test:
  `unit::tests::parses_unit_exponent_suffixes`. (This one item is in
  `regolith-qty`, the finding's own home; see the fixer's scope note.)
- **FE-8 (LOW->done, `==` ban -- name-resolved portion)** -- COMPLETED.
  The syntactic half stays in `regolith-syntax::checks` (it decides the
  unit-bearing-LITERAL operand case, `a == 5mm`). The name-resolved half
  now lands in `regolith-sem::resolve` (`check_equality_ban`): a per-decl
  field-type table (`QuantityClass` = continuous / discrete / unknown,
  from `classify_value`) resolves each bare NAME operand; `a == b` fires
  E0102 iff BOTH operands are `NameRef`s resolving continuous. The two
  halves never double-fire (one keys on a unit literal, the other on two
  names). Wired into the `lower.checks` pass (`regolith-lower/src/checks.rs`,
  per-decl, INV-20 gated) so it runs over real corpus input via
  `regolith.compiler.check`. The `TODO(FE-8)` on `is_continuous_quantity`
  was narrowed to a cross-reference. Tests: `resolve::tests::
  equality_between_two_continuous_names_is_flagged` (fires),
  `equality_involving_a_count_is_not_flagged` /
  `equality_between_two_count_names_is_not_flagged` (no false positive),
  and the retained syntactic-pass guard
  `checks::tests::equality_between_two_bare_names_is_not_flagged_syntactically`.
- **FE-9 (LOW->done, real canonicalization)** -- the formatter no longer
  reprints identity: it walks the CST token stream and regenerates
  canonical intra-line spacing (one space after `:`/`,` and around
  binary/tolerance/range operators; tight member `.`, calls/index
  brackets, `%`, and `QuantityLit` number+unit), preserving newlines and
  leading indentation. Meaning-preserving (same token stream/tree shape)
  and idempotent. Tests: `formatter::tests::{respaces_field_colon_and_operators,
  respaces_interval_and_range_and_call, canonical_form_is_a_fixed_point,
  pathological_input_is_stable_and_never_panics}` (plus the existing
  corpus/proptest idempotence). An `insta` formatter snapshot is now
  enabled (real normalization to snapshot); not added here.
- **FE-10 (LOW->done, `within [lo, hi]`)** -- the parser wires the
  demanded-window value: `within` followed by `[` produces a typed
  `WindowExpr` wrapping the `[lo, hi]` `IntervalExpr`. Guarded on the
  following `[` so the unrelated temporal `within <dur> after <ev>` claim
  form (no bracket) still degrades to an opaque tail. `grammar.ebnf`
  gained `window-value`. Tests: `parser::tests::{within_window_is_a_typed_node,
  temporal_within_is_not_a_window}`.
- **FE-7 (MEDIUM, stale doc)** -- deleted the "V/W/Hz absent" gap
  paragraph in `regolith-syntax::checks` module docs and updated the
  WO-05 header note to mark the cross-crate gap closed; `1V + 1A` now
  fires the precise `INCOMPATIBLE_QUANTITIES`. Test:
  `checks::tests::volt_plus_amp_is_incompatible_quantities`.

## Fixed (cycle 12, WO-19 depth pass -- with tests)

- **BE-2 (HIGH, INV-1)** -- FIXED. `given.materials`/`given.loads` are
  now threaded from the decl's typed `Field` tree
  (`claims.rs::given_for_decl`: `material`/`materials` fields + a
  `loads:` block's child lines). Claims differing only in material hash
  differently; INV-1 mutation half is green. `TODO(BE-2)` removed. Tests:
  `claims::tests::given_captures_material_so_the_key_is_mutation_sensitive`,
  `claims::tests::loads_block_is_threaded_into_given`,
  `test_inv_01_...mutating_a_key_component_changes_the_key`.
- **BE-3 (MEDIUM, INV-20)** -- FIXED. Per-subject gating on the
  attributed `SubjectError`/`Error` CST node
  (`entities.rs::decl_is_poisoned`): a poisoned subject is dropped at
  pass 2, so it produces no snapshot/check/obligation while clean
  siblings proceed. Tests:
  `entities::tests::a_poisoned_subject_is_gated_out_but_a_clean_sibling_is_not`,
  `claims::tests::a_poisoned_subject_emits_no_obligation`,
  `test_inv_20_poisoned_subject_is_gated_but_clean_sibling_is_not`.
- **BE-5 (MEDIUM, INV-21)** -- FIXED. `Cause` is derived structurally
  from the `ValueSource`/`CauseValue` node kind
  (`entities.rs::cause_from_value_source`), not a text scan:
  in[..]->Planner, derived->Obligation, allocated->Budget,
  free/default->Dfm. Test:
  `entities::tests::cause_is_derived_structurally_from_the_value_source_kind`.
- **BE-6 (LOW->done, INV-13)** -- FIXED. `contracts.rs` collects
  `ConformanceEdge`s for impl / `by extern` / import bindings; `claims.rs`
  emits one conformance obligation per edge (cubesat 40 -> 93
  obligations). Tests:
  `contracts::tests::{import_and_impl_edges_are_collected,extern_linkage_is_an_extern_edge}`,
  `claims::tests::an_impl_binding_emits_a_conformance_obligation`,
  `test_inv_13_impl_binding_emits_a_conformance_obligation`.
## Fixed (cycle 13, WO-05/WO-19 ownership/region/symmetry -- with tests)

- **BE-7 (HIGH, INV-04/05/23)** -- FIXED. The four ownership/region/
  symmetry invariants were blocked not on their `regolith-sem` mechanisms
  (`BorrowTable`/`OrbitTable`, done + unit-tested) but on WO-05 leaving the
  constructs that feed them as opaque islands, so `regolith-lower` never
  populated `PredictedDelta.modifies`/`.regions_touched`/`.symmetry` or
  built `EntityKind::Region` entities. WO-05 now types `bind`/`modify`
  (`OwnershipStmt`), `region`/`keepout`/`route` (`RegionStmt`), and
  `pattern`/`break`/`any`/`symmetric`/`mirror`/`flip` (`SymmetryStmt`) as
  contextual statement-start single-line nodes (arg-follower guarded, path
  parsing intact), and `regolith-lower/src/ownership.rs` feeds the sem
  mechanisms real parsed input (new `OrbitTable::contribute` builder). Three
  diagnostics now flow end-to-end: E0302 (modify of a borrowed entity /
  route into an owned exclusion region) and E0502 (`any` over a broken/
  undeclared orbit). `test_inv_04/05/23` un-xfailed to real fixtures
  (honest-pass + deliberate-violation each). RESIDUAL: INV-04's
  givens-invariance half (asymmetric-load refusal) is the discharging
  model's job (Python harness, AD-1); INV-06 stays xfail on WO-08 query
  resolution + WO-10 scope-entry snapshots. Golden deltas: corpus
  unchanged (obligations/resolutions/snapshots/diagnostics all stable),
  only the gear_reducer CST insta golden (a `flip about X` line, now
  typed). Tests: `parser`/`ownership`/`symmetry` unit tests + the three
  invariant fixtures.

- **BE-8 (HIGH, INV-06/18)** -- FIXED. The two reference invariants were
  blocked not on the `regolith-sem` query engine (`Query::resolve`,
  cardinality typing, done + unit-tested) but on it having no caller: no
  source construct produced a reference resolved against a per-scope
  snapshot, so an over/under-match could not be observed through the
  facade. WO-05 now types `feature`/`refer` as contextual statement-start
  single-line nodes (`QueryStmt`, arg-follower guarded, like the
  ownership/region/symmetry verbs), and `regolith-lower/src/query.rs`
  commits one `EntityKind::Other(<name>)` entity per `feature` into that
  declaration's scope-entry `EntityDb` snapshot (`PredictedDelta::commit`)
  and resolves each `refer <name>` as a `.only` query against it. E0301
  (`AMBIGUOUS_SELECTION`) now flows end-to-end on over-match (two `feature
  hole`), under-match (no feature), and -- crucially for INV-06 -- a
  `refer` naming a SIBLING declaration's feature: each scope's snapshot is
  built only from its own features, so a sibling's committed state is not
  name-resolvable (snapshot isolation by construction). `test_inv_06`
  (isolation) and `test_inv_18` (determinism) un-xfailed to real fixtures
  (honest-pass + deliberate-violation each). RESIDUAL: the by-name entity
  identity is the WO-19 simplification (a full per-face/per-net model needs
  the opaque geometry bodies WO-05 does not yet structure); the broader
  cardinality vocabulary (`.all`/`.any`/joins) stays unit-tested in
  `regolith-sem`, with `.only` exercised end-to-end here. Golden deltas:
  NONE (the corpus declares no `feature`/`refer`, so obligations/
  resolutions/snapshots/diagnostics and all insta/schema goldens are
  unchanged). Tests: `regolith-lower::query` unit tests (5) + the four
  invariant fixtures.

- **BE-9 (HIGH, INV-02/12)** -- FIXED. The two ladder invariants were
  blocked on the rung-7 `waive` ledger having no wiring: the `waive`
  keyword + `WaiveBlock` parsed, and `regolith_oblig::waiver` held the
  ledger schema, but no lowering pass matched declared waivers against
  obligations, so no acceptance record existed and no honesty check
  fired. `regolith-syntax` now exposes typed `WaiveBlock` accessors
  (`target`/`scope`/`basis`/`has_evidence`/`expires`, `Decl::waivers`),
  and `regolith-lower/src/waivers.rs` builds the ledger: each waiver is
  matched by claim path against the SAME declaration's obligations and
  recorded as a `WaiverRecord { waiver, kind, matched }` on
  `payload.ledger`. INV-2: the record carries NO status and the pass
  never touches the obligation/evidence set (a Rust test asserts the
  obligation set is byte-identical with and without a waiver), so no
  waiver can convert `violated` into `discharged`; a basis-less waiver
  is E0702 (`WAIVER_MISSING_BASIS`), not an acceptance. INV-12: every
  waiver surfaces as waived-with-reason; a claim target matching nothing
  is E0701 (`STALE_WAIVER`) naming it (the re-keying half reduces to
  INV-1). Rule-pack targets (`dfm`/`drc`/`erc`) the static core does not
  lower are classified `deferred_rule_pack` -- recorded and release-
  gated, never falsely stale, so the existing corpus (cubesat/mech
  `dfm` waivers) stays diagnostic-clean. `test_inv_02` + `test_inv_12`
  un-xfailed to real fixtures (honest-pass + deliberate-violation each).
  Golden deltas: hash ROTATION only from `SCHEMA_VERSION` 2 -> 3 (the
  `Waiver` shape changed + a `ledger` payload field was added);
  obligation/snapshot/resolution/evidence COUNTS unchanged on every
  corpus member (no obligation drop). Tests: `regolith-lower::waivers`
  unit tests (5) + `regolith-syntax` WaiveBlock accessor tests (2) +
  ledger unit tests + the four invariant fixtures. RESIDUAL: the
  match-set-GROWTH check (unscoped waiver absorbing a NEW failure, via
  the lockfile diff) is WO-14/orchestrator territory; rung 6 (`assume!`)
  stays expression-only.

## Mechanism landed (WO-11 / WO-12), cross-boundary fixtures still xfail

- **WO-11 (INV-15 ledger conservation)** -- the heuristic text-scan
  `parse_walk` is replaced by a structural CST consumer reading the typed
  `WalkBody`/`WalkStep` + sibling `HoleBlock`/`RegionsBlock`/
  `ConstraintsBlock`/`ExportsBlock` nodes; the DOF ledger, branch-pin, and
  export-anchoring checks in `regolith-sem` `profile` run off that
  structure. INV-15 conservation (participation is syntactic -- the ledger
  never invents a constraint the source did not write) is unit-tested in
  Rust (`profile::unit_tests::{balanced_walk_closes_from_typed_cst,
  deliberate_imbalance_is_caught, declared_free_variable_absorbs_residual}`
  and corpus tests). Exact zero-residual sketch closure is the solver's DOF
  analysis (hematite/07 OPEN-5, out of scope) -- the ledger is the sound
  conservative half. The cross-boundary Python `test_inv_15` fixture stays
  xfail (reason updated) until WO-19 lowering feeds populated walks through
  the FFI.
- **WO-12 (INV-13 role-kind / refinement)** -- `Interface`/`Impl` now carry
  `role_kinds`/`bound_kinds` + `params`; `check_role_kind` does real
  role-kind matching and `check_param_match` real parameter type/shape
  matching, with CST extractors populating them from the typed
  `roles:`/`params:`/`<params>` structure. Unit-tested (matching /
  role-kind mismatch / param mismatch / free-pin / extraction). `bound_kinds`
  end-to-end population needs the entity DB (WO-19); the cross-boundary
  Python `test_inv_13` fixture stays xfail (reason updated) until then.

## Fixed (cycle 14, WO-12/WO-19 system-node population -- with tests)

- **WO-12/WO-19 (INV-07/08/15 system nodes)** -- `regolith-lower::contracts`
  now builds REAL `SystemNode`s from the typed CST instead of empty ones:
  `BoundaryEntry`/`Reserve`/`FlowEdge`/`Target` populated per `boundary:`/
  `reserves:`/`flows:` block and `target ... of <Sys>` decl (target draws
  bound to reserves; child boundaries linked by `parts:` type reference).
  Three sound L2 checks in the new `regolith-ir::system` module emit
  diagnostics to the facade: boundary subsumption (INV-07, E0407
  `BOUNDARY_NOT_SUBSUMED` -- an enclosing envelope wider than a child's
  proven one; same-unit interval compare only, incomparable pairs left
  indeterminate), reserve over-allocation (INV-08, E0432 -- summed target
  draws over a declared reserve), and the system-flow ledger (INV-15,
  E0420 -- a flow endpoint declared nowhere in the system body is a leak;
  the participant set is a broad `name:` text scan, so intents that parse
  as opaque islands never manufacture a false leak). Rust unit tests in
  `system::tests` and `contracts::tests`; Python `test_inv_07/08/15` are
  real end-to-end fixtures (honest-pass + deliberate-violation each).
  Golden corpus unchanged (the conforming corpus stays clean). INV-19
  stays xfail with a revised reason: the contract surface is now
  promise-only by construction, so there is no surface-expressible
  deliberate violation -- its spec test is a multi-build content-addressing
  check needing escalation-edge lowering, not SystemNode population.

## Deferred with tracked markers (need a feature/architecture pass)

- **BE-4 (MEDIUM, INV-11 monomorphization)** -- RESOLVED. WO-05 now
  types generic USE-sites (`PatternOf<TappedHole<M3>>` -> `InstExpr`/
  `GenericArgs`, glued-`<` + balanced-scan disambiguation from claim
  comparisons), and `checks.rs::monomorphize` expands each generic
  declaration over its distinct typed instantiations exactly once. Two
  totality guards emit as diagnostics: arity mismatch (E0504, an
  un-expandable point) and dead generic (E0503, empty point-set via a
  compilation-wide identifier census that stays quiet for
  conformance/role-bound generics). Corpus emits ZERO monomorphization
  diagnostics and no obligation drop; only the gear_reducer CST insta
  golden changed (a `KeyedShaft<8mm>(...)` value became a typed
  `InstExpr`+`CallExpr` instead of a comparison BinExpr + opaque tail).
  `test_inv_11_monomorphization_totality.py` un-xfailed to a real
  end-to-end fixture. RESIDUAL (not INV-11): the per-instantiation static
  CHECK bodies re-run at every expanded point are future work; the
  expansion set is now real.

## Resolved (cycle 11): parser sibling-ejection desync

The 31 residual cubesat parse diagnostics were indented body statements
(`require X:`, `budget X:`, `policy:`, ...) ejected to the file level by
an early `parse_stmt_block` exit -- LOSING obligations. FIXED this cycle
(see the Fixed section above): the true trigger was NOT the `hosted_on`
tail nor a layout-pass miscount but a comment-led body -- the layout
pass emits the body `Indent` after the (stack-neutral) comment/blank
lines, and the parser only skipped `Whitespace` before testing for it.
The `kestrel.cupr` line-50 bisection landed on the first comment-led
body in the file (`intents:`, whose header is followed by three comment
lines). Not masked: obligations recovered (cubesat 21 -> 40), diagnostics
31 -> 0.

## INV-16 converter graph (converter non-instantaneity)

The sound mechanism landed: `regolith_sem::converter` builds the
continuous/discrete converter graph (domain-tagged nodes; combinational
/ converter / register edges), applies the ZOH delta-by-type rule (a
converter or register edge -- and, by typing, any domain-crossing edge
-- is a delta that cannot close a zero-delay cycle), and runs the
within-domain acyclicity check, emitting `E0105 COMBINATIONAL_CYCLE` per
same-domain combinational loop. `regolith-lower::checks` runs the
acyclicity check as a real pass (mirroring the stage-topology seam).

The check is SOUND (under-approximate): it traverses ONLY same-domain
combinational edges, so it flags exactly the loops the source declares
within one domain and never a loop a converter/register already breaks.
Unit-tested with the two INV-16 fixtures (comparator-feeds-own-threshold
legal + loop-free; genuine combinational cycle caught) plus register-
broken and cross-domain soundness cases.

TRUE BLOCKER for end-to-end (test_inv_16 stays honest-xfail): WO-05
leaves the elec `spec:`/`ports:`/converter/`on`-event bodies as
`OpaqueIsland` (confirmed via the buck_converter CST snapshot), so the
lowering pass builds an EMPTY graph over real `.cupr`. A token-scan of
the opaque islands would be the unsound text-scan heuristic WO-11
deliberately replaced, so it was not done. Un-xfail once WO-05 promotes
the elec behavioral bodies to typed CST and regolith-lower feeds them
into `ConverterGraph`. No golden deltas (the corpus grows no
diagnostics: the graph is empty).

## MEDIUM / LOW backlog

The remaining FE/BE MEDIUM and LOW findings (finer vocabulary/spelling
and doc items) are enumerated in the two findings files with code
locations; none are soundness bugs. Address opportunistically as the
relevant WOs are completed.
