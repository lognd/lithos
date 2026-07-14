# graphite: config doctrine + the interaction surface (sibling repo)

STATUS: MIXED, honestly. `regolith config` itself is WORKING (lithos,
below). graphite the product EXTRACTED to its own sibling repo (cycle
35, D233/D234) and most of its v2 surface has landed there; two pieces
(the run console and the TUI refresh) are still open. This guide
covers both halves: the doctrine graphite consumes, and what graphite
itself ships today.

Source: design-log `2026-07-13-cycle-35.md` D233 (the extraction),
D234 (the v2 product charter); graphite's own normative corpus at
`graphite:docs/spec/` (01-charter, 02-architecture, 03-design-system,
04-feature-doctrine) and its WO-G1..G8 work-order ledger (read-only
ground truth for this guide -- lithos never edits graphite's docs;
repo-qualified citation per docs/README.md Conventions, like
`feldspar:`).

## D233: graphite is a sibling repo now

graphite moved to `github.com/lognd/graphite`, checked out beside this
repo, exactly like feldspar. The consumption contract is identical in
spirit to feldspar's:

- graphite depends on the `regolith` wheel (an editable path dependency
  in dev) and touches ONLY public surfaces: CLI verbs run as
  subprocesses, reported JSON parsed with regolith's own generated
  models, and the D228 progress channel
  (`docs/guide/29-the-progress-channel.md`).
- Reaching into orchestrator/harness internals is forbidden for
  graphite -- a missing public surface is an escalated gap in
  graphite's own queue, never a private import.
- lithos dropped `apps/graphite` and the `install-graphite`/
  `test-graphite` Makefile legs; graphite's own `make check` is its
  gate, exactly like feldspar's.
- The `graphite.serve.*` keys REMAIN in `regolith config`'s vocabulary
  (a public surface, D163) even though the consumer that reads them
  now lives elsewhere.
- Git history up to the extraction commit stays in this repo; graphite
  starts its own history from an import commit citing it.

## Install

```
cd ../graphite && make install
```

See graphite's own README for its current install/launch instructions
-- this guide does not duplicate a sibling repo's setup docs (the same
posture as this repo's feldspar pointer).

## D234: graphite v2 is a chartered product

The owner directed graphite become a professional, highly user-
friendly interface (full frontend webstack), maximally deduplicated,
with visual identity "computer nerd but super professional." graphite
now carries its OWN normative corpus and workflow discipline, same
shape as this repo's: `graphite:docs/spec/01-charter.md` (mission:
"make the rigor legible" -- every obligation, verdict, margin,
artifact, and audit trail browsable and understandable in seconds),
`02-architecture.md`, `03-design-system.md`, `04-feature-doctrine.md`
(same prefix), and a `WO-G1..G8` queue. Two structural rules worth knowing before reading further:

- **TWO HEADS, ONE BODY** -- the web GUI and the textual TUI are two
  renderers over the same client/service layer and design tokens; a
  capability in one head and not the other is a recorded gap, not an
  accident.
- **The three standing questions** every home surface answers in one
  or two interactions: "is my fleet healthy?", "why did this claim
  defer/fail?", "show me the artifact."

## What ships today (WO-G1..G8 -- all `Status: done`; released v0.2.0)

- **Backend API** (WO-G1) -- the service layer graphite's own frontend
  and TUI both sit on; a durable run-history store.
- **Frontend foundation** (WO-G2) -- the web app shell and design
  system.
- **Dashboard and explorer** (WO-G3) -- the two core reading surfaces:
  fleet health at a glance, and drilling from a failing/deferred claim
  down to why.
- **Artifact viewers** (WO-G4) -- every artifact family the toolchain
  ships (sheets, payloads, traces, the calc book) viewable in place.
- **Config + doctor** (WO-G6) -- the `regolith config` 4-level
  precedence rendered honestly (effective value + source attribution,
  edits write through the real CLI, never a private file), plus
  `regolith doctor --json` rendered with found/missing external-tool
  states and re-probe.
- **Run console** (WO-G5) -- build/ship/test/optimize/health driven
  from the UI with live streamed feedback: verb+project form with
  config-aware defaults, live LogPane + per-phase ProgressRail (the
  D228 channel, single-adapter upgrade path from log-derived
  progress), cancel, durable run history with replay and re-run.
- **TUI refresh** (WO-G7) -- the textual TUI is the second renderer
  over the SAME service layer and generated tokens ("two heads, one
  body" applied retroactively): fleet dashboard, obligation list,
  run console with per-phase progress bars (ONE parser shared with
  WO-G5's adapter), config view.

- **System polish + release** (WO-G8) -- full-app accessibility in
  both themes, list virtualization, a gated bundle budget,
  count-coherence across heads, and the clean-venv wheel proof; the
  `v0.2.0` tag is the first released cut.

## What is still in flight -- named, not invented

Nothing at the WO level -- WO-G1..G8 all closed with the v0.2.0
release; graphite's own next-cycle seeds (WOG8-F1..F7) live in its
close-out ledger.

Check graphite's own work-order ledger
(`graphite:docs/workflow/work-orders/`) for current status before
relying on anything this section dates.

## Configuration: `regolith config` (this repo, WORKING)

One doctrine, four levels, weakest first: the global user file
(`~/.config/regolith/config.toml`, platformdirs-resolved) < the
project's `magnetite.toml` `[tool.regolith]` table < `REGOLITH_*`
environment variables < an explicit CLI flag. `python/regolith/config.py`
is the only reader/writer of either file.

```
regolith config get ui.port                # the effective value
regolith config where ui.port              # value + which level won it
regolith config list                       # every registered key
regolith config set ui.port 9000 --global  # or --local
```

An unregistered key is a constructive error naming the registered set
-- config never reaches the margin math (nothing here can flip a
`check`/`build` verdict). This is the doctrine graphite's Config view
(WO-G6) renders; it never invents its own config semantics.

## See also

- `docs/guide/29-the-progress-channel.md` -- the D228 wire shape the
  run console (WO-G5) is designed against.
- `docs/README.md` -- the repository layout note that graphite is no
  longer part of this tree.
