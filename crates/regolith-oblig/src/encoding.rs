//! Canonical encoding and domain-tagged content addressing (AD-5/AD-6).
//!
//! The encoder itself lives in `regolith_util::canon` (AD-18) -- the
//! bottom of the layering, shared by `regolith-sem` snapshot hashes and
//! `regolith-oblig` obligation keys. This module re-exports it
//! unchanged so no downstream caller (`regolith-api`, `regolith-py`,
//! the Python facade, `make schema`) sees a path change, and owns the
//! schemars export, which stays in `regolith-oblig` per AD-5.

pub use regolith_util::canon::{canonical_cbor, content_address, EncodeError};

use crate::SCHEMA_VERSION;

/// Export the JSON Schema of every cross-boundary type (obligations,
/// evidence, claims, lockfile rows) for the WO-18 pydantic codegen. This
/// is the single source of truth for the shared schema (AD-5).
///
/// The document is `{"schema_version": SCHEMA_VERSION, "definitions":
/// {<type name>: <JSON Schema>, ...}}`: every boundary type gets its own
/// named definition (`datamodel-code-generator` turns each into a frozen
/// pydantic model), and `schema_version` is stamped once at the document
/// root so the facade can assert it against the core at import (AD-5).
///
/// # Panics
/// Panics if the generated schema map cannot be serialized to JSON --
/// an infallible operation for schemars' own `Schema`/`Map` types, so
/// this is a programmer bug, not a user-facing error.
#[must_use]
pub fn export_schemas() -> String {
    use schemars::gen::SchemaSettings;

    let mut generator = SchemaSettings::draft07().into_generator();

    // Every cross-boundary type (AD-5): claims, obligations, evidence,
    // signatures, and the todo/assume/waive ledger.
    generator.subschema_for::<crate::claim::Window>();
    generator.subschema_for::<crate::claim::ClaimForm>();
    generator.subschema_for::<crate::claim::Claim>();
    generator.subschema_for::<crate::claim::Assumption>();
    generator.subschema_for::<crate::obligation::Given>();
    generator.subschema_for::<crate::obligation::SweepDomain>();
    generator.subschema_for::<crate::obligation::Obligation>();
    generator.subschema_for::<crate::obligation::SnapshotRecord>();
    generator.subschema_for::<regolith_qty::Cause>();
    generator.subschema_for::<regolith_qty::Resolution>();
    generator.subschema_for::<crate::evidence::Status>();
    generator.subschema_for::<crate::evidence::Evidence>();
    generator.subschema_for::<crate::evidence::EvidenceCache>();
    generator.subschema_for::<crate::solver::SolverResponse>();
    generator.subschema_for::<crate::signature::Signature>();
    generator.subschema_for::<crate::signature::ImplRecord>();
    generator.subschema_for::<crate::signature::SignatureRegistry>();
    generator.subschema_for::<crate::waiver::Waiver>();
    generator.subschema_for::<crate::waiver::WaiverRecord>();
    generator.subschema_for::<crate::waiver::LedgerEntry>();
    generator.subschema_for::<crate::waiver::WaiveLedger>();

    let definitions = generator.take_definitions();
    let document = serde_json::json!({
        "schema_version": SCHEMA_VERSION,
        "definitions": definitions,
    });
    serde_json::to_string_pretty(&document).expect("schemars Map<String, Schema> always serializes")
}

#[cfg(test)]
mod tests {
    use super::export_schemas;

    #[test]
    fn export_schemas_carries_schema_version_and_definitions() {
        let doc = export_schemas();
        let parsed: serde_json::Value = serde_json::from_str(&doc).unwrap();
        assert_eq!(parsed["schema_version"], crate::SCHEMA_VERSION);
        assert!(parsed["definitions"]["Obligation"].is_object());
        assert!(parsed["definitions"]["Evidence"].is_object());
        assert!(parsed["definitions"]["SolverResponse"].is_object());
    }
}
