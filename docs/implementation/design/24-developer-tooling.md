# Developer tooling (design charter): LSP, editor, lints, docs, scaffolding

Status: NORMATIVE (cycle 22, design-log `2026-07-07-cycle-22.md`,
D110-D116; architecture rule AD-24). Implemented by WO-38 (language
server), WO-39 (editor extension), WO-40 (lints + watch), WO-41
(docsgen + scaffolding). This document carries the shared design so
the four WOs stay tight; where a WO body conflicts with this
charter, the charter wins (the 20-solver-abstraction precedent).

## 1. The principle (AD-24): one front end for humans and tools

Everything a tool shows a developer derives from the SAME compiler
crates and tables the build uses -- the lexer's keyword tables, the
lossless CST, `regolith-diag` codes/spans/fixes, L1 name resolution,
and the schema-versioned build artifacts. No second grammar, no
second lint engine, no second renderer semantics. Editor-facing
grammar artifacts (TextMate) are GENERATED from the lexer tables and
drift-checked; accuracy beyond regex-class highlighting comes from
LSP semantic tokens computed on the real CST.

## 2. Component map

```
crates/regolith-ls/        Rust LSP server (lsp-server + lsp-types, stdio)
                           depends on regolith-api and below; NEVER regolith-py;
                           NOT in the wheel (release CI ships per-OS binaries)
editors/vscode/            TypeScript extension `lithos` (client, generated
                           TextMate grammars, snippets, commands, status)
crates/regolith-diag       + Lint code family (Warning default)
python/regolith/cli        + `check --watch`, `doc`, quarry `new`
quarry.toml [lints]        code -> allow|warn|deny (deny promotes to Error)
```

## 3. The server (WO-38)

- **Transport/runtime**: `lsp-server` (synchronous, channel-based --
  the rust-analyzer host crate), `lsp-types` for the protocol. One
  instance per workspace root (the directory holding `quarry.toml`,
  else the opened folder).
- **Position mapping (F111)**: regolith spans are byte offsets; LSP
  positions are UTF-16 line/character. A dedicated, tested converter
  (line index with UTF-16 unit widths) sits at the boundary; every
  range crossing it goes through the one converter. This is the
  classic LSP corruption bug -- it gets its own test with non-ASCII
  user content (user files are not bound by the repo's ASCII rule).
- **Document sync + tiers**: full-text sync v1 (files are small);
  on change, reparse the edited file immediately (syntax-tier
  diagnostics target < 100ms on the largest corpus file) and
  debounce (~300ms) a workspace `regolith-lower` run for
  semantic-tier diagnostics. Cancellation honored between tiers.
  Salsa-style incrementality is deferred (D110 reopen criterion).
- **Features and their sources of truth**:

| LSP feature | source |
|---|---|
| publishDiagnostics | the check pipeline's `regolith-diag` values, verbatim (code, severity, spans, related) |
| code actions / quick fix | `Fix.replacement` (F110) -- forwarded, never re-derived |
| formatting | the existing canonicalizing formatter, whole-document |
| document symbols / outline | CST decl tree (name, kind keyword, range) |
| folding + selection ranges | CST body blocks / node ancestry |
| semantic tokens | lexer token kinds + CST classification (decl names, kind words, units, claim heads) |
| hover | static: kind word docs (from the vocabulary tables), quantity/unit info, resolved declaration signature. Artifact-fed: resolved value + `Cause` (lockfile row), claim -> obligation status / margin / evidence tier / discharging model (evidence cache), record -> pinned datasheet fields |
| go to definition / references | L1 name resolution + CST identifier occurrences; cross-file via `import` resolution |
| completion | keyword tables (position-aware by enclosing block kind), in-scope declaration names, registry component ids (quarry index read), claim-vocabulary heads where a machine-readable kind table exists |
| rename | resolution-checked identifier rename; single file plus files reachable through imports (workspace-glob rename deferred until modules exceed import reach) |

- **Artifact reads (D111)**: `.regolith/` evidence cache, lockfile,
  and serialized BuildPayload are read-only inputs, revalidated by
  schema version; a missing or stale artifact degrades hovers to
  static content with an explicit "(no build artifacts)" note --
  never a guess, never a Python call. The editor command "regolith:
  build" shells to the CLI; the server picks up the new artifacts
  via file events.
- **Logging**: `tracing` to stderr per house rules; the client
  surfaces it in an output channel.

## 4. The extension (WO-39)

- Language ids `hematite`/`cuprite`/`fluorite` for
  `.hema`/`.cupr`/`.fluo`; `quarry.toml` gets TOML association plus
  a JSON schema for its tables (generated from the quarry manifest
  model).
- **Generated TextMate grammars**: a build step in the extension
  invokes the compiler's table export (a `regolith-syntax` binary
  target or `regolith debug grammar-json`) to emit keyword/token
  classes per language; the checked-in grammar files carry a
  generated-header and CI diffs them against a fresh export (the
  `_schema/` drift-check pattern). Hand-written parts are limited to
  structural scopes (comments, strings, numerics-with-units).
- Language configuration (line comment `#`, bracket pairs,
  indentation rules for `:`-terminated headers), snippets for the
  common declaration shapes (part, interface, flownet, require,
  rule), problem matcher for CLI output, status-bar item (build
  state, obligation counts from the artifacts).
- Client bundles per-platform `regolith-ls` binaries produced by the
  existing release matrix; `.vsix` built in CI; marketplace
  publishing owner-gated.

## 5. Lints (WO-40)

Compiler passes emitting the Lint code family (Warning by default),
run inside the existing check pipeline -- visible identically in CLI
and LSP (D111). `quarry.toml [lints]` maps code -> allow|warn|deny;
deny promotes to Error at diagnostic-emission time (one place).
v1 set: unused declaration, unreferenced feature, shadowed name,
unused import, retired-vocabulary usage, todo!/assume! inventory
(advisory count with locations). The waive ladder is not involved
(D112: configuration, not engineering deviation). Watch mode:
`regolith check --watch` re-runs on save via `watchfiles`, same
renderer, clear-screen + summary line.

## 6. Docs + scaffolding (WO-41)

`regolith doc [--out DIR]`: markdown per package -- public
interfaces (roles, params, flow decls), parts/blocks/flownets and
their public fields, claims (with obligation status + margins when
artifacts are present, else "(unbuilt)"), registry records with
datasheet provenance. Doc text = leading `#` comment block attached
to a declaration (existing convention; no new syntax). Deterministic
output, snapshot-tested. `quarry new <name> --template
mech|elec|fluid|system`: quarry.toml, one source file with an
honest example claim, `.gitignore` (house list), CI snippet; every
template passes `regolith check` at generation time (tested).

## 7. Deferred (reopen criteria, F90 discipline)

- **tree-sitter grammar**: reopen on concrete demand from an editor
  that cannot consume LSP semantic tokens (AD-24: a second grammar
  is the two-copies bug).
- **wasm playground**: reopen with docs-site/outreach work (the
  crates are wasm-reusable by AD-2 design; this is packaging).
- **salsa incrementality**: reopen when the D110 latency SLO breaks
  on a real workspace ~10x the corpus.
- **HTML doc rendering / site**: reopen with lodestone registry UI
  work; markdown is the v1 contract.
- **DAP debugger**: not a goal -- explain/trace is the declarative
  analog and is owned by the harness/CLI surfaces.
