# WO-39: Editor extension (VS Code `lithos` + generated grammars)

Status: todo
Depends: WO-38 (the server it bundles); the grammar-generation half
(deliverables 1-2) is dispatchable BEFORE WO-38 lands. Independent
of everything else.
Language: TypeScript (`editors/vscode/`, new top-level dir, excluded
from the wheel and from Python packaging); Rust only for the table
export target in `regolith-syntax` (deliverable 1).
Spec: `../design/24-developer-tooling.md` sec. 1 + 4 (NORMATIVE); AD-24;
design-log `2026-07-07-cycle-22.md` D113/D114.

## Goal

Installing one extension makes VS Code a lithos environment:
accurate highlighting for `.hema`/`.cupr`/`.fluo` (generated
TextMate + LSP semantic tokens), the bundled language server,
snippets, commands, and a status item reading build state -- with
zero hand-maintained grammar to drift (AD-24).

## Deliverables

1. **Table export**: a `regolith-syntax` export target (`regolith
   debug grammar-json` subcommand or a small bin target -- pick the
   one that avoids new public API) emitting per-language keyword
   classes, kind words, value-source words, unit-literal lexemes,
   and comment/bracket config as JSON. This is the ONE source the
   grammars build from.
2. **Generated TextMate grammars**: build script in
   `editors/vscode/` consumes the export and emits
   `syntaxes/{hematite,cuprite,fluorite}.tmLanguage.json` with a
   generated-file header; hand-written patterns limited to
   structural scopes (comments, strings, numbers-with-units). CI
   drift check: regenerate and diff, exactly like `_schema/`.
3. **Extension scaffold**: language registrations for the three
   extensions (read from the export, not hard-coded -- the
   registry-module tripwire extends here), `magnetite.toml` file
   association + a JSON schema for its tables (generated from the
   magnetite manifest model), language-configuration (line comment
   `#`, brackets, `:`-header indentation rules), snippets (part,
   interface, flownet, require, rule, budget).
4. **LSP client**: launches the bundled per-platform `regolith-ls`
   (falls back to `$PATH` then a configurable setting; a missing
   server degrades to grammar-only highlighting with a one-time
   notice, never an error loop).
5. **Commands + status**: `lithos: check` / `build` / `fmt` /
   `rules test` shell to the `regolith` CLI with a problem matcher
   for the one renderer's output; a status-bar item shows
   obligation counts / evidence state read from the build artifacts
   (same read-only artifact rule as the server, D111).
6. **Packaging + CI**: `.vsix` built in CI bundling the release
   matrix's server binaries per platform; marketplace publishing is
   OWNER-GATED (the WO ships the artifact, not the publish).
   Extension tests via `@vscode/test-electron` where the sandbox
   allows; grammar snapshot tests (tokenize corpus excerpts) run
   headless and are the always-on tier.

## Acceptance criteria

- Grammar snapshot: tokenizing one corpus excerpt per language
  matches goldens; regenerating grammars from the export is
  byte-identical (drift check green).
- No keyword string appears in the extension source that is not in
  the generated export (grep criterion -- AD-24).
- With the server present: diagnostics, hover, and quick fixes work
  on a corpus file end-to-end (headless client test where the
  sandbox allows; skip-with-reason otherwise, never faked).
- Without the server binary: highlighting still works; exactly one
  degradation notice.
- `.vsix` builds in CI on all three OSes; `make check` green
  (extension build wired into CI, not into the Python/Rust check
  path).

## Non-goals

- Marketplace publish (owner-gated); non-VS-Code editors (LSP is
  editor-agnostic; other clients are downstream demand);
  tree-sitter (charter deferral); TOML editing beyond the schema;
  webview UIs (evidence dashboards belong to a future registry UI,
  charter sec. 7).
