# editors/vscode -- the `lithos` VS Code extension

Client half only (WO-39): the language server (`regolith-ls`, a
separate Rust binary launched over stdio, AD-24) does the diagnostic
work; this extension is one front end with no duplicated logic. WO-120
extends it with progress UI, a census tree view, and read-only
artifact/audit navigation -- always reading the shipped `dist/`
package verbatim (`dist/calc/calc_book.json`, `dist/calc/
audit_index.json`, WO-114), never recomputing a verdict.

<a id="extension"></a>
## `src/extension.ts` -- entry point

### `activate`
The extension's activation entry point: launches the `regolith-ls`
language client over stdio and wires every command/view (WO-39/WO-120).

### `deactivate`
Stops the language client on extension deactivation.

<a id="server-path"></a>
## `src/server-path.ts` -- resolving the `regolith-ls` binary

Resolution order (charter sec. 4 / WO-39 acceptance criteria): an
explicit `lithos.serverPath` setting, then a bundled per-platform
binary shipped in the `.vsix`, then `$PATH`; degrades to grammar-only
highlighting with one notice if none resolve.

### `platformDir`
The `server/<platform>-<arch>/` directory name for the running VS Code
host, matching how the `.vsix` bundles per-platform `regolith-ls`
binaries.

### `ServerResolution`
The resolved-binary-or-degrade-reason shape `resolveServerPath` returns.

### `resolveServerPath`
Runs the three-tier resolution order and returns a `ServerResolution`.

<a id="progress"></a>
## `src/progress.ts` -- the D228/D234.3 progress wire parser

The ONE TypeScript parser site for the progress wire shape (house
rule: no duplication); mirrors `python/regolith/progress.py`'s
docstring verbatim since the extension cannot import the Python
module. Any wire-shape change must update both in the same change.

### `ProgressEvent`
One parsed progress line's shape (phase, subject, done/total, elapsed).

### `PROGRESS_WIRE_VERSION`
The wire format version this parser matches, kept in lockstep with
`progress.py`'s emitter.

### `parseProgressLine`
Parses one `REGOLITH_LOG=DEBUG` stderr line into a `ProgressEvent`, or
`undefined` for an ordinary (non-progress) log line. Covered by
`test/progress.test.ts`.

### `formatProgressMessage`
Renders a `ProgressEvent` into the determinate/indeterminate message
`vscode.window.withProgress` displays. Covered by `test/progress.test.ts`.

### `progressIncrement`
Computes a delta percentage between two progress events for the
`withProgress` increment API, never regressing on a non-advancing
event. Covered by `test/progress.test.ts`.

<a id="cli-runner"></a>
## `src/cli-runner.ts` -- long-running verb runner

Runs a long `regolith` verb (build/ship/preview/optimize/test/health)
as a child process with `REGOLITH_LOG=DEBUG`, parses its stderr through
`progress.ts`, and mirrors it into VS Code's work-done progress UI.
Full stdout/stderr always lands in the output channel; diagnostics
still flow through the existing LSP path only (AD-7).

### `CliRunResult`
The exit-code + duration shape `runWithProgress` resolves to.

### `runWithProgress`
Spawns the verb, streams progress into `vscode.window.withProgress`,
and resolves a `CliRunResult` on completion.

<a id="commands"></a>
## `src/commands.ts` -- command registration

`lithos: check/fmt/rules test` shell out to the `regolith` CLI via a
VS Code task using the ONE problem matcher declared in `package.json`
(the same `regolith-diag` renderer the LSP publishes, D111 -- no
second severity policy); WO-120's long-running verbs run as a tracked
child process (`cli-runner.ts`) instead of a bare task.

### `registerCommands`
Registers every `lithos.*` command (check/fmt/rules-test/the WO-120
long-running verbs/go-to-artifact) against the extension context.

<a id="artifacts"></a>
## `src/artifacts.ts` -- read-only dist/ artifact resolution

Resolves claim-level verdicts/margins, waiver/acceptance status, and
go-to-artifact targets from the shipped `dist/` package -- NEVER
recomputed, always read verbatim off the WO-114 calc package.

### `CalcInput` / `EvidenceChain` / `CalcSheet` / `Disposition` / `AuditRow` / `AuditSummary` / `AuditIndex` / `CalcBook`
The typed mirror of `dist/calc/calc_book.json` + `audit_index.json`'s
committed JSON shape (WO-114) -- read-only, never re-derived.

### `safeName`
Mirrors `calc.py`'s `_safe_name` character class exactly (house rule:
no second sanitization rule). Covered by `test/artifacts.test.ts`.

### `DistProject`
One discovered fleet project's `dist/` root plus its parsed `CalcBook`.

### `findDistProjects`
Discovers every `dist/` package under the workspace (root layout or a
one-level-down fleet layout), skipping `dist/` itself. Covered by
`test/artifacts.test.ts`.

### `findClaimRow`
Matches a claim by normalized `claim_name` and resolves the discharging
sheet from a project's audit index. Covered by `test/artifacts.test.ts`.

### `ArtifactTarget`
The resolved go-to-artifact target shape (calc sheet / drawing / STEP
/ GLB viewer path).

### `resolveArtifacts`
Resolves every `ArtifactTarget` that actually exists on disk for a
claim row -- never returns a path that isn't really there. Covered by
`test/artifacts.test.ts`.

<a id="goto-artifact"></a>
## `src/goto-artifact.ts` -- go-to-artifact command

`lithos: go to artifact`: from a claim's source text (current
selection or the line under the cursor), resolves and opens the calc
sheet/drawing/STEP/GLB viewer the WO-114 audit index says discharges
it. Read-only resolution via `artifacts.ts`; never recomputes a verdict.

### `goToArtifactCommand`
The command handler: extracts the claim under the cursor, resolves its
`ArtifactTarget`s via `artifacts.ts`, and opens the first that exists.

<a id="census"></a>
## `src/census.ts` -- the fleet census tree view

A tree view of per-project discharged/waived counts, read verbatim off
each project's `calc_book.json` audit index summary (WO-114) -- never
recomputed. A project's row is stale-flagged when its calc book is
older than any source file under that project root.

### `CensusItem`
One tree-view row: a project's discharged/waived counts plus its
stale flag.

### `CensusTreeProvider`
The `vscode.TreeDataProvider` backing the census view.

### `CensusTreeProvider.refresh`
Re-discovers every `dist/` project and re-renders the tree.

### `CensusTreeProvider.getTreeItem` / `CensusTreeProvider.getChildren`
The `TreeDataProvider` contract methods VS Code calls to render the view.

<a id="status"></a>
## `src/status.ts` -- the status-bar item

Reads obligation counts / evidence state from build artifacts (same
read-only artifact rule as the server, D111 -- never a guess, never
invoking Python directly).

### `LithosStatusItem`
The status-bar item wrapper, holding the current obligation summary.

### `LithosStatusItem.refresh`
Re-reads the current workspace's artifact state and updates the
status-bar text.

### `LithosStatusItem.dispose`
Disposes the underlying `vscode.StatusBarItem`.
