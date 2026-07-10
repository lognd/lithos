# Implementation Work Orders

Agent-executable decomposition of the roadmap (mech `06-roadmap.md`):
WO-01..19 cover Phases A-B (schemas, parser, the geometry-free
`check` linter, lowering, harness spine); WO-20..29 cover Phases C-E
plus the solver/ship extensions (realizers, numeric solves, the
solver plugin layer + signed evidence per `design/20-solver-abstraction.md`,
rule packs per `design/21-rule-packs.md`, manufacturing backends, and the
lowering output surface per `design/23-lowering-output-surface.md`);
WO-30..37 cover cycles 20-21 (pack contract v2 per
`design/20-solver-abstraction.md` sec. 8, the fluorite fluid track per
`docs/spec/fluorite/`, computed fields, routed runs, the elec
pin-assignment completion, the elec behavioral bodies, and the
firmware realizer); WO-38..41 cover cycle 22 (the developer-tooling
surface per `design/24-developer-tooling.md`: language server, editor
extension, lints + watch, docsgen + scaffolding); WO-42 covers
cycle 24 (realized-domain IRs per AD-25/D128: L4 payload schemas,
realizer promotion, the realized-input channel, the staged build
loop); WO-43..49 cover cycle 26 (D132-D137: the `regolith build`
CLI verb, the AD-26 plugin seam, stdlib v1, the calcite civil track
spec/front-end/lowering, and the FluidPort medium binding);
WO-50..54 cover cycle 27 (D139-D147: drawings/schedules backends
with quality audit, the FeatureProgram producer, fluorite mixing +
gas corpus, pattern libraries, and costing); WO-55..60 cover cycle
30 (D159-D166: the optimization engine per `28-optimization.md`
with `by select` + section search + staged-loop optimization, the
interaction surface per `29-interaction-surface.md` -- pass
diagrams, config doctrine, the `graphite` TUI/GUI package -- and
stdlib growth batch C); WO-62..67 cover cycle 31 (D169-D175:
geometry depth per `30-geometry-lowering.md`, the parity bar +
flagship program per `31-flagships.md`, the stdlib depth program
per `32-stdlib-depth.md` (cross-repo with feldspar WO-23/24), and
CAM verification per `33-cam-verification.md`). As of cycle 21 (D107,
reaffirmed cycles 26 and 27) EVERY remaining work order is zero-shot
dispatchable: no WO requires a design decision its file plus cited
specs does not contain. WO-46's output (the elaborated calcite spec,
executed cycle 27) awaits the owner ratification pass that flips its
Status and un-gates WO-47/48 (the D93 fluorite precedent).
Each `WO-nn-*.md` is self-contained: goal,
normative spec references, deliverables, acceptance criteria,
dependencies. An implementer agent should be able to execute one work
order end-to-end reading only that file plus the referenced spec
sections.

## Layout (taxonomy per D138, cycle 26: spec / workflow / guide)

```
docs/
  spec/                TECHNICAL truth: the regolith + language
                       tracks, and toolchain/ (00-architecture.md
                       AD-1..35, grammar.ebnf, the numbered design
                       charters 10-..33- -- a charter wins over the
                       WO bodies it governs)
  workflow/            PROCESS: this file (ground rules, dispatch
                       protocol, dependency graph, status
                       conventions), work-orders/ (WO-01..67, one
                       file per dispatchable unit), design-log/
                       (dated F*/D* ledgers -- verbatim history)
  guide/               PEOPLE: getting started + per-track teaching
                       guides + authoring guides
```

**Architecture is decided and normative:
`../spec/toolchain/00-architecture.md`**
(AD-1..26). It defines the Rust/Python split, the workspace layout,
the parser stack, the FFI boundary, and the per-WO language
assignment (AD-14). Where an older WO body conflicts with it, the
architecture document wins; WO acceptance criteria stand.

## Ground rules (all work orders)

