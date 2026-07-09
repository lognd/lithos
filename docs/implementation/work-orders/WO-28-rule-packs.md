# WO-28: Rule packs (DFM/DRC/ERC authoring surface + engine)

Status: done (deliverables 1-2 cycle 18; deliverables 3-8, the
engine half, landed 2026-07-08 -- see "Engine-half close-out" below
for what shipped and the scoped residuals, none silent)
Depends: WO-05 (parser), WO-08 (queries), WO-19 (lowering); WO-22/
WO-24 only for the realized-fact discharge half (static half ships
without them); WO-21 for expert pack signing (that slice can trail)
Language: Rust (`regolith-syntax`/`regolith-sem`/`regolith-lower`)
for grammar + engine; Python (`regolith.cli`) for `rules test|try`
Spec: hematite/04 (`process`), cuprite/04 sec. 4, regolith/03
(eager resolution), regolith/07 sec. 6, regolith/09 (E06xx),
regolith/11 sec. 3, regolith/12 sec. 3 (waive targets); design:
`../design/21-rule-packs.md` (normative for this WO), AD-21

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
   `process` decls (`regolith-syntax`); `../grammar.ebnf` in lockstep;
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

## Cuts recorded this cycle (dispatch of 2026-07-06, engine half)

This dispatch landed deliverable 3's self-contained slice only: the
E06xx code registry (`regolith-diag::codes::{RULE_VIOLATION,
RULE_NAME_COLLISION, RULE_FACT_UNPROVIDED, RULE_STALE_RESOLVER}`, the
E0601-E0604 numbering from `../design/21-rule-packs.md` sec. 3) and a real
`lower.checks` pass, `crates/regolith-lower/src/rules.rs`, that
detects E0602 rule-name collisions (`pack.rule` declared more than
once across attached packs) purely from the typed `RuleDecl` CST --
tested (4 unit tests), wired into `checks::run_checks`, `make check`
clean for the touched crates.

Everything else in deliverables 3-8 is an explicit, escalated cut, not
a silent drop:

1. **Static-rule evaluation, `resolves:` resolution, realized-fact
   lowering, fact classification, E0603/E0604** (deliverable 3's
   remaining scope). Blocked upstream, not by rule-engine effort: all
   of it needs `forall <var> in <query>` to enumerate real domain
   entities (`holes`, `bends`, `nets` and their fields) through the
   WO-08 query engine, and `crates/regolith-sem/src/entity.rs`'s
   `EntityKind` has no such domain kinds today (`Face`/`Edge`/
   `Vertex`/`Net`/`Instance`/`Port`/`Region`/`Other(String)` only) --
   `crates/regolith-lower/src/checks.rs`'s own module doc already
   names this exact gap for stage/mating/`walk:` bodies: WO-19's
   per-decl entity granularity does not populate structured domain
   entities from the `OpaqueIsland` bodies WO-05 leaves unstructured.
   Building rule-pack-only entity structuring here would open a
   second, undocumented path into `EntityDb` that the real WO-05/
   WO-19 structuring work would later have to reconcile or rip out --
   out of WO-28's scope per the dispatch protocol (architecture
   ambiguity escalates to `../00-architecture.md`/upstream WOs, it is not
   invented around). Recorded as the load-bearing blocker for
   deliverables 3 (remainder), 4, 5, 6, 7, and 8 below.
2. **Waive integration test** (deliverable 4). No rule-violation
   obligation exists yet (cut 1), so there is no fixture for a waive
   to target. Not attempted.
3. **CLI `rules test`/`rules try`** (deliverable 5). Both need
   deliverable 3's evaluation/resolution to have anything to run
   against; a CLI over an engine that only detects name collisions
   would not exercise `expect:` fixtures or match/verdict output at
   all. Not attempted.
