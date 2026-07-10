# lithos

lithos is four declarative engineering-design languages -- **hematite**
for mechanical parts and assemblies, **cuprite** for electrical and
computer designs, **fluorite** for fluid circuits, **calcite** for
civil/architectural design -- built over one shared regolith, plus the
**regolith** toolchain that type-checks them and discharges their
engineering claims against verification models. The core idea inverts
the usual workflow: instead of drawing an implementation and analyzing
it afterward, a design *states intent and obligations* (what the
artifact must do, how it is made, what it promises to its neighbors)
and the toolchain proves those obligations -- or reports honest
failures as data, with source spans and provenance. Text is the single
source of truth: diffable, reviewable, and statically checkable without
rendering or simulating anything.

## Names (one geology theme)

| Name          | What it is                                                                 |
|---------------|---------------------------------------------------------------------------|
| **lithos**    | the umbrella project (the languages + toolchain + registry); branding, not a code identifier |
| **hematite**  | the mechanical language; files `.hema`                                      |
| **cuprite**   | the electrical/computer language; files `.cupr`                            |
| **fluorite**  | the fluid-circuit language; files `.fluo` (ratified cycle 20)              |
| **calcite**   | the civil/architectural language; files `.calx` (chartered cycle 26, D133) |
| **regolith**  | the toolchain/CLI/import name (crates `regolith-*`, Python package `regolith`, lockfile `regolith.lock`) |
| **magnetite** | the package manager (manifest `magnetite.toml`, module `regolith.magnetite`, CLI `regolith magnetite`); its registry is "the magnetite registry" (cycle 26, D132; quarry/lodestone retired) |
| **feldspar**  | an external solver pack, its own repo (github.com/lognd/feldspar); optional -- discharges FEA and closed-form engineering claims through the pack contract, checked out beside this repo for local dev |

hematite, cuprite, fluorite, and calcite are deliberately "different
vocabularies over the same machinery": the type system, quantity/
interval engine, contract model, ownership discipline, and the
claim/obligation/evidence pipeline are defined once in the regolith
and bound per domain. Learning one language is most of the way to
knowing the others.

## Architecture in brief

The one-sentence shape: a Rust compiler core behind one coarse,
schema-versioned PyO3 boundary, wrapped by a Python orchestrator that
talks to the outside world. The split follows the spec's own
serialization point -- obligations are self-contained and serializable
-- so the boundary is coarse and stable rather than chatty.

- **Rust core** (`crates/regolith-*`): lexer (logos) + layout pass +
  lossless CST parser (rowan), the quantity/unit/interval engine, the
  entity database with queries/ownership/borrows, contract IR and
  budget arithmetic, lowering of claims to content-addressed
  obligations, and one diagnostic renderer. Pure, deterministic, and
  testable entirely without Python.
- **Python orchestrator** (`python/regolith/`): the verification
  harness (model registry plus numpy/scipy model packs that discharge
  physical claims), build tiers and the evidence cache, lockfile
  authorship, the `magnetite` package client, and the `regolith` CLI.

The harness discharges claims against a model registry; closed-form
model packs ship in this repo, and higher-fidelity models (FEA and
other numeric solvers) come from **feldspar**, an optional external
solver pack (github.com/lognd/feldspar, its own repo -- checked out
beside this one for local dev). feldspar is not required: a build
without it degrades honestly, discharging what the in-tree closed-form
packs can prove and reporting the rest as open obligations rather than
failing silently. It plugs in through the one plugin seam
(`regolith.plugins`, AD-26); the pack contract itself is normative in
[`docs/spec/toolchain/20-solver-abstraction.md`](docs/spec/toolchain/20-solver-abstraction.md)
sec. 7-8.

Errors are data on both sides: `regolith-diag` diagnostics in Rust,
typani `Result` values in Python; exceptions and panics are reserved
for programmer bugs. Shared schemas are single-sourced in Rust
(schemars) and code-generated into pydantic models. The full normative
architecture (decisions AD-1..29) is in
[`docs/spec/toolchain/00-architecture.md`](docs/spec/toolchain/00-architecture.md).

## A taste of the syntax

From [`examples/tracks/hematite/pillow_block.hema`](examples/tracks/hematite/pillow_block.hema),
a profile whose radius is left for the toolchain to allocate (`minimize`
picks the value that satisfies the obligations):