1. **Languages:** per `00-architecture.md` AD-1/AD-14 and each WO's
   `Language:` header line. Rust: pinned stable toolchain, workspace
   lints, `thiserror` (no `anyhow` in library crates), `tracing`
   everywhere; user-facing failures are `regolith-diag` diagnostics
   (values), `Err` is for infrastructure and bugs. Python 3.12+:
   models are **pydantic v2** (`ConfigDict(frozen=True)`), fallible
   operations return **typani** `Result[T, E]`; user-facing failures
   are error values, never exceptions; exceptions only for
   programmer bugs (`CoreBug` from the boundary included).
2. **Logging:** Rust `tracing` (span per pass, log every resolution
   decision and error path), bridged via pyo3-log; Python module
   logger + dictConfig per `~/.claude/refs/logging.md`. Never
   `print` for diagnostics -- the ONE diagnostic renderer lives in
   `regolith-diag` (AD-7).
3. **Layout** (fixed by WO-01 per AD-2): cargo workspace `crates/`
   (`regolith-util`, `regolith-diag`, `regolith-qty`, `regolith-syntax`, `regolith-sem`,
   `regolith-ir`, `regolith-oblig`, `regolith-api`, `regolith-py`) + Python package
   `python/regolith/` (`compiler.py` facade, `_schema/` generated,
   `orchestrator/`, `harness/`, `magnetite/`, `cli/`), pytest in
   `tests/`, goldens under `tests/golden/`. Strict crate layering;
   `regolith-py` contains marshalling only.
4. **Docs as part of done:** every public symbol gets a one-line
   docstring (Rust `///` included); each WO updates its listed doc
   artifacts in the same change.
5. **ASCII only** in every file. Conventional-commit messages, no
   Co-Authored-By line. Use `frob` utilities (edit staging, outline)
   for Python changes; `make check` must pass before a WO is closed.
6. **Naming:** all names are SETTLED (cycle 9 D78, renamed cycle 10;
   fluorite added cycle 20 D93; magnetite + calcite cycle 26
   D132/D133): languages **hematite** (mechanical, `.hema`),
   **cuprite** (electrical/computer, `.cupr`), **fluorite** (fluid
   circuits, `.fluo`), and **calcite** (civil/architectural, `.calx`
   -- chartered, WO-46..48); package manager **magnetite**
   (`magnetite.toml`; quarry/lodestone are retired names, the
   registry carries no separate name); the umbrella
   distribution/import/CLI name is **regolith** (lockfile
   `regolith.lock`) -- one geology theme. Extension strings live in
   ONE registry module (`regolith-syntax`); nothing else may
   hard-code any of these strings. Note on calcite: its pre-cycle-26
   usage as the fluid track's DRAFT name (with extension `.calc`) is
   dead, and `.calc` stays dead -- the civil track's extension is
   `.calx` (D133); the civil-track name assignment is a fresh
   cycle-26 owner decision.

## Dispatch protocol (every agent, every work order)

An agent picking up a WO must do these IN ORDER; no code before
step 4 is complete.

1. **Read, in order:** this README (ground rules), then
   `00-architecture.md` end-to-end (it is normative and wins over
   the WO body), then the WO itself, then every spec section the
   WO's `Spec:` line names. WO bodies written before cycle 9 may
   still phrase deliverables in Python terms; the `Language:`
   header + architecture doc decide what is actually built.
2. **Plan hierarchically before any leaf.** Decompose the WO
   top-down: deliverables -> components -> functions/types, down to
   leaves that are each trivially implementable, and map the WHOLE
   tree before implementing any single leaf. Identify, per leaf,
   which crate/module it lives in (AD-2 layering), what it depends
   on, and which acceptance criterion covers it.
