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
5. `regolith debug tokens|cst|ast|ir <file>` exists from the first parser
   commit: the pipeline's intermediate states are always inspectable.
6. Golden/snapshot tests are updatable by one command (`make
   snapshots`), never by hand-editing expected files.
7. Nothing in the repo depends on machine state: no global installs,
   no ambient registries, pinned toolchains (`rust-toolchain.toml`,
   `uv.lock`).

## 1. AD-1: Component-to-language map

The spec's four-component architecture (regolith `01` sec. 4) maps
onto languages by one rule: **Rust owns everything between source
text and serialized obligations (pure, hot, deterministic); Python
owns everything that talks to the world** (processes, networks,
files-as-artifacts, solvers-as-subprocesses, humans).

| component | language | contents |
|---|---|---|
| quantity core | Rust (`regolith-qty`) | dimensions, units, intervals, log views, value-source types |
| modeling language / compiler (L0->L3, static L5 emission) | Rust (`regolith-syntax`, `regolith-sem`, `regolith-ir`, `regolith-oblig`) | lexer, CST, parser, typed AST, formatter, entity DB, queries, ownership/borrows, scopes, monomorphization, symmetry, ledgers, budget/capability arithmetic, contract IR, obligation construction, content addressing, diagnostics |
| verification harness | Python (`regolith.harness`) | model registry, signatures/impl matching, closed-form + numeric models (numpy/scipy), planner adapters; realizer adapters at Phase C+ (OCCT via build123d; vendor toolchains) |
| orchestrator | Python (`regolith.orchestrator`, `regolith.cli`) | build tiers, evidence cache, lockfile authorship, scheduling, the lazy loop, CLI/CI surface |
| package manager | Python (`regolith.quarry`) | registry client, trust/signing, vendoring; record *parsing* is the Rust front-end like any source |

