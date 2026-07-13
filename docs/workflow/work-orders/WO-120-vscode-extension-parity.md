# WO-120 -- VS Code extension feature parity + feedback (D229)

Status: open
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
