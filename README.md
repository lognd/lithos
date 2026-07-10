# lithos

lithos is three declarative engineering-design languages -- **hematite**
for mechanical parts and assemblies, **cuprite** for electrical and
computer designs, **fluorite** for fluid circuits -- built over one
shared regolith, plus the
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
| **regolith**  | the toolchain/CLI/import name (crates `regolith-*`, Python package `regolith`, lockfile `regolith.lock`) |
| **magnetite** | the package manager (manifest `magnetite.toml`, module `regolith.magnetite`, CLI `regolith magnetite`); its registry is "the magnetite registry" (cycle 26, D132; quarry/lodestone retired) |

hematite and cuprite are deliberately "different vocabularies over the
same machinery": the type system, quantity/interval engine, contract
model, ownership discipline, and the claim/obligation/evidence pipeline
are defined once in the regolith and bound per domain. Learning one
language is most of the way to knowing the other.

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

Errors are data on both sides: `regolith-diag` diagnostics in Rust,
typani `Result` values in Python; exceptions and panics are reserved
for programmer bugs. Shared schemas are single-sourced in Rust
(schemars) and code-generated into pydantic models. The full normative
architecture (decisions AD-1..18) is in
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
  regolith/       the shared, domain-neutral abstract layer (01..13)
  hematite/        the mechanical language spec
  cuprite/         the electrical/computer language spec
  implementation/  normative architecture + work orders for the toolchain
  design-log/      dated findings and decisions, one file per design cycle
  audit/           audit findings ledgers (FE-*/BE-*)
crates/            the Rust core (regolith-util .. regolith-py)
python/regolith/   the Python orchestrator, harness, magnetite, and CLI
examples/          designs in target syntax (the golden / pressure-test corpus)
tests/             cross-boundary goldens, CLI end-to-end, and invariant tests
```

## Status

Honest state of the project:

- **Languages and specs: complete.** The regolith and both language
  tracks are settled; the technical open-question queue is empty by
  design. `docs/` is the normative source, led by the invariant ledger
  (`docs/spec/regolith/13-invariants.md`).
- **Toolchain: substantially built, `make check` green.** The Rust core
  (lexer, layout, CST parser, entity DB, quantity/interval engine,
  contract IR, and lowering to obligations), the PyO3 bridge, the
  Python orchestrator, the harness with closed-form model packs, and the
  `magnetite` package tool are implemented and pass the gate. CI runs
  format/lint/type/test on a matrix, with fuzzing and benchmarks wired.
- **Invariant suite (INV-1..27): mostly real green,** with a small
  number of deliberately tracked `xfail` fixtures where the enforcing
  machinery is still being wired.
- **Roadmap:** geometry realizers (OCCT via build123d) and the numeric
  L2 solvers are future work, not yet in the tree.

## License

GPL-2.0-only (the Linux kernel's license; owner-decided 2026-07-08):
free to use, study, modify, and redistribute -- derivatives play by
the same rules. Full text in `LICENSE`.