4. **Reference packs `std.sheet_metal`/`jlc_2l`** (deliverable 6).
   Authoring pack SOURCE TEXT is not the blocker; authoring a pack
   that is actually checked (needs 3/5) or that drives the flagship
   `bend.radius = free` resolution (needs 3's `resolves:` half)
   against entities that do not exist (cut 1) would ship dead,
   untestable source -- the dispatch protocol's "no invented
   workaround" rule forbids padding the corpus with content nothing
   exercises. Not attempted.
5. **Docs reconciliation** (deliverable 7). Flipping
   `docs/guide/03-writing-dfm-rules.md`'s status markers to WORKING
   for an engine that only checks name collisions would misrepresent
   the surface to the exact reader (the sit-down-test expert) the
   guide exists to protect. Not attempted; the guide is unchanged.
6. **INV-29 ledger entry** (deliverable 8). The candidate guarantee
   ("no rule is silently skipped or loosened") is precisely what
   cut 1's machinery would prove; there is no discharge path to write
   a real proof argument or fixture against yet, and `13-invariants.md`
   itself warns against ledger entries without real proving fixtures.
   Not attempted.

Net: this dispatch is a genuine, tested, `make check`-green sliver of
deliverable 3 (the E06xx registry plus one complete static check) with
the remaining scope's single root blocker named precisely (structured
domain entities for rule-pack `forall` domains do not exist yet, a
WO-05/WO-19 gap) so a follow-up dispatch -- ideally sequenced after
whatever WO structures `holes`/`bends`/`nets` as real `EntityKind`s --
can pick the rest up without rediscovery. THAT WO NOW EXISTS: WO-29
(lowering output surface, deliverable 2; design charter
`../design/23-lowering-output-surface.md`) -- its design pass (cycle 19, D88)
landed first-class `Hole`/`Bend` `EntityKind` variants,
query-engine-reachable via `base_selector` (`holes`/`hole`,
`bends`/`bend`), so `forall`'s TYPE-level target now exists. Real
corpus population (materializing `Hole`/`Bend` entities from `parts:`
lines) is STILL BLOCKED on the `parts:`-line parser promotion
(WO-29 Q4/D91), cut back this cycle rather than faked -- resume the
engine remainder only after that lands. Full plan and
acceptance-criteria coverage table: `WO-28-plan-checklist.md` in this
worktree.

## Engine-half close-out (dispatch of 2026-07-08)

Deliverables 3-8 landed. What shipped, per deliverable:

