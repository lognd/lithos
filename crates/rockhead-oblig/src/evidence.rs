//! `Evidence`: the only return type of discharge, and the generic
//! margin rule that decides a claim from a model result.
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md`.
//! Indeterminate is DISTINCT from violated in every surface (status,
//! report, exit code). The margin rule is implemented ONCE, generically:
//! `value + eps_model <= limit`; one toy closed-form model is wired
//! end-to-end (WO-13) to prove claim -> obligation -> evidence -> cache.

use serde::{Deserialize, Serialize};

/// The outcome of discharging an obligation. Three states, never two:
/// `Indeterminate` (no adequate model / coverage) is not `Violated`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    /// The claim holds with margin after the model's error.
    Discharged,
    /// The claim provably fails at its worst corner.
    Violated,
    /// No adequate model, coverage, or trust; neither proven nor
    /// disproven (distinct from violated).
    Indeterminate,
}

/// The evidence produced by discharging one obligation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Evidence {
    /// The discharge status.
    pub status: Status,
    /// The computed value's bits (f64 as bits for exact serialization).
    pub value_bits: u64,
    /// The model error `eps`'s bits.
    pub eps_bits: u64,
    /// The margin after error (`limit - (value + eps)`)'s bits.
    pub margin_bits: u64,
    /// The discharge model id that produced this.
    pub model_id: String,
    /// Coverage fraction for swept obligations (`1.0` = full), bits.
    pub coverage_bits: u64,
    /// Relative cost incurred.
    pub cost: u32,
    /// Content hash of this evidence (cache key component).
    pub hash: String,
}

/// The margin-driven discharge rule, generic over any model result:
/// `value + eps <= limit` -> discharged; provable `>` -> violated;
/// otherwise indeterminate. This is the ONE place the rule lives.
#[must_use]
pub fn decide_margin(_value: f64, _eps: f64, _limit: f64) -> Status {
    todo!("STUB WO-13: value+eps<=limit -> Discharged; value-eps>limit -> Violated; else Indeterminate")
}

/// A cache of evidence keyed on (subject, contract, registry versions),
/// so a second run is a hit.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceCache {
    entries: rockhead_util::IndexMap<String, Evidence>,
}

impl EvidenceCache {
    /// An empty cache.
    #[must_use]
    pub fn new() -> EvidenceCache {
        EvidenceCache {
            entries: rockhead_util::IndexMap::new(),
        }
    }

    /// Look up evidence by its content-addressed cache key.
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&Evidence> {
        self.entries.get(key)
    }

    /// Insert evidence under its cache key.
    pub fn insert(&mut self, key: String, evidence: Evidence) {
        self.entries.insert(key, evidence);
    }
}

#[cfg(test)]
mod tests {
    use super::{Evidence, EvidenceCache, Status};

    #[test]
    fn indeterminate_is_not_violated() {
        assert_ne!(Status::Indeterminate, Status::Violated);
    }

    #[test]
    fn cache_round_trips_and_hits() {
        let ev = Evidence {
            status: Status::Discharged,
            value_bits: 1.0_f64.to_bits(),
            eps_bits: 0.0_f64.to_bits(),
            margin_bits: 1.0_f64.to_bits(),
            model_id: "toy_budget_sum".to_string(),
            coverage_bits: 1.0_f64.to_bits(),
            cost: 1,
            hash: "blake3:ab".to_string(),
        };
        let mut cache = EvidenceCache::new();
        cache.insert("k".to_string(), ev.clone());
        assert_eq!(cache.get("k"), Some(&ev));
        let json = serde_json::to_string(&cache).unwrap();
        let back: EvidenceCache = serde_json::from_str(&json).unwrap();
        assert_eq!(back.get("k"), Some(&ev));
    }
}
