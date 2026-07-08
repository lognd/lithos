# Rule packs: authorable DFM/DRC/ERC rules (design)

One sentence: users author named, query-quantified DFM/DRC/ERC rules
in the design languages themselves -- at pack, project, or artifact
level -- which lower to ordinary obligations (error by default,
release-gated), are overridden ONLY through the existing waive
ladder, and eagerly resolve `free` values with rule-provenanced
causes.

Status: design accepted (cycle 18); implemented by WO-28. The rule
SYNTAX below is a proposal: WO-28's first deliverable is the spec
cycle that lands it (or its argued revision) in the track docs --
grammar spellings are owner-reviewable there, the architecture below
is not expected to move.
Architecture decision: AD-21 in `00-architecture.md`.
Spec anchors (all pre-existing; this design fills their hole):
hematite/04 (`process` = `capability:` + `dfm:` rule pack),
cuprite/04 sec. 4 (DRC/ERC as the rule-pack tier), regolith/03
(eager `free` resolution, `cause: dfm(rule)`/`drc(rule)`),
regolith/07 sec. 6 (rule packs = cheap conservative planner tier),
regolith/09 (E06xx = rule violation with rule provenance),
regolith/10 (domain-binding row: stage rule pack), regolith/11
sec. 3 (`process` package kind), regolith/12 sec. 3 (waive targets
`dfm(rule)`/`drc(rule)`/`erc(rule)` with `on <query>` scoping).

## 0. The gap this closes

Everything AROUND rules is settled: where they live (`process`
modules), how they are cited (`dfm(min_bend_radius)`), how they are
overridden (`waive ... on <query>: basis:`), what they resolve
(`free` values, Cause-typed), and their diagnostic family (E06xx).
What does not exist: the grammar INSIDE a `dfm:`/`drc:`/`erc:`
block, and the engine that evaluates rules. No corpus file authors a
`process` body; the packs the corpus names (`jlc_4l`, `cnc_mill`,
`injection_mold`) are phantom references today.

## 1. Design decisions

### D-A: rules are authored in-language, not in Python

A rule is declarative source in hematite/cuprite, inside a rule-pack
block, evaluated by the Rust core. NOT a harness model pack.

Why: the user-facing bar is "error on holes close to edge" without
writing Python; the query engine (WO-08) and quantity core already
provide the whole vocabulary; eager `free` resolution MUST be
deterministic compiler work (regolith/03: resolution happens at
lowering with a Cause -- it cannot wait for a Python round trip);
and rules-as-source means rules are content-addressed, diffable,
versioned, and publishable as ordinary `process` packages (INV-22
pinning for free).

Boundary with the harness (regolith/07 sec. 6 kept intact): rule
packs are the EAGER conservative tier; when a rule's margin is thin
or its predicate needs physics, the expensive tier is a planner/
harness model as today (`mech.sheet.min_bend_radius` the model stays;
the rule cites the same limit). Capability numbers live ONCE, in the
pack's `capability:` table -- both the rule and any harness model
read them from the obligation's givens (NO DUPLICATION).

### D-B: a rule is a quantified claim template

Proposed surface (spec cycle to confirm spellings):

```
process sheet_metal_3xx:
    capability:
        thickness: [0.5mm, 3mm]
        min_bend_ratio: 1.6

    dfm:
        rule hole_edge_distance:
            forall h in holes
            demand: distance(h, nearest_edge(h)) >= 2 * h.diameter
            why: "holes near an edge tear out during forming"

        rule bend_relief:
            forall b in bends.where(not b.at_free_edge)
            demand: b.relief_cuts.count >= 1
            why: "unrelieved interior bends crack at the web"

        rule min_bend_radius:
            forall b in bends
            demand: b.radius >= capability.min_bend_ratio * thickness
            resolves: b.radius from free
            why: "press pack minimum inside radius"

process jlc_2l:
    capability:
        min_trace: 0.09mm
        min_drill: 0.2mm

    erc:
        rule fanout_drive:
            forall n in nets.where(kind=signal)
            demand: sum(n.loads.i_input) <= n.driver.i_drive
            why: "aggregate input current beyond drive collapses edges"

    drc:
        rule bus_length_match:
            forall b in buses.where(matched)
            demand: spread(routes(b).length) <= 2mm
            why: "skew budget for matched groups"
```

