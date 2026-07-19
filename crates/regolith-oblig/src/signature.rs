//! Signature registry: the physics-model contract between the modeling
//! language and the harness, plus `impl <sig> by` records (data only).
//!
//! Regolith reference: `docs/spec/regolith/02` sec. 7. A signature names
//! inputs, outputs, and a validity domain; harness packs provide impls
//! with a cost, an error model, and a domain. Neither side sees the
//! other's internals. No harness code lives here (WO-13) -- just the
//! records the orchestrator matches on.

use regolith_util::IndexMap;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A physics-model signature: a typed input/output contract.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#signature
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
// frob:doc docs/modules/regolith-oblig.md#signature
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
// frob:doc docs/modules/regolith-oblig.md#signature
pub struct SignatureRegistry {
    signatures: IndexMap<String, Signature>,
    impls: Vec<ImplRecord>,
}

impl SignatureRegistry {
    /// An empty registry.
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#signature
    pub fn new() -> SignatureRegistry {
        SignatureRegistry {
            signatures: IndexMap::new(),
            impls: Vec::new(),
        }
    }

    /// Register a signature.
    // frob:doc docs/modules/regolith-oblig.md#signature
    pub fn add_signature(&mut self, sig: Signature) {
        self.signatures.insert(sig.name.clone(), sig);
    }

    /// Register an impl record.
    // frob:doc docs/modules/regolith-oblig.md#signature
    pub fn add_impl(&mut self, imp: ImplRecord) {
        self.impls.push(imp);
    }

    /// The impls implementing `signature`, cheapest first.
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#signature
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
    use super::{ImplRecord, Signature, SignatureRegistry};

    // frob:tests crates/regolith-oblig/src/signature.rs::SignatureRegistry.add_signature kind="unit"
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

    // frob:tests crates/regolith-oblig/src/signature.rs::SignatureRegistry.add_impl kind="unit"
    // frob:tests crates/regolith-oblig/src/signature.rs::SignatureRegistry.impls_for kind="unit"
    #[test]
    fn impls_for_sorts_cheapest_first_and_ignores_other_signatures() {
        let mut reg = SignatureRegistry::new();
        reg.add_impl(ImplRecord {
            signature: "bolted_joint_state".to_string(),
            name: "vdi_2230_full".to_string(),
            cost: 5,
            error_model: "conservative".to_string(),
            domain: vec!["clamped".to_string()],
        });
        reg.add_impl(ImplRecord {
            signature: "bolted_joint_state".to_string(),
            name: "vdi_2230_simplified".to_string(),
            cost: 1,
            error_model: "conservative".to_string(),
            domain: vec!["linear".to_string()],
        });
        reg.add_impl(ImplRecord {
            signature: "bearing_life".to_string(),
            name: "l10_basic".to_string(),
            cost: 1,
            error_model: "conservative".to_string(),
            domain: vec!["clamped".to_string()],
        });

        let matches = reg.impls_for("bolted_joint_state");
        assert_eq!(matches.len(), 2, "the unrelated signature must be excluded");
        assert_eq!(
            matches[0].name, "vdi_2230_simplified",
            "cheapest impl first"
        );
        assert_eq!(matches[1].name, "vdi_2230_full");
    }
}
