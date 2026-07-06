# TODO -- design cycles

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of cycles 1-4. That is
deliberate: your job is a fresh-eyes adversarial read. Orientation:

1. `docs/README.md` -- what this project is; revision log per cycle.
2. `docs/regolith/` 01 -> 13 in order; `13-invariants.md` is the
   ledger of every guarantee with its proof argument -- it is
   normative.
3. `docs/hematite/`, `docs/cuprite/` -- the two language tracks. NAMING IS
   SETTLED (D78, renamed cycle 10): mech = **hematite** (`.hem`),
   elec = **cuprite** (`.cupr`), package tool = **quarry**, registry
   = **lodestone**, toolchain/CLI = **regolith**; the whole project
   (the two languages + toolchain + registry) is umbrella-branded
   **lithos**; one geology theme. The rename sweep has landed, so
   docs/examples use `hematite`/`cuprite` throughout.
4. `docs/design-log/2026-07-03-cycle-{1..9}.md` -- why everything is
   the way it is (findings F1-F92, decisions D1-D79).
4a. `docs/implementation/00-architecture.md` -- NORMATIVE
   implementation architecture (Rust core + Python orchestrator,
   PyO3/maturin, AD-1..16); where a WO body conflicts, it wins.
5. `examples/` -- 16 single-file designs in target syntax plus the
   ten-file Kestrel project (`cubesat/`); they are the spec's
   pressure tests and the future golden corpus.
6. `docs/implementation/` -- work orders WO-01..18 for building the
   toolchain (Rust core + Python orchestrator per 00-architecture.md;
   ground rules and the dispatch protocol in its README).

House rules that are easy to violate accidentally: ASCII only
(repo-wide, no exemptions); one word one idea (hematite/04 sec. 1
has the principles + justified-overload registry + retired list);
every decision argued against the mantras (Unambiguous > Intent-based
> User-friendly, in that priority); every cycle gets a dated design
log; version-bump the track headers you materially change; new
guarantees go into the invariant ledger WITH a proof argument in the
same change.

## Next (all delegable)

- [x] DISPATCH: WO-02..18 built (cycles 10-11). Every STUB body filled,
      `make check` green. Architecture extended (AD-17 lowering pipeline
      crate `regolith-lower`, AD-18 canonical encoder in
      `regolith_util::canon`); WO-19 added and wired. See the full
      remaining-work ledger below: **## PATH TO DONE**.
- [ ] DISPATCH: conforming + rule-breaking script generation against
      the corpus (the original plan); the retired-vocabulary list
      (hematite/04 sec. 4) and the invariant test column (regolith/13)
      are the rule-breaking menus.
- [x] MECHANICAL: the naming rename sweep: dcad->mill, deda->loom,
      .dcad->.mill, .deda->.loom across docs/ and examples/ (file
      renames included; archive/ exempt, verbatim by charter); legacy
      extensions dropped from the registry module references. Track
      READMEs/01-overviews transition notes updated.
- [ ] MECHANICAL: verify the three registry records against real
      datasheet revisions and upgrade their evidence tier from
      `community` (registry/{stm32g0,atsamd21,rp2040}.cupr say so
      in-file).
- [x] OWNER'S CALL (last naming slot): the umbrella
      distribution/CLI/import name is **regolith** (the miner);
      registry **lodestone** (D80). All names settled -- one geology
      theme (quarry/lodestone/regolith/hematite/cuprite).
- [ ] WATCH (unchanged conditions, do not re-litigate): F79 (computer
      at intent altitude) if a real team splits ownership there;
      reopen-criteria lists in hematite/07 sec. 2a and cuprite/08 sec. 1a --
      each names the exact evidence required, nothing less counts.

## PATH TO DONE (the full remaining-work ledger, cycle 11+)

Completing every unchecked box below finishes the project: the two
languages, their toolchain, the verification harness, the package
manager, and the ship pipeline. Ordered by dependency; each item names
where it lives and what unblocks. `make check` must stay green and each
finished item flips its WO `Status:` in the same change. Audit findings
live in `docs/audit/` (FE-*/BE-*, with a `TRIAGE.md`); invariant work is
WO-17. Do not mask a bug to make a box green (see the parser desync).

### 1. Close the three in-progress core WOs

- [~] **WO-19 (lowering pipeline) -> done.** Wired + green; the cycle-12
      depth pass landed. DONE: (a) parser sibling-ejection desync fixed
      (sec. 2, earlier cycle); (b) `given:` materials/loads threaded from
      the typed `Field` tree (BE-2 -- INV-1 mutation half now green);
      (c) per-subject INV-20 gating on the `SubjectError`/`Error` CST node
      (BE-3, a poisoned subject is dropped at pass 2, clean siblings
      proceed); (d) **monomorphization implemented (INV-11) -- CUT CLOSED.**
      `checks.rs::monomorphize` expands each generic decl over its DISTINCT
      typed use-site instantiations (WO-05 now types `Foo<Bar>` call sites
      as `InstExpr`/`GenericArgs`); an arity-mismatched instantiation is an
      un-expandable point (E0504) and a generic referenced nowhere is a
      dead generic (E0503). `test_inv_11_monomorphization_totality.py` is a
      real end-to-end fixture now (un-xfailed). (e) conformance/impl/extern/
      import obligations emitted (BE-6, INV-13 -- cubesat obligations
      40 -> 93); (f) structural `Cause` derivation from the `ValueSource`
      grammar (BE-5, replaces the text heuristic).
