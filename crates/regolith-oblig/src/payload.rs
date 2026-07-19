//! `PayloadRef`: the generalized payload-ref channel (D96, sec. 8.3).
//!
//! One channel carries hash-pinned, content-addressed payload refs of
//! several kinds -- realized/parametric geometry, meshes, tables,
//! time/frequency objects (spectra, profiles, masks), computed fields,
//! flownets, and plans -- so an external pack can compete across a
//! fidelity hierarchy without a new payload schema per kind. Refs are
//! by digest ONLY, never inline bytes; resolution is an
//! orchestrator-owned content-addressed store (`orchestrator/
//! payload_store.py`), never a pack's own IO.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A hash-pinned reference to a payload of a declared `kind`, crossing
/// the `DischargeRequest.payloads` channel (D96). The kind vocabulary
/// is feldspar 09 sec. 4's list VERBATIM: `geometry.parametric`,
/// `geometry.realized`, `mesh`, `table`, `spectrum`, `profile`,
/// `mask`, `field`, `flownet`, `plan`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#payload
pub struct PayloadRef {
    /// The payload kind (feldspar 09 sec. 4 vocabulary, verbatim).
    pub kind: String,
    /// The blake3 content digest of the payload bytes.
    pub digest: String,
    /// The producing snapshot/record name, for diagnostics only (never
    /// part of the digest/identity).
    pub origin: String,
}

#[cfg(test)]
mod tests {
    use super::PayloadRef;

    #[test]
    fn payload_ref_round_trips_json() {
        let payload_ref = PayloadRef {
            kind: "geometry.realized".to_string(),
            digest: "blake3:aa".to_string(),
            origin: "bracket.step_snapshot".to_string(),
        };
        let json = serde_json::to_string(&payload_ref).unwrap();
        let back: PayloadRef = serde_json::from_str(&json).unwrap();
        assert_eq!(back, payload_ref);
    }
}
