# 29 -- The interaction surface: config, TUI, GUI (design charter; D163-D165, cycle 30)

> Charter for the human-facing interaction layer: one configuration
> doctrine, the `graphite` package (TUI + local-web GUI), and the
> pass-visualization diagram family. Ledger rule: AD-31
> (00-architecture.md). Machinery: WO-58 (diagram producers), WO-59
> (config + graphite). Where this doc and a WO body conflict, this
> doc wins. Supersedes the "Post-1.0: a UI" deferral (owner
> directive, 2026-07-09).

## 0. The gap this closes

The toolchain's outputs are honest but headless: diagnostics render
once (AD-7), drawings/schedules exist (AD-27), payloads and debug
dumps are inspectable (`regolith debug`) -- yet configuration is
flag-and-file archaeology, and verifying a lowering visually
("does the decoded block structure match my intent?") means reading
JSON. The owner asks for a TUI (configuration + driving) and a GUI
(render lower passes human-readably, bdf-like, for verification),
over ONE unified renderer.

## 1. Design decisions (load-bearing)

1. **One configuration doctrine (D164).** Precedence, weakest
   first: global user file (`~/.config/regolith/config.toml`,
   platformdirs paths) < project `magnetite.toml` tool tables (the
   `[lints]` precedent) < environment (`REGOLITH_*`) < explicit CLI
   flag. ONE module, `python/regolith/config.py`, is the only
   reader/writer; `regolith config get|set|list|where` is the
   surface. `where` attributes every effective value to its source
   -- INV-21's discipline applied to configuration. Config is
   TOOL preference only (default profiles, budgets, UI options,
   lint levels): nothing in config may change a verdict or a
   design value (the ladder owns those; a config knob that could
   flip `violated` to `discharged` is unrepresentable because
   config never reaches the margin math).
2. **One new package: `graphite`** (`apps/graphite/`, own
   distribution, depends on the `regolith` wheel; NOT in the wheel
   -- the regolith-ls / editors/vscode precedent keeps the wheel
   lean). The drawing mineral, for the drawing-and-driving surface;
   mineral naming holds.
3. **TUI** (`graphite tui`, textual): edits global + project config
   through the D164 module (never raw file pokes), drives
   `check`/`build`/`optimize`, browses diagnostics. Diagnostics are
   printed VERBATIM from the rendered strings -- the ONE renderer
   rule (AD-7) applies to TUI panes exactly as to stdout.
4. **GUI** (`graphite serve`): a LOCAL web app. Python stdlib http
   server; ONE hand-written, self-contained, ASCII, no-CDN,
   no-build-toolchain HTML/JS viewer. It displays: sheet/diagram
   SVGs (the AD-27 reference renderer's output, unmodified),
   provenance on hover (the renderer's existing metadata layers --
   interactivity is a READING of the one renderer's output, never a
   second renderer), payload/pass dumps (`regolith debug` JSON,
   pretty-printed), and optimization traces (the D165 trajectory
   sheet + candidate table). stdout of the server is data (logs to
   stderr, house rule).
5. **Artifact-only channel (AD-24 applied to UI).** graphite
   consumes the CLI's JSON surface and schema-versioned on-disk
   artifacts (`.regolith/`, `regolith.lock`, ship outputs) --
   NEVER `regolith` Python internals, never a private import of
   orchestrator state. A UI is one more consumer of the same
   producer; anything it cannot obtain through artifacts is a
   producer gap escalated per AD-22.
6. **Lower passes render through DrawingModel (D165).** New
   payload-derived diagram producers (ordinary AD-27 backends):
   - `diagram.elec_blocks`: structural blocks/ports/nets from the
     lowered elec payload -- the bdf-shaped verification view.
   - `diagram.contract_graph`: L2 frames/interfaces/connections
     from BuildPayload -- the architecture-at-a-glance sheet.
   - `diagram.opt_trace`: candidate table + convergence polyline
     from `OptimizationTrace`.
   All emit `DrawingModel` rendered by the mandatory SVG renderer;
   layout is deterministic and mechanical (layered DAG placement,
   orthogonal routing; the charter-25 "mechanical, not aesthetic"
   rule); goldens join the corpus. AD-27's diagram family thereby
   extends from net-derived to payload-derived diagrams; the one-IR
   rule is unchanged.

## 2. What already carries it

AD-27's DrawingModel + SVG renderer (WO-50, landed, with the fluid
P&ID as the payload-derived template), `regolith debug` dumps (DX
contract item 5), the CLI JSON surface, typer (TUI's sibling),
the backend/plugin seams (AD-26) for producer discovery.

## 3. Non-goals (reopen criteria attached)

- **Editing designs in the GUI**: view/verify/drive only; source
  stays the one authoring surface. Reopen on a real overlay-file
  demand (charter 25's WYSIWYG criterion, shared).
- **Remote/multi-user serving**: `graphite serve` binds localhost;
  auth/deployment are out of scope. Reopen on a real team-hosting
  need (then it is a product decision, not a flag).
- **A native (Qt/Electron) shell**: reopen only if the local-web
  viewer demonstrably cannot render a required artifact class.
- **TUI feature parity with the GUI**: the TUI is config + driving
  + text; drawings are the GUI's job. Not a defect.

## 4. Acceptance shape (what the WOs must prove)

WO-58: elec block diagram of a corpus cuprite design and contract
graph of a multi-artifact corpus design, both deterministic
(byte-identical across two runs), golden-enrolled, rendered by the
existing SVG renderer unmodified (or with AD-22-escalated schema
additions folded into WO-55's single bump); trace sheet after
WO-55. WO-59: `regolith config where` attributes every effective
value across all four precedence levels (tested matrix); the TUI
edits a global and a project value and drives a real `check` with
verbatim diagnostics (textual pilot tests); `graphite serve`
serves the corpus sheet SVGs + a payload dump + a trace view over
plain HTTP with zero external requests (asserted: no non-localhost
URL appears in served bytes); everything ASCII, logs to stderr.
