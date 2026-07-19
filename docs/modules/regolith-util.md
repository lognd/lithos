# regolith-util

Bottom of the crate layering (`util <- diag <- qty <- ...`, see
`docs/spec/toolchain/00-architecture.md`). Owns the deterministic
collection re-exports (`IndexMap`/`IndexSet`, AD-6) and the one
canonical-encoding/content-addressing implementation every other crate
that hashes builds on (`regolith-sem` snapshot hashes, `regolith-oblig`
obligation keys). Full design rationale lives in
`docs/spec/regolith/09-build-and-lockfile.md` (content addressing) and
AD-6/AD-18 (determinism, domain-tagged addressing) -- this doc is a
symbol-level index into that design, not a restatement of it.

## Hashing primitive

<a id="hash-hex"></a>
### `hash_hex`

The one hashing entry point (`crates/regolith-util/src/lib.rs`): blake3
of arbitrary bytes, lowercase hex. Everything that needs a raw digest
(including [`content_address`](#content-address)) goes through this
single function so the algorithm never forks.

## Canonical encoding and content addressing

<a id="schema-version"></a>
### `SCHEMA_VERSION`

The cross-boundary payload schema version (AD-5), folded into every
content address (AD-18). Bumped whenever a serialized wire shape
changes; the per-bump rationale is recorded inline in
`crates/regolith-util/src/canon.rs` next to the constant -- that
changelog is the source of truth for "what changed at bump N", not
duplicated here.

<a id="canonical-cbor"></a>
### `canonical_cbor`

The ONLY hash-input encoder (AD-6/AD-18): deterministic CBOR with
RFC 8949 canonical map-key ordering and rejection of non-finite floats.
JSON remains the human-facing interchange format; nothing hashes JSON
anywhere. See [`EncodeError`](#encode-error) for failure modes.

<a id="content-address"></a>
### `content_address`

Domain-tagged content address: `blake3(domain_tag || SCHEMA_VERSION ||
canonical_cbor(value))` as lowercase hex. The domain tag and schema
version are folded ahead of the payload so two different schemas (or
two versions of the same schema) never collide even if their canonical
CBOR happens to coincide.

<a id="encode-error"></a>
### `EncodeError`

Failure mode for [`canonical_cbor`](#canonical-cbor): either a
non-finite float reached the encoder (an upstream compiler bug,
surfaced here rather than silently hashed) or the CBOR codec itself
failed.
