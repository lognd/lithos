# WO-59: config doctrine + graphite v1 (TUI + local-web GUI)

Status: done
Depends: deliverable 1 (config) is independent -- land first.
Deliverables 2-4 (graphite) want WO-58's sheets and WO-55's trace
on master for real content; if dispatched before, the viewers ship
against WO-50's existing sheets and the trace view is the recorded
gated slice. NO SCHEMA_VERSION bump (D160).
Language: Python (`regolith/config.py` + CLI verb in-wheel;
`apps/graphite/` own distribution: textual TUI, stdlib-http GUI,
one hand-written ASCII HTML/JS viewer file).
Spec: docs/spec/toolchain/29-interaction-surface.md (NORMATIVE),
00-architecture.md AD-31 (+ AD-7/22/24/27), design-log
2026-07-09-cycle-30 D163/D164.

## Goal

Configuration becomes one attributed doctrine surfaced by
`regolith config` and a TUI; a local GUI renders sheets/diagrams,
pass dumps, and optimization traces -- all through artifacts only.

## Deliverables

1. **Config module + verb (in-wheel)**: `python/regolith/config.py`
   -- typed (pydantic frozen) config model; precedence global file
   (`platformdirs` user-config `regolith/config.toml`) < project
   `magnetite.toml` tool tables < `REGOLITH_*` env < CLI flag; every
   effective value carries its source. `regolith config
   get|set|list|where` (typer); `set --global|--local` writes the
   respective store through this module only. Config keys v1:
   default optimize budgets/seed, ui prefs (host/port), lint level
   passthrough -- a registered-key table, unknown keys are
   constructive errors. Config never reaches margin math (charter
   sec. 1.1; test asserts no import path from harness/discharge to
   config).
2. **`apps/graphite/` distribution**: own pyproject (deps:
   `regolith`, `textual`); console script `graphite`; ASCII
   everywhere; logs to stderr via the standard dictConfig setup;
   typani Results for fallible ops.
3. **TUI** (`graphite tui`, textual): panes for (a) config editing
   global + project through `regolith config` (subprocess or the
   module's public API -- artifact/CLI channel only, never
   orchestrator internals), (b) running `check`/`build`/`optimize`
   as subprocesses with diagnostics displayed VERBATIM (AD-7; no
   re-rendering, no re-coloring beyond pass-through), (c) browsing
   the last build report JSON. textual pilot tests for each pane.
4. **GUI** (`graphite serve`): localhost-only stdlib http server
   (port from config); serves ONE self-contained hand-written
   HTML/JS/CSS viewer (no CDN, no npm, no external requests) that
   lists and displays ship-output SVG sheets (provenance hover
   from the renderer's metadata layers), pretty-prints
   `regolith debug` / payload JSON, and renders the trace view
   (WO-58's opt_trace SVG + candidate table when present). Server
   endpoints return JSON/SVG bytes from disk artifacts and CLI
   subprocess output ONLY.
5. **Docs**: guide "graphite" page (install, tui, serve), charter
   cross-refs, WO ledger. Repo README/Makefile: `make
   install-graphite` convenience target (uv, editable).

## Acceptance criteria

- `regolith config where <key>` names the winning source across a
  tested 4-level matrix (global/project/env/flag); `set` round-trips
  both stores; unknown key errors constructively.
- TUI: pilot tests prove config edit (both scopes) and a driven
  `check` whose diagnostics bytes equal the CLI's own stderr/stdout
  rendering (verbatim assertion).
- GUI: http tests prove sheet listing + SVG serving, payload
  pretty-print, and zero external references in every served byte
  (regex assertion for scheme-bearing URLs, localhost excepted);
  binds localhost only.
- graphite imports no `regolith.orchestrator`/`regolith.harness`
  internals (import-graph test); the wheel gains no graphite deps.
- ASCII repo-wide holds; `make check` green (graphite's own tests
  wired into it); Status flipped in this change.

## Close-out (WO-59, this change)

Deliverable 1 (config module + CLI verb) and deliverables 2-4
(`apps/graphite/` distribution: TUI + GUI) both landed in the same
change since WO-58's sheets/WO-55's trace were not required to be
present for the generic viewer -- the GUI/TUI render whatever sheet
SVGs + payload JSON exist on disk generically by track name, per the
dispatch note (no hard-coded dependency on `opt_trace`/
`contract_graph` existing). See `docs/guide/11-graphite.md` for the
user-facing walkthrough.