3. **Write the plan down** as a checklist (TODO.md section or the
   dispatch's tracking mechanism) with one entry per leaf, plus one
   entry per WO acceptance criterion and per doc artifact. The
   checklist is driven to zero before the WO is closed; cut scope is
   recorded as cut, never silently dropped.
4. **Check the plan against the WO's acceptance criteria** -- every
   criterion must be covered by some leaf; every leaf must serve
   some deliverable. Anything in neither list is scope creep: leave
   it out.
5. **Stick to the work order.** The WO's scope is a contract: no
   extra features, no speculative generality, no refactors of
   neighboring code. On spec ambiguity, STOP and escalate to a
   design-log entry; on architecture ambiguity, escalate to
   `00-architecture.md`; never invent or quietly reinterpret.
6. **Close out:** `make check` green, invariant tests the WO enables
   un-reddened (WO-17 placement per AD-11), doc artifacts updated in
   the same change, WO `Status:` line flipped.

## Dependency graph

```
WO-01 scaffolding (hybrid workspace; both languages)
  -> WO-02 units/quantities -> WO-03 intervals/ranges -> WO-04 value sources   [Rust regolith-qty]
  -> WO-06 diagnostics                                                          [Rust regolith-diag]
WO-02..04, WO-06
  -> WO-05 lexer/parser (CST + typed AST)                                       [Rust regolith-syntax]
  -> WO-07 entity DB -> WO-08 query engine -> WO-09 ownership/borrows           [Rust regolith-sem]
  -> WO-10 stages/scopes                                                        [Rust regolith-sem]
  -> WO-11 profile walks (needs WO-05)                                          [Rust regolith-syntax + regolith-sem]
WO-05..11
  -> WO-12 contract IR (interfaces, matings, ledgers)                           [Rust regolith-ir]
  -> WO-13 claims -> obligations/evidence schemas                               [Rust regolith-oblig]
WO-06, WO-13
  -> WO-18 FFI bridge + schema pipeline + typed facade                          [both]
WO-12..13, WO-18
  -> WO-14 lockfile                                                             [Python orchestrator]
  -> WO-16 package/registry loader                                              [Python magnetite]
WO-05..13, WO-18
  -> WO-19 lowering pipeline (AST->entities->IR->obligations->discharge)        [Rust regolith-lower]
     -> gates WO-15 golden corpus + the bulk of WO-17
WO-05..14, 16, 18, 19 -> WO-15 `check` CLI + golden tests over examples/        [Python cli]

WO-13, WO-18, harness spine
  -> WO-20 solver plugin layer (packs + subprocess adapter)                     [Python harness; AD-19]
WO-20, WO-16
  -> WO-21 evidence signing + trust floors (adds INV-28)                        [both; AD-20]
WO-19, WO-20
  -> WO-22 mech geometry realizer (feature IR -> OCCT -> STEP)                  [Python realizer]
  -> WO-26 harness completion (claim-form lowering, numeric tier, planners)     [both]
WO-12, WO-11
  -> WO-23 L2 numeric solves (statics, stiffness, sketch) [Rust regolith-ir `solve`]
WO-16, WO-19, WO-20
  -> WO-24 elec structural realizer (bind -> netlist -> KiCad layout)           [Python realizer]
WO-22, WO-24, WO-14, WO-21
  -> WO-25 manufacturing backends + `regolith ship` (L6)                        [Python backends/cli]
WO-20, WO-21, WO-22
  -> WO-27 reference external FEA pack (packs/feldspar, separate distribution)  [Python, own wheel]
WO-05, WO-08, WO-19 (static half; realized-fact half also WO-22/24)
  -> WO-28 rule packs: DFM/DRC/ERC authoring surface + engine                   [Rust + Python cli; AD-21]
WO-19 (+ the WO-05 residue it selects)
  -> WO-29 lowering output surface (feature program, binding bridge,
     domain entities, connect->Mating)                                          [Rust regolith-lower/-sem/-syntax + schema; Python bridge]
     -> gates the END-TO-END halves of WO-22/WO-24, the WO-28 engine
        remainder (deliverables 3-8), and WO-23's connect->Mating cut
        (see `design/23-lowering-output-surface.md`, the F96 pattern)

WO-20, WO-21
  -> WO-30 pack contract v2 (structured coverage, payload-ref channel,
     given resolution + regimes, kind competition)                              [Rust regolith-oblig + Python harness/orchestrator]
     -> gates WO-27's remaining conformance surface + feldspar M4/M6
WO-05, WO-07/08
  -> WO-31 fluorite front end (.fluo, grammar/CST, AD-23 net core +
     elec discipline refit)                                                     [Rust]
WO-31, WO-30, WO-22 (engine half)
  -> WO-32 fluorite lowering (flownet payload + the routed-geometry
     extraction seam)                                                           [Rust + Python]
WO-30, WO-13/19
  -> WO-33 computed indexed fields (compute claims, field payloads)             [Rust + Python]
WO-32 (the extraction seam)
  -> WO-34 routed runs (cuprite harness: blocks, extracted lengths)             [Rust + Python]
WO-24 (engine half), WO-16
  -> WO-35 elec assignment completion (pin-mux solver, real-KiCad gate)         [Python realizer]
WO-05, WO-11
  -> WO-36 elec behavioral bodies (typed CST -> ConverterGraph, INV-16)         [Rust]
WO-35, WO-24 (engine half), WO-36, WO-16
  -> WO-37 firmware realizer (contract header, BSP codegen, extern bindings)    [Python realizer]
WO-05..19 (done)
  -> WO-38 language server regolith-ls (LSP on the compiler crates; AD-24)      [Rust]
     -> WO-39 editor extension `lithos` (generated grammars + bundled server)   [TypeScript editors/vscode]
        (grammar half of WO-39 is dispatchable before WO-38)
WO-06, WO-19, WO-16
  -> WO-40 lint framework + `check --watch` (Lint code family, [lints] config)  [Rust + Python]
WO-05, WO-16, WO-18
  -> WO-41 docsgen (`regolith doc`) + scaffolding (`magnetite new`)                [Python]
WO-30, WO-22 (engine half), WO-24 (engine half), WO-32 (D1/D2)
  -> WO-42 realized-domain IRs (L4 schemas, realizer promotion,
     realized-input channel, staged build loop; AD-25/D128)                     [Rust + Python]
     -> gates WO-32 D4b end-to-end, WO-34 extraction over real
        records, and WO-25's IR-derived reports
WO-42 (done), WO-25 framework
  -> WO-43 `regolith build [--release]` CLI verb (D136)                          [Python cli]
WO-20, WO-21, WO-25 framework, WO-37
  -> WO-44 plugin architecture v1 (`regolith.plugins`, AD-26/D134)               [Python]
WO-16, (WO-44 preferred)
  -> WO-45 stdlib v1 (`stdlib/` std.* packages, D135)                            [Python + records]
docs/spec/calcite/01-charter.md (SETTLED, D133)
  -> WO-46 calcite spec elaboration (docs + corpus; owner-ratified)              [docs]
     -> WO-47 calcite front end (.calx, grammar/CST, civil net disciplines)      [Rust]
        -> WO-48 calcite lowering + std.civil (frame IR per AD-25; needs WO-45;
           code-pack half also WO-28 engine)                                     [Rust + Python]
WO-31, WO-32 (done)
  -> WO-49 FluidPort medium binding + FOPEN-1 (closes WO-32's last item)         [Rust]
     -> WO-52 fluorite Mixer + compressible-regime corpus (D141/D142)            [Rust]
WO-25 framework, WO-42 (done), (WO-44 preferred; civil leg after WO-48)
  -> WO-50 drawings + schedules backends (DrawingModel IR, quality audit;
     AD-27/D140)                                                                 [Rust + Python]
WO-42 (done), WO-11 (done), WO-29 (done)
  -> WO-51 FeatureProgram producer (Walk promotion + cavity->flow_paths;
     D143 -- closes WO-22's end-to-end half)                                     [Rust + Python]
WO-45, WO-44, WO-41, WO-28 engine remainder
  -> WO-53 pattern libraries v1 (seed packs + advise recognition;
     AD-28/D144)                                                                 [packages + Python]
WO-30 (done), WO-45, WO-44 (+ WO-48/planner gates per estimator)
  -> WO-54 costing v1 (profiles, records, estimators, itemized evidence;
     AD-29/D147)                                                                 [Rust + Python + records]
WO-30/42 (done), NogoodCache (done), WO-14 causes
  -> WO-55 optimization engine + THE cycle-30 schema bump (AD-30/D159/D160)      [Rust schemas + Python orchestrator/cli]
     -> WO-56 `by select` + calcite section search (D161; corpus verdicts)       [Rust + Python]
     -> WO-57 staged-loop (realized-domain) optimization (D162)                  [Python]
        (WO-56/57 serialize at integration: shared orchestrator/CLI surfaces)
     -> WO-58's trace-sheet slice; WO-59's trace view
WO-50 (done)
  -> WO-58 pass-visualization diagram producers (D165; bdf-shaped views)         [Python backends]
     -> WO-59 graphite v1: config + TUI + local-web GUI (AD-31/D163/D164)        [Python; apps/graphite]
        (WO-59 deliverable 1, `regolith config`, is independent -- may land first)
WO-45/53 conventions (done)
  -> WO-60 stdlib growth batch C (D166; feeds WO-56's demo, soft)                [records]
WO-55 (bump first), WO-58's landed layout/wiring conventions
  -> WO-61 ContractGraphPayload + contract-graph sheet (D167; the ONE
     serialized follow-up bump; completes WO-58's escalated D2)                  [Rust + Python]
WO-22/42/51/55/57 (done)
  -> WO-62 geometry depth: closure solve, gauge source, coverage ledger,
     RealizedAssembly (AD-32; owns cycle-31's bump 23->24)                       [Rust + Python]
WO-50 (done), WO-55 (done)
  -> WO-63 parity report in ship --explain (AD-33/D170)                          [Python]
31-flagships.md (charter)
  -> WO-64 flagship-1 printer: phase A contract-first NOW; B/C after
     WO-62+63 (AD-33/D172)                                                       [corpus authoring]
WO-45/53/60 conventions (done)
  -> WO-66 stdlib depth wave 1: tools/stdlib generation + exhaustive
     families (AD-34/D174; feldspar half = its WO-24, after its WO-23)           [Python + records]
WO-51/42/20/44 (done), (WO-66 soft for machine/tool records)
  -> WO-67 CAM verification v1: std.cam check-mode pack (AD-35/D175)             [Python pack]
feldspar WO-23 (its repo: tributary load paths; D173)
  -> WO-65 five-design section-search verdict flip (the WO-56/F108
     residual's named reopen; GATED on feldspar WO-23)                           [Python]
```

Sequencing (cycle 26 restatement; supersedes the D101/D107/D128
paragraphs -- their history is in the design logs): the live queue
and its order are maintained in ONE place, TODO.md's "DISPATCH
QUEUE" section. Structural constraints that stay true regardless of
queue order: anything bumping `SCHEMA_VERSION` serializes with
anything else that does (WO-48, WO-50, WO-54 all add schemas);
WO-40 and WO-51 serialize with anything editing regolith-lower's
pass driver; WO-47/48 are gated on WO-46's ratification; WO-45
wants WO-44 first (else its registrations move twice); WO-25's
remainder wants WO-43; WO-52 lands with or after WO-49 (it extends
that WO's consistency check); WO-53 wants WO-45 + the WO-28 engine
remainder; WO-54's estimator set scopes to its landed gates (its
dependency note).

WO-02/03/04/06 are parallelizable after WO-01. WO-07..11 are
parallelizable after WO-05. WO-17 (the invariant suite,
regolith/13) starts after WO-06 and grows with every WO: a WO is not
done while it reddens an invariant test it enables; test placement
per AD-11 (each INV family lands beside its enforcing layer;
cross-boundary INVs in pytest).

## Stub convention (architecture-first scaffolding)

The crates are being scaffolded architecture-first: the full public
type surface, module layout, and tests land first; the logic bodies a
less-capable agent can fill follow. Every deferred body is a greppable
marker so the remaining work is a single search:

```
grep -rn 'todo!("STUB WO-' crates/     # Rust bodies still to implement
```

Each marker names its WO and what it must do
(`todo!("STUB WO-03: outward-rounded endpoint sum ...")`). Trivial data
plumbing (constructors, accessors, serde derives, builders) is
implemented inline so types are usable and tests compile; only real
logic is stubbed. Tests for stubbed behaviour are written now and
`#[ignore]`-d with a reason ending `... pending`; un-ignoring them is
the acceptance signal when the body lands. A WO is `done` only when its
STUB markers are gone, its ignored tests pass, and `make check` is
green.

## Status

Mark each WO's Status line (`todo` / `in-progress` / `done` / `cut`)
in place; a cut must name why and where the scope went.
