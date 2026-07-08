//! Obligation, evidence, and lockfile-row schemas; canonical CBOR
//! encoding; domain-tagged content addressing; schemars export.
//!
//! Regolith reference: `docs/regolith/07-claims-and-evidence.md`.
//! These types are the single source of truth that crosses the FFI and
//! lands on disk (AD-5): defined once here, generated into pydantic on
//! the Python side (WO-18). Claims lower to self-contained, serializable
//! [`obligation::Obligation`]s; [`evidence::Evidence`] is the only
//! return type of discharge (WO-13).

pub mod attestation;
pub mod claim;
pub mod encoding;
pub mod evidence;
pub mod obligation;
pub mod payload;
pub mod signature;
pub mod solver;
pub mod waiver;

pub use attestation::{Attestation, SignatureAlgorithm};
pub use claim::{Assumption, Claim, ClaimForm, Window};
pub use encoding::{canonical_cbor, content_address, export_schemas, EncodeError};
pub use evidence::{
    decide_margin, Coverage, CoverageAxis, CoverageDomain, CoverageMethod, Evidence, EvidenceCache,
    Status,
};
pub use obligation::{Given, Obligation, SnapshotRecord, SweepDomain};
pub use payload::PayloadRef;
pub use signature::{ImplRecord, Signature, SignatureRegistry};
pub use solver::SolverResponse;
pub use waiver::{LedgerEntry, WaiveLedger, Waiver, WaiverKind, WaiverRecord};

/// Schema version stamped on every cross-boundary payload (AD-5). Now
/// defined in `regolith_util::canon` (AD-18), the bottom of the
/// layering, and re-exported here unchanged so no caller sees a path
/// change. Bumped whenever a serialized shape changes; the facade
/// asserts it against the core at import.
pub use regolith_util::canon::SCHEMA_VERSION;

#[cfg(test)]
mod tests {
    #[test]
    fn schema_version_is_pinned() {
        // Bumped 5 -> 6 by WO-30 (F100, ONE bump): structured coverage
        // (D95), the payload-ref channel (D96), Given.refs + regime
        // tags (D97/D103), and the D102/D105(d) claim-form/waiver
        // fields all ride this single schema-version bump.
        // Bumped 6 -> 7 by WO-29 deliverable 3: the `feature_programs`
        // `BuildPayload` field.
        assert_eq!(super::SCHEMA_VERSION, 7);
    }
}
