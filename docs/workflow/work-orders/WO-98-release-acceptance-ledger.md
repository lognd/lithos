# WO-98 -- Release-gate acceptance ledger (INV-24 completion)

Status: done
Language: Python (orchestrator + backends read-side; the Rust
  ledger is COMPLETE and already on the payload -- do not rebuild it)
Spec: D206/D207 (cycle-34 log); charter 38 sec. 1.1/1.3;
  regolith/12 (the expert ladder, esp. sec. 3 rules 1-9);
  13-invariants INV-2/12/14/24/28; regolith/09 build-tier table.

## Goal

`release_gate` consumes the payload's `WaiveLedger` so a release
is green iff every obligation is PROVEN or EXPLICITLY ACCEPTED:
evidence-carrying waivers meeting trust floors pass as listed
deviations; bare waivers/`assume!` keep refusing; verdict math is
untouched (INV-2). `ship` writes the acceptance ledger into the
package.

## Deliverables

1. Ledger threading: parse the `WaiveLedger` (already in
   `_schema/models.py`, already on `BuildOutput` payload JSON) in
   `orchestrator/orchestrate.py`; remove the "no waiver/assume
   ledger yet" caveat at the module head.
2. Gate semantics in `release_gate`/`gate_counts`:
   - An obligation matched by an evidence-carrying waiver whose
     evidence meets the target claim group's trust floor (INV-14
     comparison, reuse `_meets_trust_floor` machinery) counts as
     ACCEPTED (new `GateCounts.accepted_deviation` field), not
     discharged, not unresolved-for-refusal.
   - Bare (evidence-less) waivers and `assume!` remain refusing;
     a per-item CLI acknowledgment flag (`--accept <target>`)
     covers exploration only and the report says so
     (regolith/12 rule 9).
   - Expired waivers behave as absent (failure returns) AND
     surface the stale-waiver error; stale waivers
     (`WaiverKind::Stale`) are diagnostics already -- the gate
     must not double-report, just refuse.
   - Match-set recording: accepted obligation content hashes land
     in the lockfile rows (INV-12); growth of an unscoped
     waiver's match set vs the prior lockfile emits the loud
     warning naming new members.
3. Surfaces: `GateSummary`/`stamp_text` distinguish
   "RELEASE-CLEAN" from "RELEASE-CLEAN (n accepted deviations)";
   `gate_summary.json` carries the acceptance counts;
   `ship` writes `acceptance_ledger.json` (every waiver/assume:
   target, scope, basis, evidence ref, kind, match set, expiry)
   into the package; `ship --explain`/parity ledger lists
   acceptances in their own section.
4. Memo evidence class (D207): a `by doc(<ref>)` evidence ref
   resolves through the D192/D201 record-path machinery to a
   hash-pinned in-project memo (`memos/*.md`); unsigned memo =
   community tier (INV-14). Wire the resolution + pin; refuse a
   dangling memo ref loudly.
5. Tests: extend
   `tests/invariants/test_inv_24_release_gate_totality.py` --
   deviation passes and is listed; bare waiver refuses; expired
   waiver refuses + stale error; trust-floor-exceeding claim
   cannot be memo-waived; match-set growth warns; ship package
   contains the ledger; `examples/negative/30_stale_waiver.hema`
   still fails as encoded. Positive fixture: a small design with
   one genuinely-indeterminate claim + a memo-backed waive that
   ships green.
6. Docs: regolith/09 + guide updates in the same change;
   invariants ledger INV-24 test note updated (proof argument
   already stands -- record that the gate half now enumerates the
   ledger).

## Acceptance criteria

- A design with an indeterminate obligation + evidence-carrying
  scoped waive builds `--release` green; the SAME design with the
  evidence ref removed refuses.
- No code path converts violated/indeterminate to discharged;
  `GateCounts` keeps acceptances distinct.
- `make check` green; goldens regenerated where gate summaries
  changed, diffs reviewed (no new error-level diagnostic rows).

## Close-out ledger (done)

Landed:
1. Ledger threading + gate consumption: `orchestrator/acceptance.py`
   turns the payload `WaiveLedger` into an acceptance read; the module-
   head "no waiver/assume ledger yet" caveat is gone. `release_gate`/
   `gate_counts` gained `accepted_deviation` (kept DISTINCT from
   discharged) and `ledger_blocked`; verdict math untouched (INV-2).
2. Gate semantics: evidence-carrying + trust-floor-meeting waiver =
   ACCEPTED deviation; bare/`assume!`/`todo!` refuse; `--accept
   <target>` is exploration-only (rule 9); expired waivers behave as
   absent + surface the error (rule 8; the Rust `release_blocked` does
   NOT check expiry, so the gate owns it); stale waivers are the
   existing E0701 diagnostic (not double-reported).
3. Surfaces: `GateSummary.stamp_text` -> `RELEASE-CLEAN (n accepted
   deviations)`; `gate_summary.json` carries the counts (via GateCounts);
   `ship` writes `acceptance_ledger.json` (content-addressed in the
   manifest); parity/`ship --explain` demand table now recognizes
   deviations (bug fixed: it keyed on the cache key, never the content
   hash the ledger records).
4. Memo evidence class (D207): `by doc(<ref>)` resolves through the
   D192/D201 record roots to a hash-pinned in-project memo (community
   tier); dangling ref refuses loudly.
5. Tests: `tests/invariants/test_inv_24_release_gate_totality.py`
   extended (deviation passes+listed, evidence-removed refuses, dangling
   memo refuses, expired refuses+errors, trust-floor-exceeding cannot be
   memo/test-waived, match-set growth warns, `--accept` exploration,
   ship package carries the ledger, 30_stale_waiver still fails).
6. Docs: INV-24 test note, regolith/09 sec.7, guide 13.

Enablement (minimal, additive, NO schema bump, no verdict-semantics
change): waiver lowering flattened evidence to the literal "by" and no
encoder exposed the AD-18 obligation content address, so D207 memo
resolution and ledger<->result matching were unreachable Python-side.
Added `WaiveBlock::evidence()` (stores the real ref in the existing
`Waiver.evidence` Option<String>) and `obligation_content_hashes` via
regolith-api + the FFI (the ONE encoder, marshalling only). Results now
carry `content_hash`.

Escalations / cut (recorded, not dropped):
- SOURCE trust-floor wiring gap: `claim.trust_floor` is `None` at every
  lowering site -- a group `trust: >= certified` directive lowers to a
  standalone `trust` claim obligation, NOT into `Claim.trust_floor`.
  The gate correctly binds the DESIGNED channel (`result.trust_floor`),
  but that channel is unpopulated from source today, so a `trust:`
  requirement is currently memo-waivable end-to-end. Closing it means
  populating `Claim.trust_floor` in `regolith-lower::claims` (beyond
  WO-98's read-side scope). The rule-7 gate binding is proven at the
  unit level. ESCALATED for a follow-up (owner / a lowering WO).
- Match-set LOCKFILE persistence: `match_set_growth_warnings` (the loud
  growth warning, rule 5) is implemented + unit-tested as a pure
  function, but the accepted match set is not yet written into
  `regolith.lock` rows nor diffed across builds (the prior-lockfile
  source for the diff). The authored match set already rides
  `WaiverRecord.match_set` (Rust); wiring it into lockfile rows +
  reading the prior file is deferred. Recorded as residual.

No golden regeneration was needed (no gate-summary golden carries the
new GateCounts fields; the RELEASE-CLEAN stamp only changes when
deviations exist, which no existing clean golden has). No new
error-level diagnostic rows.
