//! Pass 6: static discharge of the WO-13 toy closed-form subset,
//! cached by obligation content hash.
//!
//! Substrate reference: `docs/substrate/07` (evidence, margin rule).
//! The only closed-form model wired end-to-end anywhere in the
//! codebase is the toy `value + eps <= limit` margin rule
//! (`rockhead_oblig::decide_margin`, `model_id = "toy_budget_sum"`,
//! WO-13's own fixture). This pass recognizes obligations whose claim
//! comparison names two directly-parseable numeric literals (the only
//! shape this static pass -- with no harness, no realizer -- can
//! honestly evaluate) and discharges those; everything else is left
//! undischarged (no `Evidence` emitted), never invented.

use rockhead_oblig::{decide_margin, ClaimForm, Evidence, EvidenceCache, Obligation};

/// Discharge the toy-model subset of `obligations` against `cache`,
/// inserting fresh results and reusing cache hits.
///
/// `registry_version` is the harness model-registry version (Python-side,
/// AD-1), threaded here so it is folded into every evidence-cache key
/// (BE-1/INV-1): a model fix/upgrade bumps the version, which changes the
/// keys and forces re-verification rather than reusing stale evidence.
#[must_use]
pub fn discharge_static(
    obligations: &[Obligation],
    _graph: &crate::contracts::ContractGraph,
    cache: &mut EvidenceCache,
    registry_version: &str,
) -> Vec<Evidence> {
    let span = tracing::info_span!("lower.discharge", registry_version = %registry_version);
    let _enter = span.enter();

    let mut evidence = Vec::new();

    for obligation in obligations {
        let key = obligation.evidence_cache_key(registry_version);
        if let Some(cached) = cache.get(&key) {
            tracing::debug!(hash = %key, "evidence cache hit");
            evidence.push(cached.clone());
            continue;
        }

        let Some((value, limit)) = toy_numeric_bound(&obligation.claim.form) else {
            tracing::debug!(hash = %key, "no toy closed-form model applies; left undischarged");
            continue;
        };

        let eps = 0.0;
        let status = decide_margin(value, eps, limit);
        let ev = Evidence {
            status,
            value_bits: value.to_bits(),
            eps_bits: eps.to_bits(),
            margin_bits: (limit - (value + eps)).to_bits(),
            model_id: "toy_budget_sum".to_string(),
            coverage_bits: 1.0_f64.to_bits(),
            cost: 1,
            hash: key.clone(),
        };
        tracing::info!(hash = %key, status = ?status, "discharged obligation (toy model)");
        cache.insert(key, ev.clone());
        evidence.push(ev);
    }

    evidence
}

/// Recognize the one claim shape this static toy model can evaluate: a
/// `Comparison` whose `lhs`/`rhs` are both bare numeric literals (no
/// harness, no realized signal). Anything else -- a real subject
/// expression, a signal claim (`peak`/`settles`/...) -- has no
/// closed-form static model and returns `None`.
fn toy_numeric_bound(form: &ClaimForm) -> Option<(f64, f64)> {
    match form {
        ClaimForm::Comparison { lhs, rhs, .. } => {
            let value: f64 = lhs.trim().parse().ok()?;
            let limit: f64 = rhs.trim().parse().ok()?;
            Some((value, limit))
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::discharge_static;
    use crate::contracts::ContractGraph;
    use rockhead_oblig::{Claim, ClaimForm, EvidenceCache, Given, Obligation};

    /// A dischargeable toy obligation: `1 <= 2` (two numeric literals).
    fn dischargeable() -> Obligation {
        Obligation {
            claim: Claim {
                name: None,
                form: ClaimForm::Comparison {
                    lhs: "1".to_string(),
                    op: "<=".to_string(),
                    rhs: "2".to_string(),
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
                materials: vec![],
                loads: vec![],
                backing: vec![],
            },
            hints: vec![],
            sweep: None,
        }
    }

    #[test]
    fn model_registry_bump_invalidates_cached_evidence() {
        // BE-1/INV-1 end-to-end at the discharge seam: evidence computed
        // under registry version v1 must NOT be reused under v2. The same
        // obligation discharged under a bumped version keys differently,
        // so the second discharge is a cache miss (recomputed), and the
        // v1 entry is left untouched (its key is unreachable under v2).
        let graph = ContractGraph::default();
        let obligations = vec![dischargeable()];
        let mut cache = EvidenceCache::new();

        let ev_v1 = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        assert_eq!(ev_v1.len(), 1);
        let key_v1 = obligations[0].evidence_cache_key("registry@1");
        assert!(cache.get(&key_v1).is_some(), "v1 evidence must be cached");

        // Same obligation, bumped registry version: different key => miss.
        let key_v2 = obligations[0].evidence_cache_key("registry@2");
        assert_ne!(key_v1, key_v2);
        assert!(
            cache.get(&key_v2).is_none(),
            "v2 must not hit v1's cached evidence (stale-reuse guard)"
        );

        let ev_v2 = discharge_static(&obligations, &graph, &mut cache, "registry@2");
        assert_eq!(ev_v2.len(), 1);
        assert!(cache.get(&key_v2).is_some(), "v2 evidence must be cached");
        assert_eq!(
            ev_v2[0].hash, key_v2,
            "evidence carries its version-folded key"
        );
    }

    #[test]
    fn same_registry_version_is_a_cache_hit() {
        // Determinism (INV-10): identical obligation + identical version
        // reuses the cached evidence on a second discharge.
        let graph = ContractGraph::default();
        let obligations = vec![dischargeable()];
        let mut cache = EvidenceCache::new();

        let first = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        let second = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        assert_eq!(
            first, second,
            "same version must reproduce the same evidence"
        );
    }
}
