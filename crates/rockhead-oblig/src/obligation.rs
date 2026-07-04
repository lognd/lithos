//! `Obligation`: the self-contained, serializable unit a claim lowers
//! to. Its JSON serialization IS the interchange format (golden-filed).
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md`
//! sec. 2. An obligation carries everything a discharger needs with no
//! back-reference to the compiler: the claim, a content-addressed
//! subject ref, the `given:` block, hints, and any `sweep:` domain. One
//! obligation carries one domain of a sweep.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::claim::Claim;

/// The `given:` context an obligation is evaluated under: the pinned
/// facts (materials, loads, backing evidence) the discharge assumes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
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
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct SweepDomain {
    /// The swept axis name.
    pub axis: String,
    /// The domain description (interval or discrete set, as text).
    pub domain: String,
}

/// A self-contained verification obligation.
//
// TODO(BE-1, INV-1): the content hash omits the harness model-registry
// version, so a model fix/upgrade cannot invalidate cached evidence.
// The registry version is Python-side (AD-1); the fix threads it into
// the evidence-cache key at discharge time. See
// docs/audit/backend-conformance.md BE-1. (Plain comment, not `///`, so
// it stays out of the generated schema description.)
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
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
    ///
    /// # Panics
    /// Panics if `self` contains a non-finite float: that is an
    /// upstream compiler bug (the canonical encoder refuses to hash
    /// it silently), not a recoverable obligation-construction error.
    #[must_use]
    pub fn content_hash(&self) -> String {
        crate::encoding::content_address("rockhead.oblig.obligation", self)
            .expect("Obligation must not contain non-finite floats (upstream compiler bug)")
    }
}

/// One committed `EntityDb` scope's content-addressed snapshot, keyed
/// by its scope name -- the WO-19 lowering pipeline emits one of these
/// per scope (`docs/design-log/2026-07-04-cycle-11.md`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct SnapshotRecord {
    /// The scope this snapshot belongs to (a declaration name).
    pub scope: String,
    /// The scope's `EntityDb::snapshot_hash()` content address.
    pub hash: String,
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
