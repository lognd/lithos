# CLAUDE.md -- project guardrails

Spec-first project: four declarative engineering design languages
over one shared regolith, plus the toolchain that checks them.
Cold-start orientation lives in `TODO.md` (START HERE section) --
read it first in any fresh session.

## Names (SETTLED, cycle 10 / D81; fluorite cycle 20 / D93; magnetite + calcite cycle 26 / D132-D133 -- do not re-litigate or "fix")

| Name          | What it is                                  |
|---------------|---------------------------------------------|
| **lithos**    | the overall project/repo umbrella name (languages + toolchain + registry); branding only, NOT a code identifier |
| **hematite**  | mechanical language, files `.hema`           |
| **cuprite**   | electrical/computer language, files `.cupr` |
| **fluorite**  | fluid-circuit language, files `.fluo` (cycle 20, D93) |
| **calcite**   | civil/architectural language, files `.calx` (cycle 26, D133; charter in `docs/spec/calcite/`) |
| **magnetite** | the package manager (manifest `magnetite.toml`, module `regolith.magnetite`, CLI `regolith magnetite`); its registry has no separate name |
| **regolith**  | umbrella toolchain/CLI/import name; crates `regolith-*`, Python package `regolith`, lockfile `regolith.lock` |
| **feldspar**  | the external solver pack, its own repo (github.com/lognd/feldspar; cite as `feldspar:<path>`, never a `../` path -- checked out beside this repo for local dev) |

Old names (`mill`, `loom`, `dcad`, `deda`, `.mill`, `.loom`,
`quarry`, `lodestone` -- retired cycle 26, D132) are DEAD. They
legitimately appear only in: `docs/workflow/design-log/` (verbatim history --
NEVER sweep or edit these) and negative tests. "mill" as a machining
operation (lathe/mill) in mech content is not the language name.
calcite's OLD life as the fluid track's draft name (`.calc`) is dead
too, and `.calc` stays dead -- the civil track's extension is `.calx`
(a second user-confirmed decision; do not "normalize" it to `.calc`).

## Normative order (higher wins)

1. `docs/spec/regolith/13-invariants.md` -- every guarantee (INV-1..28)
   with its proof argument. New guarantees need a proof argument in
   the SAME change; nothing converts `violated` to `discharged`.
2. `docs/spec/toolchain/00-architecture.md` (AD-1..26) -- wins over
   any work-order body it conflicts with; WO acceptance criteria
   still stand.
3. `docs/workflow/work-orders/WO-nn-*.md` -- each WO's `Language:` header
   decides Rust vs Python; pre-cycle-9 Python phrasing in old WO
   bodies is superseded.

## Tripwires (each one has burned someone before)

- Extension strings (`.hema`, `.cupr`, `.fluo`, and `.calx` when
  WO-47 lands) live in EXACTLY ONE place: the registry module in
  `crates/regolith-syntax`. Never hard-code them anywhere else,
  including tests and docs examples that could drift.
- Schemas are single-sourced in Rust (schemars). Everything under
  `python/regolith/_schema/` is GENERATED -- regenerate via
  `make schema`, never hand-edit; CI drift-checks it (`schema-check`
  diffs against the COMMITTED file, so it only passes after the
  regenerated file is committed).
- Only `python/regolith/compiler.py` may import `regolith._core`
  (AD-4; `make guard-core` enforces). `regolith-py` is marshalling
  only -- no logic in the FFI crate.
- Failing builds and user-facing errors are DATA: `regolith-diag`
  diagnostics in Rust, typani `Result` values in Python. Exceptions/
  panics are for programmer bugs only (panics cross FFI as `CoreBug`).
  There is ONE diagnostic renderer (`regolith-diag`, AD-7).
- stdout is data; all logs go to stderr (Rust `tracing` bridged via
  pyo3-log; Python module loggers + dictConfig).
- ASCII only in every file (repo-wide, no exemptions).
- Deferred design questions have explicit reopen criteria
  (hematite/07 sec. 2a, cuprite/08 sec. 1a, fluorite/04, calcite
  charter sec. 7). Do not reopen without the named evidence; the
  technical open queue is EMPTY by design (F90).
- Toolchain pinned (`rust-toolchain.toml`, 1.90.0); `thiserror` not
  `anyhow` in library crates.
- Out-of-wheel extensions enter through the ONE plugin seam
  (`regolith.plugins`, AD-26) once WO-44 lands -- never a new
  entry-point group.
- After any merge touching Rust or `SCHEMA_VERSION`: `make install`
  before `make check` (a stale compiled `_core` fails collection
  with schema-version mismatches).

## Working on work orders

Any agent (including subagents) picking up a WO MUST follow the
dispatch protocol in `docs/workflow/README.md`: read the ground
rules + architecture + WO + its spec sections first, produce a full
hierarchical plan (whole tree mapped before any leaf is implemented),
write the plan as a checklist, verify it covers every acceptance
criterion, and stay strictly inside the WO's scope -- ambiguities are
escalated (spec -> design log, architecture -> 00-architecture.md),
never invented. Include the protocol verbatim-by-reference in every
subagent dispatch prompt. Dispatched agents never operate outside
their own worktree (see TODO.md DISPATCH RULES).

`make check` (fmt, clippy, ty (the typechecker -- NOT mypy), core-import guard, Rust +
Python tests, cheapest first) must be green before a WO is closed;
flip the WO's `Status:` line in the same change.
