# hematite Open Questions

> Spec 0.13. Consolidated from all drafts; resolved items moved to
> section 3. Regolith-level questions live in the regolith docs
> ([SOPEN-n]); elec questions in `../cuprite/08-open-questions.md`.
> As of cycle 8 the technical queue is EMPTY: every remaining decision
> was either closed on existing machinery or explicitly deferred with a
> reopen criterion (section 2a). Naming was settled in cycle 9.

## 1. Open decisions

None. OPEN-10 CLOSED (cycle 9, D78; renamed cycle 10, owner's
decision): the mechanical language is **hematite** (`.hema`, iron ore
-> steel/structure); the electrical/computer language is **cuprite**
(`.cupr`); the package tool remains **quarry**, the registry is
**lodestone**, and the shared toolchain/CLI is **regolith** -- one
geology theme. The corpus-rename sweep has landed; the extension
registry recognizes only `.hema`/`.cupr`.

## 2. Seams -- all resolved in 0.5

The 0.4 seams were weaknesses of the language and have been redesigned
into settled rules:

| id | resolution | where |
|---|---|---|
| SEAM-1 | impls resolve at stage exit; the named stage must finish the surface; `refining` ops compose within the finishing stage; later-stage touches are borrow conflicts reported bidirectionally | `03-contracts-and-assemblies.md` 2.1 |
| SEAM-2 | patterns bind as whole orbits; verify-one-instantiate-n when the orbit is intact; single-instance binding splits the orbit conservatively | `03-contracts-and-assemblies.md` 2.2 |
| SEAM-3 | swept obligations: one obligation carrying the domain; harness decides coverage from declared model shape (monotonicity); evidence states coverage; per-point caching | regolith `07-claims-and-evidence.md` sec. 2 |
| SEAM-4 | `zones over <set>:` blocks with partition checking, `remainder`, auto-datum boundaries, zone extents as owned regions, content-addressed piecewise fields in obligations | `02-language.md` sec. 7 |

## 2a. Deferred with reopen criteria (cycle 8; not "open", not forgotten)

These are settled v1 postures whose *extension* is deliberately future
work. Each names the exact evidence that would reopen it -- anything
short of that evidence is speculation and must not reopen the item.

- **OPEN-3 residue** (kinematic sweeps, collision over motion): v2
  model packs over the existing hooks (D64, section 3). Reopen only on
  a design whose *syntax* cannot express the motion claim -- a model
  gap is a pack gap, never a reopen.
- **OPEN-2 residue** (Cpk/statistical allocation): a
  distribution-aware `allocate:` policy pack plus distribution-valued
  capability data (D63, section 3). Reopen only if a policy pack turns
  out to need language surface beyond `allocate: <policy>(<params>)`.
- **OPEN-5 residue** (solver integration detail): implementation-owned
  (WO-11 and Phase C); the language surface is closed (D65).

## 3. Resolved (for the record)

- Statically unpredictable topology changes -> conservative prediction +
  mandatory post-geometry verification; data-dependent feature classes
  must declare it (0.2).
- `.original` vs `.current` -> both retired; queries read the scope-entry
  snapshot; datums serve pre-modification references (0.2).
- Ownership granularity -> per-entity; contested merge regions get
  explicit `merge()` ownership only when queried (0.2).
- Assemblies x borrows -> parts are ownership islands; matings are
  explicit joins; alignment is the only positioning mechanism (0.2).
- Lockfile -> yes, with causes (0.2).
- Query grammar -> method chain only (FIX-3).
- Electrical ownership semantics -> answered by the elec track design:
  single-driver rule + owned layout regions; see
  `../cuprite/03-behavioral-layer.md` and `../regolith/10-domain-binding.md`.
- All FIX-1..10 and V1..V8 -> adopted; see `04-vocabulary.md` section 3.
- OPEN-9 (time-domain claims) -> designed in 0.5, jointly with the elec
  track: events, windows, masks, transient/frequency claim forms in the
  quantity core (regolith `02-quantity-core.md` sec. 5).
- CAM -> planning-as-evidence: manufacturability/cost/time are claims
  discharged by planner models; backends serialize plan evidence
  (`02-language.md` sec. 8).
- OPEN-4 (fatigue claim language) -> spelling designed in 0.6:
  `mech.life(<subject>, under=<spectrum>) >= <life>, scatter_factor=k`
  and `mech.damage(miner, under=...) <= d`; harness models remain
  future work but the source syntax is settled.
- Multi-piece parts (weldments) -> `pieces:` + joining stages with
  mating-style `align:` (0.6, `02-language.md` sec. 7a); weld physics
  vocabulary spun off as OPEN-13.
- Profile export anchoring -> feature-first addressing; profile-value
  exports are placeless (0.6, `02-language.md` sec. 5).
- Standalone-part loads -> interface envelopes; `boundary.` in part
  claims resolves per enclosing assembly (0.6,
  `03-contracts-and-assemblies.md` sec. 4).
- OPEN-1 (variants) -> closed in 0.8: cross-variant evidence sharing
  is the swept-obligation machinery over the variant domain
  (`02-language.md` sec. 7b); per-variant lockfile sections stand.
- OPEN-13 (welds) -> closed in 0.8: `std.mech.weld` pack with
  `weld_line_state` signature (line-weld cheap tier, shell-FEA
  expensive tier) + weld DFM rules (`02-language.md` sec. 7a rule 4).
- Expert overrides -> the ladder, `waive`, `policy:` and external
  linkage land regolith-wide in 0.8 (regolith `12`, regolith `08`
  sec. 4); mech surface: waives on DFM rules, supplied plans
  (`plan: extern`), DXF profiles, `model=` on claims.
