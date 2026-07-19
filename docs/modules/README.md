# Module contract docs

One file per `crates/regolith-*` crate, each a concise WHY/WHAT contract
for that crate's public API surface, with one anchor per symbol (or
tight symbol group) so `frob:doc` edges in the Rust source have a real
target. These are companions to -- not replacements for -- the
normative spec: where a spec section already describes a surface, the
crate doc points at it instead of duplicating prose (see
`docs/spec/toolchain/00-architecture.md` AD-1..43 for the crate-level
architecture these expand on).

- [regolith-util](regolith-util.md) -- bottom-of-layering primitives
  (canonical CBOR, content addressing, hashing).
- [regolith-lower](regolith-lower.md) -- the pass-pipeline driver
  (AD-17); currently covers the crate's top-level entry points only,
  per-pass submodules are in progress.

More crates are added to this index as their module contract docs are
written (see `tickets.md` T-0002 for the in-progress crates/** sweep).
