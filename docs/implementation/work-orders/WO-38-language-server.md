# WO-38: Language server (regolith-ls)

Status: todo
Depends: WO-05..19 (all done -- the compiler crates it embeds);
independent of the WO-29/30 chain and of WO-31..37 (new crate, no
shared files; `.fluo` support arrives automatically when WO-31 lands
because the server reads the extension registry). GATES WO-39's
client half.
Language: Rust (new crate `crates/regolith-ls`, binary target)
Spec: `../design/24-developer-tooling.md` sec. 1-3 (NORMATIVE); AD-24;
design-log `2026-07-07-cycle-22.md` D110/D111/F110/F111; AD-2 (crate
layering: depends on `regolith-api` and below, never `regolith-py`);
regolith/09 (artifact/lockfile shapes the hovers read).

## Goal

`regolith-ls` speaks LSP over stdio and makes every editor a lithos
environment: live diagnostics identical to the CLI's, quick fixes
from `Fix.replacement`, formatting, outline, semantic tokens, hover
(including margins/evidence when build artifacts exist), definition/
references, completion, and rename -- all computed in-process on the
real compiler crates.

## Deliverables

1. **Crate + lifecycle**: `regolith-ls` (bin) on `lsp-server` +
   `lsp-types`; initialize/shutdown, workspace root discovery
   (nearest `quarry.toml`, else opened folder), full-text document
   sync, request cancellation between tiers, `tracing` to stderr.
   Workspace file enumeration through the ONE extension registry
   (never hard-coded extensions).
2. **Position mapping (F111)**: a line-index converter between byte
   offsets and UTF-16 line/character, used by EVERY boundary
   crossing; unit tests with multi-byte content (user files are not
   ASCII-bound) including edits at non-ASCII boundaries.
3. **Diagnostics**: on change, syntax-tier reparse of the edited
   file publishes immediately (SLO: < 100ms on the largest corpus
   file, asserted by a benchmark test); a ~300ms-debounced workspace
   lower publishes semantic-tier diagnostics. Mapping is verbatim
   per D111 (code -> code, severity -> severity, spans -> ranges,
   `related` -> relatedInformation); NO server-side filtering or
   re-ranking.
4. **Code actions**: `Fix` values forward as quick fixes;
   `replacement` becomes a WorkspaceEdit; fixes without replacements
   surface as disabled actions carrying the message.
5. **Read-side features**: formatting (existing formatter, whole
   document), document symbols (CST decl tree), folding + selection
   ranges (CST blocks/ancestry), semantic tokens (token kinds + CST
   classification: decl names, kind words, units, claim heads,
   value-source keywords).
6. **Navigation + editing**: go-to-definition and references via L1
   name resolution + identifier occurrences, cross-file through
   `import` resolution; resolution-checked rename across the import
   graph (refuse with a diagnostic when resolution is ambiguous --
   INV-18 discipline applies to tooling too); completion v1 =
   position-aware keywords (from the lexer tables, filtered by
   enclosing block kind) + in-scope declaration names + registry
   component ids when a quarry index is present.
7. **Artifact-fed hover (D111)**: read `.regolith/` evidence cache,
   lockfile, and serialized BuildPayload (schema-version checked):
   resolved values show value + `Cause`; claims show obligation
   status, margin, evidence tier, discharging model; records show
   pinned provenance. Missing/stale artifacts degrade to static
   hover with an explicit "(no build artifacts)" tail -- never a
   guess, never a Python call. Artifacts refresh on file events.
8. **Distribution**: release CI matrix gains the `regolith-ls`
   per-platform binary artifact (the existing 3-OS pipeline); the
   wheel is UNCHANGED (AD-2). A `make ls` target builds it locally.
9. **Tests**: protocol-level integration tests driving the server
   over an in-memory transport (initialize, open corpus file, edit,
   assert diagnostics/hover/defs/rename edits); the F111 converter
   suite; the SLO benchmark; a golden semantic-token dump for one
   corpus file per language.

## Acceptance criteria

- Opening each corpus example produces byte-identical diagnostic
  sets to `regolith check` on the same file (same codes, spans).
- A diagnostic carrying a `Fix.replacement` round-trips to an
  applied edit that makes the diagnostic disappear on re-check.
- Hover over a claim in a BUILT workspace shows status/margin/
  evidence tier; after deleting `.regolith/`, the same hover shows
  the static form with the "(no build artifacts)" tail.
- Rename across `examples/systems/cubesat/` (kestrel imports) updates all
  occurrences or refuses with the ambiguity diagnostic -- never a
  partial rename.
- The F111 suite passes with non-ASCII fixtures; the SLO benchmark
  passes in CI.
- `cargo-deny`/layering: `regolith-ls` depends on api and below
  only; `make check` green.

## Non-goals

- Salsa incrementality, tree-sitter, wasm, DAP (charter sec. 7
  deferrals).
- Editing `quarry.toml` intelligence beyond the JSON schema WO-39
  ships.
- Workspace-glob rename beyond import reach (charter sec. 3 table).
- Any Python embedding or build-triggering from inside the server.
