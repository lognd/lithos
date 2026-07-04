//! Canonical encoding and domain-tagged content addressing (AD-5/AD-6).
//!
//! Substrate reference: `docs/substrate/07` and AD-5. Content addresses
//! are `blake3(domain_tag || schema_version || canonical_cbor(value))`.
//! JSON is the human-facing interchange and durable artifact; canonical
//! CBOR exists ONLY as hash input -- nothing hashes JSON. The canonical
//! encoder enforces key ordering and rejects NaN/non-finite (compiler
//! bugs upstream).

use serde::Serialize;

use crate::SCHEMA_VERSION;

/// Canonically encode a value to CBOR bytes: deterministic key order,
/// no floating NaN/non-finite. The ONLY hash input encoder (AD-6).
///
/// # Errors
/// Returns an error if the value contains a non-finite float (a compiler
/// bug upstream, surfaced here rather than silently hashed).
pub fn canonical_cbor<T: Serialize>(_value: &T) -> Result<Vec<u8>, EncodeError> {
    todo!("STUB WO-13: ciborium encode with enforced canonical ordering; reject non-finite floats")
}

/// The domain address of a value: `blake3(domain_tag || schema_version
/// || canonical_cbor(value))` as a lowercase hex digest.
///
/// # Errors
/// Propagates [`canonical_cbor`] failure.
pub fn content_address<T: Serialize>(_domain_tag: &str, _value: &T) -> Result<String, EncodeError> {
    // domain_tag and SCHEMA_VERSION are folded in before the payload so
    // two schemas can never collide on a hash.
    let _ = SCHEMA_VERSION;
    todo!("STUB WO-13: blake3 over domain_tag || SCHEMA_VERSION || canonical_cbor(value)")
}

/// Export the JSON Schema of every cross-boundary type (obligations,
/// evidence, claims, lockfile rows) for the WO-18 pydantic codegen. This
/// is the single source of truth for the shared schema (AD-5).
#[must_use]
pub fn export_schemas() -> String {
    todo!("STUB WO-18 feed: schemars gather of the boundary types -> one JSON Schema document")
}

/// Failure canonically encoding a value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EncodeError {
    /// A non-finite float reached the canonical encoder (upstream bug).
    NonFiniteFloat,
    /// The CBOR serializer failed.
    Serialize(String),
}

#[cfg(test)]
mod tests {
    // Determinism (same value -> same bytes -> same hash) and non-finite
    // rejection are property-tested with the encoder body (WO-13); the
    // 3-OS hash-diff CI job (AD-6) is the cross-platform guard.
    #[test]
    #[ignore = "WO-13 impl: canonical_cbor + content_address bodies pending"]
    fn content_address_is_deterministic() {}
}
