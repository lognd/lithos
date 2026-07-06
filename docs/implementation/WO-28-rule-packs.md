# WO-28: Rule packs (DFM/DRC/ERC authoring surface + engine)

Status: in-progress (deliverables 1-2 DONE, cycle 18 -- spec landed
in the track docs per design-log 2026-07-05-cycle-18 D84-D86/F93-F95,
typed grammar + ebnf + snapshots green; deliverables 3-8, the engine
half, remain)
Depends: WO-05 (parser), WO-08 (queries), WO-19 (lowering); WO-22/
WO-24 only for the realized-fact discharge half (static half ships
without them); WO-21 for expert pack signing (that slice can trail)
Language: Rust (`regolith-syntax`/`regolith-sem`/`regolith-lower`)
for grammar + engine; Python (`regolith.cli`) for `rules test|try`
Spec: hematite/04 (`process`), cuprite/04 sec. 4, regolith/03
(eager resolution), regolith/07 sec. 6, regolith/09 (E06xx),
regolith/11 sec. 3, regolith/12 sec. 3 (waive targets); design:
`21-rule-packs.md` (normative for this WO), AD-21

## Goal

The inside of `dfm:`/`drc:`/`erc:` blocks becomes real: named,
query-quantified, citation-carrying rules that lower to obligations,
resolve `free` values with rule provenance, defer honestly on
realized facts, and are overridden only through the waive ladder.
The surface must survive the sit-down test: a manufacturing expert
co-authors rules in a working session using `rules test`/`rules try`
as the feedback loop.

## Deliverables

1. **Spec cycle FIRST** (dispatch protocol escalation path, done as
   this WO's opening change): land the rule grammar in the track
   docs -- hematite/04 + 02 (`process` body: `capability:`, rule
   blocks, `rule` fields `forall`/`demand`/`advise`/`resolves`/
   `per`/`why`/`expect`), cuprite/04/07 mirror, regolith/03 cross-ref,
   grammar argued against the mantras in a dated design-log entry,
   track headers version-bumped. Spelling changes from the design
   doc's proposal are fine; silent divergence is not.
2. Grammar: typed `RuleDecl`/`RulePackBlock`/`ExpectBlock` CST under
   `process` decls (`regolith-syntax`); `grammar.ebnf` in lockstep;
   fuzz targets inherit.
3. Engine (`regolith-lower` + `regolith-sem`): pass-order touch
   points per the design doc sec. 2 -- `resolves:` in
   `lower.entities` (Cause-typed, INV-21), static-rule evaluation in
   `lower.checks` (E0601 + violated obligations), realized-fact
   rules to obligations in `lower.claims` (givens name required
   facts). Fact classification derives the level (D-E); E0603 for
   unprovidable facts, E0602 name collisions, E0604 stale resolvers.
   Match order deterministic (AD-6); swept obligations where the
   match domain is homogeneous.
4. Waive integration test: `waive dfm(<pack>.<rule>) on <query>`
   flows through the existing ladder untouched (fixture: violated
   rule -> basis-less waive release-gated -> evidence-carrying waive
   is a listed deviation).
5. CLI: `regolith rules test <pack>` (runs `expect:` fixtures; a
   rule missing pass or fail case is a lint warning) and
   `regolith rules try <pack> <file>` (matches, verdicts, near-miss
   margins; no build).
6. **Reference packs, authored in-corpus** (un-phantoms the golden
   corpus's `process=` references): `std.sheet_metal` (hole-edge
   distance, bend relief, min bend radius WITH `resolves:` --
   subsumes the eager half that `mech.sheet.min_bend_radius`
   currently fakes from the harness side; the harness model remains
   the expensive tier) and `jlc_2l` (trace/space + drill from
   `capability:`, fanout limit static rule, bus length-match as a
   realized-fact rule that defers honestly until WO-24).
7. Docs: the AUTHORING GUIDE exists at
   `docs/guide/03-writing-dfm-rules.md` (written cycle 18, ahead of
   the engine, status-marked DESIGNED): rule anatomy, the
   expect-driven workflow, worked sheet-metal + PCB packs, the waive
   story -- the document you put in front of the professor. This WO
   RECONCILES it against whatever the spec cycle changes and flips
   its status markers to WORKING as the engine lands.
8. If the spec cycle admits the no-silent-skip guarantee: INV-29
   ledger entry with proof argument, real fixtures (honest pass +
   deliberate violation: collision error, loosening-impossible,
   deferral visible), same change.

## Acceptance

- The corpus builds with the two reference packs attached; every
  static rule evaluates (E0601 fixtures fire with `pack.rule`
  provenance and `per:`/`why:` text rendered); realized-fact rules
  appear as indeterminate obligations naming their missing facts.
- `resolves:` drives the sheet-bracket `bend.radius = free` corpus
  resolution with `cause: dfm(std.sheet_metal.min_bend_radius)`,
  replacing the current harness-side-only path; INV-26
  free-variable fixture stays green through the new path.
- Rule violation -> waive -> release behavior matches the ladder
  fixtures (nothing new to learn, nothing bypassed).
- `rules test` runs every reference-pack `expect:` green;
  `rules try` output golden-tested.
- An expert-shaped read test: the authoring guide + one reference
  pack suffice to add a new rule without reading any other doc
  (dogfood: add one rule to each reference pack following only the
  guide, record friction in the WO close-out note).
- `make check` green; goldens updated in the same change.
