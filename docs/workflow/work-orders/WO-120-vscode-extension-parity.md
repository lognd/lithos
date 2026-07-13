# WO-120 -- VS Code extension feature parity + feedback (D229)

Status: done (close-out ledger at the end of this file)
Language: Rust (crates/regolith-ls) + TypeScript (editors/vscode);
  gates: after WO-119 (shares the D228 progress channel) and after
  the wave-1..3 merges (the features it surfaces must exist);
  before WO-117.
Spec: D229; WO-38/39 ledgers (the landed LSP/extension base +
  accepted residuals); AD-7 (ONE diagnostic renderer -- diagnostics
  already flow, do not add a second pipeline); D228 (progress
  channel); charter 29 (interaction surface).

## Goal

The VS Code extension exposes the toolchain's CURRENT feature set
with live feedback: a user can build, ship, preview, optimize,
test, and run health from the editor, watch $/progress bars, and
navigate from a claim to its verdict, calc sheet, and artifacts --
with the editor consuming shipped/reported JSON, never recomputing
verdicts.

## Deliverables

1. Editor tasks/commands: build (--release), ship, preview,
   optimize, test, health -- each streaming $/progress via the
   D228 channel adapter (LSP work-done progress), results
   surfaced in the editor (problems panel via existing
   diagnostics; summary in a status/output view).
2. Claim-level navigation and hovers: verdict + margin on hover
   (from the build report/census JSON); waiver/acceptance status
   (memo reference) on waived claims; go-to-artifact commands
   (open calc sheet PDF/JSON, drawing, STEP/GLB viewer.html) from
   the claim or part site, using the WO-114 audit index to
   resolve.
3. Census/rigor status surface: per-project discharged/waived
   counts (the WO-117 census shape) in a tree/status view, stale
   marked when reports are older than sources.
4. The WO-38 accepted residuals re-assessed: artifact-hover
   (registry_version persistence) and registry-id completion --
   land what the current architecture now permits; re-record
   what still does not, with the same honesty.
5. Extension packaging/e2e: the WO-39 grammar/extension harness
   extended to cover the new commands (headless e2e where the
   harness supports it); README/guide updated.

## Acceptance

- From a fresh editor session on a fleet project: diagnostics
  live, build+ship tasks run with visible progress, hover shows
  a real verdict with margin, go-to-artifact opens a real shipped
  file, health summary renders.
- No editor-side verdict math; no second diagnostic renderer;
  `make check` (incl. the ls/extension test legs) green.

## Escalation

Protocol gaps (LSP surface missing a needed request shape) get a
placeholder-labeled finding + the minimal regolith-ls addition;
anything smelling like a second renderer or editor-side
recomputation stops and escalates.

## Close-out ledger (branch wo120-vscode-parity)

Deliverable outcomes:

1. Editor tasks/commands -- DONE. `lithos: build --release / ship /
   preview / optimize / test / health` spawn the real CLI with
   `REGOLITH_LOG=DEBUG` and mirror the D228 stream into a VS Code
   progress notification (`editors/vscode/src/cli-runner.ts`);
   results land in the "lithos" output channel; diagnostics keep
   flowing through the existing LSP path (AD-7 -- no second
   renderer, no new problem matcher).
   PARSER-SITE DECISION: the wire shape is parsed in the extension,
   in exactly ONE module (`editors/vscode/src/progress.ts`), because
   the canonical parser (`python/regolith/progress.py::parse_line`)
   is Python the extension cannot import and regolith-ls never
   spawns the CLI (D111 discipline: the server stays a pure
   compiler front end). The module cites the progress.py wire-shape
   docstring verbatim and must be updated in the same change as any
   wire bump.
2. Claim hovers + navigation -- DONE. Hover over a claim line in a
   `require` block shows verdict + margin (discharged) or the
   waiver memo / deferral / violation detail, read verbatim from
   `dist/calc/calc_book.json` (`crates/regolith-ls/src/
   artifacts.rs` + `hover.rs`); `lithos.goToArtifact` opens the
   calc sheet PDF / calc book JSON / STEP / GLB viewer.html
   resolved through the audit index (`editors/vscode/src/
   artifacts.ts` + `goto-artifact.ts`) -- only files that exist,
   never invented. No calc book (or no matching row) degrades to
   the honest "(no build artifacts)" tail.
3. Census/rigor surface -- DONE. Activity-bar tree view
   ("Rigor census", `editors/vscode/src/census.ts`): one row per
   dist/ project, discharged/waived/deferred read off the audit
   index summary, stale-flagged when any source file is newer than
   the shipped calc book.
4. WO-38 residuals re-assessed -- artifact-fed hover LANDED (the
   WO-114 calc book removed the registry_version blocker WO-38
   named; see crates/regolith-ls/src/artifacts.rs module docs).
   Registry-id completion STILL CUT, honestly: no Rust crate within
   regolith-ls's allowed dependency reach (regolith-api and below)
   reads a magnetite package index, and building that reader is a
   new-crate/layering decision, not a WO-120 detail -- escalated as
   WO120-F1.
5. Packaging/e2e -- DONE within the harness's reach. The WO-39
   headless always-on tier extended with `test/progress.test.ts` +
   `test/artifacts.test.ts` (17/17 green); README updated. The
   @vscode/test-electron tier remains sandbox-gated exactly as
   WO-39 recorded (no Xvfb/Electron in the dispatch sandbox) --
   unchanged residual, not new scope.

Acceptance: `make check` green (foreground, exit 0, incl. cargo
test -p regolith-ls 43/43); extension leg `npm test` 17/17;
grammars + token goldens regenerated after upstream keyword drift
(the drift predated this WO). No editor-side verdict math anywhere:
every surfaced number is read from shipped JSON.

Escalations:

- WO120-F1: registry-component-id completion needs a Rust-side
  magnetite index reader below regolith-api; new-crate decision for
  the coordinator/architecture doc.
- WO120-F2 (observation, no action taken): the extension-side and
  regolith-ls-side calc-book readers plus the pydantic models in
  backends/calc.py are now THREE homes for the calc-book shape
  (each cites calc.py as the one source; TS/Rust cannot import it).
  If the shape starts moving, consider generating the TS/Rust
  mirrors from the schema pipeline like `_schema/` -- schema-seam
  decision, out of WO-120 scope.
