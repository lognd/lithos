# WO-15: `check` CLI + golden corpus

Status: done
Depends: WO-05..14, WO-16
Language: Python (`regolith.cli`, typer over the WO-18 facade) -- see `../../spec/toolchain/00-architecture.md` (normative; supersedes Python-specific implementation notes below)
Spec: regolith/09 sec. 1; hematite/06 Phase B ("a linter ships first")

## Goal

`regolith check <files>` -- L0-L3 static everything, geometry-free,
simulation-free: THE first shippable artifact.

## Deliverables

- CLI (App/AppConfig pattern per `~/.claude/refs/python-app.md`):
  `check`, `--explain <code>`, `--waive <Group.claim>`, `--target`,
  exit codes distinguishing clean / diagnostics / internal error.
- Pass pipeline: parse -> typed AST -> contract IR -> per-artifact L3
  (queries, ownership, scopes, monomorphized sweep, symmetry, profile
  ledgers) -> ledgers/budgets -> closed-form-dischargeable obligations
  (WO-13's toy tier) -> report + lockfile (static sections).
- Wall-clock budget: the full examples/ corpus in < 2s (the ms-s
  latency target; profile if missed, log pass timings always).
- Golden tests: for every file in examples/, a committed expected
  outcome (clean, or a diagnostic list). The corpus IS the regression
  suite; a spec change that alters an outcome must update the golden
  in the same commit.

## Acceptance

- All current examples/ produce their committed outcomes.
- Deliberate-error fixtures (one per E-family) under
  `tests/fixtures/errors/` produce exactly their goldens.
- README quickstart: install, run check on an example, read a
  diagnostic.