- [~] **WO-12 (contract IR) -> role/param matching REAL.** DONE:
      `Interface` carries `role_kinds` + `params`, `Impl` carries
      `bound_kinds` + `params`; `check_role_kind` does coverage +
      role-kind compatibility, `check_param_match` does parameter kind +
      type/shape matching (free-pin allowed). CST extractors
      `Interface::from_decl` / `Impl::from_impl_stmt` populate role kinds
      + params + role bindings from the typed CST. Tested (matching /
      role-kind mismatch / param mismatch / free-pin / extraction).
      REMAINING (not this WO's scope): `bound_kinds` end-to-end
      population needs the entity DB (WO-19 lowering resolves bindings);
      the cross-boundary INV-13 fixture stays xfail until then.
      SYSTEM-NODE POPULATION (this cycle, INV-07/08/15 flipped):
      `regolith-lower` now builds REAL `SystemNode`s from the typed CST --
      `BoundaryEntry`/`Reserve`/`FlowEdge`/`Target` populated from each
      `system`/`assembly` decl's `boundary:`/`reserves:`/`flows:` blocks
      and its `target ... of <Sys>` decls (draws linked to reserves; child
      boundaries linked by `parts:` type reference). Three sound L2 checks
      in `regolith-ir::system` flow to the facade: boundary subsumption
      (INV-07, E0407 -- enclosing envelope must be contained in a child's
      proven one, same-unit interval compare only, else indeterminate),
      reserve over-allocation (INV-08, E0432 -- summed target draws over a
      declared reserve), and the system-flow ledger (INV-15, E0420 -- a
      flow endpoint declared nowhere in the system body is a leak; the
      participant set is a broad `name:` text scan so opaque-island intents
      never yield a false leak). `test_inv_07/08/15` are real end-to-end
      fixtures (honest-pass + deliberate-violation each). Golden corpus
      unchanged (conforming corpus stays clean). INV-19 stays xfail: the
      contract surface is now promise-only by construction, so there is no
      surface-expressible deliberate violation -- the spec's test is a
      multi-build content-addressing check needing escalation-edge lowering
      (recorded, not faked).
- [~] **WO-11 (profiles) -> ledger half DONE.** The heuristic text-scan
      `parse_walk` is replaced by a structural CST consumer
      (`regolith_syntax::walk::parse_walk`) that reads the typed
      `WalkBody`/`WalkStep` nodes and the sibling `HoleBlock`/
      `RegionsBlock`/`ConstraintsBlock`/`ExportsBlock` nodes (gathered at
      profile-body level). The DOF ledger, branch-pin completeness, and
      export-anchoring checks in `regolith-sem` `profile` run off the
      typed structure; tested over the real corpus walk bodies +
      synthetic balanced/imbalanced/branch-pin/anchoring fixtures. CUT:
      exact zero-residual sketch closure is the constraint solver's DOF
      analysis (hematite/07 OPEN-5, implementation-owned, out of scope); the
      ledger is the sound conservative half (INV-15 conservation). The
      cross-boundary INV-15 fixture stays xfail until WO-19 feeds
      populated walks end-to-end.

### 2. Parser hardening (`regolith-syntax`) -- unblocks WO-19/12/11

- [x] **FIX the `hosted_on`-tail sibling-ejection desync** -- DONE
      (cycle 11, the comment-led-body fix in `enter_body_block`; see
      TRIAGE.md). Corpus 79 -> 18.
- [x] **Full statement grammar for the residual opaque constructs**
      (WO-05 residual list) -- DONE. Root cause of the 18 residual
      diagnostics was NOT domain-body payloads but the layout pass
      lacking bracket-aware implicit line joining: multi-line
      `()`/`[]` continuations emitted spurious INDENT/DEDENT that
      ejected siblings. `layout.rs` now joins bracketed continuations
      (18 -> 4). Then `impl ... for ... as`, `connect`, `parts`,
      `stage`/`setup`, `zones`, `boundary`, `flows`, decl-header
      generics `<...>`, and `prefer`/`forbid`/`minimize`/`maximize`/
      `use` policy rules are promoted to typed CST nodes
      (`StageStmt`/`SetupStmt`/`ImplStmt`/`*Block`/`PolicyRule`/
      `GenericParams`); their comment-led bodies open via the shared
      `enter_body` (4 -> 0). `grammar.ebnf` updated in lockstep.
      TRACKED CUTS (honest opaque residue): `parts` per-line orbit
      constructors (`n x Thing`) are inside a typed `PartsBlock` but
      not decomposed; `flows:` arrow lines are inside a typed
      `FlowsBlock` but the `a -> b` arrow is not a typed edge;
      `margin` / multi-line claim continuations / `override` / `plan:`
      / `flip` stay opaque continuations (see WO-05 report note).
- [x] **Ownership / region / symmetry statements typed** (unblocks
      INV-04/05/23) -- DONE. `bind`/`modify` (`OwnershipStmt`),
      `region`/`keepout`/`route` (`RegionStmt`), and `pattern`/`break`/
      `any`/`symmetric`/`mirror`/`flip` (`SymmetryStmt`) are promoted to
      typed single-line CST nodes, recognized contextually at
      statement-start only (arg follower required, so `region:` fields
      and `route = x` ctors are never mis-promoted; path parsing intact).
      `regolith-lower/src/ownership.rs` reads the leading verb + arg
      idents back to build a `BorrowTable`, `EntityKind::Region` entities
      + `PredictedDelta.regions_touched`, and an `OrbitTable`, feeding the
      pre-existing `regolith-sem` mechanisms (new `OrbitTable::contribute`
      builder). `grammar.ebnf` updated in lockstep. Tests:
      `parser`/`ownership` unit tests + the INV-04/05/23 fixtures.
- [x] **Use-site generic instantiations typed** (unblocks INV-11) --
      DONE. `Foo<Bar>` / nested `PatternOf<TappedHole<M3>>` at call/value
      sites now parse to typed `InstExpr`/`GenericArgs` nodes (mirroring
      decl-header `GenericParams`). `<`/`>` disambiguation: the opener
      must be GLUED to the head name and the angle group must scan as a
      balanced, type-argument-like list closing on the same line with an
      acceptable follower -- so claim comparisons (`mass < 5kg`,
      `a < b and c > d`) stay `BinExpr`. `grammar.ebnf` updated in
      lockstep. Test:
      `parser::tests::use_site_generic_instantiation_is_typed`.
- [x] **Subject-attributed parse errors** (enables INV-20 gating) --
      DONE. A stray closing bracket at statement position emits `E0193`
      MALFORMED_IN_BODY attributed to the enclosing declaration subject
      (secondary span into the subject header + a `SubjectError` CST
      node). Test:
      `parser::tests::malformed_in_body_stmt_is_attributed_to_subject`.
      regolith-lower's per-subject INV-20 gate (WO-19) can now consume
      the attribution.
- [x] **FE-3:** ASCII-enforce source at the lexer -- DONE. Layout pass
      rejects any non-ASCII character with `E0194` (batch-emitted).
      Tests in `layout.rs`.
- [x] **FE-4:** parse unit exponent suffixes (`m2`, `s2`) so `W/m2` and
      `kg/s2` work -- DONE in `regolith-qty::unit` (`parse_atom`); false
      `kg.m/s2` docstring example fixed. Test
      `unit::tests::parses_unit_exponent_suffixes`.
- [x] **FE-8:** DONE end-to-end. Name-resolved INV-17 `==` ban now lives
      in `regolith-sem::resolve` (`check_equality_ban` over a per-decl
      `QuantityClass` field table); `a == b` between two continuous names
      fires E0102, discrete counts do not. Wired into the `lower.checks`
      pass (INV-20 gated) and verified through `regolith.compiler.check`.
      The syntactic half (unit-literal operand) stays in `checks.rs`; the
      `TODO(FE-8)` there was narrowed to a cross-reference. Tests in
      `resolve.rs` + retained syntactic guard in `checks.rs`.
- [x] **FE-9:** formatter now canonicalizes (respacing around
      operators/`:`/`,`, tight calls/paths/quantities), not identity --
      DONE. Meaning-preserving + idempotent. Tests in `formatter.rs`.
- [x] **FE-10:** parse `within [lo, hi]` demanded windows -- DONE. Typed
      `WindowExpr` (guarded on a following `[`; temporal `within` stays
      opaque). `grammar.ebnf` updated. Tests in `parser.rs`.

### 3. Quantity core (`regolith-qty`) audit fixes

- [x] FE-2 (missing INV-21 causes extern/derived-intent/policy) -- DONE.
- [x] FE-5 (offset-unit tolerance delta bug) -- DONE.
- [x] **FE-1 (HIGH): logarithmic-unit views** (regolith/02 sec. 5a).
      `dB`/`dBm`/`dBi`/`dBc` stored linear in `regolith-qty::log`; one L1
      reference-legality check (`log_sum_reference`) wired in
      `regolith-syntax::checks`: `dBm + dBm` is `E0104` (linear product
      mW^2 is not a power), `dBm + dBi - dB` is a legal power. Enables
      the INV-17 log-sum case and the Kestrel link budget as a real
      dB claim.
- [x] **FE-6:** outward-round unit-converted bounds in `Interval::new`
      and `contains` (cross-unit soundness, AD-6/INV-9).
- [x] **FE-7:** deleted the stale `V`/`W`/`Hz`-absent comments in
      `checks.rs` and the WO-05 header (the table now has them).

### 4. Obligation keying (`regolith-oblig` + `regolith-lower`)

- [x] **BE-1 (HIGH, INV-1):** fold the harness model-registry version
      into the obligation/evidence-cache key so a model upgrade
      invalidates cached evidence. Registry versions are Python-side
      (AD-1) -> thread at discharge time. DONE:
      `Obligation::evidence_cache_key(registry_version)` threaded from
      `harness.MODEL_REGISTRY_VERSION` through the facade/FFI/discharge;
      `TODO(BE-1)` marker removed. Tests in `regolith-oblig`,
      `regolith-lower`, and `tests/test_ffi_bridge.py`.
- [x] **BE-2 (HIGH, INV-1):** DONE. `given.materials`/`given.loads` are
      populated from the decl's typed `Field` tree
      (`claims.rs::given_for_decl`): `material`/`materials` fields and a
      `loads:` block's child lines. Two claims differing ONLY in material
      now hash differently (INV-1 mutation half green, both in a
      `regolith-lower` unit test and `test_inv_01_...changes_the_key`).
      `TODO(BE-2)` marker removed.

### 5. WO-17 invariant suite -> all green (`tests/invariants/`, both sides)

All 27 families are real+green; INV-26's 6th and last default (derived
workloads) closed this cycle -- ALL 6 defaults now real, 0 xfail, 0 stub
in `tests/invariants/`. WO-17 `Status:` flipped to `done`. Grouping by
blocker (history retained):

