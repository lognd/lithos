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

- [ ] DISPATCH: WO-02/03/04/06 in parallel (WO-01 scaffold is DONE,
      cycle 10); WO-05 (parser + grammar EBNF, AD-3 stack) is the
      long pole -- point its goldens at examples/cubesat/ first
      (largest corpus member), escalate spec ambiguities to a design
      log, architecture ambiguities to 00-architecture.md, never
      invent. WO-18 (FFI bridge) gates WO-14/15. Every dispatch
      follows the protocol in docs/implementation/README.md
      (hierarchical plan first, WO scope is a contract).
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
- [ ] Dispatch WO-02/03/04/06 in parallel (protocol:
      docs/implementation/README.md sec. "Dispatch protocol")
- [ ] WO-05 (parser + grammar EBNF) is the long pole; escalate spec
      ambiguities to a design log instead of inventing
- [ ] WO-17 (invariant suite) starts after WO-06 and grows with every
      WO

## Deferred / explicitly cut

- `avoid` (soft negative preference): only if an example produces an
  unexpressible preference.
- Multi-FPGA floorplanning / partial reconfiguration (EOPEN-17 v1 cut).
- EOPEN-7 is CLOSED; do not reopen without a failing example.
- docs/archive/ contains pre-rule non-ASCII; kept verbatim by charter.
