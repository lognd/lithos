# Module contract docs

One file per `crates/regolith-*` crate, each a concise WHY/WHAT contract
for that crate's public API surface, with one anchor per symbol (or
tight symbol group) so `frob:doc` edges in the Rust source have a real
target. These are companions to -- not replacements for -- the
normative spec: where a spec section already describes a surface, the
crate doc points at it instead of duplicating prose (see
`docs/spec/toolchain/00-architecture.md` AD-1..43 for the crate-level
architecture these expand on).

Rust crates:

- [regolith-util](regolith-util.md) -- bottom-of-layering primitives
  (canonical CBOR, content addressing, hashing).
- [regolith-lower](regolith-lower.md) -- the pass-pipeline driver
  (AD-17).
- [regolith-syntax](regolith-syntax.md) -- lexing/parsing and the
  extension-string registry (AD-14).
- [regolith-sem](regolith-sem.md) -- semantic analysis.
- [regolith-ir](regolith-ir.md) -- the intermediate representations.
- [regolith-oblig](regolith-oblig.md) -- the obligation engine.
- [regolith-qty](regolith-qty.md) -- quantities and units.
- [regolith-diag](regolith-diag.md) -- the one diagnostic renderer
  (AD-7).
- [regolith-api](regolith-api.md) -- the stable API crate.
- [regolith-ls](regolith-ls.md) -- the LSP server.

Python packages (python/regolith):

- [py-regolith](py-regolith.md) -- package top level (compiler seam,
  config, errors, plugins, procio, toolenv, progress, schema base).
- [py-orchestrator](py-orchestrator.md) -- the build orchestrator.
- [py-harness](py-harness.md) -- the model harness.
- [py-realizer](py-realizer.md) -- mech/elec/firmware realizers.
- [py-backends](py-backends.md) -- artifact backends (drawings,
  three_d, bom, calc, and friends).
- [py-magnetite](py-magnetite.md) -- the package manager and citation
  models.
- [py-cli](py-cli.md) -- the CLI surface.
- [py-docgen](py-docgen.md) -- documentation generation.

Periphery:

- [tools](tools.md) -- tools/health, tools/stdlib, tools/codegen.
- [demos](demos.md) -- the demo proof packs and their harness.
- [vscode-extension](vscode-extension.md) -- editors/vscode.
- [examples](examples.md) -- examples/ flagship sources.

Entries whose file does not exist yet are planned surface for the
in-progress crates/python sweep (`tickets.md` T-0002); each file is
created together with its `frob:doc` edges.
