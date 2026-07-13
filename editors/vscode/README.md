# lithos (VS Code extension)

Makes VS Code a lithos environment for `.hema` (hematite), `.cupr`
(cuprite), `.fluo` (fluorite), and `.calx` (calcite) files: generated
TextMate highlighting, the bundled `regolith-ls` language server (when
present), snippets, `lithos: check/build/fmt/rules test` commands, and
(WO-120/D229) feature parity with the toolchain's current surface:

- **Progress-tracked commands**: `lithos: build --release`, `ship`,
  `preview`, `optimize`, `test`, `health` run the real CLI with
  `REGOLITH_LOG=DEBUG`, parse its D228 progress stream (the ONE parser
  site for that wire shape is `src/progress.ts`, citing
  `python/regolith/progress.py`'s docstring verbatim), and mirror it
  into a VS Code progress notification; diagnostics still flow through
  the existing LSP path (AD-7) and the output channel carries the full
  run log.
- **Claim hovers**: hovering a claim line inside a `require ...:` block
  shows its verdict/margin (discharged) or waiver memo/deferral/
  violation reason, read from the shipped `dist/calc/calc_book.json`
  (WO-114) -- never recomputed. With no matching shipped row (or no
  `dist/` at all), the hover degrades to an honest "(no build
  artifacts)" tail, same discipline as every other hover (D111).
- **Go to artifact** (`lithos.goToArtifact`, also on the command
  palette): from the claim under the cursor, opens the calc sheet PDF,
  calc book JSON, STEP file, or 3D viewer the audit index says
  discharges it (`src/artifacts.ts`/`src/goto-artifact.ts`).
- **Rigor census** (activity bar view "lithos" -> "Rigor census"): one
  row per `dist/` project found under the workspace, showing
  discharged/waived/deferred counts straight off its audit index
  summary, flagged stale when a source file is newer than the report.

See `docs/spec/toolchain/24-developer-tooling.md` sec. 4,
`docs/workflow/work-orders/WO-39-editor-extension.md`, and
`docs/workflow/work-orders/WO-120-vscode-extension-parity.md` for the
design and scope.

## WO-38 residuals, re-assessed (WO-120 deliverable 4)

- **Artifact-fed hover**: LANDED, via a different path than WO-38's cut
  assumed. WO-38 needed a `registry_version`-keyed evidence-cache read
  the orchestrator alone could compute; WO-114's `dist/calc/
  calc_book.json` is a self-contained, read-only JSON artifact keyed by
  claim name, so `crates/regolith-ls/src/artifacts.rs` reads it
  directly -- no Python embedding, no registry-version sidecar needed.
- **Registry-id completion**: STILL CUT. No Rust crate in
  `regolith-ls`'s dependency reach (`regolith-api` and below) reads a
  magnetite package index; that index reader does not exist anywhere in
  Rust today. Landing this needs a new Rust-side magnetite index reader
  crate, which is an architecture decision (a new crate + its layering
  slot), not an in-scope WO-120 implementation detail -- escalated as
  WO120-F1.

## Development

```
npm install
npm run gen:grammar          # regenerate syntaxes/*.tmLanguage.json from
                              # the compiler's own tables (cargo run -p
                              # regolith-syntax --bin grammar-json)
npm run gen:magnetite-schema # regenerate schemas/magnetite.schema.json
npm run compile               # tsc + esbuild -> dist/extension.js
npm test                      # grammar snapshot + drift + keyword tests
npm run package                # build a .vsix (no marketplace publish)
```

Both generators are drift-checked in CI (`npm run check:grammar`,
`npm run check:magnetite-schema`) exactly like `python/regolith/_schema/`
-- regenerate and commit rather than hand-editing `syntaxes/*.json` or
`schemas/magnetite.schema.json`.
