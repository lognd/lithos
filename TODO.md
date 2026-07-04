# TODO -- design cycles

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of cycles 1-4. That is
deliberate: your job is a fresh-eyes adversarial read. Orientation:

1. `docs/README.md` -- what this project is; revision log per cycle.
2. `docs/substrate/` 01 -> 13 in order; `13-invariants.md` is the
   ledger of every guarantee with its proof argument -- it is
   normative.
3. `docs/mech/`, `docs/elec/` -- the two language tracks. NAMING IS
   SETTLED (D78, renamed cycle 10): mech = **hematite** (`.hem`),
   elec = **cuprite** (`.cupr`), package tool = **quarry**, registry
   = **lodestone**, umbrella toolchain/CLI = **rockhead**; one geology
   theme. The rename sweep has landed, so docs/examples use
   `hematite`/`cuprite` throughout.
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
(docs/archive/ exempt, verbatim); one word one idea (mech/04 sec. 1
has the principles + justified-overload registry + retired list);
every decision argued against the mantras (Unambiguous > Intent-based
> User-friendly, in that priority); every cycle gets a dated design
log; version-bump the track headers you materially change; new
guarantees go into the invariant ledger WITH a proof argument in the
same change.

## Next (all delegable)

- [x] DISPATCH: WO-02..18 built (cycles 10-11). Every STUB body filled,
      `make check` green. Architecture extended (AD-17 lowering pipeline
      crate `rockhead-lower`, AD-18 canonical encoder in
      `rockhead_util::canon`); WO-19 added and wired. See the full
      remaining-work ledger below: **## PATH TO DONE**.
- [ ] DISPATCH: conforming + rule-breaking script generation against
      the corpus (the original plan); the retired-vocabulary list
      (mech/04 sec. 4) and the invariant test column (substrate/13)
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
      distribution/CLI/import name is **rockhead** (the miner);
      registry **lodestone** (D80). All names settled -- one geology
      theme (quarry/lodestone/rockhead/hematite/cuprite).
- [ ] WATCH (unchanged conditions, do not re-litigate): F79 (computer
      at intent altitude) if a real team splits ownership there;
      reopen-criteria lists in mech/07 sec. 2a and elec/08 sec. 1a --
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
      proceed); (e) conformance/impl/extern/import obligations emitted
      (BE-6, INV-13 -- cubesat obligations 40 -> 93); (f) structural
      `Cause` derivation from the `ValueSource` grammar (BE-5, replaces
      the text heuristic). TRACKED CUT: (d) monomorphization is a real
      SEAM (`checks.rs::expand_generics` enumerates every generic decl
      header) but concrete instantiation USE-site args are still opaque
      (WO-05 does not type `Foo<Bar>` at call sites), so per-point
      expansion / dead-generic detection stays blocked on WO-05 -- INV-11
      xfail reason updated to name this. Marker: seam doc-comment in
      `checks.rs`.
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
- [~] **WO-11 (profiles) -> ledger half DONE.** The heuristic text-scan
      `parse_walk` is replaced by a structural CST consumer
      (`rockhead_syntax::walk::parse_walk`) that reads the typed
      `WalkBody`/`WalkStep` nodes and the sibling `HoleBlock`/
      `RegionsBlock`/`ConstraintsBlock`/`ExportsBlock` nodes (gathered at
      profile-body level). The DOF ledger, branch-pin completeness, and
      export-anchoring checks in `rockhead-sem` `profile` run off the
      typed structure; tested over the real corpus walk bodies +
      synthetic balanced/imbalanced/branch-pin/anchoring fixtures. CUT:
      exact zero-residual sketch closure is the constraint solver's DOF
      analysis (mech/07 OPEN-5, implementation-owned, out of scope); the
      ledger is the sound conservative half (INV-15 conservation). The
      cross-boundary INV-15 fixture stays xfail until WO-19 feeds
      populated walks end-to-end.

### 2. Parser hardening (`rockhead-syntax`) -- unblocks WO-19/12/11

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
- [x] **Subject-attributed parse errors** (enables INV-20 gating) --
      DONE. A stray closing bracket at statement position emits `E0193`
      MALFORMED_IN_BODY attributed to the enclosing declaration subject
      (secondary span into the subject header + a `SubjectError` CST
      node). Test:
      `parser::tests::malformed_in_body_stmt_is_attributed_to_subject`.
      rockhead-lower's per-subject INV-20 gate (WO-19) can now consume
      the attribution.