- [x] Cycle 17 -- derived-workload discharge CLOSED. `orchestrator.
      translate` lowers the realization obligation's `implies` claim
      (`_translate_realization`), recognizing a rule-3 DERIVED edge via
      its `cause: derived(intent ...)` tag; a new harness identity model
      (`harness/models/workload_realization.py`) discharges it cleanly
      (verbatim-copy demand vectors make the implication a structural
      identity -- zero fabricated numbers). A DECLARED edge's implication
      still needs the intent's own demand quantities (not threaded,
      WO-05/WO-12 cut), so it defers honestly -> indeterminate ->
      release-gate refuses -- the sound, un-faked loud case for the same
      rule-2/3 family (rule 3's own derivation cannot be numerically
      wrong by construction). INV-26 is now 6-of-6 real. See TRIAGE C17.

- [x] INV-19 (promises, not actuals) FLIPPED GREEN -- a two-build
      content-addressing fixture (mirrors INV-27): edit an artifact
      internal (a part's `material`, unreachable from any system claim);
      every system-level obligation key (subject to the assembly system
      node) is byte-identical across builds (zero re-runs) while the
      part's own snapshot/obligations move (non-vacuous isolation). Teeth
      control: editing the promised mass budget re-keys the system
      obligation. FUTURE WORK (not faked): the "except via escalation
      edge" clause (`model=`/`measured`/`spice_extracted` legitimately
      reaching an internal) needs escalation-edge lowering that does not
      exist yet (WO-12/escalation); left as an honest note in the module.

- [x] Cycle 16 -- obligation->DischargeRequest conformance bridge CLOSED.
      `orchestrator.translate` lowers a `conforms` obligation into the
      `harness.conformance` model; `claims.rs` threads the upper/lower
      leading comparator bounds into the obligation's `given.loads`. INV-26
      implicit-`by spec` un-xfailed (a widening impl -> violated + release
      gate refuses, refining-impl control), and INV-13's discharge half now
      rides a REAL lowered obligation via `orchestrate.build` (not a hand-
      built request). Honest cut: positional first-bound extraction; non-
      literal or name-matched windows deferred. Golden: cubesat 5 `conforms`
      obligation keys shifted (93->93, no drop). See TRIAGE C16.