- OPEN-12 (plan granularity) -> closed in 0.12: per stage, setups are
  internal plan structure; exercised by the gear reducer's mixed
  supplied+generated setups under one stage obligation.
- Claim subject `all` -> canonicalized in 0.12 (cycle 7, D59; was
  watchlist F63): bare `all` means the FULL subject domain of the
  claim form (`mech.mass(all)` = all parts; `info.utilization(all)` =
  all executors) -- the same one idea as the `.all` cardinality
  intent. `all_parts` is retired.
- OPEN-7 (host-language escape) -> SETTLED FOR V1 in 0.12 (cycle 7,
  D60): design source has NO host language; the generative constructs
  are the closed set (PatternOf, variants, orbits + orbit connections,
  monomorphized domains, parameterized `from_fn`/`from_table`).
  Rationale: the charter's local verifiability -- source stays
  statically checkable without executing anything. v2 may add a
  harness-side plugin API restricted to *registry content* (models,
  rule packs, format readers), never design source.
- OPEN-2 (statistical tolerance allocation) -> closed in 0.13
  (cycle 8, D63) by the D49 pattern: **allocation policies are
  pack-provided budget math**, not language surface. `allocate:`
  already takes a named policy with parameters; std ships
  `worst_case` and `rss`; `statistical(cpk=1.33)` is one pack away.
  What it genuinely needs is *distribution-valued* process capability
  data (a Cpk per (process, feature class)), which is ordinary
  evidence-tiered registry content -- community-tier distributions
  refuse a `trust: >= certified` claim group, correctly. No syntax
  slot was ever needed; the slot is `allocate:` itself.
- OPEN-3 (mechanisms/kinematics) -> closed for v1 in 0.13 (cycle 8,
  D64). The constraint that held it open -- "the syntax must not need
  to change" -- is now *dischargeable by inspection*: every kinematic
  concept a v2 layer needs already has a home (config variables +
  `exposing` for mechanism coordinates, `couples:` for transmission
  laws, the DOF ledger for mobility, `forall <cfg>` for quantifying
  over motion, claim forms + harness models for range/collision/
  clearance-over-sweep). A motion-sweep collision check is an ordinary
  claim (`mech.clearance(a, b) > 2mm forall pivot.theta`) discharged
  by a sweep-capable model pack -- L5 content, not language. v2 is a
  models-and-stdlib project; reopen only on a failing *syntax* example.
- OPEN-5 (sketch language detail) -> closed in shape in 0.13 (cycle 8,
  D65). The profile layer's language surface is settled (walk +
  constraints + exports, branch pins, the sketch DOF ledger); the
  **constraint vocabulary is a closed v1 set equal in power to the
  SolveSpace constraint kinds** (coincident, distance, angle,
  radius/diameter, tangent, perpendicular, parallel, horizontal/
  vertical relative to the profile frame, equal, symmetric, midpoint,
  on_entity), which is the de facto standard the solver target already
  implements. Solver interaction (parameterization, convergence
  reporting, degenerate-configuration diagnostics) is
  implementation-owned: WO-11 (walk grammar + ledger) now, Phase C
  (solve) later.
- OPEN-6 (imported-geometry re-import) -> closed in 0.13 (cycle 8,
  D66): no schema was ever missing. Re-import = publishing new content
  at the import stage: the hash pin fails loudly (INV-22), the human
  re-pins, queries re-resolve against the new measured entity DB, T2
  conformance re-runs, and a binding that no longer resolves is the
  ordinary constructive query error listing near-miss entities with
  their measures. The genuinely new artifact is a *report*, not a
  mechanism: `check --explain` renders the re-import diff (per-query:
  same entity / moved / gone, per-impl: T2 delta) from information the
  build already has. Tooling, Phase C.
- OPEN-8 (friction source-of-truth granularity) -> closed in 0.13
  (cycle 8, D67): the surface-treatment edge case is the trait
  coherence rulebook doing its job. `contact { A, B }` records may
  carry a `surface:` qualifier (as-machined, ground, anodized,
  passivated...) as part of the record key; resolution picks the
  unique most-specific record (pair + both surface states > pair +
  one > bare pair) or errors, exactly like material class specificity.
  The finishing stage supplies each side's surface state (the
  capability table already exports finish; `sn_curve(...,
  surface=per_finishing_stage)` set the precedent). `lubrication:` on
  the connection keeps selecting fields within the resolved record.
- OPEN-11 (`refining` taxonomy) -> closed in 0.13 (cycle 8, D68):
  refinement legality is declared **per-(op, geometry-class) in the
  process module** (`Ream refining on cylindrical`, `Polish refining
  on planar|cylindrical`), checked at L3 like any capability lookup.
  A wrong declaration is a pack bug with provenance (E06xx family
  names the pack), not a language hole -- the same trust posture as
  every other capability table.

## 4. Watchlist (not yet actionable)

- Walk-grammar EBNF lands in Phase A.
- (resolved in 0.11, D49) `budget kind=` is pack-provided; std ships
  eight kinds including `mass`/`energy`, and a thermal kind is one
  pack away, not a spec change.
- `effects:` blocks are powerful but dense -- possibly the one place a
  stdlib author's syntax leaks into end-user reading; consider a rendered
  "connection datasheet" view rather than a syntax change.
- (resolved in 0.5, example-driven) One-feature `then:` boilerplate:
  bare statements at stage/setup level now imply their own scope
  (regolith `06-execution-model.md`); adopted while writing
  `examples/mech/pillow_block.hema`.
- `constraints:` (profile) vs part-level constraint vocabulary: parts
  constrain via value sources, tolerances, and claims -- one word, one
  scope currently holds; watch in Phase A.
- (resolved in 0.12, D59) Claim-subject spelling: bare `all` is
  canonical, `all_parts` retired -- see section 3.
