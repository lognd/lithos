//! `Evidence`: the only return type of discharge, and the generic
//! margin rule that decides a claim from a model result.
//!
//! Regolith reference: `docs/regolith/07-claims-and-evidence.md`.
//! Indeterminate is DISTINCT from violated in every surface (status,
//! report, exit code). The margin rule is implemented ONCE, generically:
//! `value + eps_model <= limit`; one toy closed-form model is wired
//! end-to-end (WO-13) to prove claim -> obligation -> evidence -> cache.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// One axis's domain for structured coverage (D95, sec. 8.2): either a
/// continuous interval (text) or an enumerated discrete set -- the
/// G43/COPEN-7 demand (valve line-ups, failure states, range selections).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CoverageDomain {
    /// A continuous domain, as text (e.g. `"[300K, 400K]"`).
    Interval(String),
    /// A discrete domain (valve line-ups, failure states, ...).
    Values {
        /// The enumerated values, as text.
        values: Vec<String>,
    },
}

/// How one coverage axis was swept.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum CoverageMethod {
    /// Corner-only sampling.
    Corners,
    /// A grid with per-axis resolution `k` (multi-dim: `grid(k x m)`,
    /// the G29 demand).
    Grid {
        /// Per-axis grid resolution.
        k: Vec<u32>,
    },
    /// Every discrete value was enumerated.
    Enumerated,
    /// A closed-form analytic bound covers the whole domain.
    Analytic,
    /// Declared monotonicity lets the worst corner stand for the domain.
    Monotone,
}

/// One axis of structured coverage: the swept variable, its domain,
/// and the method used to cover it (D95, sec. 8.2).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct CoverageAxis {
    /// The swept axis name.
    pub axis: String,
    /// The axis's domain (continuous or discrete).
    pub domain: CoverageDomain,
    /// The method used to cover this axis.
    pub method: CoverageMethod,
}

/// Structured coverage (D95, sec. 8.2): per-axis coverage plus the
/// conservative scalar collapse kept for margin notes and old
/// consumers -- `fraction` must never overstate what `axes` states.
/// `Evidence`/`SolverResponse` carry this instead of a bare float.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Coverage {
    /// The per-axis coverage record (empty for a closed-form/full claim).
    pub axes: Vec<CoverageAxis>,
    /// The conservative scalar collapse (`1.0` = full), as `f64` bits.
    pub fraction_bits: u64,
}

impl Coverage {
    /// Full coverage with no swept axes: the closed-form precedent
    /// (`Coverage::full()` = no axes + fraction 1.0).
    #[must_use]
    pub fn full() -> Coverage {
        Coverage {
            axes: Vec::new(),
            fraction_bits: 1.0_f64.to_bits(),
        }
    }

    /// Coverage of `fraction` with no per-axis detail (the bare-float
    /// precedent, kept for callers not yet stating axes).
    #[must_use]
    pub fn from_fraction(fraction: f64) -> Coverage {
        Coverage {
            axes: Vec::new(),
            fraction_bits: fraction.to_bits(),
        }
    }

    /// The scalar fraction as an `f64` (the conservative collapse).
    #[must_use]
    pub fn fraction(&self) -> f64 {
        f64::from_bits(self.fraction_bits)
    }
}

/// The outcome of discharging an obligation. Three states, never two:
/// `Indeterminate` (no adequate model / coverage) is not `Violated`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
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
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
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
    /// Structured per-axis coverage (D95, sec. 8.2); `Coverage::full()`
    /// for a closed-form/full claim.
    pub coverage: Coverage,
    /// Relative cost incurred.
    pub cost: u32,
    /// Content hash of this evidence (cache key component).
    pub hash: String,
}

/// The margin-driven discharge rule, generic over any model result:
/// `value + eps <= limit` -> discharged; provable `>` -> violated;
/// otherwise indeterminate. This is the ONE place the rule lives.
#[must_use]
pub fn decide_margin(value: f64, eps: f64, limit: f64) -> Status {
    if value + eps <= limit {
        Status::Discharged
    } else if value - eps > limit {
        Status::Violated
    } else {
        Status::Indeterminate
    }
}

/// A cache of evidence keyed on (subject, contract, registry versions),
/// so a second run is a hit.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct EvidenceCache {
    entries: regolith_util::IndexMap<String, Evidence>,
}

impl EvidenceCache {
    /// An empty cache.
    #[must_use]
    pub fn new() -> EvidenceCache {
        EvidenceCache {
            entries: regolith_util::IndexMap::new(),
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
    use super::{
        Coverage, CoverageAxis, CoverageDomain, CoverageMethod, Evidence, EvidenceCache, Status,
    };

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
            coverage: Coverage::full(),
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

    #[test]
    fn structured_coverage_round_trips_grid_and_enumerated_axes() {
        // The G29/G43 demand: a 2-D grid axis crossed with a discrete
        // enumerated axis, round-tripping through JSON bit-exactly.
        let coverage = Coverage {
            axes: vec![
                CoverageAxis {
                    axis: "mr".to_string(),
                    domain: CoverageDomain::Interval("[0.5, 1.5]".to_string()),
                    method: CoverageMethod::Grid { k: vec![4, 8] },
                },
                CoverageAxis {
                    axis: "valve_lineup".to_string(),
                    domain: CoverageDomain::Values {
                        values: vec!["open".to_string(), "closed".to_string()],
                    },
                    method: CoverageMethod::Enumerated,
                },
            ],
            fraction_bits: 1.0_f64.to_bits(),
        };
        let json = serde_json::to_string(&coverage).unwrap();
        let back: Coverage = serde_json::from_str(&json).unwrap();
        assert_eq!(back, coverage);
        assert_eq!(back.fraction().to_bits(), 1.0_f64.to_bits());
    }
}