- [~] Enabled once the pipeline is complete (sec. 1-2). FLIPPED GREEN
      (WO-19 depth pass): INV-20 (per-subject check gating), INV-13
      (conformance obligation emitted for impl bindings), INV-01
      mutation half (given: materials/loads), INV-11 (monomorphization
      totality -- use-site generic instantiations typed in WO-05 and
      expanded per-point in regolith-lower; arity-mismatch E0504 +
      dead-generic E0503 as real end-to-end fixtures). FLIPPED GREEN
      (this cycle, harness/facade layers): INV-09 (corner conservatism,
      harness-side worst corner), INV-17 (E0103 interval/range + E0104
      log-sum, all four L1 classes now green), INV-25 (coverage honesty:
      partial coverage -> indeterminate via the real discharge rule),
      INV-27 (file-layout invariance: split-file identity diff),
      INV-13 discharge half (spec contradicted by its impl FAILS
      equivalence -- the Python harness conformance-refinement model,
      `harness/models/conformance.py`, drives a conforming impl to
      discharged and a contradicting impl to violated end-to-end through
      the registry; the obligation->DischargeRequest bridge is now CLOSED,
      cycle 16 -- see the entry above), INV-18 (reference determinism: `.only` query
      resolution yields E0301 on over/under-match; WO-08 wiring via the
      QueryStmt feature/refer nodes), INV-06 (snapshot isolation: a
      refer naming a sibling scope's feature under-matches -- committed
      state is not name-resolvable across the scope boundary). No
      remaining xfail in this group.
- [x] Enabled by the checks landing over real input (BE-7): INV-04
      (symmetry soundness), INV-05 (ownership finality), INV-23 (region
      exclusivity) -- FLIPPED GREEN this cycle. WO-05 now types the
      ownership/region/symmetry statements (`bind`/`modify`,
      `region`/`keepout`/`route`, `pattern`/`break`/`any`), and
      `regolith-lower/src/ownership.rs` populates `PredictedDelta.modifies`
      / `.regions_touched` / the `OrbitTable` + `EntityKind::Region`
      entities from that parsed source, feeding the done-and-unit-tested
      `regolith-sem` `BorrowTable`/`OrbitTable`. Each fixture asserts an
      honest pass AND a deliberate violation caught: INV-05 modify of a
      borrowed entity (E0302, bidirectional), INV-23 route into an owned
      exclusion region (E0302) vs a declared `join`/arbitration exemption,
      INV-04 `any` over a broken/undeclared orbit (E0502) vs a live cyclic
      orbit. HONEST RESIDUAL (not flipped): INV-04's givens-invariance half
      (symmetric subject + asymmetric LOAD refuses verify-one) is the
      discharging model's check (Python harness, AD-1), out of WO-05/19
      scope -- the orbit-soundness gate is what is real here. INV-15
      (ledger conservation) still needs populated walks through the FFI.
      NOW GREEN (cycle 15, WO-08/WO-19 query-resolution wiring): INV-06
      (snapshot isolation) and INV-18 (reference determinism). WO-05 types
      `feature`/`refer` as `QueryStmt` single-line nodes;
      `regolith-lower/src/query.rs` commits one entity per `feature` into a
      per-declaration scope-entry `EntityDb` snapshot and resolves each
      `refer <name>` as a `.only` `Query` (`regolith-sem`). Over/under-match
      is E0301 (INV-18); each scope resolves only against its OWN snapshot,
      so a `refer` at a sibling declaration's feature under-matches (INV-06
      isolation). Both un-xfailed to real fixtures (honest-pass +
      deliberate-violation). Golden deltas: NONE (corpus has no
      `feature`/`refer`). RESIDUAL: by-name entity identity is the WO-19
      simplification; wider cardinality (`.all`/`.any`/joins) stays
      unit-tested in `regolith-sem`.
- [x] Enabled by FE-1: INV-17 log-sum case (E0104) -- DONE, plus the
      interval/range confusion case (E0103). All four INV-17 L1 classes
      (E0101/E0102/E0103/E0104) now pass end-to-end through
      `regolith.compiler.check`.
- [~] Enabled by the harness + ladder + release layers (sec. 6-8).
      GREEN: INV-09 (corner conservatism, harness-model side), INV-14
      (trust totality), INV-22 (foreign-content pinning), INV-24
      (release-gate totality), INV-25 (coverage honesty),
      INV-02 (ladder safety) + INV-12 (waiver honesty) -- the in-source
      `waive` ladder + ledger landed (`regolith-lower::waivers`): a
      waiver records an acceptance (never a verdict), a basis-less
      waiver is E0702, a claim target matching nothing is E0701 stale.
      REMAINING INV-12 surface (out of static-core scope): the
      match-set-GROWTH check (an unscoped waiver silently absorbing a
      NEW failure, surfaced in the lockfile diff) needs the lockfile
      materialization (WO-14/orchestrator); and rungs 6 (`assume!`) is
      still expression-only. NOW GREEN (cycle 15): INV-03 (hint
      droppability) -- `@hint(...)` is a typed verdict-inert `HintStmt`
      and `orchestrator.translate` recovers the comparator from a
      `require`-placeholder claim's `rhs` (the true cause of
      `resolutions=0`: every obligation deferred `unsupported_op`), so a
      resolved beam design discharges twice through `orchestrator.build`
      with/without `@hint`/`policy: prefer` and the verdict sets diff
      IDENTICAL. INV-26 (defaults meta) -- PARTIALLY REAL (4 of 6): eager
      candidate acceptance (violated/indeterminate loud + release-gated),
      canonical `any` (E0502 loud), FREE-VARIABLE RESOLUTION (the shipped
      `sheet_bend` DFM pack eagerly resolves a `free` bend radius to the
      manufacturable minimum -> a tighter demanded window is `violated` +
      release-gated), and LOCAL TOLERANCE ALLOCATION (a new closed-form
      `mech.tolerance.worst_case_stack` harness model sums the locally-
      allocated contributor bands -> a chain that cannot close, the E0432
      condition, is `violated` + release-gated) are now real fixtures, each
      with a negative control; the other two defaults (implicit `by spec`
      conformance discharge, derived workloads -- both WO-12) stayed HONEST
      tracked xfails with reopen criteria AT THE TIME -- both since closed
      (cycles 16 and 17 respectively; see above).
      INV-16 (converter non-instantaneity): the SOUND mechanism now
      exists -- `regolith_sem::converter` builds the continuous/discrete
      converter graph, applies the ZOH delta-by-type rule (a converter or
      register edge, and any domain-crossing edge by typing, is a delta
      that breaks a cycle), and runs the within-domain acyclicity check
      (E0105 COMBINATIONAL_CYCLE). Unit-tested in Rust (comparator-feeds-
      own-threshold legal; combinational-cycle caught; register/cross-
      domain breaks); `regolith-lower::checks` runs the acyclicity check
      as a real pass. STILL xfail end-to-end for a TRUE blocker naming
      WO-05: the elec `spec:`/`ports:`/converter/`on`-event bodies are
      `OpaqueIsland` (confirmed via buck_converter CST), so the lowering
      pass builds an EMPTY graph over real `.cupr`. Un-xfail once WO-05
      promotes the elec behavioral bodies to typed CST and regolith-lower
      feeds them into `ConverterGraph`.
      NOW GREEN (this cycle, WO-12/WO-19 system-node population):
      INV-07 (boundary subsumption, E0407), INV-08 (target additivity /
      reserve over-allocation, E0432), INV-15 (system-flow ledger
      conservation, E0420) are real end-to-end fixtures over populated
      `SystemNode`s. INV-19 (promises-not-actuals) STILL xfail but for a
      REVISED reason: the contract surface is now promise-only by
      construction (no surface-expressible violation); the spec test is a
      multi-build content-addressing check needing escalation-edge
      lowering, not SystemNode population.
