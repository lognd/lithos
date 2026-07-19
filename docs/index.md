# docs index

This is the doc-link root for the repo (frob's DOC001 crawl starts
here and at the top-level `README.md`). It exists to make every
document under `docs/` reachable by markdown link, not to duplicate
`docs/README.md`'s orientation -- read that first.

## Orientation

- [docs/README.md](README.md) -- what lithos is, repository layout,
  how the four spec tracks relate.

## Spec (normative)

- [docs/spec/regolith/README.md](spec/regolith/README.md) -- the
  shared abstract layer (01-13; `13-invariants.md` is the guarantee
  ledger).
- [docs/spec/hematite/README.md](spec/hematite/README.md) -- the
  mechanical language (`.hema`).
- [docs/spec/cuprite/README.md](spec/cuprite/README.md) -- the
  electrical/computer language (`.cupr`).
- [docs/spec/fluorite/README.md](spec/fluorite/README.md) -- the
  fluid-circuit language (`.fluo`).
- [docs/spec/calcite/README.md](spec/calcite/README.md) -- the
  civil/architectural language (`.calx`).
- [docs/spec/toolchain/README.md](spec/toolchain/README.md) -- the
  normative toolchain architecture (`00-architecture.md`, AD-1..47)
  and the numbered design charters.

## Workflow (process)

- [docs/workflow/README.md](workflow/README.md) -- ground rules and
  the dispatch protocol every agent follows.
- [docs/workflow/work-orders/README.md](workflow/work-orders/README.md)
  -- every WO file, one row each. The live dispatch queue is
  `tickets.md` (`frob ticket doable`); WO `Status:` lines are
  historical narrative, not a second queue.
- [docs/workflow/design-log/README.md](workflow/design-log/README.md)
  -- the dated findings (F-numbers) and decisions (D-numbers)
  ledger -- verbatim project history, never edited.
- [docs/workflow/research/README.md](workflow/research/README.md)
  -- standalone research/market/benchmark notes.
- [docs/workflow/visual-acceptance-2026-07-19.md](workflow/visual-acceptance-2026-07-19.md) -- coordinator AD-39 visual acceptance record
- [docs/workflow/strata-system-model.md](workflow/strata-system-model.md)
  -- companion doc for `design/lithos.strata` (the system topology
  model): node/flow rationale, the AD-4 flow-graph-vs-code-property
  distinction, and every known scanner gap (fixed vs. in-design waived).

## Modules (crate contracts)

- [docs/modules/README.md](modules/README.md) -- per-crate module
  contract docs backing `frob:doc` edges under `crates/**` (COV001).

## Guide (teaching)

- [docs/guide/README.md](guide/README.md) -- one guide per language
  track plus authoring/tooling guides, in reading order.