- [x] **FE-3:** ASCII-enforce source at the lexer -- DONE. Layout pass
      rejects any non-ASCII character with `E0194` (batch-emitted).
      Tests in `layout.rs`.
- [x] **FE-4:** parse unit exponent suffixes (`m2`, `s2`) so `W/m2` and
      `kg/s2` work -- DONE in `rockhead-qty::unit` (`parse_atom`); false
      `kg.m/s2` docstring example fixed. Test
      `unit::tests::parses_unit_exponent_suffixes`.
- [x] **FE-8:** DONE end-to-end. Name-resolved INV-17 `==` ban now lives
      in `rockhead-sem::resolve` (`check_equality_ban` over a per-decl
      `QuantityClass` field table); `a == b` between two continuous names
      fires E0102, discrete counts do not. Wired into the `lower.checks`
      pass (INV-20 gated) and verified through `rockhead.compiler.check`.
      The syntactic half (unit-literal operand) stays in `checks.rs`; the
      `TODO(FE-8)` there was narrowed to a cross-reference. Tests in
      `resolve.rs` + retained syntactic guard in `checks.rs`.
- [x] **FE-9:** formatter now canonicalizes (respacing around
      operators/`:`/`,`, tight calls/paths/quantities), not identity --
      DONE. Meaning-preserving + idempotent. Tests in `formatter.rs`.
- [x] **FE-10:** parse `within [lo, hi]` demanded windows -- DONE. Typed
      `WindowExpr` (guarded on a following `[`; temporal `within` stays
      opaque). `grammar.ebnf` updated. Tests in `parser.rs`.

### 3. Quantity core (`rockhead-qty`) audit fixes

- [x] FE-2 (missing INV-21 causes extern/derived-intent/policy) -- DONE.
- [x] FE-5 (offset-unit tolerance delta bug) -- DONE.
- [x] **FE-1 (HIGH): logarithmic-unit views** (substrate/02 sec. 5a).
      `dB`/`dBm`/`dBi`/`dBc` stored linear in `rockhead-qty::log`; one L1
      reference-legality check (`log_sum_reference`) wired in
      `rockhead-syntax::checks`: `dBm + dBm` is `E0104` (linear product
      mW^2 is not a power), `dBm + dBi - dB` is a legal power. Enables
      the INV-17 log-sum case and the Kestrel link budget as a real
      dB claim.
- [x] **FE-6:** outward-round unit-converted bounds in `Interval::new`
      and `contains` (cross-unit soundness, AD-6/INV-9).
- [x] **FE-7:** deleted the stale `V`/`W`/`Hz`-absent comments in
      `checks.rs` and the WO-05 header (the table now has them).

### 4. Obligation keying (`rockhead-oblig` + `rockhead-lower`)

- [x] **BE-1 (HIGH, INV-1):** fold the harness model-registry version
      into the obligation/evidence-cache key so a model upgrade
      invalidates cached evidence. Registry versions are Python-side
      (AD-1) -> thread at discharge time. DONE:
      `Obligation::evidence_cache_key(registry_version)` threaded from
      `harness.MODEL_REGISTRY_VERSION` through the facade/FFI/discharge;
      `TODO(BE-1)` marker removed. Tests in `rockhead-oblig`,
      `rockhead-lower`, and `tests/test_ffi_bridge.py`.
- [x] **BE-2 (HIGH, INV-1):** DONE. `given.materials`/`given.loads` are
      populated from the decl's typed `Field` tree
      (`claims.rs::given_for_decl`): `material`/`materials` fields and a
      `loads:` block's child lines. Two claims differing ONLY in material
      now hash differently (INV-1 mutation half green, both in a
      `rockhead-lower` unit test and `test_inv_01_...changes_the_key`).
      `TODO(BE-2)` marker removed.

### 5. WO-17 invariant suite -> all green (`tests/invariants/`, both sides)

25 of 27 remain xfail. Un-xfail each with a real fixture as its
mechanism lands. Grouping by blocker:

- [~] Enabled once the pipeline is complete (sec. 1-2). FLIPPED GREEN
      this cycle (WO-19 depth pass): INV-20 (per-subject check gating),
      INV-13 (conformance obligation emitted for impl bindings), INV-01
      mutation half (given: materials/loads). Still xfail with updated
      blocker reasons: INV-11 (monomorphization -- seam exists but
      use-site instantiation args opaque, WO-05), INV-13 discharge half
      (needs the Python harness equivalence model), INV-18, INV-06,
      INV-27 (split-file fixture).
