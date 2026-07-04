//! Obligation, evidence, and lockfile-row schemas; canonical CBOR
//! encoding; domain-tagged content addressing; schemars export.
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md`.
//! These types are the single source of truth that crosses the FFI
//! and lands on disk (AD-5): defined once here, generated into
//! pydantic on the Python side. WO-13 fills this in; WO-01 anchors
//! the crate and pins the schema version.

/// Schema version stamped on every cross-boundary payload (AD-5).
/// Bumped whenever a serialized shape changes; the facade asserts it
/// against the core at import.
pub const SCHEMA_VERSION: u32 = 1;

#[cfg(test)]
mod tests {
    #[test]
    fn schema_version_is_pinned() {
        assert_eq!(super::SCHEMA_VERSION, 1);
    }
}
