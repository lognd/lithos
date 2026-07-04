# CLAUDE.md -- project guardrails

Spec-first project: two declarative engineering design languages over
one shared substrate, plus the toolchain that checks them. Cold-start
orientation lives in `TODO.md` (START HERE section) -- read it first
in any fresh session.

## Names (SETTLED, cycle 10 / D81 -- do not re-litigate or "fix")

| Name          | What it is                                  |
|---------------|---------------------------------------------|
| **lithos**    | the overall project/repo umbrella name (the two languages + toolchain + registry together); branding only, NOT a code identifier |
| **hematite**  | mechanical language, files `.hem`           |
| **cuprite**   | electrical/computer language, files `.cupr` |
| **quarry**    | package tool (manifest `quarry.toml`)       |
| **lodestone** | the registry                                |
| **regolith**  | umbrella toolchain/CLI/import name; crates `regolith-*`, Python package `regolith`, lockfile `regolith.lock` |

Old names (`mill`, `loom`, `dcad`, `deda`, `.mill`, `.loom`) are DEAD.
They legitimately appear only in: `docs/design-log/` (verbatim history
-- NEVER sweep or edit these), `TODO.md` decision history, and negative
tests. "mill" as a machining operation (lathe/mill) in mech content is
not the language name.

## Normative order (higher wins)

1. `docs/substrate/13-invariants.md` -- every guarantee (INV-1..27)
   with its proof argument. New guarantees need a proof argument in
   the SAME change; nothing converts `violated` to `discharged`.
2. `docs/implementation/00-architecture.md` (AD-1..16) -- wins over
   any work-order body it conflicts with; WO acceptance criteria
   still stand.
3. `docs/implementation/WO-nn-*.md` -- each WO's `Language:` header
   decides Rust vs Python; pre-cycle-9 Python phrasing in old WO
   bodies is superseded.

## Tripwires (each one has burned someone before)

- Extension strings (`.hem`, `.cupr`) live in EXACTLY ONE place: the
  registry module in `crates/regolith-syntax`. Never hard-code them
  anywhere else, including tests and docs examples that could drift.
- Schemas are single-sourced in Rust (schemars). Everything under
  `python/regolith/_schema/` is GENERATED -- regenerate via
  `make schema`, never hand-edit; CI drift-checks it.
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
- Deferred design questions have explicit reopen criteria (hematite/07
  sec. 2a, cuprite/08 sec. 1a). Do not reopen without the named
  evidence; the technical open queue is EMPTY by design (F90).
- Toolchain pinned (`rust-toolchain.toml`, 1.90.0); `thiserror` not
  `anyhow` in library crates.

## Working on work orders

Any agent (including subagents) picking up a WO MUST follow the
dispatch protocol in `docs/implementation/README.md`: read the ground
rules + architecture + WO + its spec sections first, produce a full
hierarchical plan (whole tree mapped before any leaf is implemented),
write the plan as a checklist, verify it covers every acceptance
criterion, and stay strictly inside the WO's scope -- ambiguities are
escalated (spec -> design log, architecture -> 00-architecture.md),
never invented. Include the protocol verbatim-by-reference in every
subagent dispatch prompt.

`make check` (fmt, clippy, mypy --strict, core-import guard, Rust +
Python tests, cheapest first) must be green before a WO is closed;
flip the WO's `Status:` line in the same change.