- [ ] Enabled by the checks landing over real input (BE-7): INV-04
      (symmetry soundness), INV-05 (ownership finality), INV-15 (ledger
      conservation), INV-23 (region exclusivity). STILL xfail: the FE-8
      L1 name-resolution primitive (`rockhead_sem::resolve`) landed and is
      wired end-to-end, but it resolves scalar-field quantity CLASSES, a
      different axis than these invariants need. INV-04/05/23 need
      `PredictedDelta.symmetry`/`.modifies`/`.regions_touched` (and
      `EntityKind::Region`) flowing from parsed source; `rockhead-lower`
      cannot build them while WO-05 leaves pattern/mating/keepout bodies
      as opaque islands. xfail reasons updated to name this true blocker
      (the sem mechanisms are done + unit-tested; the grammar surface is
      the gap). TRACKED CUT: remaining blocker = WO-05 structuring the
      domain `OpaqueIsland` bodies.
- [ ] Enabled by FE-1: INV-17 log-sum case. The Rust-side L1 check
      (`checks::two_reference_log_sum_is_flagged`, E0104) now lands
      `dBm + dBm`; a Python end-to-end fixture through
      `rockhead.compiler.check` remains to be added to
      `tests/invariants/test_inv_17_type_soundness.py` (the `==` and
      interval-misuse halves already pass).
- [ ] Enabled by the harness + ladder + release layers (sec. 6-8):
      INV-02 (ladder safety), INV-03 (hint droppability), INV-07
      (boundary subsumption), INV-08 (target additivity), INV-09
      (corner conservatism, harness-model side), INV-12 (waiver honesty
      end-to-end), INV-14 (trust totality), INV-16 (converter
      non-instantaneity), INV-19 (promises-not-actuals), INV-22
      (foreign-content pinning), INV-24 (release-gate totality), INV-25
      (coverage honesty), INV-26 (defaults-test meta-invariant).
- [ ] Flip WO-17 `Status:` to done only when every INV test is real and
      green (no xfail, no stub).

### 6. Verification harness (`python/rockhead/harness/`) -- roadmap Phase C/D

- [ ] Model registry + signature/impl matching (Python).
- [ ] Closed-form model packs (numpy/scipy): bolted-joint diagram, beam,
      Lame, sheet-metal DFM, buck/link budgets -- the corpus's claims.
- [ ] Numeric models + planner adapters; `deterministic:` flag folded
      into evidence hash inputs (INV-10).
- [ ] Harness as a separate process (roadmap Phase E, item 13); keep
      obligations serializable across the boundary (already true).

### 7. Realizers + geometry + L2 solvers -- roadmap Phase C/D

- [ ] Feature IR -> build123d/OCCT -> STEP export (Phase C, item 8).
- [ ] Post-geometry verification pass: confirm static topology
      predictions (item 9); one eager sheet-metal DFM pack (item 10).
- [ ] L2 numeric solves in Rust behind `rockhead-ir`'s `solve` feature
      (`faer`): rigid statics, stiffness network (Phase D); sketch
      solver integration (OPEN-5 residue, language surface closed D65).
- [ ] Elec realizer adapters: vendor toolchains, netlist/`extern`
      linkage, behavioral layer (elec/03), the two-bank FPGA path.

### 8. Orchestrator + quarry + ship pipeline

- [ ] **Orchestrator** (`rockhead.orchestrator`): build tiers, evidence
      cache, eager DFM resolution of `free`, the lazy loop with
      sensitivity hooks (roadmap Phase E, item 15).
- [ ] **Quarry/lodestone** (`rockhead.quarry`): registry client (httpx),
      trust/signing, vendoring; lodestone sparse index +
      content-addressed archives (substrate/11 sec. 10).
- [ ] **Registry records:** verify `registry/{stm32g0,atsamd21,rp2040}`
      against real datasheet revisions; upgrade evidence tier from
      `community` (they say so in-file).
- [ ] **CI/CD (AD-12):** GitHub Actions -- fast gate, 3-OS matrix + the
      determinism hash-diff job, `maturin-action` wheels (abi3,
      manylinux/musllinux/macos-universal2/windows), fuzz smoke,
      tag-release to PyPI (`rockhead`); `cargo-deny` in the fast gate.