Two expression capabilities the surface REQUIRES (both existing
machinery, no new mechanism):

- **Aggregates over entity sets** in `demand:`/`advise:` --
  `sum(...)`, `count`, `max(...)`, `spread(...)` fold a quantity over
  a query result, dimension-checked.
- **Registry-record dereference (the vendor-LUT path)** -- a rule
  expression may read fields of the records bound to matched
  entities: `n.loads.i_input` / `n.driver.i_drive` resolve through
  each entity's `component`/`family` record (datasheet limits as
  intervals, `f(T)`/`f(V)` derating via `from_table()` -- cuprite/07
  sec. A), hash-pinned per INV-22, evaluated at the check's worst
  corner (corner discipline; rules never spell corners). This is why
  fanout is CURRENT-driven, not count-driven: the rule states the
  physics once and the per-part vendor tables decide each verdict.

- `forall <var> in <query>` REUSES the settled claim quantifier
  (regolith/07 sec. 1) with a WO-08 query as the domain -- no new
  quantification concept. The query addresses the CONSUMING
  artifact's entities at the stage the pack is attached to.
- `demand:` is one boolean claim expression in quantity-core
  vocabulary. Rule-time conditions ("except free edges") are query
  filters or boolean structure INSIDE the predicate -- deliberate:
  conditions an author can state generally belong in the rule;
  design-specific exceptions belong in waives (D-D).
- `resolves: <field> from free` marks the rule as the eager resolver
  for that field: the engine solves the demand for the field's
  cheapest legal value (regolith/03) and records
  `cause: dfm(<pack>.<rule>)` -- the INV-21 Cause API, existing.
- `why:` is the diagnostic's explanation text (E06xx renders it).
- `advise:` in place of `demand:` makes the rule a WARNING: a
  rendered diagnostic, verdict-inert, never an obligation, never
  release-gated (the INV-3 discipline: droppable guidance is never
  load-bearing). Default severity is error -- a rule you write
  blocks release unless waived.

### D-B2: what is NOT a rule -- built-in discipline (shorts et al.)

Some electrical errors are CORE LANGUAGE SEMANTICS, not pack
content, and rule packs must not restate them (NO DUPLICATION):
the v1 net discipline (cuprite/03 sec. 2) -- terminal ledger
(everything connected or explicitly `discard`ed), reference
reachability, ONE voltage-imposer per net, and the supply-short
check -- plus the single-driver check with declared `arbitrate`
joins (cuprite/06 L3 row). A short is an ownership/ledger compile
error (E03xx family, like a borrow conflict), NOT an E06xx rule
violation: it fires with no pack attached, cannot be detached, and
is NOT waivable -- the escape hatch for intentional cases is the
in-language construct (`arbitrate` for shared drive, declared joins
for deliberate supply ties), never an override. Rules EXTEND the
floor; discipline IS the floor. Enforcement status honestly: the
discipline is specced and the checks exist in `regolith-sem`
mechanism form, but end-to-end enforcement over real `.cupr` waits
on the WO-05 residual (elec behavioral/`nets:` bodies are opaque
islands today -- the INV-16 blocker); the rule engine must not
paper over that gap by reimplementing shorts as pack rules.

### D-C: rules attach at any level; composition is union + collision error

Three attachment levels, one mechanism (a rule pack is a rule pack):

1. **Registry pack** -- `stage bare: process=pcb_fab(jlc_2l)`
   (existing syntax, now with real referents). Fab/process vendor
   rules ride the stage.
