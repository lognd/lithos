# lithos (VS Code extension)

Makes VS Code a lithos environment for `.hema` (hematite), `.cupr`
(cuprite), `.fluo` (fluorite), and `.calx` (calcite) files: generated
TextMate highlighting, the bundled `regolith-ls` language server (when
present), snippets, and `lithos: check/build/fmt/rules test` commands.

See `docs/spec/toolchain/24-developer-tooling.md` sec. 4 and
`docs/workflow/work-orders/WO-39-editor-extension.md` for the design and
scope.

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
