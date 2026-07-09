# TODO -- the live queue

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of earlier cycles.
Orientation, in order:

1. `docs/README.md` -- what this project is (four declarative
   engineering languages over one shared regolith + the toolchain).
2. `docs/spec/regolith/` 01 -> 13; `13-invariants.md` is the ledger of
   every guarantee (INV-1..28) with its proof argument -- normative.
3. The language tracks: `docs/spec/hematite/` (mech, `.hema`),
   `docs/spec/cuprite/` (elec/computer, `.cupr`), `docs/spec/fluorite/`
   (fluid, `.fluo`, ratified cycle 20), `docs/spec/calcite/`
   (civil/architectural, `.calx`, chartered cycle 26, ELABORATED
   cycle 27 -- 02/03/04 + corpus exist, awaiting owner
   ratification).
4. `docs/spec/toolchain/00-architecture.md` -- NORMATIVE (AD-1..29);
   wins over any WO body it conflicts with. Charters 25 (drawings +
   quality audit), 26 (pattern libraries), 27 (costing) are the
   cycle-27 additions.
5. `docs/workflow/README.md` -- ground rules + the DISPATCH
   PROTOCOL every agent follows + the WO dependency graph.
6. `docs/workflow/design-log/` -- dated ledgers of every finding (F1..) and
   decision (D1..); THE project history. Nothing here is re-decided
   without new evidence.
7. `examples/` -- the spec pressure corpus and golden workload.
8. SIBLING REPO `feldspar` (github.com/lognd/feldspar; locally
   checked out beside this repo) -- the external solver pack
   (M1 + symbolic core DONE through its WO-11). Its regolith-side
   contract asks live in
   `docs/spec/toolchain/20-solver-abstraction.md` sec. 7.