2. **Project level** -- a local `.hema`/`.cupr` file authoring a
   `process`-kind module (house rules: "our shop wants 2.5x hole-edge
   clearance"), attached the same way or declared project-wide in
   `quarry.toml` (`[rules] apply = ["shop_floor"]` -- spelling is the
   spec cycle's call).
3. **Artifact level** -- for one-off demands on one part, the
   existing `require` block already IS the mechanism; no rule needed.
   A `rules: [pack, ...]` field on part/board/assembly decls is the
   proposed middle ground for reusable-but-local packs.

Composition: all attached packs' rules apply (union). Two rules with
the same qualified name is an ERROR (unambiguous -- no silent
shadowing, no priority arithmetic). A stricter project rule beside a
looser vendor rule is fine: both run, the binding constraint governs.
LOOSENING a pack's rule is impossible by construction -- the only
paths past a rule are (a) don't attach the pack, or (b) waive, which
is attributed and release-visible. That is the user requirement
"error unless EXPLICITLY overridden" landing on existing machinery.

### D-D: override = the waive ladder, nothing new

`waive dfm(hole_edge_distance) on holes.where(name=drain_hole):
basis: "reinforced boss, see FEA-102" [by <evidence>]` -- already
specced (regolith/12 sec. 3), already implemented in the static core
(INV-2/INV-12 fixtures green). Rule violations are obligations, so
waives apply to them exactly as to any claim: an acceptance record,
never a verdict change; basis-less waivers are release-gated;
evidence-carrying waivers are deviations, listed in release; a waiver
matching nothing is E0701 stale; match-set GROWTH is flagged from the
lockfile diff (WO-26). Zero new override surface -- this is the
design's most load-bearing property.

### D-E: the engine derives each rule's discharge level; deferral is honest

No `level:` annotation. The engine classifies each rule by the
entity facts its predicate references:

- **Static facts** (entity DB: counts, declared dimensions, net
  loads, topology) -> evaluated in `lower.checks` as a real pass;
  violations are E06xx diagnostics AND lowered obligations
  (violated) so the release gate and waive machinery see them.
- **Realized facts** (measured geometry: actual edge distances on
  the solid; routed facts: trace lengths, spread) -> the rule lowers
  to obligations whose givens name the required measured facts; they
  discharge in the post-realization passes (WO-22 post-geometry,
  WO-24 post-route extraction) and are honestly INDETERMINATE until
  the realizer has run -- release-gated, never silently skipped.

A predicate referencing a fact no layer provides is a compile ERROR
on the RULE (the pack author's bug), not a deferral -- rules fail
loud at definition, not quietly at use.

### D-F: engine home is Rust, in the lowering pipeline

Rule parsing is `regolith-syntax` (typed `RuleDecl` CST under the
existing `process` decl); matching/evaluation is a `lower.checks`
pass using `regolith-sem` queries; obligation emission rides
`lower.claims` (one obligation per match, or one swept obligation
carrying the match domain per regolith/07 sec. 2 when the domain is
homogeneous). Determinism: match order is entity-DB source order
(AD-6). Evaluation of `resolves:` runs in `lower.entities` where
`free` resolution already lives. E06xx diagnostics carry
`pack.rule` provenance and the `why:` text.

Rejected: a Python rule engine (breaks eager resolution and check
latency; splits provenance across the boundary); regex/JSON rule
files (a second, weaker language -- the design languages exist
precisely to say these things); severity levels beyond
error/advise (priority arithmetic invites rule-ordering bugs;
two levels + waives cover the corpus).

### D-G: the fab-capability single source feeds the external tools

WO-24 generates the KiCad DRC settings FROM the attached pack's
`capability:` table (min trace/space/drill) rather than maintaining
a parallel KiCad config: the vendor tool enforces during routing
what the pack declares, and the pack's own `drc:` rules re-check the
result from the extraction facts. One source, two enforcement
points, no desync (NO DUPLICATION at the tool boundary).

### D-H: rule packs are expert-authorable (the sit-down test)

The design target for the surface is a WORKING SESSION: a DML
professor or an industry manufacturing engineer, next to one regolith
user, turning their checklist into a pack in an afternoon -- reading
and writing rules themselves. Four features serve exactly that:

1. **Citation field.** `per: "Boothroyd & Dewhurst sec. 9.3"` /
   `per: "IPC-2221B table 6-1"` on a rule records WHERE the number
   came from. It renders in the E06xx diagnostic and the pack's
   generated rule index -- the expert's provenance survives into the
   error message a designer reads years later. (Registry-record
   precedent: evidence wants sources.)
2. **In-pack examples.** Each rule may carry `expect:` fixtures --
   minimal inline entity sketches (or corpus-file references) that
   MUST pass and MUST fail:

   ```
   rule hole_edge_distance:
       forall h in holes
       demand: distance(h, nearest_edge(h)) >= 2 * h.diameter
       per: "DML handbook rev 4, hole tear-out"
       why: "holes near an edge tear out during forming"
       expect:
           pass: hole(diameter=3mm, edge_distance=8mm)
           fail: hole(diameter=3mm, edge_distance=4mm)
   ```

   `regolith rules test <pack>` runs every `expect:`; a rule without
   both a pass and a fail case is a lint warning (a rule nobody has
   seen fire is untested law). The authoring session becomes
   test-driven: write the rule, watch the fail case catch, move on.
3. **Try-it loop.** `regolith rules try <pack> <design-file>` runs
   ONE pack against one design and prints every match, verdict, and
   near-miss (margin within 20%) -- the projector-friendly feedback
   loop for the session, no build required.
4. **Expert-signed packs.** A pack is registry content, so WO-21
   record signing applies as-is: the professor signs the pack with
   their key; a consumer designating that key `certified`/`tested`
   gets that tier on the pack's rules and resolutions. The expert's
   authority travels with the pack cryptographically, not socially
   (INV-14: signing carries trust, hosting does not).

Rejected: a separate "simple rule DSL" or spreadsheet import for
experts (a second language desyncs from the first; the whole point
of D-A is that the real surface is already checklist-shaped); a web
form (tooling can come later -- the artifact it would produce is
this same source text).

## 2. Data flow summary

```
process pack (.hema/.cupr, typed CST)
  -> lower.entities: `resolves:` rules resolve free values (Cause: dfm/drc)
  -> lower.checks:   static rules evaluate; E06xx + violated obligations
  -> lower.claims:   realized-fact rules -> obligations (givens name facts)
  -> WO-22/24 realizers: measured facts -> discharge/violate
  -> waive ladder / release gate: overrides, deviations, refusal
```

## 3. Error types (new diagnostics; E06xx family per regolith/09)

| code | condition |
|---|---|
| E0601 | rule violation (static), with `pack.rule` provenance + `why:` |
| E0602 | rule name collision across attached packs |
| E0603 | rule predicate references a fact no layer provides |
| E0604 | `resolves:` target is not `free` at any use site (stale resolver -- mirror of the stale-waiver check) |

Realized-fact violations reuse the obligation/evidence path (violated
evidence citing the rule), not a new code.

## 4. Dependencies and integration points

- `regolith-syntax` (RuleDecl grammar + grammar.ebnf), `regolith-sem`
  (query engine, existing), `regolith-lower` (three pass touch
  points above), `regolith-oblig` (obligation `given` gains the
  required-fact naming; schema bump).
- Waive machinery: unchanged, consumed as-is.
- WO-22/WO-24: provide measured/extracted facts; WO-24 additionally
  consumes `capability:` for KiCad DRC generation (D-G).
- Registry: `process` packages (regolith/11) become real content;
  the corpus's phantom packs (`jlc_4l`, `cnc_mill`, `sheet_metal`)
  get authored bodies -- which also un-phantoms the golden corpus.
- New guarantee candidate for the spec cycle: "no rule is silently
  skipped or loosened" (attachment union + collision error + honest
  deferral + waive-only override) -- if the cycle admits it, it
  enters the ledger as INV-29 with its proof argument in the WO-28
  implementation change (house rule; same treatment as INV-28).
