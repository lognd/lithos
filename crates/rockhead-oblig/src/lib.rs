//! Obligation, evidence, and lockfile-row schemas; canonical CBOR
//! encoding; domain-tagged content addressing; schemars export.
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md`.
//! These types are the single source of truth that crosses the FFI and
//! lands on disk (AD-5): defined once here, generated into pydantic on
//! the Python side (WO-18). Claims lower to self-contained, serializable
//! [`obligation::Obligation`]s; [`evidence::Evidence`] is the only
//! return type of discharge (WO-13).

pub mod claim;
pub mod encoding;
pub mod evidence;
pub mod obligation;
pub mod signature;
pub mod waiver;

pub use claim::{Assumption, Claim, ClaimForm, Window};
pub use encoding::{canonical_cbor, content_address, export_schemas, EncodeError};
pub use evidence::{decide_margin, Evidence, EvidenceCache, Status};
pub use obligation::{Given, Obligation, SweepDomain};
pub use signature::{ImplRecord, Signature, SignatureRegistry};
pub use waiver::{LedgerEntry, WaiveLedger, Waiver};

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
