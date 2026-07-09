# WO-47: calcite front end (`.calx` grammar/CST/AST)

Status: todo
Depends: WO-46 (ratified calcite 02-language -- HARD gate: do not
dispatch against the charter alone). Pattern: WO-31 (the fluorite
front end -- read its file AND its close-out notes; it is the
proven shape of "add a track to the one parser stack").
Language: Rust (`regolith-syntax`, + `regolith-sem` net-core
binding stubs); grammar.ebnf in lockstep.
Spec: docs/calcite/02-language.md (post-WO-46, NORMATIVE),
docs/calcite/03-lowering.md (the CST shapes lowering will consume),
00-architecture.md AD-3 (one parser stack) / AD-23 (one net core,
per-discipline plugins) / AD-24 (one front end); the WO-31
deliverable list as the template.

## Goal

`.calx` files parse to typed CST/AST through the ONE parser stack:
extension registered in the ONE registry module, the calcite
construct set (space/member/assembly/site/circulation/load-path
surfaces per 02-language) promoted to typed nodes, negative
fixtures for the track's diagnostic families, and the corpus
parsing clean (or with tracked-cut opaque residue recorded exactly
as WO-31 recorded fluorite's).

## Deliverables

1. `.calx` added to the extension-registry module in
   `regolith-syntax` (the ONE home; grep-verify nothing else gains
   the string).
2. Grammar/CST/AST for the 02-language construct set; comment-led
   bodies via the shared `enter_body`; `grammar.ebnf` updated in
   lockstep; insta snapshots over the calcite corpus.
3. AD-23 net-core discipline binding for the load-path net (the
   fluid-discipline refit precedent: a `civil` discipline with its
   node/edge typing; ZERO golden churn on the other tracks --
   the WO-31 acceptance bar).
4. Negative fixtures (`examples/negative/`): per 02-language's
   diagnostic families -- CHECK master's current fixture numbering
   at integration (the WO-36 collision lesson is recorded in the
   coordinator memory; sequential numbers do not git-conflict).
5. Corpus: the five WO-46 designs parse; opaque residue (if any) is
   a tracked cut in this WO's close-out naming the construct and
   the follow-up owner.

## Acceptance criteria

- `regolith check` runs over `.calx` files end-to-end (L0-L1);
  the calcite corpus is in the golden corpus dict with stable
  hashes; no golden drift on hematite/cuprite/fluorite tracks.
- Extension string appears in exactly one module (grep-proven).
- `make check` green including new snapshots/fixtures.

## Non-goals

- Lowering, obligations, packs, frame IR (WO-48).
- Formatter canonicalization beyond what the shared formatter
  already does for the shared statement shapes.
- LSP/editor surface (WO-38/39 pick calcite up for free through
  the one front end; verify nothing hard-codes a track list --
  if something does, THAT is a bug to report, not scope here).
