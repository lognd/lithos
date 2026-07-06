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
   `orchestrator/`, `harness/`, `quarry/`, `cli/`), pytest in
   `tests/`, goldens under `tests/golden/`. Strict crate layering;
   `regolith-py` contains marshalling only.
4. **Docs as part of done:** every public symbol gets a one-line
   docstring (Rust `///` included); each WO updates its listed doc
   artifacts in the same change.
5. **ASCII only** in every file. Conventional-commit messages, no
   Co-Authored-By line. Use `frob` utilities (edit staging, outline)
   for Python changes; `make check` must pass before a WO is closed.
6. **Naming:** all names are SETTLED (cycle 9 D78, renamed cycle 10):
   languages **hematite** (mechanical, `.hem`) and **cuprite**
   (electrical/computer, `.cupr`); package tool **quarry**; registry
   **lodestone**; the umbrella distribution/import/CLI name is
   **regolith** (lockfile `regolith.lock`) -- one geology theme.
   Extension strings live in ONE registry module (`regolith-syntax`);
   the corpus rename sweep has landed, so it recognizes only
   `.hem`/`.cupr`. Nothing else may hard-code any of these strings.

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
  -> WO-16 package/registry loader                                              [Python quarry]
WO-05..13, WO-18
  -> WO-19 lowering pipeline (AST->entities->IR->obligations->discharge)        [Rust regolith-lower]
     -> gates WO-15 golden corpus + the bulk of WO-17
WO-05..14, 16, 18, 19 -> WO-15 `check` CLI + golden tests over examples/        [Python cli]
```

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
