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
  sec. 5a) are now a `rockhead-qty` module (`log.rs`): `dB`/`dBc`/`dBi`
  (ratio) and `dBm`/`dBW`/`dBuV` (referenced) view stored-linear
  quantities, with the one sum-reference legality check
  (`log_sum_reference`). `rockhead-syntax::checks` wires it at L1, so
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
  `rockhead-qty`, the finding's own home; see the fixer's scope note.)
- **FE-8 (LOW, `==` ban -- syntactic portion)** -- documented the
  syntactic limit precisely: `a == b` between two continuous NAMES
  carries no unit token and cannot be decided without name resolution
  (discrete `Count` operands legitimately use `==`), so it is
  intentionally not flagged in `rockhead-syntax::checks`. A `TODO(FE-8)`
  on `is_continuous_quantity` records the REMAINDER and WHERE it lives:
  the name-resolved completion of INV-17's `==` ban belongs in
  `rockhead-sem` (WO-07/WO-09 L1 completion), which as of this change has
  NO such check. Test: `checks::tests::
  equality_between_two_bare_names_is_not_flagged_syntactically`.
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
  paragraph in `rockhead-syntax::checks` module docs and updated the
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
## Mechanism landed (WO-11 / WO-12), cross-boundary fixtures still xfail

- **WO-11 (INV-15 ledger conservation)** -- the heuristic text-scan
  `parse_walk` is replaced by a structural CST consumer reading the typed
  `WalkBody`/`WalkStep` + sibling `HoleBlock`/`RegionsBlock`/
  `ConstraintsBlock`/`ExportsBlock` nodes; the DOF ledger, branch-pin, and
  export-anchoring checks in `rockhead-sem` `profile` run off that
  structure. INV-15 conservation (participation is syntactic -- the ledger
  never invents a constraint the source did not write) is unit-tested in
  Rust (`profile::unit_tests::{balanced_walk_closes_from_typed_cst,
  deliberate_imbalance_is_caught, declared_free_variable_absorbs_residual}`
  and corpus tests). Exact zero-residual sketch closure is the solver's DOF
  analysis (mech/07 OPEN-5, out of scope) -- the ledger is the sound
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

## Deferred with tracked markers (need a feature/architecture pass)

- **BE-4 (MEDIUM, INV-11 monomorphization)** -- SEAM landed
  (`checks.rs::expand_generics` enumerates every generic-decl header),
  but concrete instantiation USE-site args (`PatternOf<TappedHole<M3>>`)
  are opaque -- WO-05 types only decl-header `GenericParams`, not
  use-site `<...>`. Per-point expansion / dead-generic detection stay
  blocked on WO-05; INV-11 xfail reason names the true blocker.

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

## MEDIUM / LOW backlog

The remaining FE/BE MEDIUM and LOW findings (finer vocabulary/spelling
and doc items) are enumerated in the two findings files with code
locations; none are soundness bugs. Address opportunistically as the
relevant WOs are completed.