### 9. Test-infrastructure completeness (AD-11) -- can proceed in parallel

- [ ] **cargo-fuzz** lexer/parser/CBOR-decode targets ("never panics",
      "CST covers every input byte" -- AD-3 makes this part of parser
      done); runs 60s in CI, long ad hoc.
- [ ] **insta** snapshots for CST/AST dumps, diagnostics, formatter
      output; `make snapshots` review flow.
- [ ] **criterion** benches over the Kestrel corpus (`make bench`);
      `cargo llvm-cov` + coverage.py under `make coverage`.

### 10. Later (roadmap "Later" -- post-1.0)

- [ ] Rust migration of remaining hot paths; kinematics model packs
      (v2, OPEN-3 closed for v1 D64); statistical allocation pack +
      capability distributions (OPEN-2 closed D63); a UI; LSP/wasm hosts
      as new consumers of `rockhead-api` (not rewrites).

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
were needed, the completeness signal for the substrate.

- [x] D54 -> SETTLED (D62): second organic use was already in the
      corpus (PayloadPcb<bits: image>, F88); injection-not-templating
      discipline recorded (substrate/04 sec. 1)
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
- [x] SOPEN-3 technical half: registry hosting model (substrate/11
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

- [x] SOPEN-6 -> the geom role kit (substrate/10 sec. 3a): 7 role
      predicates, each a declared-measures + T2-measurement pair both
      realizers evaluate; Kestrel pack conforms (D55)
- [x] SOPEN-5 -> logarithmic unit views (substrate/02 sec. 5a):
      views of linear quantities; one-reference sum rule validated by
      experiment; corners commute; INV-17 extended; Kestrel link
      budget is now a real dB claim (D56)
- [x] EOPEN-18 -> harvest vocabulary + profile windows (elec/02,
      substrate/02 sec. 5): supply=definite, resources as profiled
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
+ FPGA payload + firmware + flatsat target. The substrate held; the
failures were unstated composition rules and two domain gaps.

- [x] EOPEN-17 CLOSED (D47): payload.deda is the two-bank decider
- [x] Intent partition pins: inline `hosted_on` (D48); budget kinds
      pack-provided incl. mass/energy (D49); path-import root (D51);
      orbit connections substrate-wide, `pairwise .. by <Mating>`
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
      EOPEN-16 advertised open after closure); mech/02 and mech/03 doc
      examples fixed against their own rules (path rule, impl-not-
      feature mating sides, zones spelling, coherent budget)
- [x] Invariant re-derivation (F71): INV-7/INV-16 matched; INV-15
      gained the sketch DOF ledger; substrate/09 cause list aligned
      with INV-21
- [x] Decisions, code-informed: claim-position `within` is infix, no
      `=` (D42, grammar experiment); implicit `src` stage for
      artifact-position imports (D43); partitions use `remainder`
      (D44); EOPEN-4 retired (D46)
- [x] Collaboration: projects/files/teams (substrate/11 sec. 9) +
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

- [x] Invariant ledger `substrate/13-invariants.md` (INV-1..26, all
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
  `waive` (substrate 12); `policy:` (SOPEN-4); manual lowering +
  `extern` linkage (substrate 08 sec. 4); EOPEN-7 settled in shape
  via sampled buck; OPEN-1/OPEN-13 closed; gear reducer.

## Implementation kickoff (any time)

- [x] Dispatch WO-01 (scaffolding) -- DONE cycle 10
- [x] WO-02..18 built (cycles 10-11); AD-17/AD-18 added; WO-19 wired.
      All STUB bodies filled; `make check` green.
- [ ] Remaining work is the **## PATH TO DONE** ledger above (in-progress
      WOs 11/12/19, parser hardening, audit FE-*/BE-*, WO-17 invariants,
      harness/realizers/solvers, orchestrator/quarry, CI + ship). The
      parser `hosted_on`-tail desync (sec. 2) is the highest-value next
      fix -- it recovers lost obligations and unblocks several invariants.

## Deferred / explicitly cut

- `avoid` (soft negative preference): only if an example produces an
  unexpressible preference.
- Multi-FPGA floorplanning / partial reconfiguration (EOPEN-17 v1 cut).
- EOPEN-7 is CLOSED; do not reopen without a failing example.
- docs/archive/ contains pre-rule non-ASCII; kept verbatim by charter.
