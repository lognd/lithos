//! `Obligation`: the self-contained, serializable unit a claim lowers
//! to. Its JSON serialization IS the interchange format (golden-filed).
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md`
//! sec. 2. An obligation carries everything a discharger needs with no
//! back-reference to the compiler: the claim, a content-addressed
//! subject ref, the `given:` block, hints, and any `sweep:` domain. One
//! obligation carries one domain of a sweep.

use serde::{Deserialize, Serialize};

use crate::claim::Claim;

/// The `given:` context an obligation is evaluated under: the pinned
/// facts (materials, loads, backing evidence) the discharge assumes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Given {
    /// Pinned material/component records (name -> content hash).
    pub materials: Vec<(String, String)>,
    /// Applied loads/environment, as text expressions.
    pub loads: Vec<String>,
    /// Backing evidence references the given relies on.
    pub backing: Vec<String>,
}

/// A sweep domain an obligation is instantiated over (one obligation per
/// domain point; the obligation carries its own domain).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SweepDomain {
    /// The swept axis name.
    pub axis: String,
    /// The domain description (interval or discrete set, as text).
    pub domain: String,
}

/// A self-contained verification obligation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Obligation {
    /// The claim being discharged.
    pub claim: Claim,
    /// Content-addressed reference to the subject (entity/snapshot hash).
    pub subject_ref: String,
    /// The pinned evaluation context.
    pub given: Given,
    /// Discharge hints carried from the claim/symmetry.
    pub hints: Vec<String>,
    /// The sweep domain this obligation instance carries, if any.
    pub sweep: Option<SweepDomain>,
}

impl Obligation {
    /// The content address of this obligation (the cache/lockfile key).
    /// Delegates to the canonical encoder (`crate::encoding`).
    #[must_use]
    pub fn content_hash(&self) -> String {
        todo!("STUB WO-13: domain-tagged blake3 over canonical CBOR of self (via crate::encoding)")
    }
}

#[cfg(test)]
mod tests {
    use super::{Given, Obligation, SweepDomain};
    use crate::claim::{Claim, ClaimForm};

    fn sample() -> Obligation {
        Obligation {
            claim: Claim {
                name: None,
                form: ClaimForm::Comparison {
                    lhs: "stress".to_string(),
                    op: "<".to_string(),
                    rhs: "limit".to_string(),
                },
                forall: vec![],
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: vec![],
                model_pin: None,
            },
            subject_ref: "blake3:deadbeef".to_string(),
            given: Given {
                materials: vec![("AISI_4140".to_string(), "blake3:aa".to_string())],
                loads: vec!["radial: 12kN".to_string()],
                backing: vec![],
            },
            hints: vec![],
            sweep: Some(SweepDomain {
                axis: "temp".to_string(),
                domain: "[300K, 400K]".to_string(),
            }),
        }
    }

    #[test]
    fn obligation_is_the_json_interchange_format() {
        // JSON serialization is THE interchange format (WO-13): stable,
        // reloadable, self-contained. Golden-filed in WO-18.
        let o = sample();
        let json = serde_json::to_string(&o).unwrap();
        let back: Obligation = serde_json::from_str(&json).unwrap();
        assert_eq!(back, o);
    }
}