3. **Engine.** One shared evaluator
   (`crates/regolith-lower/src/rule_engine.rs`): pack index,
   `process=<head>(args)` attachment (head or bare dotted-ident arg),
   the documented bare-identifier binding order (decl fields -> stage
   process kwargs -> scalar capability entries; guide sec. 2a), and a
   quantity-core comparison evaluator (`+ - * /`, parens, unit
   literals through regolith-qty, dimension-checked, INV-17 `==` ban).
   Pass touch points exactly per design/21 sec. 2: `resolves:` in
   `lower.entities` (free measures pinned at the demand bound,
   `Cause::Dfm(pack.rule)`, INV-21; E0604 staleness accounted there
   because pre-resolution free-ness is only observable there);
   static evaluation in `lower.checks` (E0601 errors rendering
   `why:`/`per:`, `advise:` as verdict-inert warnings); violated AND
   deferred outcomes lowered to obligations in `lower.claims` (claim
   name = the waive-target spelling `dfm(pack.rule)`; givens name the
   blocking facts; swept via the forall domain). Fact classification
   is derived (D-E): unevaluable terms, `.where(...)` filters, and
   unpopulated domains DEFER (INV-29's no-vacuous-pass discipline);
   E0602/E0603 as before, E0603 still forall-scoped only (below).
4. **Waive integration.** `waivers.rs::classify` matches rule-pack
   targets against the lowered rule obligations (qualified or the
   corpus's unqualified inner-name spelling); unmatched stays
   `DeferredRulePack`, never falsely stale. Tests prove basis-less
   rejection, evidence-less matched waivers release-gate, `by`
   evidence is a listed deviation, and the obligation set is
   byte-identical with/without the waive (INV-2).
5. **CLI.** `regolith rules test <packs...>` (expect-fixture runs;
   missing pass/fail case = lint warning) and `regolith rules try
   <pack> <design>` (forced attachment, match/verdict/margin rows,
   near-miss <= 20%). Rust engine in `regolith-api::rules` (JSON out),
   FFI + `_core.pyi` + `compiler.rules_test|rules_try` (typani
   Result, pydantic models) + typer sub-app. `rules try` output
   golden-tested (`tests/golden/test_rules_cli.py` +
   `data/rules_try_sheet_bracket.json`).
6. **Reference packs, in-corpus.**
   `examples/tracks/hematite/std_sheet_metal.hema` (dotted pack name
   `std.sheet_metal`; attached by sheet_bracket's
   `process=press_brake(std.sheet_metal)`) and
   `examples/systems/espresso_machine/jlc_2l.cupr` (attached by the
   existing `process=pcb_fab(jlc_2l)` in control_board.cupr). The
   flagship resolution is real end to end: `radius=free` ->
   `flange.radius = 2.4mm`, `cause:
   dfm(std.sheet_metal.min_bend_radius)` (payload resolution row;
   corpus golden `sheet_bracket.json`). Hole-edge-distance defers
   naming `h.edge_distance` (a measured fact, WO-22's to discharge);
   bend-relief defers behind its `.where` filter; every jlc_2l rule
   defers until WO-24 extraction. Negative corpus: 35 flipped to
   EXPECT (E0601), 48 (E0603) and 49 (E0604, attached stale resolver)
   added. `rules test` green over both packs is itself a test.
7. **Guide reconciled** (`docs/guide/03-writing-dfm-rules.md`):
   STATUS -> WORKING; new sec. 2a (binding order + the evaluated
   subset + domain measure vocabularies); the PCB worked example
   matched to the shipped jlc_2l spelling with the aggregate form
   kept, marked as the target vocabulary; static-vs-deferred markers
   throughout.
8. **INV-29 (rule totality)** in `regolith/13` with its proof
   argument (evaluation total over attached rules by construction:
   {verdict, deferral-as-obligation, definition error}; loosening
   unrepresentable: union + collision error + two severities +
   waive-only override riding INV-2), proven by
   `tests/invariants/test_inv_29_rule_totality.py` (honest pass,
   loud waivable violation, collision, visible deferral,
   obligation-untouched-by-waive).

Scoped residuals (recorded, not silent; each with its reopen door):

- **Aggregates / registry-record dereference / `.where(...)`
  evaluation.** Out of the evaluator's subset by design this wave;
  such rules DEFER as obligations naming the term. Reopen when the
  WO-08 predicate registry is wired into rule matching and quarry
  records are readable at lowering time (the guide marks the
  aggregate spellings as target vocabulary).
- **Elec static tier.** Nets/pins/traces/vias/buses still carry no
  populated entities/fields (the WO-29 note), so the "fanout limit
  static rule" ships as a per-net extracted-fact comparison that
  defers in a build; nothing elec evaluates statically yet. Un-defers
  as WO-24's extraction facts land (the deferral obligations already
  name their domains).
- **E0603 for unquantified rules** (fixture 36's shape): a bare
  identifier without a forall domain has no vocabulary to classify
  against; stays EXPECT-TODO in the negative corpus README.
- **Realized-fact DISCHARGE** (deferral -> verdict post-realization):
  WO-22/WO-24 territory per this WO's own Depends line, unchanged.
- **Project-wide attachment** (`quarry.toml [rules] apply`, D-C
  level 2): still deferred exactly as the cycle-18 design log
  recorded ("engine wave, when the loader exists to check a spelling
  against") -- check sessions do not consult the quarry manifest;
  attachment is the `process=` reference surface only.
- **Expert pack signing** (WO-21 slice): trails per the header.

Dogfood friction (the expert-read acceptance test; one rule added to
each pack following ONLY the guide -- `std.sheet_metal.
min_punch_diameter`, `jlc_2l.annular_ring`, both green under
`rules test` first try): (a) the author needs the domain's measure
vocabulary in front of them or E0603 greets their first field typo --
fixed by putting the vocabulary table in guide sec. 2a; (b) it was
not obvious that an `expect:` fixture's kwargs also supply the BARE
design facts (`sheet=1.5mm`) -- now stated in sec. 2a; (c) a
`PatternOf<Pierce<circle(dia 4.5mm)>>` measure token needed a
tokenizer fix (`claim_scope::positional_value`) before the pierced
holes carried diameters -- found BY the dogfood rule, which is the
point of the exercise.
