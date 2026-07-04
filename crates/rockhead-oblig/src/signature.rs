//! Signature registry: the physics-model contract between the modeling
//! language and the harness, plus `impl <sig> by` records (data only).
//!
//! Substrate reference: `docs/substrate/02` sec. 7. A signature names
//! inputs, outputs, and a validity domain; harness packs provide impls
//! with a cost, an error model, and a domain. Neither side sees the
//! other's internals. No harness code lives here (WO-13) -- just the
//! records the orchestrator matches on.

use rockhead_util::IndexMap;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A physics-model signature: a typed input/output contract.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Signature {
    /// Signature name (`bolted_joint_state`).
    pub name: String,
    /// Input port names -> their quantity type (as text).
    pub inputs: Vec<(String, String)>,
    /// Output port names -> their quantity type.
    pub outputs: Vec<(String, String)>,
    /// Validity domain tags (`clamped`, `linear`).
    pub domain: Vec<String>,
}

/// A harness impl record for a signature (data only; the code lives in
/// the Python harness).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct ImplRecord {
    /// The signature this implements.
    pub signature: String,
    /// The impl's name (the discharge model id).
    pub name: String,
    /// Relative cost hint for scheduling.
    pub cost: u32,
    /// The error-model tag (how `eps` is derived).
    pub error_model: String,
    /// The validity domain this impl covers.
    pub domain: Vec<String>,
}

/// The signature + impl registry the orchestrator matches discharge
/// against.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct SignatureRegistry {
    signatures: IndexMap<String, Signature>,
    impls: Vec<ImplRecord>,
}

impl SignatureRegistry {
    /// An empty registry.
    #[must_use]
    pub fn new() -> SignatureRegistry {
        SignatureRegistry {
            signatures: IndexMap::new(),
            impls: Vec::new(),
        }
    }

    /// Register a signature.
    pub fn add_signature(&mut self, sig: Signature) {
        self.signatures.insert(sig.name.clone(), sig);
    }

    /// Register an impl record.
    pub fn add_impl(&mut self, imp: ImplRecord) {
        self.impls.push(imp);
    }

    /// The impls implementing `signature`, cheapest first.
    #[must_use]
    pub fn impls_for(&self, signature: &str) -> Vec<&ImplRecord> {
        let mut matching: Vec<&ImplRecord> = self
            .impls
            .iter()
            .filter(|imp| imp.signature == signature)
            .collect();
        // Stable sort: ties keep registration order (AD-6 determinism).
        matching.sort_by_key(|imp| imp.cost);
        matching
    }
}

#[cfg(test)]
mod tests {
    use super::{Signature, SignatureRegistry};

    #[test]
    fn registry_round_trips_json() {
        let mut reg = SignatureRegistry::new();
        reg.add_signature(Signature {
            name: "bolted_joint_state".to_string(),
            inputs: vec![("preload".to_string(), "N".to_string())],
            outputs: vec![("slip_margin".to_string(), "N".to_string())],
            domain: vec!["clamped".to_string(), "linear".to_string()],
        });
        let json = serde_json::to_string(&reg).unwrap();
        let back: SignatureRegistry = serde_json::from_str(&json).unwrap();
        assert_eq!(back, reg);
    }
}