```
profile BodyOutline:
    walk:
        from base_plane
        line right                    # a: base
        line up                       # b: right wall
        arc tangent, bulge=left       # c: dome
        line down                     # d: left wall
        close
    constraints:
        a.length = 90mm
        b.length = 22mm
        c.radius = in [28mm, 36mm] minimize
        symmetric(b, d, about=mid_plane)
    exports:
        mid_plane: datum
```

The `examples/` tree holds many more, including a ten-file cubesat
project (`examples/systems/cubesat/`) used as the integration stress test.

## Getting started

Prerequisites: the pinned Rust toolchain (`rust-toolchain.toml`, stable
1.90.0) and [uv](https://github.com/astral-sh/uv) for the Python side.
One command sets up a working dev environment (uv sync plus building the
compiled extension into the venv):

```
make install
make check
```

`make check` is the single quality gate -- format, lint, types, and both
Rust and Python tests, cheapest first. Key targets:

| target       | does                                                        |
|--------------|-------------------------------------------------------------|
| `install`    | uv sync + build the `regolith._core` extension (debug)      |
| `dev`        | rebuild the extension into the venv on Rust change          |
| `check`      | full gate: fmt, lint, typecheck, core-import guard, tests   |
| `test`       | all tests (`test-rs` / `test-py` to split)                  |
| `snapshots`  | review insta snapshots                                      |
| `schema`     | regenerate the generated pydantic schema from Rust          |
| `bench`      | criterion benchmarks over the cubesat corpus                |
| `fuzz`       | fuzz the lexer/parser/CBOR decode (needs nightly cargo-fuzz)|
| `coverage`   | Rust + Python coverage                                      |
| `build`      | release wheel via maturin                                   |
| `install-graphite` | uv sync the `graphite` TUI/GUI app (`apps/graphite/`)  |

Run `make help` for the full list.

## Repository layout

```
docs/
  spec/            technical truth: regolith/ (shared abstract layer,
                    01..13), hematite/ cuprite/ fluorite/ calcite/
                    (the four language tracks), toolchain/ (normative
                    architecture + numbered design charters)
  workflow/        process: ground rules, dispatch protocol,
                    work-orders/, design-log/ (dated findings and
                    decisions, verbatim history)
  guide/           teaching guides, one per track plus authoring guides
crates/            the Rust core (regolith-util .. regolith-py)
python/regolith/   the Python orchestrator, harness, magnetite, and CLI
examples/          designs in target syntax (the golden / pressure-test corpus)
stdlib/            the standard library packages (std.*)
tests/             cross-boundary goldens, CLI end-to-end, and invariant tests
```

## The CLI

`regolith` is the single entry point; verbs include `check` (the
geometry-free linter), `fmt`, `debug`, `build`, `ship`, `doc`, `rules
test`/`rules try` (rule-pack authoring), `plugin list` (AD-26 plugin
seam), and the `magnetite` package-manager subtree (`magnetite new`,
`vendor`, `fetch`, `key`, `index`, `manifest check`, with `new` and
`vendor` also aliased at the top level). Run `regolith --help` or
`regolith <verb> --help` for the current, authoritative list --
verbs land and change per work order faster than this README does.

## Status

Honest state of the project:

- **Languages and specs: complete.** The regolith and all four language
  tracks (hematite, cuprite, fluorite, calcite) are settled; the
  technical open-question queue is empty by design. `docs/` is the
  normative source, led by the invariant ledger
  (`docs/spec/regolith/13-invariants.md`).
- **Toolchain: substantially built, `make check` green.** The Rust core
  (lexer, layout, CST parser, entity DB, quantity/interval engine,
  contract IR, and lowering to obligations), the PyO3 bridge, the
  Python orchestrator, the harness with closed-form model packs, and the
  `magnetite` package tool are implemented and pass the gate. CI runs
  format/lint/type/test on a matrix, with fuzzing and benchmarks wired.
- **Invariant suite (INV-1..29): mostly real green,** with a small
  number of deliberately tracked `xfail` fixtures where the enforcing
  machinery is still being wired.
- **Roadmap:** the mechanical geometry realizer (`FeatureProgram` IR
  through build123d/OCCT to STEP) has landed as a model pack; the
  numeric L2 solvers and higher-fidelity FEA verification remain
  future work -- FEA is expected to arrive via the optional feldspar
  solver pack rather than in-tree.

## License

GPL-2.0-only (the Linux kernel's license; owner-decided 2026-07-08):
free to use, study, modify, and redistribute -- derivatives play by
the same rules. Full text in `LICENSE`.
