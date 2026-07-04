//! Shared low-level primitives for the rockhead compiler core.
//!
//! Substrate reference: `docs/substrate/09-build-and-lockfile.md`
//! (content addressing) and AD-6 (determinism). This crate is the
//! bottom of the strict layering `util <- diag <- qty <- ...`; it owns
//! the blessed, insertion-ordered collection re-exports so no output
//! path ever depends on `HashMap` iteration order.

pub mod canon;

/// Deterministic map/set re-exports (AD-6): outputs use insertion order.
pub use indexmap::{IndexMap, IndexSet};

/// Hash `bytes` with blake3 and return the lowercase hex digest.
///
/// The one hashing entry point so every content address in the tree
/// shares an algorithm (full domain-tagged addressing lives in
/// [`canon::content_address`], here at the bottom of the layering,
/// AD-18; this is the primitive it builds on).
#[must_use]
pub fn hash_hex(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}

#[cfg(test)]
mod tests {
    use super::hash_hex;

    #[test]
    fn hash_is_stable_and_hex() {
        let digest = hash_hex(b"rockhead");
        assert_eq!(digest.len(), 64);
        assert_eq!(digest, hash_hex(b"rockhead"));
    }
}
