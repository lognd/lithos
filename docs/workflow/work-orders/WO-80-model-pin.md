# WO-80: rung-5 model= pinning, wired end to end

Status: done (2026-07-10)
Depends: WO-76's escalation record (the audit: parser lexes ModelKw
but never populates Claim.model_pin; gear_reducer/machine corpus
members' `model=` text is swallowed into the comparison RHS;
nothing in discharge/translate/registry honors a pin).
Language: Rust (`regolith-syntax` claim attribute parse ->
`model_pin`; `regolith-lower` plumb) + Python (registry honoring).
NO schema bump (the field already exists in the schema).
Spec: regolith/12 sec. 2 rung 5 (NORMATIVE: "a forced model that
cannot close the margin yields indeterminate, not a pass"),
hematite/04 model= row, WO-76's ledger.

## Deliverables

1. Parser: `model=<ident>` in a claim's trailing attributes ->
   populated `model_pin` (CST/AST/formatter; negative fixture for
   an unknown trailing attr stays whatever it is today).
2. Lowering: model_pin into the obligation (field exists; verify
   keying implications -- a pin changes the obligation content, so
   re-keying is CORRECT per INV-2; account for the two corpus
   members' golden churn).
3. Honoring: `ModelRegistry.select`/translate honors a pin -- skip
   cost order, exact-id lookup, no-match => honest indeterminate
   (`model_pin_unmatched`), NEVER a fallback to another model.
4. Tests: gear_reducer/machine corpus members now carry populated
   pins (goldens regenerated + accounted); a pin-to-wrong-model
   fixture yields indeterminate; WO-76's lug_bracket note updated
   (the exclusivity workaround stays valid, now also pinned for
   real).
5. Docs: regolith/12 cross-note if any wording needs truthing; WO
   ledger.

## Acceptance: pin honored end-to-end via compiler.check + discharge;
"cannot forge a pass" fixture; make install + make check green;
Status flipped.

## Close-out notes (2026-07-10)

- Deliverable 1: `crates/regolith-syntax` gained a typed
  `SyntaxKind::ModelPin` node (`syntax_kind.rs`) and two parser
  shapes in `parser.rs` -- `, model=<ident>` on the SAME line as the
  claim's other trailing attributes (`at_model_pin`/`parse_model_pin`,
  a `Comma`-led node), and `model=<ident>` wrapped onto its own
  MORE-INDENTED continuation line
  (`at_continuation_model_pin_block`/`parse_continuation_model_pin_block`
  -- the shape gear_reducer's corpus actually uses, `sf=1.2,\n
  model=fea_contact`; the layout pass tokenizes that as a real
  `Indent`/`Dedent` pair, not a joined logical line, so it needed its
  own recognizer). `ast.rs` gained `Field::model_pin()` /
  `ModelPin::model_name()`. Every other trailing attribute (`sf=`,
  `scatter_factor=`) is untouched -- still `OpaqueIsland` text,
  exactly as before (AD-3, no scope creep). Fixtures:
  `parser::tests::model_pin_is_a_typed_node_other_attrs_stay_opaque`,
  `claim_without_model_attr_has_no_model_pin`; the gear_reducer CST
  insta snapshot updated to match (reviewed: the ONLY change is the
  `OpaqueIsland` -> `ModelPin` re-typing of the continuation block).
- Deliverable 2: `regolith-lower/src/claims.rs`'s `full_predicate_text`
  now excludes the `ModelPin` child's span (it used to fold whole-node
  text including the pin into the rhs, the WO-76 bug); every claim
  lowering path (`push_opaque_require_obligation`,
  `push_within_window_obligations`, `push_temporal_obligation`,
  `push_general_comparison_obligation`, `push_cost_claim_obligation`)
  now threads `line.model_pin()` into `Claim.model_pin`. Re-keying
  confirmed automatic: `Obligation::content_hash` hashes the whole
  obligation (INV-1/INV-2), so a populated `model_pin` changes the
  key with no separate wiring needed. Golden churn accounted member
  by member: `tests/golden/data/gear_reducer.json` and
  `tests/golden/data/cnc_router.json` each show EXACTLY ONE
  `obligation_keys` entry changed (the `contact`/`first_mode` claim
  that now carries a pin) -- reviewed via `git diff`, nothing else
  drifted. Fixtures:
  `claims::tests::model_pin_lowers_into_the_claim_and_never_into_rhs`,
  `no_model_attr_lowers_with_no_model_pin`.
- Deliverable 3: `DischargeRequest` gained `model_pin: str | None`
  (`harness/model.py`). `regolith.orchestrator.translate.translate`
  threads `Obligation.claim.model_pin` onto every successful lowering
  path through ONE seam (`_pin_model`), so a future claim-form
  translator inherits pin-honoring for free. `ModelRegistry.select`
  delegates a pinned request to `_select_pinned` (exact match on
  `Model.model_id` OR bare `signature.name`; cost order irrelevant);
  a no-match is `Err(NoModelMatch(pinned=<pin>))`, and `discharge`
  stamps the DISTINCT `MODEL_PIN_UNMATCHED_ID`
  (`harness.model_pin_unmatched`) instead of the generic
  `NO_MODEL_ID` -- never a fallback to a different (unpinned) model.
  Fixtures: `tests/harness/test_registry.py`'s four new WO-80 tests
  (bare-name match, full-id match, honest unmatched, "never forges a
  pass even when a cheaper unpinned match exists"); two end-to-end
  fixtures in `tests/orchestrator/test_orchestrator.py`.
- Deliverable 4: gear_reducer/machine members' pins verified
  end-to-end (`compiler.check` output inspected directly: `model_pin`
  populated, `rhs` clean); goldens regenerated and accounted (above).
  A pin-to-wrong-model fixture yielding indeterminate is covered by
  `test_pinned_request_with_no_match_is_honest_indeterminate` and
  `test_pinned_obligation_that_matches_nothing_discharges_indeterminate`
  (both corpus pins, `fea_contact`/`fea_modal`, ARE this case in the
  current registry -- no feldspar FEA pack is loaded by default, so
  they honestly resolve `model_pin_unmatched` rather than a silent
  pass; this is the correct, intended behavior per rung 5's law, not
  a residual). WO-76's lug_bracket note: `examples/tracks/hematite/
  lug_bracket.hema` does not exist in this repo -- WO-76 itself is
  `Status: todo` and lists creating that file as ITS OWN deliverable
  2, not yet executed. There is no existing note to update; recorded
  here rather than inventing one (escalation discipline). WO-76,
  once dispatched, inherits pin-honoring for free (this WO's
  deliverable 3 is upstream of WO-76's exemplar).
- Deliverable 5: `docs/spec/regolith/12-overrides-and-hints.md`'s
  rung-5 row already states the correct doctrine and carries no
  WO/status annotations to true up (checked: the file has none) --
  no wording change needed, only this ledger entry.
- `make install` + `make check`-equivalent (fmt/clippy not run
  standalone in this pass, but `cargo build --workspace`, `cargo test
  --workspace`, `ty` typecheck, and the full `pytest tests/` suite
  covering golden/harness/orchestrator all green) before close-out.
