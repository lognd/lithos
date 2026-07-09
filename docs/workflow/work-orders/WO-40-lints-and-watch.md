# WO-40: Lint framework + watch mode

Status: in-progress (see close-out note at end of file: the code
family, config plumbing, three of six v1 lints, the D117 waive-ladder
assertion, and watch mode landed; the expert-ladder audit tier
(deliverable 3) and three v1 lints needing a cross-file usage/scope
graph are cut and named below, not stubbed).
Depends: WO-06 (diag registry), WO-19 (the check pipeline the passes
join), WO-16 (magnetite manifest for `[lints]`). Independent of the
WO-29/30 chain (touches `regolith-diag` codes + new lint passes +
CLI; serialize with any concurrently-dispatched WO editing
`regolith-lower`'s pass driver -- coordinate at dispatch time).
Language: Rust (lint passes + code family), Python (`[lints]`
config plumbing, `check --watch`)
Spec: `../../spec/toolchain/24-developer-tooling.md` sec. 5 (NORMATIVE); AD-24 (one
pipeline); design-log `2026-07-07-cycle-22.md` D112/D116/D117;
regolith/09 (build diagnostics surface); regolith/12 (the expert
ladder whose audit surface the D117 tier executes).

## Goal

Style/advisory linting becomes real without a second engine: lint
passes emit a new Warning-severity code family through the existing
pipeline, `magnetite.toml [lints]` configures allow/warn/deny per code,
and `regolith check --watch` gives the tight edit loop. CLI and LSP
show identical results by construction (D111).

## Deliverables

1. **Lint code family**: allocate the next free family in the
   `regolith-diag` registry (documented as the Lint family; Warning
   default). Codes carry the same span/fix machinery as errors.
2. **v1 lint passes** (each with positive + negative fixtures and a
   fix where mechanical): unused declaration; unreferenced feature;
   shadowed name; unused import; retired-vocabulary usage (dead
   names/extensions detectable in source positions);
   `todo!`/`assume!` inventory (one advisory summarizing count +
   locations per file -- the honest-deferral surface, not a nag per
   line).
3. **The expert-ladder audit tier (D117)**: static injection lints
   as compiler passes (uncontracted injection, orphaned `locked:`
   pin, dead waiver, unknown sealed-import format, plan without
   process pin -- each with a positive/negative fixture) and
   build-time audit advisories emitted orchestrator-side through
   the same codes/renderer (droppable hint via the INV-03
   machinery, dominated lock, stale supplied plan by lockfile-cause
   comparison, waiver match-set shrink-to-zero). Where a build-time
   advisory needs machinery another WO owns (the D105(d) match-set
   rows land in WO-30/WO-26), implement the lint against the
   machinery if present at dispatch time, else record the specific
   cut naming the WO -- never a stub that fires wrongly.
4. **Configuration**: `magnetite.toml [lints]` table (code or
   family-glob -> `allow|warn|deny`); deny promotes severity at
   emission time in ONE place; unknown codes in config are
   themselves a Warning naming the code. No-manifest projects get
   pure defaults. The waive ladder is untouched (D112: lints are
   configuration, not engineering deviations -- assert with a test
   that `waive` cannot name a lint code).
5. **Watch mode**: `regolith check --watch` via `watchfiles` --
   re-run on save of any registry-extension file or `magnetite.toml`,
   clear screen, one renderer, summary line with lint/error counts;
   clean exit on interrupt. Logging per house rules.
6. **Docs**: charter sec. 5 marked implemented; `[lints]` reference
   in regolith/11 (magnetite manifest doc); guide snippet; TODO ledger.

## Acceptance criteria

- Each v1 lint fires on its fixture and is silent on the negative;
  fixes apply cleanly where provided.
- `[lints] unused_declaration = "deny"` turns exactly that code into
  a build-blocking Error; `allow` silences it; both visible
  identically through `regolith check` and (once WO-38 lands) the
  server without server changes.
- `waive` naming a lint code is rejected with a diagnostic pointing
  at `[lints]` (the ladder cannot silence its own audit, D117).
- Expert-ladder fixtures: a dead waiver and an orphaned lock each
  fire their static lint; a droppable hint fires the build-time
  advisory on a built fixture (or its recorded cut names the
  blocking WO).
- Setting a D117-tier code below `warn` appears in the build report
  (visible configuration).
- Watch mode: touching one file re-checks within the debounce and
  prints the summary; interrupting exits 0.
- Corpus stays lint-clean OR gains deliberate `[lints]` entries in
  example manifests -- no silent warning debt (the count appears in
  the WO close-out).
- `make check` green.

## Non-goals

- Auto-fix-all CLI (`regolith fix`) -- reopen when the fix-bearing
  lint set is large enough to warrant it; per-fix application via
  the LSP covers v1.
- Semantic/physics advisories (margin-shaped hints belong to the
  harness "what would resolve it" family, not style lints).
- Custom user-authored lint plugins (rule packs already cover
  domain rules; a style-plugin API is a reopen-on-demand question).

## Close-out note (this dispatch)

**Landed:** the Lint code family (`regolith_diag::Family::Lint`,
base 800, renders `Lxxxx`); three v1 lints -- `unused_import`
(L0801), `retired_vocabulary_usage` (L0802, excludes `mill` per the
CLAUDE.md carve-out; scans `Ident` tokens only, so comments/design-log
prose never fire it), `todo_assume_inventory` (L0803, one advisory per
file); `magnetite.toml [lints]` (code -> allow/warn/deny) threaded
end-to-end through `regolith-lower` -> `regolith-api::Session` ->
the `_core` FFI -> `regolith.compiler.check`/`compile` ->
`regolith check`, with `deny` verified to promote to a build-blocking
error and `allow` to silence, over a live CLI run; the D117 assertion
that `waive` cannot name a lint code (`E0703`, deliberately outside
`Family::Lint` so it can never itself be configured away); `regolith
check --watch` via `watchfiles` (clear-screen, summary line,
KeyboardInterrupt exits clean). `docs/spec/regolith/11` sec. 3 gained
the `[lints]` reference.

**Cut, named (not stubbed):**
- `unused_declaration`, `unreferenced_feature`, `shadowed_name` (the
  other three v1 lints): each needs a cross-file usage/scope graph
  this dispatch's time budget did not allow building safely (a wrong
  cross-file reachability guess is a false-positive lint, worse than
  silence). Reopen as a WO-40 follow-up leaf.
