# TODO -- the live queue

## START HERE (note to a fresh instance)

You are (probably) reading this with no memory of earlier cycles.
Orientation, in order:

1. `docs/README.md` -- what this project is (four declarative
   engineering languages over one shared regolith + the toolchain).
2. `docs/regolith/` 01 -> 13; `13-invariants.md` is the ledger of
   every guarantee (INV-1..28) with its proof argument -- normative.
3. The language tracks: `docs/hematite/` (mech, `.hema`),
   `docs/cuprite/` (elec/computer, `.cupr`), `docs/fluorite/`
   (fluid, `.fluo`, ratified cycle 20), `docs/calcite/`
   (civil/architectural, `.calx`, chartered cycle 26 -- charter
   only until WO-46).
4. `docs/implementation/00-architecture.md` -- NORMATIVE (AD-1..26);
   wins over any WO body it conflicts with.
5. `docs/implementation/README.md` -- ground rules + the DISPATCH
   PROTOCOL every agent follows + the WO dependency graph.
6. `docs/design-log/` -- dated ledgers of every finding (F1..) and
   decision (D1..); THE project history. Nothing here is re-decided
   without new evidence.
7. `examples/` -- the spec pressure corpus and golden workload.
8. SIBLING REPO `../feldspar` -- the external solver pack
   (M1 + symbolic core DONE through its WO-11). Its regolith-side
   contract asks live in
   `docs/implementation/design/20-solver-abstraction.md` sec. 7.

NAMES (settled; do not re-litigate): hematite / cuprite / fluorite /
calcite the languages; **magnetite** the package manager
(`magnetite.toml`; quarry + lodestone are RETIRED names, cycle 26
D132); **regolith** the toolchain/CLI/import name; **lithos** the
umbrella brand; **feldspar** the sibling solver pack. Dead names
(`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, and
calcite's old life as the fluid draft with `.calc`) appear verbatim
only in `docs/design-log/` history and negative tests.

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
DONE; what remains is the queue below.

## DISPATCH QUEUE (the one live queue; structural constraints in implementation/README)

Wave 1 -- independent, dispatchable NOW, any order:

- [ ] **WO-43** `regolith build [--release]` CLI verb (D136; small,
      Python; makes the two-command demo real; unblocks the WO-25
      remainder).
- [ ] **WO-44** plugin architecture v1 (`regolith.plugins`, AD-26/
      D134; folds the four discovery seams into one).
- [ ] **WO-46** calcite spec elaboration (docs + corpus from the
      SETTLED charter `docs/calcite/01-charter.md`; output is
      owner-ratified before Status flips).
- [ ] **WO-49** `impl FluidPort<medium=...>` binding + FOPEN-1
      (closes WO-32's only open item).
- [ ] **WO-27** reference external FEA pack conformance
      (feldspar-side M1+WO-11 are DONE in `../feldspar`; this is the
      lithos-side conformance run; needs WO-20/21/30 -- all done).
- [ ] **WO-28 engine remainder** (deliverables 3-8: in-language
      `rule` decls, engine passes, `rules test|try`, authoring
      guide, reference packs; its root blocker WO-29 is DONE).
- [ ] **WO-34 D2-D6** routed runs (grammar D1 landed; use the
      WO-32-style slice split recorded in the WO file).
- [ ] **WO-26 remainder** (D102 temporal claim forms, D103 link
      budget end-to-end, D105a-d; D104 landed).
- [ ] SIMPLE: `docs/guide/04-fluorite-guide.md` (ratified
      `docs/fluorite/` is the source; match the other guides'
      voice; teaching arc = the five D122 track examples).
- [ ] SIMPLE: deny.toml cleanup (pre-existing cargo-deny failures:
      pyo3 RUSTSECs, wildcards key rename, yanked num-bigint;
      document each ignore or upgrade).
- [ ] SIMPLE: verify `registry/{stm32g0,atsamd21,rp2040}` against
      real datasheet revisions; upgrade evidence tier from
      `community` (they say so in-file).
- [ ] SIMPLE (owner-confirm first): remove the temporary
      `~/projects/cad -> lithos` symlink and prune the stale
      worktrees/branches (`git worktree list`; wo29-*, wo30-pack,
      wo31-*, wo32-*, stress-*, wo38-ls, wo41-docsgen ... all
      pre-merge or merged) -- verify each is subsumed by master
      (`git merge-base --is-ancestor`) before deleting; then
      `make install && make check` from the real path.

Wave 2 -- after their named gates:

- [ ] **WO-45** stdlib v1 (`stdlib/`, D135) -- after WO-44 (else
      registrations move twice).
- [ ] **WO-25 remainder** manufacturing backends close-out -- after
      WO-43; its RealizedLayout leg also wants the WO-24 producer
      below.
- [ ] **WO-24 end-to-end half** (lowering output -> BlockRequirement
      bridge, now unblocked by WO-29; the real-KiCad
      `RealizedLayout` producer + its WO-42 `put` seam; kicad-cli
      absence in this sandbox stays the recorded environment cut).
- [ ] **WO-22 end-to-end half** (the `FeatureProgram` producer from
      lowered `.hema` -- the hematite/07 sec. 2a cavity->flow_paths
      deferral bounds v1 scope; D130's declared `flow_paths` +
      hand-authored programs remain the legitimate producer until
      the profile/Walk surface is promoted).
- [ ] **WO-47** calcite front end -- after WO-46 ratification.
- [ ] **WO-40** lints + `check --watch` (serializes with anything
      editing regolith-lower's pass driver).
- [ ] **WO-38 remainder** language server (crate scaffold +
      lifecycle landed; the WO file's ledger has the rest).
- [ ] **WO-39** editor extension (grammar-generation half
      dispatchable before WO-38 finishes).

Wave 3 -- the tail:

- [ ] **WO-48** calcite lowering + `std.civil` -- after WO-47 +
      WO-45 (+ WO-28 for the code-pack half; its L2-check half may
      land first, the WO says how to split).
- [ ] Core-residual xfails (recorded, honest): WO-12's
      cross-boundary INV-13 fixture (needs entity-DB bound_kinds
      end-to-end), WO-11's cross-boundary INV-15 fixture (needs
      populated walks through the FFI), INV-19's escalation-edge
      clause (needs escalation-edge lowering, WO-12 family), INV-12
      match-set growth over the lockfile diff (WO-26 D105 family),
      INV-04 givens-invariance half (discharging model side).
      Each lives beside its WO; none blocks anything else.
- [ ] Firmware realizer follow-up (WO-37 close-out note): promote
      `EventDecl` to consume WO-36's typed `OnBlock` CST directly.
- [ ] WO-33 cut follow-ups if wanted (its close-out lists two small
      example/doc slices -- optional).

## DISPATCH RULES (unchanged, load-bearing)

- Every dispatch follows `docs/implementation/README.md`'s protocol
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
- Reopen-criteria ledgers: hematite/07 sec. 2a, cuprite/08 sec. 1a,
  fluorite/04, calcite charter sec. 7 -- each names the exact
  evidence required; nothing less counts. The technical open queue
  is EMPTY by design (F90).
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
- Post-1.0: Rust migration of remaining hot paths; kinematics model
  packs (v2, D64); statistical allocation pack (D63); a UI; wasm
  hosts as new `regolith-api` consumers.
- History: every completed cycle's ledger is in `docs/design-log/`;
  completed WO details are in each WO file's close-out. This file
  carries NO history by design (D137).
