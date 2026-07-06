//! `Obligation`: the self-contained, serializable unit a claim lowers
//! to. Its JSON serialization IS the interchange format (golden-filed).
//!
//! Regolith reference: `docs/regolith/07-claims-and-evidence.md`
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
        crate::encoding::content_address("regolith.oblig.obligation", self)
            .expect("Obligation must not contain non-finite floats (upstream compiler bug)")
    }

    /// The evidence-cache key for this obligation under a given harness
    /// model-registry version (INV-1, BE-1). Folds `registry_version`
    /// into the hash alongside the obligation itself, so a harness model
    /// fix/upgrade (a new registry version) produces a DIFFERENT key and
    /// forces re-verification instead of silently reusing stale cached
    /// evidence. The registry version originates Python-side (AD-1) and
    /// is threaded here at discharge time; `content_hash` (the
    /// obligation's own JSON-interchange identity) is deliberately left
    /// version-free so obligation records stay stable across model bumps.
    ///
    /// # Panics
    /// Panics if `self` contains a non-finite float (upstream compiler
    /// bug), for the same reason as [`Obligation::content_hash`].
    #[must_use]
    pub fn evidence_cache_key(&self, registry_version: &str) -> String {
        // Built-in models carry the pack identity
        // `("regolith", registry_version)` (AD-19), so the un-packed
        // key is the pack-aware key at the built-in identity.
        self.evidence_cache_key_for_pack(registry_version, "regolith", registry_version)
    }

    /// The evidence-cache key under a discharging model's pack identity
    /// (AD-19, extending BE-1): folds `(pack_name, pack_version)` in
    /// addition to `registry_version`, so upgrading ONE pack produces a
    /// different key for exactly that pack's evidence and no other.
    /// Built-ins pass `("regolith", registry_version)` -- see
    /// [`Obligation::evidence_cache_key`]. The Python orchestrator's
    /// `obligation_cache_key` mirrors this fold with the same defaults.
    ///
    /// # Panics
    /// Panics if `self` contains a non-finite float (upstream compiler
    /// bug), for the same reason as [`Obligation::content_hash`].
    #[must_use]
    pub fn evidence_cache_key_for_pack(
        &self,
        registry_version: &str,
        pack_name: &str,
        pack_version: &str,
    ) -> String {
        crate::encoding::content_address(
            "regolith.oblig.evidence_key",
            &(self, registry_version, pack_name, pack_version),
        )
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
    fn evidence_cache_key_is_sensitive_to_registry_version() {
        // BE-1/INV-1 mutation-sensitivity: the SAME obligation under two
        // different model-registry versions MUST produce different cache
        // keys (a model upgrade invalidates stale evidence), while the
        // same version reproduces the same key (determinism, INV-10).
        let o = sample();
        let k_v1 = o.evidence_cache_key("model-registry@1.0.0");
        let k_v1_again = o.evidence_cache_key("model-registry@1.0.0");
        let k_v2 = o.evidence_cache_key("model-registry@2.0.0");

        assert_eq!(k_v1, k_v1_again, "same version must be a stable key");
        assert_ne!(k_v1, k_v2, "a version bump must change the key");
        // The version-folded key is also distinct from the version-free
        // content_hash, so evidence keys never collide with obligation
        // interchange identities.
        assert_ne!(k_v1, o.content_hash());
    }

    #[test]
    fn evidence_cache_key_folds_pack_identity() {
        // AD-19: upgrading ONE pack must invalidate exactly its own
        // cached evidence -- the pack pair is a key input; and the
        // un-packed key IS the pack-aware key at the built-in identity
        // ("regolith", registry_version), so there is ONE key rule.
        let o = sample();
        let rv = "model-registry@1.0.0";
        let k_pack_v1 = o.evidence_cache_key_for_pack(rv, "feldspar", "1.0.0");
        let k_pack_v1_again = o.evidence_cache_key_for_pack(rv, "feldspar", "1.0.0");
        let k_pack_v2 = o.evidence_cache_key_for_pack(rv, "feldspar", "2.0.0");
        let k_other_pack = o.evidence_cache_key_for_pack(rv, "galena", "1.0.0");

        assert_eq!(k_pack_v1, k_pack_v1_again, "same pack version: stable key");
        assert_ne!(k_pack_v1, k_pack_v2, "a pack bump must change the key");
        assert_ne!(k_pack_v1, k_other_pack, "pack name is a key input");
        assert_eq!(
            o.evidence_cache_key(rv),
            o.evidence_cache_key_for_pack(rv, "regolith", rv),
            "built-in keying delegates to the pack-aware rule"
        );
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
