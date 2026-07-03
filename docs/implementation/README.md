# Implementation Work Orders

Agent-executable decomposition of roadmap Phases A-B (mech
`06-roadmap.md`): the schemas, the parser, and the geometry-free
`check` linter. Each `WO-nn-*.md` is self-contained: goal, normative
spec references, deliverables, acceptance criteria, dependencies. An
implementer agent should be able to execute one work order end-to-end
reading only that file plus the referenced spec sections.

**Architecture is decided and normative: `00-architecture.md`**
(AD-1..16). It defines the Rust/Python split, the workspace layout,
the parser stack, the FFI boundary, and the per-WO language
assignment (AD-14). Where an older WO body conflicts with it, the
architecture document wins; WO acceptance criteria stand.

## Ground rules (all work orders)

1. **Languages:** per `00-architecture.md` AD-1/AD-14 and each WO's
   `Language:` header line. Rust: pinned stable toolchain, workspace
   lints, `thiserror` (no `anyhow` in library crates), `tracing`
   everywhere; user-facing failures are `decl-diag` diagnostics
   (values), `Err` is for infrastructure and bugs. Python 3.12+:
   models are **pydantic v2** (`ConfigDict(frozen=True)`), fallible
   operations return **typani** `Result[T, E]`; user-facing failures
   are error values, never exceptions; exceptions only for
   programmer bugs (`CoreBug` from the boundary included).
2. **Logging:** Rust `tracing` (span per pass, log every resolution
   decision and error path), bridged via pyo3-log; Python module
   logger + dictConfig per `~/.claude/refs/logging.md`. Never
   `print` for diagnostics -- the ONE diagnostic renderer lives in
   `decl-diag` (AD-7).
3. **Layout** (fixed by WO-01 per AD-2): cargo workspace `crates/`
   (`decl-util`, `decl-diag`, `decl-qty`, `decl-syntax`, `decl-sem`,
   `decl-ir`, `decl-oblig`, `decl-api`, `decl-py`) + Python package
   `python/decl/` (`compiler.py` facade, `_schema/` generated,
   `orchestrator/`, `harness/`, `quarry/`, `cli/`), pytest in
   `tests/`, goldens under `tests/golden/`. Strict crate layering;
   `decl-py` contains marshalling only.
4. **Docs as part of done:** every public symbol gets a one-line
   docstring (Rust `///` included); each WO updates its listed doc
   artifacts in the same change.
5. **ASCII only** in every file. Conventional-commit messages, no
   Co-Authored-By line. Use `frob` utilities (edit staging, outline)
   for Python changes; `make check` must pass before a WO is closed.
6. **Naming:** the languages are NAMED (cycle 9, D78): **mill**
   (mechanical, `.mill`) and **loom** (electrical/computer,
   `.loom`); the package tool is **quarry**. The umbrella
   distribution/CLI name is the one remaining naming slot -- until
   it is chosen, dist stays `decl-eng`, import package `decl`, CLI
   `decl`, lockfile `decl.lock`. Extension strings live in ONE
   registry module (`decl-syntax`); the corpus rename sweep has
   landed, so it recognizes only `.mill`/`.loom`. Nothing else may
   hard-code any of these strings.

## Dependency graph

```
WO-01 scaffolding (hybrid workspace; both languages)
  -> WO-02 units/quantities -> WO-03 intervals/ranges -> WO-04 value sources   [Rust decl-qty]
  -> WO-06 diagnostics                                                          [Rust decl-diag]
WO-02..04, WO-06
  -> WO-05 lexer/parser (CST + typed AST)                                       [Rust decl-syntax]
  -> WO-07 entity DB -> WO-08 query engine -> WO-09 ownership/borrows           [Rust decl-sem]
  -> WO-10 stages/scopes                                                        [Rust decl-sem]
  -> WO-11 profile walks (needs WO-05)                                          [Rust decl-syntax + decl-sem]
WO-05..11
  -> WO-12 contract IR (interfaces, matings, ledgers)                           [Rust decl-ir]
  -> WO-13 claims -> obligations/evidence schemas                               [Rust decl-oblig]
WO-06, WO-13
  -> WO-18 FFI bridge + schema pipeline + typed facade                          [both]
WO-12..13, WO-18
  -> WO-14 lockfile                                                             [Python orchestrator]
  -> WO-16 package/registry loader                                              [Python quarry]
WO-05..14, 16, 18 -> WO-15 `check` CLI + golden tests over examples/            [Python cli]
```

WO-02/03/04/06 are parallelizable after WO-01. WO-07..11 are
parallelizable after WO-05. WO-17 (the invariant suite,
substrate/13) starts after WO-06 and grows with every WO: a WO is not
done while it reddens an invariant test it enables; test placement
per AD-11 (each INV family lands beside its enforcing layer;
cross-boundary INVs in pytest).

## Status

Mark each WO's Status line (`todo` / `in-progress` / `done` / `cut`)
in place; a cut must name why and where the scope went.