Rationale: the boundary coincides with the spec's own serialization
point -- obligations are "self-contained, serializable" (regolith
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
in Rust (`regolith-ir` behind a `solve` feature, `faer` for linear
algebra) because they are deterministic compiler work, not harness
physics. Harness models stay Python.

## 2. AD-2: Repository layout (one repo, one wheel)

Monorepo; cargo workspace + maturin mixed Rust/Python layout; ONE
distributable: the `regolith` wheel containing the `regolith` Python
package with the compiled `regolith._core` extension inside. No version
skew between core and wrapper is representable, ever.

```
Cargo.toml                # [workspace]; shared [workspace.package] version/lints
rust-toolchain.toml       # pinned stable channel
pyproject.toml            # [build-system] maturin; dist name regolith
uv.lock
Makefile
crates/
  regolith-util/     ids, interning, IndexMap re-exports, blake3 hashing helpers,
                 canonical CBOR encoder + domain-tagged content addressing (AD-18)
  regolith-diag/     diagnostic model + the ONE renderer (annotate-snippets)
  regolith-qty/      quantity core (WO-02/03/04)
  regolith-syntax/   logos lexer, layout pass, rowan CST, parser, AST views,
                 formatter, extension registry (WO-05, WO-11 grammar half)
  regolith-sem/      entity DB, queries, ownership/borrows, stages/scopes,
                 monomorphization, symmetry, sketch ledger (WO-07..11)
  regolith-ir/       contract IR, ledgers, budgets, L2 arithmetic (WO-12)
  regolith-oblig/    obligation/evidence/lockfile-row/snapshot-record
                 schemas, schemars export (WO-13); re-exports the AD-18 encoder
  regolith-lower/    pass-pipeline driver: AST -> entity DB -> contract IR ->
                 obligations -> static discharge; pure, no IO (WO-19, AD-17)
  regolith-api/      Session + BuildOutput: the coarse compile API; pure
                 Rust, fully testable without Python
  regolith-py/       PyO3 bindings ONLY (thin, no logic); cdylib regolith._core
python/regolith/
  __init__.py    py.typed
  _core.pyi      typed stubs for the extension (drift-checked)
  _schema/       GENERATED pydantic models (AD-5); never hand-edited
  compiler.py    typani-Result facade over _core (AD-4)
  orchestrator/  build tiers, evidence cache, lockfile, lazy loop
  harness/       model registry, signatures, model packs
  quarry/        registry client, trust, vendoring
  cli/           typer app (`regolith check|build|debug|fmt ...`)
  logging_setup.py
tests/           pytest: cross-boundary goldens, CLI e2e, invariants
docs/ examples/  (existing)
```

Crate layering is strict and enforced (`cargo-deny` bans cycles;
each crate's docstring names its regolith doc):
`util <- diag <- qty <- syntax <- sem <- ir <- oblig <- lower <- api <- py`.
`regolith-py` contains zero logic -- if a function body in `regolith-py` is
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
   per the spec (regolith `09` sec. 4).
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

- `regolith._core` exposes a handful of types: `CoreSession` (open a
  project root / file set), `session.check()` / `session.compile()`
  returning a `BuildOutput` handle; `format(text) -> text`;
  `debug_dump(stage, path)`; `init_logging()`; `core_version()`,
  `schema_version()`.
- `BuildOutput` exposes: pre-rendered diagnostics (strings, colored
  and plain) AND structured payloads -- diagnostics, resolutions with
  causes, obligations, snapshot records, evidence -- as JSON bytes that
  parse into the generated pydantic models (AD-5). Hot scalar metadata
  (counts, verdict booleans) as native getters.
- **GIL:** every compile call runs under `py.allow_threads`;
  parallelism is rayon inside Rust. Python threads never touch core
  internals.
- **abi3:** `pyo3` with `abi3-py312` -- one wheel per platform, any
  Python >= 3.12.
- **Panic policy:** panics are programmer bugs. Every pyo3 entry
  point wraps in `catch_unwind`; a panic becomes a `regolith.CoreBug`
  exception carrying the Rust backtrace. Expected failure is NEVER
  an exception: a failing build is a successful function call whose
  BuildOutput contains violated/indeterminate results and
  diagnostics (claims-as-data, exactly like the spec's evidence
  model). Infrastructure errors (unreadable file) are a single
  `regolith.CoreError` exception at the boundary...
- ...which the thin facade `regolith/compiler.py` immediately converts:
  **all Python-facing APIs return typani `Result[T, E]`** per house
  style. `CoreBug` alone propagates (unrecoverable programmer bug).
  No other module imports `regolith._core` directly -- the facade is the
  one door (enforced by a lint-grep in `make check`).

Rejected: fine-grained AST bindings (GIL churn, lifetime hazards,
unversionable surface); pickling Rust objects (opaque, fragile);
gRPC/subprocess split (operationally heavier, kills the
zero-rebuild Python loop; can be revisited for remote discharge
later since obligations are already serializable).

## 5. AD-5: One source of truth for every shared schema

Types that cross the boundary or land on disk (diagnostics,
obligations, evidence, resolutions/lockfile rows, build reports) are
defined ONCE, in Rust (`regolith-oblig`), with `serde` + `schemars`:

```
Rust structs --schemars--> JSON Schema --datamodel-code-generator-->
pydantic v2 frozen models in python/regolith/_schema/ (committed)
```

- `make schema` regenerates; CI fails on drift (generated files are
  committed so editors and agents always see real types).
- Every schema carries a `schema_version`; `regolith/compiler.py` asserts
  it against `regolith._core.schema_version()` at import (belt over the
  single-wheel suspenders).
- **Hash discipline:** content addresses are
  `blake3(domain_tag || schema_version || canonical_cbor(value))`
  using `ciborium` with enforced canonical ordering. JSON is for the
  FFI payloads and durable artifacts (human-debuggable, diffable);
  canonical CBOR exists ONLY as hash input. Nothing hashes JSON. The
  canonical encoder itself is implemented once, in `regolith_util::canon`
  (AD-18), and re-exported by `regolith-oblig`; `SCHEMA_VERSION` lives
  beside it.
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
   (sorted); `regolith-util` re-exports the blessed types and the
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
6. One canonical encoder: `regolith_util::canon` is the only producer
   of hash-input bytes; every content address in the workspace --
   entity snapshot hashes included -- goes through `content_address`.
   serde_json output is never hashed, anywhere (AD-18).

## 7. AD-7: Error handling (both sides of the fence)

- **Rust:** `thiserror` enums per crate; library crates never use
  `anyhow` (xtask may). *User* errors are `regolith-diag` Diagnostics
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
  `~/.claude/refs/logging.md` (`regolith/logging_setup.py`); Rust events
  appear as ordinary records under the `regolith._core.*` logger
  hierarchy. `regolith._core.init_logging()` is called by the facade on
  import.
- Pure-Rust contexts (cargo test, benches, fuzz) use
  `tracing-subscriber` with `REGOLITH_LOG` EnvFilter, same span names --
  one mental model everywhere.

## 9. AD-9: Numerics

- Dimension vector: fixed base dimensions with **rational exponents**
  (`num-rational Ratio<i32>`) -- required, not optional: noise
  density (nV/sqrt(Hz)) is rational-exponent territory the elec
  track already needs.
- Unit scale factors: exact rationals; conversion factors never
  drift. Values: `f64`. Intervals: `[lo, hi]` f64, outward-rounded
  (AD-6). Log views per regolith `02` sec. 5a: stored linear, one
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
- Lint/type: `ruff` (format + lint) and `ty --strict`. The
  generated `_schema/` and `_core.pyi` must pass strict -- typed all
  the way down to the boundary.
- Artifacts on disk: project-local `.regolith/` (evidence cache, build
  state; gitignored) and `regolith.lock` (committed; one lockfile per
  project root per
  regolith `11` sec. 9).

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
  (`-D warnings`), ruff, ty, cargo test, pytest on linux;
  (2) matrix -- {ubuntu, macos, windows} full tests + the AD-6
  determinism hash diff; (3) wheels -- `maturin-action`, abi3,
  manylinux_2_28 + musllinux + macos universal2 + windows;
  (4) fuzz smoke (60s per target); (5) release on tag: wheels +
  sdist to PyPI (`regolith`) per ground rule 6.
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
| `check` | cheapest-first gate: fmt-check -> clippy -> ruff -> ty -> cargo test -> pytest |
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
Pyright/ty green (py.typed, committed stubs + schema models).

## 14. AD-14: Work-order impact map (normative reassignment)

Ground rule 1 in the README ("Language: Python") is superseded: it
now reads "language per this table". Acceptance criteria in every WO
stand unchanged unless noted.

| WO | home | notes |
|---|---|---|
| WO-01 scaffolding | both | REWRITTEN for the hybrid workspace (see file) |
| WO-02 quantity core | Rust `regolith-qty` | pydantic mentions -> serde/schemars |
| WO-03 intervals/ranges | Rust `regolith-qty` | outward rounding per AD-6 |
| WO-04 value sources | Rust `regolith-qty` | Cause-typed resolution API (INV-21) |
| WO-05 parser | Rust `regolith-syntax` | technology paragraph superseded by AD-3 |
| WO-06 diagnostics | Rust `regolith-diag` | one renderer (AD-7) |
| WO-07 entity DB | Rust `regolith-sem` | |
| WO-08 query engine | Rust `regolith-sem` | |
| WO-09 ownership/borrows | Rust `regolith-sem` | |
| WO-10 stages/scopes | Rust `regolith-sem` | |
| WO-11 profile walks | Rust `regolith-syntax` + `regolith-sem` | grammar half + ledger half |
| WO-12 contract IR | Rust `regolith-ir` | |
| WO-13 obligations | Rust `regolith-oblig` | + schemars export (feeds WO-18) |
| WO-14 lockfile | Python `regolith.orchestrator` | consumes Rust resolutions; TOML authoring |
| WO-15 check CLI | Python `regolith.cli` | typer over the facade |
| WO-16 registry loader | Python `regolith.quarry` | record parsing is the Rust front-end |
| WO-17 invariant suite | both | per AD-11 placement |
| WO-18 FFI bridge (NEW) | both | regolith-py, facade, schema codegen, stubs, drift checks |
| WO-19 lowering pipeline (NEW) | Rust `regolith-lower` + `regolith-api` wiring | AD-17; un-cuts WO-18 deliverable 6 |

New dependency edges: WO-18 depends on WO-06/13 and gates WO-14/15;
WO-19 depends on WO-05..13 and WO-18, and gates WO-15's golden corpus
and the bulk of WO-17; everything Rust-side is unchanged in order.

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
| naming rename later | ground rule 6 holds: extension strings live in `regolith-syntax`'s registry module, re-exported; all names settled (hematite/cuprite/quarry/lodestone/regolith, D78 + cycle 10) |
| Windows paths/encoding | camino Utf8PathBuf; ASCII source enforced at lex; Windows in CI matrix from day one (AD-12) |
| incremental compilation pressure later | not v1: pure functions + content-addressed obligations already give artifact-level incrementality; `salsa` is the known upgrade path, and the crate layering keeps it adoptable without redesign |
| LSP/wasm future | rowan CST + logic-free `regolith-py` keep the core embeddable (tower-lsp or wasm are new consumers of `regolith-api`, not rewrites) |
| fancy dependencies rotting | cargo-deny advisories; every dep above is boring, maintained, pure-Rust (logos, rowan, serde, schemars, blake3, ciborium, rayon, thiserror, tracing, insta, proptest, criterion) |

## 16. What is deliberately NOT decided here

Granular module layouts inside crates, exact AST shapes, the
grammar's production list, pydantic model organization, CLI flag
spellings -- all of that is WO-level planning, intentionally left to
the implementing agents within the rails above.

## 17. AD-17: The lowering pipeline (one assembly seam)

The end-to-end driver from parsed source to populated build payload
lives in ONE crate, `regolith-lower`, slotted between `regolith-oblig`
and `regolith-api` (AD-2 layering becomes
`util <- diag <- qty <- syntax <- sem <- ir <- oblig <- lower <- api <- py`).

- `regolith-lower` is a PURE function of source text: no IO, no
  rendering, and it never returns `Err`. `lower(sources) -> LowerOutput`
  always materializes; a failing build is diagnostics in the output
  (AD-7). All IO (file discovery/read, evidence-cache load/store)
  stays in `regolith-api::Session`; the ONE renderer stays invoked
  from `regolith-api`.
- Pass order (one `tracing` span each, AD-8): `parse` ->
  `lower.entities` (AST -> declaration table -> EntityDb snapshots +
  Cause-typed resolutions, INV-21) -> `lower.checks` (monomorphization
  expansion, then queries/ownership/stages/profiles/symmetry per
  instantiation point) -> `lower.contracts` (contract IR + ledgers +
  budgets + conformance) -> `lower.claims` (claims ->
  content-addressed obligations, INV-1) -> `lower.discharge`
  (compile() only: the statically dischargeable toy subset against
  the evidence cache; harness physics discharge remains Python, AD-1).
- Gating is per subject (INV-20): a subject with error diagnostics at
  pass N is excluded from later passes; the pipeline always completes
  for unaffected subjects and always returns the full output.
- `check()` = through `lower.claims`; `compile()` = plus
  `lower.discharge`.

Rejected: growing the driver inside `regolith-api` (couples the
stability-critical FFI surface to pass-pipeline churn and makes the
boundary crate the largest logic crate); Python-side assembly
(violates AD-1). The seam is also the salsa adoption point (risk
register): pass functions become queries without touching AD-4.

## 18. AD-18: Canonical encoder home (amends AD-5/AD-6)

The canonical-CBOR encoder (`canonical_cbor`), `EncodeError`,
domain-tagged `content_address`, and the workspace `SCHEMA_VERSION`
constant live in `regolith-util` (`regolith_util::canon`) -- the
bottom of the layering -- so every crate that hashes (`regolith-sem`
snapshot hashes, `regolith-oblig` obligation keys, future
foreign-content pinning) uses ONE implementation. `regolith-oblig`
re-exports all four names unchanged; schemas and `export_schemas`
stay in `regolith-oblig` per AD-5. Nothing anywhere hashes JSON:
`EntityDb::snapshot_hash`'s serde_json framing was the one violation
and is migrated.

Rejected: a dedicated hash crate (ceremony -- util is already the
determinism home: blessed collections, blake3 primitive); a
documented sem/oblig encoder split (two canonicalizers desync
silently and break INV-1/INV-10 key stability).

## 19. AD-19: External solver integration (the plugin seam)

Full design: `20-solver-abstraction.md` (accepted, cycle 18).
The load-bearing rules, normatively:

- The harness model registry IS the solver abstraction layer. Every
  external solver -- FEA, SPICE, CAM planner, vendor tool -- enters
  as a model pack conforming to the existing `Model`/`ModelSignature`
  contract. No second solver API, ever (NO DUPLICATION).
- Packs are separate Python distributions discovered via the
  `regolith.model_packs` entry-point group; `register(registry)` is
  the whole protocol. Packs depend on `regolith`; regolith never
  imports a pack (no cycle representable). Composition order is
  deterministic (built-ins, then packs sorted by name).
- Non-Python solvers are wrapped by ONE subprocess adapter speaking
  the existing serialized schemas (DischargeRequest in, SolverResponse
  out, JSON, schema-versioned per AD-5; stderr is logs). Adapter
  failure is `harness.adapter_error` INDETERMINATE evidence -- never
  a pass, never an exception. This adapter is also the Phase E
  harness-as-separate-process seam and the future remote-discharge
  wire format: one protocol, three deployments.
- Evidence hashes fold the discharging model's
  `(pack_name, pack_version)` in addition to
  `MODEL_REGISTRY_VERSION` (BE-1 extended): upgrading one pack
  invalidates exactly its own cached evidence.
- Solver packs ship OUTSIDE the regolith wheel (AD-2 stands:
  `packs/<name>/` top-level dirs with their own pyproject, excluded
  from the wheel); the regolith repo keeps the pack-protocol
  conformance suite (`tests/packs/`).

## 20. AD-20: Evidence attestation (solver-signed solutions)

Full design: `20-solver-abstraction.md` sec. D-E/D-G.

- `Attestation` (model id, pack name+version, key id, ed25519
  signature) is an ENVELOPE over evidence: the signature covers the
  evidence's AD-18 content address, so signing never perturbs hashes
  or cache keys, and key rotation never invalidates a cache.
- The schema lives in Rust (`regolith-oblig`, AD-5); signing and
  verification live in Python (keys and processes talk to the world,
  AD-1). Keys are quarry trust-store content: the CONSUMER's key-set
  designations decide the conferred tier (INV-14 verbatim -- signing
  carries trust, storage does not). Unsigned evidence is `community`
  tier; a present-but-invalid signature makes the evidence
  INDETERMINATE (never violated, never accepted), with its own
  diagnostic family. Per-claim `trust: >= tier` floors thereby apply
  to computed evidence with zero new claim surface.
- The guarantee enters the invariant ledger as INV-28 (evidence
  attribution) in the same change as the WO-21 implementation, with
  its proof argument (house rule; drafted in the design doc).

## 21. AD-21: Rule packs (authorable DFM/DRC/ERC rules)

Full design: `21-rule-packs.md` (accepted, cycle 18; syntax
spellings go through the WO-28 spec cycle). The load-bearing rules:

- Rules are authored IN-LANGUAGE (typed `rule` decls inside
  `process` modules' `dfm:`/`drc:`/`erc:` blocks), never in Python:
  a rule is a `forall <var> in <query>` quantified claim template
  plus optional `resolves: <field> from free` (eager resolution with
  `cause: dfm/drc(<pack>.<rule>)`, the INV-21 API). The engine is
  Rust, in the lowering pipeline (parse in `regolith-syntax`, match
  via `regolith-sem` queries, evaluate in `lower.checks`, emit
  obligations in `lower.claims`).
- Two severities only: `demand:` (obligation, release-gated,
  default) and `advise:` (verdict-inert warning, INV-3 discipline).
  Overrides are EXCLUSIVELY the existing waive ladder -- no
  priority arithmetic, no rule-level disable. Pack composition is
  union; same-name collision is an error; loosening is
  unrepresentable except as an attributed waive.
- Discharge level is DERIVED from the facts a predicate references:
  static facts evaluate at `lower.checks` (E06xx); realized facts
  (geometry, routed lengths) lower to obligations discharged by the
  WO-22/WO-24 post-realization passes and stay honestly
  indeterminate until then. A predicate referencing a fact no layer
  provides is a compile error on the rule.
- Fab capability numbers live ONCE in the pack's `capability:`
  table; WO-24 generates external-tool DRC configs (KiCad) from it.
- Packs are expert-authorable artifacts: `per:` citations,
  mandatory-by-lint `expect: pass/fail` fixtures,
  `regolith rules test|try` CLI, and WO-21 record signing so a
  domain expert's pack carries their trust tier.

## 22. AD-22: One producer, no consumer side channels

Full design: `23-lowering-output-surface.md` (WO-29 design pass,
cycle 19, F96/D87). Four independent work orders (WO-22/23/24/28)
each needed typed IR `regolith-lower` did not yet emit, each found the
wall, and each refused to invent a private path into the compiler --
recording a cut instead. That convention is now a rule, not an
accident of four agents' good judgment:

- Downstream consumers (realizers, rule packs, allocation search, any
  future one) bind ONLY to `regolith-lower`'s schema-versioned
  `BuildPayload` (or a future sibling payload type under the same
  `regolith-api` seam, AD-17) -- never to the CST (AD-4 already said
  this), never to `EntityDb`/registry state via a second read path.
- A consumer's forward-authored contract type (written ahead of the
  producer existing, e.g. WO-22's `FeatureProgram`,
  WO-24's `BlockRequirement`/`ComponentCandidate`) is a SPEC for what
  the payload must eventually carry, not a permanent parallel type:
  once the producer lands, the contract is promoted into the payload
  verbatim or regenerated from the Rust source of truth (AD-5), and
  the hand-written version is deleted or demoted to a drift check.
- A consumer that hits a producer gap escalates it (a WO-29-shaped
  dispatch, or a recorded cut naming the gap) rather than growing its
  own extraction path against internal compiler state. This is the
  same discipline AD-17 already applies to the CST; AD-22 extends it
  to every internal producer-side type a downstream WO might be
  tempted to read directly.

## 23. AD-23: One net core, per-discipline plugins

Decided cycle 20 (D100, closing the fluid track's COPEN-2). The net
ledger machinery -- terminal ledger (every terminal joins exactly one
net or is explicitly discarded/sealed), reference reachability,
imposer counting, per-subnet consistency -- exists ONCE, in
`regolith-sem`, parameterized by a `NetDiscipline`:

- **elec** (cuprite/03 sec. 2's settled v1 checks): single-driver
  ledger for digital, at-most-one voltage imposer per analog net,
  supply-short detection, `discard` as the intentional-unconnected
  escape.
- **fluid** (fluorite/02 sec. 4): at-least-one pressure imposer per
  subnet (reference, regulator, pump curve, `Imposer`), medium
  consistency per subnet, `sealed` as the escape.

A discipline contributes check predicates and diagnostic codes over
the shared ledger/reachability core; it never reimplements the core.
cuprite's existing checks REFIT onto the core in the same change that
adds the fluid discipline (WO-31) -- two parallel ledger
implementations are the named failure mode (NO DUPLICATION). Future
disciplines (thermal networks, optical paths) are new plugins, not
new cores. Routed RUNS (wire harnesses, D99) are not nets and do not
ride this core; they share the realized-geometry extraction seam
instead (WO-32/WO-34).

## 24. AD-24: One front end for humans and tools

Decided cycle 22 (D113; full design `24-developer-tooling.md`).
Every developer-tool surface derives from the compiler's own crates
and tables:

- The language server (`regolith-ls`, Rust, lsp-server/lsp-types)
  reuses `regolith-api` and below IN-PROCESS; it never depends on
  `regolith-py`, never embeds or spawns Python, and is not part of
  the wheel (AD-2) -- per-platform binaries ship via the release
  matrix and are bundled by the editor extension.
- Diagnostics have ONE pipeline: the server publishes the same
  `regolith-diag` values the CLI renders (codes, severities, spans,
  fixes -> quick fixes). Lints are compiler passes in the same code
  registry, configured via `quarry.toml [lints]` -- there is no
  separate lint engine or second severity policy.
- Editor grammar artifacts (TextMate) are GENERATED from the lexer/
  parser tables and drift-checked in CI, like `_schema/`; an
  independently-maintained grammar is the two-copies bug in editor
  form. Accuracy beyond that comes from LSP semantic tokens computed
  on the real CST.
- Orchestrator-only facts (margins, evidence tiers, causes) reach
  the editor by READING schema-versioned build artifacts, never by a
  private channel into Python state -- AD-22's one-producer rule
  applied to tooling.
