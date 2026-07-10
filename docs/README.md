# lithos -- Documentation

Declarative, goal-oriented engineering design languages built on one
shared regolith:

- **hematite** -- mechanical design (parts, processes, assemblies).
- **cuprite** -- electrical and computer design (circuits, boards,
  logic, processors).
- **fluorite** -- fluid circuits (feed systems, coolant loops,
  hydraulics, pneumatics; ratified cycle 20, D93).
- **calcite** -- civil/architectural design (spaces, structure,
  envelope; chartered cycle 26, D133 -- the youngest track).

Named on one geology theme (D78, cycle 10; fluorite cycle 20;
magnetite + calcite cycle 26): **hematite** is iron ore (steel,
structure -> mechanical); **cuprite** is copper ore (wire, current ->
electrical); **fluorite** is the mineral named for flowing (flux ->
fluids); **calcite** is the mineral of limestone and cement (->
buildings); **magnetite** (the package manager) attracts them all;
everything is worked by **regolith** (the shared toolchain). The
whole project -- languages, toolchain, registry -- is umbrella-branded
**lithos**. Retired names: `quarry`/`lodestone` (-> magnetite, D132),
`mill`/`loom`/`dcad`/`deda`, and calcite's dead draft usage as the
fluid track's name (`.calc`, D93; the civil track uses `.calx`);
retired names appear verbatim only in `design-log/` history.

All the languages invert the traditional workflow:

```
Traditional:  Implementation -> (manual analysis) -> "does it work?"
Here:         Claims + Contracts -> (solvers, provers) -> Implementation + Evidence
```

The designer declares what the artifact must do, how it will be made,
and what it promises to other artifacts. The system derives the
implementation, allocates the numbers nobody wants to pick by hand,
and attaches evidence to every physical claim. Text is the single
source of truth: diffable, reviewable, and statically checkable
without rendering or simulating anything -- which makes design
generation (human or LLM) a locally verifiable problem. The north
star: write a declarative file, inject a high-skill engineer at the
intermediate steps only if necessary, and get something out the end
that just works.

The languages are deliberately "different vocabularies over the same
machinery": the type system, the contract model, the ownership
discipline, the claim/obligation/evidence pipeline, the lowering
architecture, and the build system are all defined once, in the
regolith, and bound per domain. Learning one language should mean
already knowing 80% of the others.

## Reading order

1. `spec/regolith/` -- the abstract backing layer. Read this first; every
   language track is an instantiation of it.
2. `spec/hematite/` -- the mechanical language. The most mature track.
3. `spec/cuprite/` -- the electrical and computer language.
4. `spec/fluorite/` -- the fluid-circuit language (ratified v1, cycle 20).
5. `spec/calcite/` -- the civil/architectural track (charter cycle 26,
   elaborated cycle 27, ratified 2026-07-08, D149; front end landed,
   WO-47).
6. `guide/` -- the teaching guides (getting started + per-track).

## Directory map

Three top-level categories (D138, cycle 26): `spec/` is technical
truth, `workflow/` is process, `guide/` is for people.

```
docs/
  spec/          TECHNICAL -- normative specifications
    regolith/    the shared abstract layer (domain-neutral), 01-13;
                 13-invariants.md is the guarantee ledger (INV-1..30)
    hematite/    mechanical track (unified spec; version on header)
    cuprite/     electrical + computer track
    fluorite/    fluid-circuit track, `.fluo` (ratified v1, cycle 20)
    calcite/     civil/architectural track, `.calx` (charter cycle 26;
                 ratified D149, 2026-07-08)
    toolchain/   00-architecture.md (NORMATIVE, AD-1..35),
                 grammar.ebnf, numbered design charters (10-..37-);
                 20-solver-abstraction.md sec. 7-8 is the feldspar
                 pack contract (AD-26 plugin seam)

  workflow/      PROCESS -- how the project is built
    README.md    ground rules, the dispatch protocol, the WO
                 dependency graph
    work-orders/ WO-01..83, agent-executable, one per dispatchable unit
    design-log/  dated findings + decisions ledgers, one per design
                 cycle -- THE project history, verbatim (never edited)

  guide/         PEOPLE -- teaching + authoring guides
                 (getting started, per-track guides, then
                 authoring/tooling guides: DFM rules, optimization,
                 graphite, parity reports, CAM/HDL verification,
                 board correctness, design testing)

../examples/     the spec pressure corpus (see examples/README.md):
                 tracks/ per-language single-file tests, systems/
                 multi-file projects (cubesat Kestrel, cnc_router,
                 espresso_machine, sdr_transceiver, dune_buggy,
                 regen_engine, reaction_wheel, small_office), hdl/
                 coverage fixtures, negative/ diagnostic fixtures,
                 registry/ component records
../stdlib/       the standard library packages (std.*, D135)
../apps/         out-of-wheel applications (graphite: the TUI +
                 local-web GUI interaction surface, WO-59/AD-31;
                 see guide/12-graphite.md)
```

## Status legend

Used throughout:

- **[SETTLED]** -- decided; changing it is a spec revision.
- **[LEANING: x]** -- default direction chosen, revisit allowed cheaply.
- **[OPEN-n] / [EOPEN-n] / [FOPEN-n] / [SOPEN-n]** -- needs a decision
  (mech / elec / fluid / regolith numbering). The technical open queue
  is EMPTY by design (F90); deferred items carry explicit reopen
  criteria in each track's open-questions doc.
- **[SEAM-n]** -- designed on both sides, the joint itself unspecified.

## Cross-domain composition

A mechatronic system is one `system` with parts from several domains:
a board is simultaneously an electrical artifact and a mechanical one;
a building (calcite) hosts fluid loops (fluorite) and power (cuprite).
The regolith's contract model is what makes this tractable -- an
interface may carry roles and promises from more than one domain's
quantity namespaces. See `regolith/10-domain-binding.md`.

## feldspar (the optional solver pack)

**feldspar** (github.com/lognd/feldspar) is an external, optional
solver pack -- its own repo, checked out beside this one for local
dev. It supplies higher-fidelity FEA and closed-form engineering
verification models that plug into the regolith harness's model
registry through the one plugin seam (`regolith.plugins`, AD-26).
It is not required: a build without feldspar checked out degrades
honestly, discharging whatever the in-tree closed-form model packs
can prove and reporting the rest as open obligations rather than
failing. The pack contract itself -- what a pack must implement,
claim-kind naming, coverage/evidence encoding, the payload-ref
channel -- is normative in
`spec/toolchain/20-solver-abstraction.md` sec. 7-8. Cite paths inside
it as `feldspar:<path>` (never a `../` path; see Conventions below).

## Conventions

- Cross-repo citations are repo-qualified, never filesystem-relative:
  `feldspar:docs/spec/09-model-integration.md` means that path in the
  `feldspar` repo (github.com/lognd/feldspar). `../` paths out of
  this repository are banned in living docs (they do not resolve on
  GitHub); design-log history keeps whatever it originally said.

- All documentation and source examples are ASCII-only. The languages
  themselves define ASCII canonical operator spellings (`&`, `dia`,
  `+-`, `deg`, `mu_`); formatters may render unicode, files never
  store it.
- Spec versions ride each track's header line and bump when the track
  materially changes; the per-cycle change ledgers live in
  `design-log/` (one dated file per cycle, findings F* and decisions
  D* numbered globally).

## Revision history

Lives in `workflow/design-log/`, one dated ledger per design cycle -- that is
the authoritative trail of every finding (F1..) and decision (D1..).
This file intentionally carries no duplicate changelog (D137: git
history and the design logs are the archive).