- [x] Flip WO-17 `Status:` to done only when every INV test is real and
      green (no xfail, no stub). DONE this cycle.

### 6. Verification harness (`python/regolith/harness/`) -- roadmap Phase C/D

- [x] Model registry + signature/impl matching (Python). DONE:
      `harness.registry.ModelRegistry` (versioned via
      `MODEL_REGISTRY_VERSION`, folded into every evidence hash --
      BE-1/INV-1), `harness.signature.ModelSignature`, deterministic +
      TOTAL selection (`select` returns a typani `Result`; a no-match is
      the explicit `harness.no_model` indeterminate evidence value, never
      a silent pass). The generic margin-driven discharge rule
      (`value +- eps` vs limit, INV-9 corner-conservative worst corner)
      lives once in `harness.model.Model.discharge`. Tested:
      `tests/harness/`.
- [~] Closed-form model packs (numpy/scipy): the FIRST pack is DONE --
      the buck-converter output-voltage-ripple model
      (`harness.models.buck_ripple`, corpus claim
      `require Regulation: ripple`), numpy worst-corner evaluation, wired
      into the default registry, known-answer + determinism tested.
      DONE this cycle (registered + known-answer/verdict/determinism
      tested in `tests/harness/`): bolted-joint preload diagram (VDI 2230,
      `mech.bolt.joint_separation`), Euler-Bernoulli cantilever beam
      (`mech.beam.cantilever_deflection`), and the link budget
      (`elec.link.margin`, dB power balance for the Kestrel downlink).
      ALSO DONE (registered + known-answer/verdict/corner/determinism
      tested): thick-wall Lame bore von-Mises stress
      (`mech.cylinder.lame_bore_stress`, torch-igniter chamber hoop
      claim) and the eager sheet-metal DFM min-bend-radius rule
      (`mech.sheet.min_bend_radius`, sheet-bracket flange).
      ALSO DONE this cycle (INV-13 discharge half): the
      conformance-refinement pack (`harness.models.conformance`,
      `harness.conformance.upper_bound`/`lower_bound`) -- a PROMISE
      comparison (INV-19) checking the lower impl bound refines the upper
      spec bound; a contradicting impl -> violated, a non-comparable bound
      -> honest indeterminate, tested end-to-end (conforming discharges,
      contradiction caught, determinism) in `tests/harness/test_conformance.py`
      and driven from `tests/invariants/test_inv_13_no_dead_uppers.py`.
      REMAINING pack (explicit tracked TODO, extension point +
      `# TODO(harness)` marker left in `harness/models/__init__.py`):
      the buck efficiency/transient claims.
- [~] Numeric models + planner adapters; `deterministic:` flag folded
      into evidence hash inputs (INV-10). DONE for the closed-form tier:
      the `deterministic` flag is a hash input in
      `harness.evidence.build_evidence` (non-deterministic models fold a
      settings blob). Numeric/reduced tiers + planner adapters remain
      -> now work-ordered as **WO-26** (sec. 7).
- [ ] Harness as a separate process (roadmap Phase E, item 13); keep
      obligations serializable across the boundary (already true).
      -> absorbed into **WO-20**'s subprocess adapter seam (sec. 7):
      one wire protocol for in-process / subprocess / remote.

### 7. PATH TO SHIP -- realizers, solvers, backends (WO-20..27, cycle 18+)

Work-ordered this cycle (design doc:
`docs/implementation/20-solver-abstraction.md`; architecture AD-19
solver plugin seam + AD-20 evidence attestation added to
00-architecture.md). Completing these turns the green static core
into a toolchain that ships real manufacturing packages. Dependency
order (graph in implementation/README.md):

- [ ] **WO-20 solver plugin layer**: entry-point pack discovery
      (`regolith.model_packs`), the ONE subprocess solver adapter
      (DischargeRequest/SolverResponse JSON over stdio; failure =
      `harness.adapter_error` indeterminate, never a pass), per-pack
      version folded into evidence keys (BE-1 extended), pack
      conformance suite `tests/packs/`. Also the Phase E
      harness-as-separate-process seam (absorbs the sec. 6 item).
- [ ] **WO-21 evidence signing**: `Attestation` envelope over the
      AD-18 content address (never a hash input), ed25519, quarry
      trust key designations decide the conferred tier (INV-14
      verbatim), release gate enforces `trust: >=` floors on
      computed evidence; invalid signature -> indeterminate. Adds
      **INV-28 evidence attribution** to the ledger WITH proof
      argument in the same change.
- [ ] **WO-22 mech geometry realizer**: feature IR -> build123d/OCCT
      -> STEP (Phase C items 8-9), post-geometry verification of
      static predictions, realized-geometry record as evidence.