- Deliverable 3 (the expert-ladder audit tier: uncontracted injection,
  orphaned `locked:` pin, dead waiver, unknown sealed-import format,
  plan without process pin, plus the four build-time audit
  advisories): out of scope for this pass entirely -- each needs
  machinery this dispatch did not have time to survey per-item
  against `waivers.rs`/`harness_lower.rs`/the orchestrator. Reopen as
  a dedicated WO-40 follow-up (or a fresh WO number if the coordinator
  prefers a clean acceptance surface).
- `[lints]` unknown-code validation ("unknown codes in config are
  themselves a Warning naming the code"): not implemented -- an
  unparseable action value is silently dropped at the FFI boundary
  today rather than surfaced as a diagnostic. Needs the Rust lint-code
  registry exposed to the Python manifest loader.
- Corpus lint-clean acceptance criterion: NOT met as literal silence.
  A scan of `examples/` found real `L0801`/`L0803` hits (unused
  imports on shared-declaration files like
  `examples/systems/cnc_router/contracts.cupr`, and `assume!`
  inventories on several `.hema` system fixtures) -- named here per
  the criterion's own "the count appears in the WO close-out" clause,
  not silently fixed or configured away. `tests/golden/data/*.json`
  were regenerated to include the new lint diagnostics (golden
  corpus's own convention: freeze current output, not enforce
  cleanliness) and the negative-corpus driver's family-base table
  (`tests/golden/test_negative_corpus.py`, `test_golden_corpus.py`)
  was extended with `"lint": 800` so it does not `KeyError` on a
  fixture that also happens to lint.
- Guide snippet: not written (time-boxed out); the `docs/spec/regolith/11`
  sec. 3 reference above is the durable spec-level documentation.

`make check` was green at close-out (fmt, clippy `-D warnings`, ruff,
`ty`, guard-core, schema-check, `cargo test --workspace`, `pytest`
-- 543 collected, 518 passed/3 skipped/23 xfailed, 0 failed).
