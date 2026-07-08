//! `Attestation`: an ENVELOPE over evidence (WO-21/AD-20).
//!
//! Design: `docs/implementation/design/20-solver-abstraction.md` sec. D-E/3.
//! The signature covers the evidence's EXISTING content address; it is
//! never a hash input itself, so a signed and an unsigned copy of the
//! same evidence key identically (the envelope property this WO's
//! acceptance test proves). Signing/verification logic (ed25519, via
//! `cryptography`) lives in Python (`harness/attest.py`) -- this crate
//! defines the wire SHAPE only (AD-1: keys and processes talk to the
//! world).

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// The one signature algorithm this WO speaks. A closed enum (not a
/// free string) so an unrecognized algorithm is a deserialization
/// error, not a silently-accepted unknown.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum SignatureAlgorithm {
    /// Ed25519 (RFC 8032) -- the only algorithm implemented in v1.
    Ed25519,
}

/// A solver's signature over one evidence value's content address.
///
/// Attaching, detaching, or re-signing (key rotation) an `Attestation`
/// never changes the evidence's own hash (D-E): this type carries
/// attribution metadata (which model/pack/key produced and vouched for
/// the result) alongside the signature bytes, and nothing here is a
/// hash input for `Evidence` itself.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Attestation {
    /// The discharging model's id (matches `Evidence::model_id`).
    pub model_id: String,
    /// The signing solver pack's name (AD-19 pack identity).
    pub pack_name: String,
    /// The signing solver pack's version.
    pub pack_version: String,
    /// The signing key's identifier (matched against the consumer's
    /// quarry key-set designations at verification time, INV-14/INV-28).
    pub key_id: String,
    /// The signature algorithm.
    pub algorithm: SignatureAlgorithm,
    /// The signature bytes, base64-encoded on the wire (JSON has no
    /// native byte type; the Python side decodes before verifying).
    pub signature_base64: String,
}

#[cfg(test)]
mod tests {
    use super::{Attestation, SignatureAlgorithm};

    #[test]
    fn attestation_round_trips_json() {
        let att = Attestation {
            model_id: "beam.euler_bernoulli@1".to_string(),
            pack_name: "feldspar".to_string(),
            pack_version: "0.3.0".to_string(),
            key_id: "project-signing-key-1".to_string(),
            algorithm: SignatureAlgorithm::Ed25519,
            signature_base64: "c2lnbmF0dXJl".to_string(),
        };
        let json = serde_json::to_string(&att).unwrap();
        let back: Attestation = serde_json::from_str(&json).unwrap();
        assert_eq!(back, att);
    }

    #[test]
    fn unknown_algorithm_is_a_deserialization_error() {
        let json = r#"{"model_id":"m","pack_name":"p","pack_version":"1",
            "key_id":"k","algorithm":"rsa","signature_base64":"x"}"#;
        assert!(serde_json::from_str::<Attestation>(json).is_err());
    }
}