- [ ] **WO-23 L2 numeric solves** (Rust, `regolith-ir` `solve`
      feature, faer): rigid statics -> real interface-load envelopes,
      stiffness network, exact sketch residual closure (OPEN-5
      residue; completes the WO-11 ledger's other half).
- [ ] **WO-24 elec structural realizer**: allocation-search component
      binding against registry records, netlist emission, KiCad
      layout adapter (place/route/DRC; DRC report = evidence, layout
      = pinned artifact), post-route extraction hook. EXPLICIT CUTS:
      FPGA/bitstream path, firmware measured-DB, SPICE extraction
      (reopen criteria in the WO).
- [ ] **WO-25 manufacturing backends + `regolith ship`** (L6):
      mech STEP+BOM+fab notes, elec gerber/drill/PnP/BOM via the
      pinned layout, signed ship manifest; ship refuses anything
      short of `--release` totality (INV-24) incl. trust floors.
      Backends serialize evidence, never decide (regolith/07 sec. 6).
- [ ] **WO-26 harness completion**: temporal/containment claim-form
      lowering (peak/settles/rms/stays_within), unit-suffix + named
      bound resolution, dB terms (Kestrel link budget end-to-end),
      buck efficiency/transient packs, numeric-tier + planner-adapter
      base classes, INV-12 match-set-growth over the lockfile diff.
- [ ] **WO-27 reference external FEA pack (feldspar -- name and
      separate-repo placement CONFIRMED by owner 2026-07-05; lives at
      `../feldspar`, never in the regolith wheel)**: CalculiX + gmsh
      via the WO-20 adapter, mesh-convergence eps, signed evidence;
      the outside-consumer proof of the whole plugin contract.
- [ ] **WO-28 rule packs (DFM/DRC/ERC authoring surface + engine)**:
      the inside of `dfm:`/`drc:`/`erc:` blocks (design:
      `docs/implementation/21-rule-packs.md`, AD-21) -- in-language
      `rule` decls (`forall <var> in <query>` + `demand:`/`advise:` +
      `per:` citation + `expect:` pass/fail fixtures), Rust engine in
      the lowering passes, `resolves: ... from free` eager resolution
      with rule-provenanced Causes, overrides EXCLUSIVELY via the
      existing waive ladder, `regolith rules test|try` CLI, authoring
      guide for domain experts (the sit-down-with-the-DML-professor
      workflow), reference packs `std.sheet_metal` + `jlc_2l`
      (un-phantoms the corpus `process=` refs). Opens with its own
      spec cycle (grammar into the track docs + design log). Static
      half needs only WO-05/08/19 (dispatchable NOW); realized-fact
      half lands with WO-22/24. Closes the sec. 8 tracked cut
      "eager DFM resolution ... blocked on the DFM rule engine
      surface".
- [ ] **WO-05 residual (unblocks INV-16)**: promote the elec
      behavioral bodies (`spec:`/`ports:`/converter/`on`-event) to
      typed CST and feed `ConverterGraph` from real `.cupr`; un-xfail
      the INV-16 end-to-end fixture. Also unblocks future behavioral
      packs (cuprite/03) -- do before or alongside WO-24's extraction
      work, not after.

### 8. Orchestrator + quarry + ship pipeline

- [x] **Orchestrator** (`regolith.orchestrator`): build tiers (T0..T3,
      `tiers.py`), harness evidence cache keyed with registry version
      folded in (`cache.py`, INV-1/BE-1, blake3 matching the Rust key),
      obligation->`DischargeRequest` translation + routing to the harness
      registry (`translate.py`/`discharge.py`, harness selects+computes,
      orchestrator owns caching/ordering), the lazy loop with sensitivity
      hooks (`loop.py`, regolith/12), and the top build driver with the
      release-gate totality check (`orchestrate.py`, INV-24). Tests:
      `tests/test_orchestrator.py`. TRACKED CUTS: (a) eager DFM
      resolution of `free` reads the core's `resolutions` payload but does
      not yet re-drive DFM rules Python-side -- blocked on the DFM rule
      engine surface (the core emits resolved values; no Python rule
      re-derivation was in scope); (b) the obligation translator lowers
      only the scalar-comparison claim form and parses literal bounds,
      deferring (honestly) on `within`/temporal/non-literal bounds --
      blocked on WO-05 typing quantity expressions at claim sites; (c) the
      harness-as-separate-process seam is preserved (obligations stay
      serializable, keys are pure functions of the payload) but not yet
      split out (roadmap Phase E item 13).
- [x] **Quarry/lodestone** (`regolith.quarry`): registry client over
      httpx with an injectable transport (`client.py`), lodestone sparse
      index (`index.py`) + content-addressed blake3 archive fetch with
      hash-pin verification (INV-22), manifest-declared sources
      (`sources.py`), signature-carried trust with local key sets
      (`trust.py`, INV-14 -- hosting confers nothing), yank-not-delete
      semantics, and `quarry vendor` offline vendoring with re-verified
      reads (`vendor.py`). Tests: `tests/test_quarry_registry.py` (mock
      transport, never the network). Added `blake3` dep. TRACKED CUT:
      publish-side computed-semver re-check (regolith/11 sec. 10.6) is
      server-side and out of this client's scope.
- [ ] **Registry records:** verify `registry/{stm32g0,atsamd21,rp2040}`
      against real datasheet revisions; upgrade evidence tier from
      `community` (they say so in-file).
- [x] **CI/CD (AD-12):** GitHub Actions -- fast gate (`cargo-deny` in
      it), 3-OS matrix + the determinism hash-diff job
      (`tests/determinism_hash.py`), `maturin-action` wheels (abi3,
      manylinux/musllinux/macos-universal2/windows), fuzz smoke (60s),
      tag-release to PyPI (`regolith`, `release.yml`).
      `.github/workflows/{ci,release}.yml`; docs: `docs/implementation/
      10-test-infra-and-ci.md`.

### 9. Test-infrastructure completeness (AD-11) -- can proceed in parallel

- [x] **cargo-fuzz** lexer/parser/CBOR-decode targets ("never panics",
      "CST covers every input byte" -- AD-3); `fuzz/` detached
      workspace, `make fuzz` runs 60s each (degrades without nightly
      cargo-fuzz), CI fuzz-smoke job.
- [x] **insta** snapshots for CST/AST/tokens dumps, diagnostics,
      formatter output over representative corpus files
      (`crates/regolith-syntax/tests/snapshots.rs`); `make snapshots`
      review flow.
- [x] **criterion** benches over the Kestrel corpus
      (`crates/regolith-syntax/benches/parse.rs`, `make bench`);
      `cargo llvm-cov` (degrades if absent) + coverage.py under
      `make coverage`.

### 10. Later (roadmap "Later" -- post-1.0)

- [ ] Rust migration of remaining hot paths; kinematics model packs
      (v2, OPEN-3 closed for v1 D64); statistical allocation pack +
      capability distributions (OPEN-2 closed D63); a UI; LSP/wasm hosts
      as new consumers of `regolith-api` (not rewrites).

## Cycle 10 (2026-07-03) -- DONE (WO-01 scaffold + name change)

Ledger: `docs/design-log/2026-07-03-cycle-10.md` (D81). No spec
changes (hematite 0.13 / cuprite 0.10 unchanged).

- [x] WO-01 built: hybrid Rust/Python workspace (9 crates + maturin +
      uv), `rockhead._core` importable, pyo3-log bridge proven,
      `make install && make check` green. Status: done.
- [x] D81: owner renamed the names to a single geology theme --
      mill -> **hematite** (`.hem`), loom -> **cuprite** (`.cupr`),
      umbrella -> **rockhead**; quarry/lodestone kept. Extensions
      chosen to avoid collisions (`.loom` clashed with loompy). Rename
      swept across code + living docs + examples (file renames incl.);
      docs/archive/ and docs/design-log/ left verbatim as history.

## Cycle 9 (2026-07-03) -- DONE (implementation architecture + names)

Ledger: `docs/design-log/2026-07-03-cycle-9.md` (F92, D78-D79). No
spec changes (mech 0.13 / elec 0.10 unchanged).

- [x] D78/D80: names DECIDED by owner -- mill (`.mill`) / loom
      (`.loom`); quarry confirmed; registry = **lodestone** (D80);
      umbrella dist/CLI name still open (candidate: wright)
- [x] D79: `docs/implementation/00-architecture.md` (AD-1..16,
      normative): Rust core (logos + rowan CST + hand-written parser;
      entity DB/queries/borrows/ledgers; blake3 + canonical CBOR
      content addressing; one diagnostic renderer) behind a coarse
      abi3 PyO3 boundary; Python orchestrator/harness/quarry/CLI
      (uv, pydantic v2, typani, typer); schemas single-sourced in
      Rust -> generated pydantic (CI drift-checked); determinism
      rules + 3-OS golden-hash CI; DX contract (make install / dev /
      check) leads the document
- [x] WO set updated: WO-01 rewritten (hybrid scaffold), WO-18 added
      (FFI bridge + schema pipeline), every WO carries a Language:
      header, WO-05's lark note superseded by AD-3,
      implementation/README ground rules + dependency graph redone
- [x] F92: the spec's four-component split and serializable
      obligations landed exactly on the Rust/Python seam -- no spec
      accommodation needed for the hybrid architecture

## Cycle 8 (2026-07-03) -- DONE (the final pass: emptied the queue)

## Cycle 8 (2026-07-03) -- DONE (the final pass: emptied the queue)

Ledger: `docs/design-log/2026-07-03-cycle-8.md` (F88-F91, D62-D77).
Versions: mech 0.13 / elec 0.10. Mandate: fresh read; resolve ALL
open questions; make the specs powerful. Meta-finding (F90): every
remaining open resolved to EXISTING machinery -- zero new mechanisms
were needed, the completeness signal for the regolith.

- [x] D54 -> SETTLED (D62): second organic use was already in the
      corpus (PayloadPcb<bits: image>, F88); injection-not-templating
      discipline recorded (regolith/04 sec. 1)
- [x] Mech opens closed: OPEN-2 allocation policies are pack math
      (D63); OPEN-3 kinematics = v2 model packs, syntax sufficient
      (D64); OPEN-5 constraint vocab = closed SolveSpace-equivalent
      set (D65); OPEN-6 re-import = re-pin + re-resolve + T2, diff is
      a report (D66); OPEN-8 surface state joins the contact
      coherence key (D67); OPEN-11 refining per-(op, geometry-class)
      (D68)
- [x] Elec opens closed: EOPEN-5 pre-layout lazy loop (D69); EOPEN-6
      no workload sublanguage, consequence of D60 (D70); EOPEN-8
      modes are config variables (D71); EOPEN-9 conformance depth is
      pack content (D72); EOPEN-10 HIL = by test (D73); EOPEN-11 EMC
      = honest deferral working (D74); EOPEN-13 nogoods per-run +
      stated cross-run soundness condition (D75); EOPEN-14 WCET
      models are registry content (D76)
- [x] SOPEN-3 technical half: registry hosting model (regolith/11
      sec. 10, D77) -- sparse index + content-addressed archives,
      manifest-declared sources, signing carries trust (hosting never
      does), yank-not-delete, quarry vendor; INV-22 corollary added
      in the same change
- [x] Fresh-read sweep: last stale marker fixed ([ELEC-TBD] profile
      row, F89); both open-questions docs restructured with
      deferred-with-reopen-criteria sections (F91); track README
      status lines made true; naming candidates written (cycle-8
      log sec. C)

## Cycle 7 (2026-07-03) -- DONE (closed the judgment queue)

Ledger: `docs/design-log/2026-07-03-cycle-7.md` (F85-F87, D55-D61).
Versions: mech 0.12 / elec 0.9. Mandate: resolve everything a
less-capable agent should not be trusted with.

- [x] SOPEN-6 -> the geom role kit (regolith/10 sec. 3a): 7 role
      predicates, each a declared-measures + T2-measurement pair both
      realizers evaluate; Kestrel pack conforms (D55)
- [x] SOPEN-5 -> logarithmic unit views (regolith/02 sec. 5a):
      views of linear quantities; one-reference sum rule validated by
      experiment; corners commute; INV-17 extended; Kestrel link
      budget is now a real dB claim (D56)
- [x] EOPEN-18 -> harvest vocabulary + profile windows (cuprite/02,
      regolith/02 sec. 5): supply=definite, resources as profiled
      boundary truth, convert endpoints, store(q) retention overload
      (D57)
- [x] EOPEN-12 -> settled on three records: G0 (flat table), SAMD21
      (F85: function_modes + combos), RP2040 (column rules + PIO
      wildcard + required companions); tier=community until datasheet
      hashes verified (D58)
- [x] `all` canonical, `all_parts` retired, corpus swept (D59);
      OPEN-7 settled for v1 -- no host language in design source
      (D60); OPEN-12 closed (D61)

## Cycle 6 (2026-07-03) -- DONE (the LARGE-project stress test)

Ledger: `docs/design-log/2026-07-03-cycle-6.md` (F74-F84, D47-D54).
Versions: mech 0.11 / elec 0.8. Built **Kestrel**
(`examples/cubesat/`, ten files): 1U cubesat, both languages, shared
contract pack, quarry.toml, 4 boards + structure + deployable antenna
+ FPGA payload + firmware + flatsat target. The regolith held; the
failures were unstated composition rules and two domain gaps.

- [x] EOPEN-17 CLOSED (D47): payload.deda is the two-bank decider
- [x] Intent partition pins: inline `hosted_on` (D48); budget kinds
      pack-provided incl. mass/energy (D49); path-import root (D51);
      orbit connections regolith-wide, `pairwise .. by <Mating>`
      (D53); composite-artifact impls (F82); config-domain resolution
      per enclosing context (F75); artifact-typed params [LEANING D54]
- [x] Newly opened, honestly: EOPEN-18 (energy harvest), SOPEN-5
      (dB quantities), SOPEN-6 (geom role predicates)

## Cycle 5 (2026-07-03) -- DONE (the fresh-eyes cycle)

Ledger: `docs/design-log/2026-07-03-cycle-5.md` (F57-F73, D42-D46).
Versions: mech 0.10 / elec 0.7. This was the last spec pass before
dispatching agents to write conforming/violating scripts against the
corpus.

- [x] Cold adversarial read; stale-marker sweep (OPEN-13 / EOPEN-7 /
      EOPEN-16 advertised open after closure); hematite/02 and hematite/03 doc
      examples fixed against their own rules (path rule, impl-not-
      feature mating sides, zones spelling, coherent budget)
- [x] Invariant re-derivation (F71): INV-7/INV-16 matched; INV-15
      gained the sketch DOF ledger; regolith/09 cause list aligned
      with INV-21
- [x] Decisions, code-informed: claim-position `within` is infix, no
      `=` (D42, grammar experiment); implicit `src` stage for
      artifact-position imports (D43); partitions use `remainder`
      (D44); EOPEN-4 retired (D46)
- [x] Collaboration: projects/files/teams (regolith/11 sec. 9) +
      INV-27 file-layout invariance; import forms defined (bare =
      registry contributions; path imports must name); acyclic imports
- [x] Corpus made self-contained for the agent test phase: gear
      reducer elisions completed (+ output side of the train),
      molded-clip harness run given real impls, weldment pattern forms
      normalized, supply-port direction + `use by_spec` + `err:`
      drift fixed

## Cycle 4 (2026-07-03) -- DONE

Ledger: `docs/design-log/2026-07-03-cycle-4.md` (F46-F56, D38-D41).
Versions: mech 0.9 / elec 0.6. Mandates: prove every invariant, audit
every decision (including user-directed ones), close the queue.

- [x] Invariant ledger `regolith/13-invariants.md` (INV-1..26, all
      guarantees incl. founding ones; per-model obligations flagged
      honestly); WO-17 makes it executable
- [x] Audit holes fixed: hint droppability defined (F46); orbit
      extension givens-invariance (F49); targets/parasitics hole
      (F52); waiver-vs-resolver (F47), match-set growth (F53), trust
      floors on deviations (F54), expiry (D40); reproducibility
      restated (F50); intent latency through flow budgets (F55);
      semver literal-slot scope (F51)
- [x] D1-D37 re-audited against the mantras: affirmed; five adjusted
- [x] EOPEN-7 closed entirely (formal sketch, elec 03 sec. 1a)
- [x] EOPEN-17 hardened with IO banking; frame-grabber shows
      `hosted_on`
- [x] Construct x level matrices updated; `--release` semantics
      restated (INV-24)

## Cycles 1-3 (2026-07-03) -- DONE (summaries)

- **Cycle 1** (mech 0.6 / elec 0.3): vocabulary made collision-free
  (`process`->`on`, `pins:`->`locked:`, `kept=`); spellings defined
  (`within [lo,hi]`, `[a,b]` vs `[i..j]`, `.bits`); weldments
  (`pieces:`), variants, derived-structure handles, `by circuit`
  bodies; 8 new examples; work orders WO-01..16.
- **Cycle 2** (mech 0.7 / elec 0.4): SOPEN-2 core settled (import-
  based cross-language refs, declaring-system obligation ownership,
  boundary subsumption); EOPEN-15 (`realizes`), EOPEN-16 (analog net
  discipline); panelization = planner; torch igniter + frame grabber
  + servo pair.
- **Cycle 3** (mech 0.8 / elec 0.5): the expert ladder + in-source
  `waive` (regolith 12); `policy:` (SOPEN-4); manual lowering +
  `extern` linkage (regolith 08 sec. 4); EOPEN-7 settled in shape
  via sampled buck; OPEN-1/OPEN-13 closed; gear reducer.

## Implementation kickoff (any time)

- [x] Dispatch WO-01 (scaffolding) -- DONE cycle 10
- [x] WO-02..18 built (cycles 10-11); AD-17/AD-18 added; WO-19 wired.
      All STUB bodies filled; `make check` green.
- [ ] Remaining work is the **## PATH TO DONE** ledger above; the
      static core (sec. 1-5, 8-9) is green, so what is left is
      sec. 6 residuals + **sec. 7 PATH TO SHIP (WO-20..27)** + the
      sec. 8 registry-record verification. Recommended dispatch
      order: WO-20 -> WO-21 (they gate everything solver-shaped and
      are pure-Python + one schema) and WO-28's spec-cycle + static
      half (independently dispatchable NOW, needs only the green
      core), then WO-22/WO-23/WO-26 in parallel, then WO-24, then
      WO-25, with WO-27 anytime after WO-21+WO-22 and WO-28's
      realized-fact half riding WO-22/24.

## Deferred / explicitly cut

- `avoid` (soft negative preference): only if an example produces an
  unexpressible preference.
- Multi-FPGA floorplanning / partial reconfiguration (EOPEN-17 v1 cut).
- EOPEN-7 is CLOSED; do not reopen without a failing example.
- docs/archive/ (pre-rename drafts 0.1-0.3) was removed from the tree
  before going public (still recoverable in git history); the repo is
  now uniformly ASCII with no exemptions.
