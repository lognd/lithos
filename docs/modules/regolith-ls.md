# regolith-ls

`regolith-ls`: the LSP server, one front end for humans and tools over
the compiler crates (AD-24, `docs/spec/toolchain/24-developer-tooling.md`).
Depends on `regolith-api` and below only (AD-2 layering); never
`regolith-py`, never embeds or spawns Python (D111). Library form exists
so the protocol-level integration tests can drive `server::Server`
without a real stdio transport.

## Transport and dispatch

<a id="main"></a>
### `main`

LSP over stdio (WO-38 deliverable 1). Logs go to stderr (`tracing`,
house rule); stdout is the LSP transport only.

<a id="server"></a>
### `server`

The dispatch core: server capabilities, document store, and the
request/notification handlers, split out of `main.rs` so protocol-level
tests can drive it without a real stdio transport (WO-38 deliverable
9).

<a id="workspace"></a>
### `workspace`

Workspace root discovery (WO-38 deliverable 1): the nearest
`magnetite.toml` above the opened folder, else the opened folder
itself.

## Text coordinates

<a id="position"></a>
### `position`

F111: the one byte-offset <-> UTF-16 line/character converter.
Regolith spans are byte offsets into UTF-8 source text (AD-3/AD-7);
LSP positions are UTF-16 code-unit line/character pairs. Every boundary
crossing (diagnostics, hover ranges, edits, symbols) goes through
`LineIndex` so a second ad-hoc conversion never reintroduces the
classic LSP corruption bug.

## Diagnostics and fixes

<a id="diagnostics"></a>
### `diagnostics`

The one `regolith-diag` pipeline, mapped verbatim to LSP `Diagnostic`
values (D111): code to code, severity to severity, spans to ranges,
`related` to relatedInformation, with no server-side filtering or
re-ranking (WO-38 deliverable 3).

<a id="actions"></a>
### `actions`

Code actions: `Fix.replacement` forwarded verbatim as quick fixes
(WO-38 deliverable 4). Fixes are never re-derived here -- the LSP
diagnostic carries the original core diagnostic (with its `fixes`) in
its `data` field, stashed by `diagnostics::to_lsp_diagnostic`.

## Editor surface: read-only views

<a id="folding"></a>
### `folding`

Folding ranges (WO-38 deliverable 5): CST block/node ancestry, no
second grammar. One folding range per top-level declaration body.

<a id="symbols"></a>
### `symbols`

Document symbols / outline (WO-38 deliverable 5): the CST decl tree,
read directly off the real parser, no second grammar.

<a id="semtok"></a>
### `semtok`

Semantic tokens (WO-38 deliverable 5): lexer token kinds + CST
classification over the real parse tree, no second grammar. Legend:
`keyword`, `number`, `string`, `comment`, `variable`.

<a id="hover"></a>
### `hover`

Hover: a static half (kind word + resolved declaration signature off
the real CST) plus the WO-120/D229 artifact-fed half over claim lines
(verdict + margin, or waiver/deferral/violation detail), read from the
WO-114 calc book (`crate::artifacts`). A claim with no matching shipped
row, or a workspace with no `dist/calc/calc_book.json` at all,
degrades to the same honest "(no build artifacts)" tail every other
hover carries (D111: never a guess, never invented).

<a id="artifacts"></a>
### `artifacts`

WO-120 deliverable 4: read-only reader of `dist/calc/calc_book.json`
(landed by WO-114, the calc package + audit index), keyed by
`claim_name`/`subject_anchor`, carrying verdict, margin, disposition,
and (for a discharged claim) the full calc sheet. Supersedes the
earlier WO-38 "artifact-fed hover" cut, which needed
`Obligation::evidence_cache_key` keyed on a `registry_version` only the
Python orchestrator computed -- an architecture gap this module's
different, self-contained artifact path avoids entirely.

## Editor surface: write/navigate

<a id="completion"></a>
### `completion`

Completion v1 (WO-38 deliverable 6): the lexer's own keyword table
filtered by the enclosing block kind (top level offers decl-starter
keywords; inside a decl body offers statement/field keywords), plus
every in-scope declaration name in the current file. Registry component
ids (a magnetite index read) are out of scope for this pass -- no
magnetite-index reader exists in this crate yet.

<a id="formatting"></a>
### `formatting`

Formatting (WO-38 deliverable 5): the existing canonicalizing
formatter, whole document, thin delegation to `regolith_api::format`
(the one formatter, AD-4).

<a id="nav"></a>
### `nav`

Navigation + editing (WO-38 deliverable 6): go-to-definition,
references, and resolution-checked rename over the real CST. Scope
note: this is name-text identifier resolution over `Decl` headers and
`Ident` tokens, not a full scoped semantic resolver (`regolith-sem`
exposes an entity DB and query engine, not a name -> declaration
lookup a language server can drive directly). Within one file this is
exact; across files it walks `import` declarations to reachable files
only, never a workspace-wide grep. Rename refuses (`RenameOutcome::
Ambiguous`) whenever more than one reachable file defines the same
name (INV-18 applied to tooling), never applying a guessed edit.