NAMES (settled; do not re-litigate): hematite / cuprite / fluorite /
calcite the languages; **magnetite** the package manager
(`magnetite.toml`; quarry + lodestone are RETIRED names, cycle 26
D132); **regolith** the toolchain/CLI/import name; **lithos** the
umbrella brand; **feldspar** the sibling solver pack. Dead names
(`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, and
calcite's old life as the fluid draft with `.calc`) appear verbatim
only in `docs/workflow/design-log/` history and negative tests.

House rules that are easy to violate accidentally: ASCII only
(repo-wide, no exemptions); one word one idea (hematite/04 sec. 1);
every decision argued against the mantras (Unambiguous >
Intent-based > User-friendly); every cycle gets a dated design log;
version-bump the track headers you materially change; new
guarantees enter the invariant ledger WITH a proof argument in the
same change; extension strings live in EXACTLY ONE registry module
(`regolith-syntax`); schemas are single-sourced in Rust (`make
schema`, never hand-edit `_schema/`); only `compiler.py` imports
`regolith._core`; errors are DATA (diagnostics / typani Results);
stdout is data, logs to stderr; `make check` green before any WO
closes, flipping its `Status:` line in the same change.

Current state in one line: the static core, invariant suite
(INV-1..28 real+green), fluorite track, realized-IR channel, staged
build loop, firmware realizer, docsgen/scaffolding, and pin-mux are
DONE; cycle 27 elaborated calcite, closed every deferral ledger, and
chartered drawings/patterns/costing -- what remains is the queue
below, all zero-shot.

## DISPATCH QUEUE (the one live queue; structural constraints in workflow/README)

Wave 0 -- owner, blocking:

- [x] **Ratify the calcite elaboration** -- DONE (D149, cycle-27
      log addendum): adversarial read clean, six folds applied,
      WO-46 Status flipped, WO-47/48 un-gated.

Wave 1 -- independent, dispatchable NOW, any order:

- [x] **WO-43** DONE (cycle 28): `regolith build [--release]` +
      `ship --build DIR`; two-command demo proven by subprocess
      test; WO-25 blocker cleared.
- [x] **WO-44** DONE (cycle 28): the one `regolith.plugins` seam;
      feldspar migrated to it in the same cycle (its lazy MANIFEST +
      the stderr logging fix -- a root [root]+stdout config in a
      plugin had hijacked host stdout).
- [x] **WO-49** DONE (cycle 28): FluidPort medium binding lands as
      E0210 (renumbered from the branch's E0204 at integration --
      ratified calcite owns E0204-E0209); WO-32 flipped done;
      compatibility-record positive case CUT (no spec shape exists;
      needs a design-log entry first).
- [x] **WO-51** DONE (cycle 28, three dispatches + D150/D151/D152):
      walk labels (E0442), lower.programs pass, cavity->flow_paths
      (E0443-E0445), coolant_gallery exemplar, SCHEMA_VERSION 17;
      fixtures 57-59. WO-22 honestly NOT flipped (sheet_bracket STEP
      needs the close-edge closure-solve + a sheet-gauge source --
      recorded on WO-22's Status line).
- [x] **WO-27** DONE (cycle 28): real-feldspar conformance run green
      (signed Valid(certified) discharge, uninstall reverts to
      indeterminate, byte-identical evidence hash). Cut, recorded in
      the WO file: CI separate-job leg; discretized ccx/gmsh path
      (planner resolves via cheaper closed-form at tested budget).
- [x] **WO-28 engine remainder** DONE (cycle 28): rule engine
      (E0601/E0603/E0604, resolves: with INV-21 causes), `rules
      test|try` CLI, reference packs, guide WORKING, INV-29 + proof;
      fixtures landed as 55/56 (renumbered at integration); honest
      residuals in the WO ledger (aggregates, elec static tier,
      realized-fact discharge rides WO-22/24).
- [x] **WO-34 D2-D6** DONE (cycle 28): harness elaboration +
      HarnessPayload (SCHEMA_VERSION 16), wiring_harness golden,
      fixtures 52-54 (renumbered); E0306 cross-net stays EXPECT-TODO
      (no cuprite net-membership seam into regolith-lower).
- [x] **WO-26 remainder** DONE (cycle 28): D102 typed temporal
      forms (E0435/E0436), D103 link budget e2e (E0437), D105a sweep
      domains + buck/transient packs, D105b numeric base, D105c
      planner shape, D105d schema half (growth-diff pass out per
      ledger). StaysWithin window field = recorded residual awaiting
      a schema slot.
- [x] SIMPLE DONE (cycle 28): `docs/guide/03-fluorite-guide.md`
      (five D122 examples, current spellings).
- [x] SIMPLE DONE (cycle 28): MCU registry verified against real
      datasheets; DS12232 rev citation FIXED (rev6 does not exist ->
      rev5). Tier deliberately NOT upgraded: INV-14 makes tiers
      above community earned by signature over content hash, not by
      text cross-check -- verification notes recorded in-file.
- [x] SIMPLE (Rust, real bug -- F103, cycle 27): the layout pass
      breaks on CRLF sources (a `\r\n` blank line before a top-level
      declaration kills the next declaration's parse). Windows is
      first-class (AD-12): accept `\r\n` uniformly in the lexer OR
      reject with a constructive encoding diagnostic; fixtures both
      ways; found via feldspar's autocrlf working tree.
      DONE: `\r\n` accepted uniformly (the lexer's `Newline` token is
      now `\r\n|\n`, so a CRLF source yields an IDENTICAL layout token
      stream to its LF twin); a lone `\r` (classic-Mac) is pinned to a
      constructive E0195 encoding diagnostic. Fixtures both ways in
      `crates/regolith-syntax/src/layout.rs` tests.
- [x] SIMPLE DONE (cycle 28): manifold + dune_buggy enrolled in
      golden + deferral corpus dicts (flagship sets only per the
      AD-11 tradeoff; goldens regenerated, not hand-edited).
- [ ] SIMPLE (owner-confirm first): remove the temporary
      `~/projects/cad -> lithos` symlink and prune the stale
      worktrees/branches (`git worktree list`; wo29-*, wo30-pack,
      wo31-*, wo32-*, stress-*, wo38-ls, wo41-docsgen ... all
      pre-merge or merged) -- verify each is subsumed by master
      (`git merge-base --is-ancestor`) before deleting; then
      `make install && make check` from the real path.

Wave 2 -- after their named gates:

- [x] **WO-45** DONE (cycle 28): stdlib/ std.* catalog + TOML
      record loader + de-phantoming test; benchmark-memo datasets
      cited in-record; D153 rules std.compute/std.fluorite
      compiler-owned builtins.
- [x] **WO-52** DONE (cycle 28): Mixer edge kind + declared-outlet
      E0210 exemption (no laundering; fixture 51), gn2_purge golden,
      FOPEN-1 CLOSED in fluorite/04.
- [ ] **WO-25 remainder** manufacturing backends close-out -- after
      WO-43; its RealizedLayout leg also wants the WO-24 producer
      below.
- [ ] **WO-24 end-to-end half** (lowering output -> BlockRequirement
      bridge, now unblocked by WO-29; the real-KiCad
      `RealizedLayout` producer + its WO-42 `put` seam). ENVIRONMENT
      UPDATE (cycle 26): kicad-cli 10.0.4 is on PATH and `make
      install` links system pcbnew into the venv (`make
      kicad-link`) -- `real_kicad_available()` is OPEN and the
      `-m kicad` tier runs real (2 passed). Note: KiCad deprecates
      the SWIG pcbnew API; prefer kicad-cli/IPC where possible.
- [ ] **WO-50** drawings + schedules backends w/ quality audit
      (AD-27/D140) -- after WO-25 framework; schema + mech + fluid
      legs dispatchable before WO-48; civil sheets after WO-48;
      SCHEMA_VERSION serialization rule applies.
- [x] **WO-47** DONE (cycle 28): `.calx` end-to-end at L0-L1, all 5
      corpus designs zero-diagnostic, goldens enrolled; E0204/E0208
      + terminal-half-of-E0209 wired via Circulation/LoadPath
      disciplines. Escalated to WO-48: E0205/E0206/E0207 + the
      tributary half of E0209 (need net_core reachability traversal
      / quantity eval); `assembly` CST left generic (homonym).
- [ ] **WO-40** lints + `check --watch` (serializes with anything
      editing regolith-lower's pass driver, incl. WO-51).
- [ ] **WO-38 remainder** language server (crate scaffold +
      lifecycle landed; the WO file's ledger has the rest).
- [ ] **WO-39** editor extension (grammar-generation half
      dispatchable before WO-38 finishes).

Wave 3 -- the tail:

- [ ] **WO-48** calcite lowering + `std.civil` -- after WO-47 +
      WO-45 (+ WO-28 for the code-pack half; its L2-check half may
      land first, the WO says how to split). Un-gates: WO-50 civil
      leg, WO-54 civil estimator, feldspar's frame-consumer WO.
- [ ] **WO-53** pattern libraries v1 (AD-28/D144) -- after WO-45 +
      WO-44 + the WO-28 engine remainder.
- [ ] **WO-54** costing v1 (AD-29/D147) -- after WO-45/WO-44;
      estimator set scopes to landed gates (its dependency note);
      SCHEMA_VERSION serialization rule applies.
- [x] SIMPLE DONE (cycle 28): `docs/guide/04-calcite-guide.md`
      (worked corpus tour, cross-track MEP section; guide README
      numbering settled 01-04 = track order).
- [ ] Cross-run nogood cache (cuprite EOPEN-13/D75; pure
      orchestrator work, soundness condition already stated: key on
      catalog record revisions the blame set consumed).
- [ ] Core-residual xfails (recorded, honest): WO-12's
      cross-boundary INV-13 fixture (needs entity-DB bound_kinds
      end-to-end), WO-11's cross-boundary INV-15 fixture (needs
      populated walks through the FFI), INV-19's escalation-edge
      clause (needs escalation-edge lowering, WO-12 family), INV-12
      match-set growth over the lockfile diff (WO-26 D105 family),
      INV-04 givens-invariance half (discharging model side).
      Each lives beside its WO; none blocks anything else.
- [x] Firmware realizer follow-up DONE (cycle 28): `on_events`
      crosses the FFI; `events_from_on_blocks` builds EventDecl from
      the real typed OnBlock CST (pin/interrupt facts stay
      caller-supplied -- WO-35 territory, not CST data).
- [ ] WO-33 cut follow-ups if wanted (its close-out lists two small
      example/doc slices -- optional).

## DISPATCH RULES (unchanged, load-bearing)

- Every dispatch follows `docs/workflow/README.md`'s protocol
  VERBATIM-BY-REFERENCE in the prompt; agents never spawn their own
  subagents; single-slice work goes to a plain agent type, not an
  orchestrator type.
- Dispatched agents work ONLY in their isolated worktree -- never
  cd to or operate on the shared repo path, including for
  self-correction. Coordinator re-verifies every "landed"/"green"
  claim from its own checkout (`git branch -v` first -- collect
  tools can silently move HEAD).
- Verify a worktree agent's branch point (`git merge-base BRANCH
  master`) before trusting its diff; rebase stale bases, keep both
  sides on conflict, regenerate (never hand-merge) generated files
  (`make schema`, goldens).
- After any merge touching Rust or SCHEMA_VERSION: `make install`
  before `make check` (stale `_core` otherwise).
- New `examples/negative/` fixtures: check filename-number
  collisions against master's CURRENT state (numbering does not
  git-conflict).
- Findings from corpus/stress agents promote per D124's rules
  (cycle-23 log).

## WATCH (unchanged conditions, do not re-litigate)

- F79 (computer at intent altitude) -- only if a real team splits
  ownership there.
- Reopen-criteria ledgers, thinned by cycle 27: fluorite/04 is
  fully decided (FOPEN-1 answered/D142, FOPEN-2 closed/D141);
  hematite/07 sec. 2a's cavity item is SCHEDULED (WO-51, D143);
  cuprite/08 sec. 1a re-reviewed, dispositions stand; calcite/04
  carries the civil deferrals (drawings non-goal revised by D140;
  construction cost closed by D147). Each remaining entry names the
  exact evidence required; nothing less counts. The technical open
  queue is EMPTY by design (F90).
- AD-26's non-goal (tracks as plugins) -- reopen only on a real
  third-party track attempt preserving AD-24.

## Deferred / explicitly cut (project-level)

- `avoid` (soft negative preference): only if an example produces
  an unexpressible preference.
- Multi-FPGA floorplanning / partial reconfiguration (EOPEN-17 v1
  cut).
- Registry HOSTING service (server side): out of client scope
  (regolith/11 sec. 10 stands; publish-side semver re-check is
  server work).
- Post-1.0: Rust migration of remaining hot paths; statistical
  allocation pack (D63); a UI; wasm hosts as new `regolith-api`
  consumers. (Kinematics packs, formerly this list: SCHEDULED by
  D144 -- the mechanism-library halves ride WO-53 + feldspar's
  dynamics phase.)
- History: every completed cycle's ledger is in `docs/workflow/design-log/`;
  completed WO details are in each WO file's close-out. This file
  carries NO history by design (D137).
