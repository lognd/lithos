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

1. `regolith/` -- the abstract backing layer. Read this first; every
   language track is an instantiation of it.
2. `hematite/` -- the mechanical language. The most mature track.
3. `cuprite/` -- the electrical and computer language.
4. `fluorite/` -- the fluid-circuit language (ratified v1, cycle 20).
5. `calcite/` -- the civil/architectural track (charter only so far;
   spec elaboration is WO-46).
6. `guide/` -- the teaching guides (getting started + per-track).

## Directory map

```
docs/
  regolith/    the shared abstract layer (domain-neutral)
    01-principles.md              mantras, defaults test, four-component architecture
    02-quantity-core.md           quantities, units, intervals, zones, registries
    03-value-sources.md           the five-source grammar for every number
    04-contracts.md               interfaces, connections, conformance, vendors
    05-ownership-and-queries.md   entity DB, queries, borrows, datums, symmetry
    06-execution-model.md         stages, scopes, snapshot/commit semantics
    07-claims-and-evidence.md     obligations, signatures, margin-driven discharge
    08-lowering-architecture.md   the generic L0-L6 stack
    09-build-and-lockfile.md      build tiers, lockfile, diagnostics, deferral
    10-domain-binding.md          the regolith-concept x domain binding table
    11-packages-and-stdlib.md     package manager (magnetite), registries,
                                  trust, the stdlib catalog; projects, files,
                                  and team workflow
    12-overrides-and-hints.md     the expert ladder: pins, hints, policy,
                                  override-by-evidence, waive; audit surface
    13-invariants.md              the invariant ledger (INV-1..28): every
                                  guarantee with mechanism + proof argument

  hematite/    mechanical track (unified spec; version on its header)
  cuprite/     electrical + computer track (version on its header)
  fluorite/    fluid-circuit track, `.fluo` (ratified v1, cycle 20)
  calcite/     civil/architectural track, `.calx` (charter, cycle 26)
  guide/       teaching guides (getting started, per-track guides,
               DFM-rule authoring)

  design-log/  dated findings + decisions ledgers, one per design
               cycle -- THE project history; the revision trail that
               used to live in this file is cycle-by-cycle in there

  implementation/  the build-the-toolchain tree (ground rules +
                   dispatch protocol + dependency graph in its README)
    00-architecture.md   NORMATIVE architecture (AD-1..26)
    grammar.ebnf         normative grammar artifact
    design/              numbered cross-WO design charters
    work-orders/         WO-01..49, agent-executable

../examples/     the spec pressure corpus (see examples/README.md):
                 tracks/ per-language single-file tests, systems/
                 multi-file projects (cubesat Kestrel, cnc_router,
                 espresso_machine, sdr_transceiver), hdl/ coverage
                 fixtures, negative/ diagnostic fixtures, registry/
                 component records
../stdlib/       the standard library packages (std.*, D135) as they
                 land (WO-45)
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

## Conventions

- All documentation and source examples are ASCII-only. The languages
  themselves define ASCII canonical operator spellings (`&`, `dia`,
  `+-`, `deg`, `mu_`); formatters may render unicode, files never
  store it.
- Spec versions ride each track's header line and bump when the track
  materially changes; the per-cycle change ledgers live in
  `design-log/` (one dated file per cycle, findings F* and decisions
  D* numbered globally).

## Revision history

Lives in `design-log/`, one dated ledger per design cycle -- that is
the authoritative trail of every finding (F1..) and decision (D1..).
This file intentionally carries no duplicate changelog (D137: git
history and the design logs are the archive).
