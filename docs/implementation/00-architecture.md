# Implementation Architecture (normative)

> The top-level technical decisions for building the toolchain, made
> once, here, so every work order below can be planned and executed by
> a less-capable agent without re-litigating anything structural.
> Decisions are numbered AD-1.. (architecture decisions, distinct from
> the spec's D-numbers). Where a WO body conflicts with this document,
> THIS DOCUMENT WINS; the WO's *acceptance criteria* still stand.
> Ledger entry: design-log cycle 9.

The one-sentence architecture: **a Rust compiler core behind one
coarse, schema-versioned boundary, wrapped by a Python orchestrator
that talks to the outside world** -- and the whole thing tuned for
developer experience first: one-command setup, seconds-scale
edit-test loop, one renderer for every diagnostic, one source of
truth for every schema, and determinism you can diff.

## 0. The DX contract (what every decision below serves)

These are promises to the people (and agents) working in this repo.
Any future change that breaks one of them is wrong until proven
otherwise.

1. `make install` on a clean clone gives a working dev environment
   (Rust + Python + editable extension) with no manual steps.
2. `make check` is the single gate: format, lint, types, tests, both
   languages, cheapest first. Green means shippable-quality.
3. The edit-test loop for Rust changes is `make dev` (rebuild the
   extension into the venv on save); for Python changes it is zero
   rebuild (editable install).
4. Every failure a developer sees -- compiler diagnostic, test
   failure, invariant violation -- renders through ONE renderer with
   source spans, and is reproducible from a plain command printed
   alongside it.
5. `decl debug tokens|cst|ast|ir <file>` exists from the first parser
   commit: the pipeline's intermediate states are always inspectable.
6. Golden/snapshot tests are updatable by one command (`make
   snapshots`), never by hand-editing expected files.
7. Nothing in the repo depends on machine state: no global installs,
   no ambient registries, pinned toolchains (`rust-toolchain.toml`,
   `uv.lock`).

## 1. AD-1: Component-to-language map

The spec's four-component architecture (substrate `01` sec. 4) maps
onto languages by one rule: **Rust owns everything between source
text and serialized obligations (pure, hot, deterministic); Python
owns everything that talks to the world** (processes, networks,
files-as-artifacts, solvers-as-subprocesses, humans).

| component | language | contents |
|---|---|---|
| quantity core | Rust (`decl-qty`) | dimensions, units, intervals, log views, value-source types |
| modeling language / compiler (L0->L3, static L5 emission) | Rust (`decl-syntax`, `decl-sem`, `decl-ir`, `decl-oblig`) | lexer, CST, parser, typed AST, formatter, entity DB, queries, ownership/borrows, scopes, monomorphization, symmetry, ledgers, budget/capability arithmetic, contract IR, obligation construction, content addressing, diagnostics |
| verification harness | Python (`decl.harness`) | model registry, signatures/impl matching, closed-form + numeric models (numpy/scipy), planner adapters; realizer adapters at Phase C+ (OCCT via build123d; vendor toolchains) |
| orchestrator | Python (`decl.orchestrator`, `decl.cli`) | build tiers, evidence cache, lockfile authorship, scheduling, the lazy loop, CLI/CI surface |
| package manager | Python (`decl.quarry`) | registry client, trust/signing, vendoring; record *parsing* is the Rust front-end like any source |

Rationale: the boundary coincides with the spec's own serialization
point -- obligations are "self-contained, serializable" (substrate
`07` sec. 2) *by design*, so the FFI is coarse and stable instead of
chatty. The compiler stays a pure function (testable entirely in
Rust, no Python in the loop); the orchestrator stays replaceable
(CLI today, CI/LSP host tomorrow) without touching the core.
Rejected: Rust-everything (kills harness DX -- physics models want
scipy and rapid iteration); Python-everything (the original WO
assumption -- cannot hit `check` latency targets on the Kestrel
corpus, and parsing/borrow-checking is exactly the graph work Rust
is for).

Numeric L2 solves (rigid statics, stiffness network -- Phase D) land
in Rust (`decl-ir` behind a `solve` feature, `faer` for linear
algebra) because they are deterministic compiler work, not harness
physics. Harness models stay Python.

## 2. AD-2: Repository layout (one repo, one wheel)

Monorepo; cargo workspace + maturin mixed Rust/Python layout; ONE
distributable: the `decl-eng` wheel containing the `decl` Python
package with the compiled `decl._core` extension inside. No version
skew between core and wrapper is representable, ever.

```
Cargo.toml                # [workspace]; shared [workspace.package] version/lints
rust-toolchain.toml       # pinned stable channel
pyproject.toml            # [build-system] maturin; dist name decl-eng
uv.lock
Makefile
crates/
  decl-util/     ids, interning, IndexMap re-exports, blake3 hashing helpers
  decl-diag/     diagnostic model + the ONE renderer (annotate-snippets)
  decl-qty/      quantity core (WO-02/03/04)
  decl-syntax/   logos lexer, layout pass, rowan CST, parser, AST views,
                 formatter, extension registry (WO-05, WO-11 grammar half)
  decl-sem/      entity DB, queries, ownership/borrows, stages/scopes,
                 monomorphization, symmetry, sketch ledger (WO-07..11)
  decl-ir/       contract IR, ledgers, budgets, L2 arithmetic (WO-12)
  decl-oblig/    obligation/evidence/lockfile-row schemas, canonical
                 encoding, content addressing, schemars export (WO-13)
  decl-api/      Session + BuildOutput: the coarse compile API; pure
                 Rust, fully testable without Python
  decl-py/       PyO3 bindings ONLY (thin, no logic); cdylib decl._core
python/decl/
  __init__.py    py.typed
  _core.pyi      typed stubs for the extension (drift-checked)
  _schema/       GENERATED pydantic models (AD-5); never hand-edited
  compiler.py    typani-Result facade over _core (AD-4)
  orchestrator/  build tiers, evidence cache, lockfile, lazy loop
  harness/       model registry, signatures, model packs
  quarry/        registry client, trust, vendoring
  cli/           typer app (`decl check|build|debug|fmt ...`)
  logging_setup.py
tests/           pytest: cross-boundary goldens, CLI e2e, invariants
docs/ examples/  (existing)
```

Crate layering is strict and enforced (`cargo-deny` bans cycles;
each crate's docstring names its substrate doc):
`util <- diag <- qty <- syntax <- sem <- ir <- oblig <- api <- py`.
`decl-py` contains zero logic -- if a function body in `decl-py` is
more than marshalling, it is in the wrong crate. Rationale: every
crate below `api` is a normal Rust library (unit-testable, benchable,
fuzzable, future-LSP/wasm-reusable); Python is one consumer among
possible several.

## 3. AD-3: Lexer/parser technology

The professional, cross-platform 2026 stack for an
indentation-based DSL with formatter + future-LSP requirements --
the rust-analyzer/ruff/biome architecture, not a parser generator:

1. **Lexer: `logos`.** DFA-compiled, fastest mainstream Rust lexer,
   pure Rust (no C, trivially cross-platform). Emits raw tokens
   including whitespace/comments (full fidelity).
2. **Layout pass** (own ~200 lines): converts leading whitespace into
   INDENT/DEDENT/NEWLINE tokens, Python-style, so the lexer stays
   regular and the parser stays context-free. Tabs are an E01xx
   error (ASCII-only source is already spec; indentation is spaces).
3. **Syntax tree: `rowan` lossless CST** (red/green trees). Every
   byte of source is in the tree; comments and spacing survive.
   This buys, for free: the formatter (WO-05's normalizer), precise
   spans forever, error-resilient trees (a broken file still has a
   CST for the parts that parse), and the future LSP/refactor story.
   Typed AST = zero-cost view structs over the CST (rust-analyzer
   pattern), generated by a small `xtask` codegen from an ungrammar
   file.
4. **Parser: hand-written recursive descent + Pratt** for
   expressions, event-based (parser emits events; a builder folds
   them into the rowan tree). Error recovery anchors on the layout
   tokens (INDENT/DEDENT are natural sync points), so one bad
   statement never eats the file -- diagnostics stay batch-emitted
   per the spec (substrate `09` sec. 4).
5. **Grammar EBNF remains a deliverable** (`grammar.ebnf`,
   documentation + conformance artifact); it documents the parser
   and the corpus tests enforce it. It does not generate code.
6. **Fuzzing is part of the definition of done for the parser:**
   `cargo-fuzz` targets (lexer, parser) with the invariants "never
   panics" and "CST covers every input byte"; runs short in CI,
   long ad hoc.

Rejected: `lark` (the old WO-05 note -- superseded with the language
switch); `lalrpop`/`chumsky`/`pest` (generator ergonomics fight
indentation layout, error recovery, and CST fidelity -- every
production-grade Rust language tool hand-writes for these reasons);
`tree-sitter` (superb for editors, wrong as a compiler front-end:
C runtime dependency, weaker typed-AST story).

## 4. AD-4: The FFI boundary (PyO3 + maturin)

**Coarse-grained, schema-versioned, one crossing per build.**

- `decl._core` exposes a handful of types: `CoreSession` (open a
  project root / file set), `session.check()` / `session.compile()`
  returning a `BuildOutput` handle; `format(text) -> text`;
  `debug_dump(stage, path)`; `init_logging()`; `core_version()`,
  `schema_version()`.
- `BuildOutput` exposes: pre-rendered diagnostics (strings, colored
  and plain) AND structured payloads -- diagnostics, resolutions with
  causes, obligations, snapshot hashes -- as JSON bytes that parse
  into the generated pydantic models (AD-5). Hot scalar metadata
  (counts, verdict booleans) as native getters.
- **GIL:** every compile call runs under `py.allow_threads`;
  parallelism is rayon inside Rust. Python threads never touch core
  internals.
- **abi3:** `pyo3` with `abi3-py312` -- one wheel per platform, any
  Python >= 3.12.
- **Panic policy:** panics are programmer bugs. Every pyo3 entry
  point wraps in `catch_unwind`; a panic becomes a `decl.CoreBug`
  exception carrying the Rust backtrace. Expected failure is NEVER
  an exception: a failing build is a successful function call whose
  BuildOutput contains violated/indeterminate results and
  diagnostics (claims-as-data, exactly like the spec's evidence
  model). Infrastructure errors (unreadable file) are a single
  `decl.CoreError` exception at the boundary...
- ...which the thin facade `decl/compiler.py` immediately converts:
  **all Python-facing APIs return typani `Result[T, E]`** per house
  style. `CoreBug` alone propagates (unrecoverable programmer bug).
  No other module imports `decl._core` directly -- the facade is the
  one door (enforced by a lint-grep in `make check`).

Rejected: fine-grained AST bindings (GIL churn, lifetime hazards,
unversionable surface); pickling Rust objects (opaque, fragile);
gRPC/subprocess split (operationally heavier, kills the
zero-rebuild Python loop; can be revisited for remote discharge
later since obligations are already serializable).

## 5. AD-5: One source of truth for every shared schema

Types that cross the boundary or land on disk (diagnostics,
obligations, evidence, resolutions/lockfile rows, build reports) are
defined ONCE, in Rust (`decl-oblig`), with `serde` + `schemars`:

```
Rust structs --schemars--> JSON Schema --datamodel-code-generator-->
pydantic v2 frozen models in python/decl/_schema/ (committed)
```

- `make schema` regenerates; CI fails on drift (generated files are
  committed so editors and agents always see real types).
- Every schema carries a `schema_version`; `decl/compiler.py` asserts
  it against `decl._core.schema_version()` at import (belt over the
  single-wheel suspenders).
- **Hash discipline:** content addresses are
  `blake3(domain_tag || schema_version || canonical_cbor(value))`
  using `ciborium` with enforced canonical ordering. JSON is for the
  FFI payloads and durable artifacts (human-debuggable, diffable);
  canonical CBOR exists ONLY as hash input. Nothing hashes JSON.
- House rule made mechanical: **Python never hand-writes a type that
  mirrors a Rust type** -- that is the NO DUPLICATION rule at the
  language boundary, and the drift check enforces it.

Rejected: hand-mirrored pydantic models (will desync, guaranteed);
Python as schema source (the compiler constructs these objects in
its hot path); protobuf/capnp (heavier toolchain, worse diffs, no
benefit at this payload size).

## 6. AD-6: Determinism rules (the reproducibility invariants, made code)

INV-10/INV-21/INV-22 (bit-reproducible decisions, provenanced
resolutions, pinned content) become these standing rules, enforced by
clippy lints, code review, and a CI determinism job:

1. No `HashMap`/`HashSet` iteration order ever reaches an output:
   outputs use `IndexMap` (insertion = source order) or `BTreeMap`
   (sorted); `decl-util` re-exports the blessed types and the
   workspace denies `std::collections::HashMap` in output paths.
2. Float formatting is `ryu` shortest-round-trip everywhere;
   budget/ledger summation orders are fixed (source order), interval
   ops outward-round via `f64::next_up`/`next_down` on our own
   `Interval` type (no third-party interval semantics to chase).
3. The canonical encoder rejects NaN and non-finite values at the
   boundary (they are compiler bugs upstream).
4. CI runs the golden corpus on linux + macos + windows and diffs the
   *hashes* -- same source, same lockfile rows, same obligation keys,
   byte-identical, or the build is red.
5. Resolutions are constructed only through a `Cause`-requiring API
   (INV-21 as a type: causeless resolved values are unrepresentable
   -- WO-04's contract, now in Rust).

## 7. AD-7: Error handling (both sides of the fence)

- **Rust:** `thiserror` enums per crate; library crates never use
  `anyhow` (xtask may). *User* errors are `decl-diag` Diagnostics
  (values), never `Err` -- `Err` is reserved for infrastructure
  (IO, cache corruption) and bugs. This mirrors the spec: a failing
  claim is data, not an exception.
- **Python:** typani `Result[T, E]` for every fallible operation per
  the house rules; pydantic models frozen; exceptions only for
  programmer bugs. Error types live beside their module, composed
  with typani ErrorSet where flows merge.
- One diagnostic renderer exists in the world (Rust,
  `annotate-snippets`, the rustc-style renderer maintained by the
  rust-lang org): Python prints returned strings verbatim; `--json`
  emits the structured form. No second renderer, ever (NO
  DUPLICATION applied to UX).

## 8. AD-8: Logging and tracing (one config point)

- Rust instruments with `tracing`: a span per pass (lex, layout,
  parse, lower, each check), fields for subject ids and timing;
  every resolution decision and every error path logs (house rule:
  LOG EVERYTHING).
- Bridge: `tracing` -> `tracing-log` -> `pyo3-log` -> Python
  `logging`. Python configures ONCE via dictConfig per
  `~/.claude/refs/logging.md` (`decl/logging_setup.py`); Rust events
  appear as ordinary records under the `decl._core.*` logger
  hierarchy. `decl._core.init_logging()` is called by the facade on
  import.
- Pure-Rust contexts (cargo test, benches, fuzz) use
  `tracing-subscriber` with `DECL_LOG` EnvFilter, same span names --
  one mental model everywhere.

## 9. AD-9: Numerics

- Dimension vector: fixed base dimensions with **rational exponents**
  (`num-rational Ratio<i32>`) -- required, not optional: noise
  density (nV/sqrt(Hz)) is rational-exponent territory the elec
  track already needs.
- Unit scale factors: exact rationals; conversion factors never
  drift. Values: `f64`. Intervals: `[lo, hi]` f64, outward-rounded
  (AD-6). Log views per substrate `02` sec. 5a: stored linear, one
  L1 reference-legality check -- no second numeric domain.
- Complex quantities (impedance) via `num-complex` when the elec
  behavioral work lands; no arbitrary precision in v1 anywhere.

## 10. AD-10: Python-side stack

- **uv** for env/lock; Python >= 3.12; **pydantic v2** (frozen) for
  every Python-side model; **typani** Result/Option/ErrorSet;
  `python-dotenv` for env loading; **httpx** for quarry's network.
- **CLI: `typer`** (type-hint-driven, first-class help/completion --
  the DX pick). Subcommands: `check`, `build`, `optimize`,
  `fmt`, `debug tokens|cst|ast|ir`, `quarry add|update|vendor`,
  `explain <code>`. Rich output only in the CLI layer; libraries
  return data.
- Lint/type: `ruff` (format + lint) and `mypy --strict`. The
  generated `_schema/` and `_core.pyi` must pass strict -- typed all
  the way down to the boundary.
- Artifacts on disk: project-local `.decl/` (evidence cache, build
  state; gitignored) and `decl.lock` (committed; placeholder name
  per the naming decision, one lockfile per project root per
  substrate `11` sec. 9).

## 11. AD-11: Testing strategy (per layer, cheapest first)

| layer | tools | what |
|---|---|---|
| Rust unit | cargo test | per-crate logic |
| Rust snapshot | `insta` | CST/AST dumps, diagnostics, formatter output; `make snapshots` reviews |
| Rust property | `proptest` | interval algebra (outward soundness), unit algebra, canonical-encoding round-trip, formatter idempotence |
| Rust fuzz | `cargo-fuzz` | lexer/parser/CBOR decode: no panics, full coverage of input |
| Rust bench | `criterion` | corpus benchmarks (Kestrel = the standard workload); `make bench` |
| cross-boundary | pytest | golden corpus through the real wheel: every `examples/` file -> BuildOutput goldens (diagnostics, resolutions, obligation keys) |
| Python unit | pytest | orchestrator, harness, quarry with fakes |
| CLI e2e | pytest + subprocess | exit codes, JSON output, exact rendering |
| invariants (WO-17) | both | each INV-n test family lands beside its enforcing layer; cross-boundary INVs (INV-1 keys, INV-27 layout invariance) in pytest |

Coverage: `cargo llvm-cov` + `coverage.py`, both under
`make coverage`. The golden corpus is the same one the spec calls
the pressure-test suite -- examples/ is a build input to CI, not
documentation.

## 12. AD-12: CI/CD and platforms

- GitHub Actions. Jobs: (1) fast gate -- rustfmt, clippy
  (`-D warnings`), ruff, mypy, cargo test, pytest on linux;
  (2) matrix -- {ubuntu, macos, windows} full tests + the AD-6
  determinism hash diff; (3) wheels -- `maturin-action`, abi3,
  manylinux_2_28 + musllinux + macos universal2 + windows;
  (4) fuzz smoke (60s per target); (5) release on tag: wheels +
  sdist to PyPI (`decl-eng`), placeholder name per ground rule 6.
- Toolchains pinned: `rust-toolchain.toml` (stable, exact version),
  `uv.lock`. Dependency hygiene: `cargo-deny` (licenses,
  duplicates, advisories) in the fast gate.
- Windows is a first-class target from day one (paths through
  `camino` Utf8PathBuf in core; source files are UTF-8-checked,
  ASCII-enforced by the lexer per spec).

## 13. AD-13: The developer loop (DX, concretely)

Makefile targets (the interface; `frob`/uv/cargo underneath):

| target | does |
|---|---|
| `install` | uv sync + maturin develop (debug profile) |
| `dev` | watchexec: rebuild extension into venv on Rust change |
| `check` | cheapest-first gate: fmt-check -> clippy -> ruff -> mypy -> cargo test -> pytest |
| `test` / `test-rs` / `test-py` | tests, split when iterating |
| `snapshots` | cargo insta review |
| `schema` | regenerate `_schema/` + `_core.pyi`; part of `check` drift test |
| `fmt` / `lint` / `typecheck` / `coverage` / `bench` / `fuzz` | as named |
| `build` | release wheel via maturin |
| `clean` | cargo clean + venv/artifact scrub |

Notes: `maturin develop --uv` for speed; `make dev-release`
(opt-level 3 + debug assertions) documented for perf work on the
corpus; `profiling` cargo profile keeps symbols for flamegraphs.
Editor story out of the box: rust-analyzer green (workspace),
Pyright/mypy green (py.typed, committed stubs + schema models).

## 14. AD-14: Work-order impact map (normative reassignment)

Ground rule 1 in the README ("Language: Python") is superseded: it
now reads "language per this table". Acceptance criteria in every WO
stand unchanged unless noted.

| WO | home | notes |
|---|---|---|
| WO-01 scaffolding | both | REWRITTEN for the hybrid workspace (see file) |
| WO-02 quantity core | Rust `decl-qty` | pydantic mentions -> serde/schemars |
| WO-03 intervals/ranges | Rust `decl-qty` | outward rounding per AD-6 |
| WO-04 value sources | Rust `decl-qty` | Cause-typed resolution API (INV-21) |
| WO-05 parser | Rust `decl-syntax` | technology paragraph superseded by AD-3 |
| WO-06 diagnostics | Rust `decl-diag` | one renderer (AD-7) |
| WO-07 entity DB | Rust `decl-sem` | |
| WO-08 query engine | Rust `decl-sem` | |
| WO-09 ownership/borrows | Rust `decl-sem` | |
| WO-10 stages/scopes | Rust `decl-sem` | |
| WO-11 profile walks | Rust `decl-syntax` + `decl-sem` | grammar half + ledger half |
| WO-12 contract IR | Rust `decl-ir` | |
| WO-13 obligations | Rust `decl-oblig` | + schemars export (feeds WO-18) |
| WO-14 lockfile | Python `decl.orchestrator` | consumes Rust resolutions; TOML authoring |
| WO-15 check CLI | Python `decl.cli` | typer over the facade |
| WO-16 registry loader | Python `decl.quarry` | record parsing is the Rust front-end |
| WO-17 invariant suite | both | per AD-11 placement |
| WO-18 FFI bridge (NEW) | both | decl-py, facade, schema codegen, stubs, drift checks |

New dependency edges: WO-18 depends on WO-06/13 and gates WO-14/15;
everything Rust-side is unchanged in order.

## 15. Risk register (the stones, turned)

| risk | disposition |
|---|---|
| panic crossing FFI | catch_unwind at every entry; CoreBug; fuzzers hunt panics (AD-3/AD-4) |
| schema drift Rust<->Python | generated + committed + CI drift check (AD-5) |
| platform nondeterminism | AD-6 rules + 3-OS hash-diff CI job |
| GIL contention | one coarse call, allow_threads, rayon inside (AD-4) |
| wheel/py version skew | single wheel contains both; schema_version assert as backstop (AD-2/5) |
| HashMap order leaks | banned type in output paths; blessed re-exports (AD-6) |
| float text drift | ryu everywhere; goldens hash-compared (AD-6) |
| slow dev loop | maturin develop --uv, `make dev`, debug-profile default (AD-13) |
| two diagnostic renderers emerging | renderer lives in Rust only; Python prints strings (AD-7) |
| logging split-brain | pyo3-log bridge, one dictConfig (AD-8) |
| naming rename later | ground rule 6 holds: extension strings live in `decl-syntax`'s registry module, re-exported; dist/CLI placeholders `decl-eng`/`decl` (spec OPEN-10) |
| Windows paths/encoding | camino Utf8PathBuf; ASCII source enforced at lex; Windows in CI matrix from day one (AD-12) |
| incremental compilation pressure later | not v1: pure functions + content-addressed obligations already give artifact-level incrementality; `salsa` is the known upgrade path, and the crate layering keeps it adoptable without redesign |
| LSP/wasm future | rowan CST + logic-free `decl-py` keep the core embeddable (tower-lsp or wasm are new consumers of `decl-api`, not rewrites) |
| fancy dependencies rotting | cargo-deny advisories; every dep above is boring, maintained, pure-Rust (logos, rowan, serde, schemars, blake3, ciborium, rayon, thiserror, tracing, insta, proptest, criterion) |

## 16. What is deliberately NOT decided here

Granular module layouts inside crates, exact AST shapes, the
grammar's production list, pydantic model organization, CLI flag
spellings -- all of that is WO-level planning, intentionally left to
the implementing agents within the rails above.
