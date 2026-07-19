//! Pass 6: static discharge of the WO-13 toy closed-form subset plus
//! the WO-23 L2 stiffness-network tier, cached by obligation content
//! hash.
//!
//! Regolith reference: `docs/spec/regolith/07` (evidence, margin rule),
//! `docs/spec/hematite/03-contracts-and-assemblies.md` sec. 4 item 3. Two
//! static models are wired end-to-end: the toy `value + eps <= limit`
//! margin rule (`regolith_oblig::decide_margin`,
//! `model_id = "toy_budget_sum"`, WO-13's own fixture), and the L2
//! lumped stiffness network (`model_id = "l2_stiffness_network"`,
//! WO-23) behind `mech.stiffness(<node>) >= <limit>` claims whose
//! `given.loads` carry the network (entries `<name>: spring(<a>, <b>,
//! k=<f>)` and `<name>: ground(<node>)` -- a decl's `loads:` block
//! already threads through `given_for_decl`). The lumped network is a
//! conservative LOWER bound on stiffness, so this tier discharges
//! only with fat margin: a thin margin is INDETERMINATE (deferred to
//! the harness), never violated. Everything else is left undischarged
//! (no `Evidence` emitted), never invented.

use regolith_diag::Diagnostic;
use regolith_ir::solve::stiffness::{effective_stiffness, Spring, StiffnessNetwork};
use regolith_oblig::{
    decide_margin, ClaimForm, Coverage, Evidence, EvidenceCache, Given, Obligation, Status,
};

/// The evidence the static tiers produced plus any solve diagnostics
/// (singular networks are diagnostics -- values, AD-7 -- surfaced
/// through the pipeline, never panics).
// frob:doc docs/modules/regolith-lower.md#discharge
#[derive(Debug, Clone, Default)]
pub struct DischargeOutcome {
    /// Evidence for every obligation a static model could evaluate.
    pub evidence: Vec<Evidence>,
    /// Diagnostics from the numeric solves (E0440 family).
    pub diagnostics: Vec<Diagnostic>,
}

/// The model id of the WO-23 L2 lumped stiffness-network tier.
const L2_STIFFNESS_MODEL_ID: &str = "l2_stiffness_network";

/// The L2 stiffness model's relative error band: the lumped network
/// abstracts joint compliance and load-path geometry, so a claim
/// discharges only when the computed stiffness clears the limit by
/// this fraction of the limit; anything thinner defers to the harness.
const L2_STIFFNESS_REL_EPS: f64 = 0.05;

/// Discharge the toy-model subset of `obligations` against `cache`,
/// inserting fresh results and reusing cache hits.
///
/// `registry_version` is the harness model-registry version (Python-side,
/// AD-1), threaded here so it is folded into every evidence-cache key
/// (BE-1/INV-1): a model fix/upgrade bumps the version, which changes the
/// keys and forces re-verification rather than reusing stale evidence.
// frob:doc docs/modules/regolith-lower.md#discharge
#[must_use]
// frob:invariant INV-010
pub fn discharge_static(
    obligations: &[Obligation],
    _graph: &crate::contracts::ContractGraph,
    cache: &mut EvidenceCache,
    registry_version: &str,
) -> DischargeOutcome {
    let span = tracing::info_span!("lower.discharge", registry_version = %registry_version);
    let _enter = span.enter();

    let mut outcome = DischargeOutcome::default();

    for obligation in obligations {
        let key = obligation.evidence_cache_key(registry_version);
        if let Some(cached) = cache.get(&key) {
            tracing::debug!(hash = %key, "evidence cache hit");
            outcome.evidence.push(cached.clone());
            continue;
        }

        if let Some(ev) = discharge_stiffness(obligation, &key, &mut outcome.diagnostics) {
            cache.insert(key, ev.clone());
            outcome.evidence.push(ev);
            continue;
        }

        let Some((value, limit)) = toy_numeric_bound(&obligation.claim.form) else {
            tracing::debug!(hash = %key, "no static model applies; left undischarged");
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
            coverage: Coverage::full(),
            cost: 1,
            hash: key.clone(),
        };
        tracing::info!(hash = %key, status = ?status, "discharged obligation (toy model)");
        cache.insert(key, ev.clone());
        outcome.evidence.push(ev);
    }

    outcome
}

/// Try the WO-23 L2 stiffness tier on one obligation: a
/// `mech.stiffness(<node>) >= <limit>` claim whose `given.loads`
/// carry a spring network. Returns the evidence (Discharged with fat
/// margin, else Indeterminate -- NEVER Violated: the lumped network
/// is a lower bound, so a low estimate cannot disprove the claim) or
/// `None` when this tier does not apply. A singular network pushes
/// its diagnostic and yields no evidence (left undischarged).
fn discharge_stiffness(
    obligation: &Obligation,
    key: &str,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<Evidence> {
    let (node, limit) = stiffness_claim(&obligation.claim.form)?;
    let net = network_from_given(&obligation.given)?;

    let solution = effective_stiffness(&net, &node);
    diagnostics.extend(solution.diagnostics);
    let k = solution.k_eff?;

    let eps = L2_STIFFNESS_REL_EPS * limit.abs();
    // Conservative bound in, conservative margin out: compare the
    // OUTWARD LOWER bound of the computed stiffness against the limit
    // plus the model band.
    let status = if k.lo - eps >= limit {
        Status::Discharged
    } else {
        tracing::info!(
            k_lo = k.lo,
            limit,
            eps,
            "stiffness margin inside the L2 model band; deferred to the harness"
        );
        Status::Indeterminate
    };
    tracing::info!(hash = %key, status = ?status, node = %node, "L2 stiffness tier evaluated");
    Some(Evidence {
        status,
        value_bits: k.lo.to_bits(),
        eps_bits: eps.to_bits(),
        margin_bits: (k.lo - eps - limit).to_bits(),
        model_id: L2_STIFFNESS_MODEL_ID.to_string(),
        coverage: Coverage::full(),
        cost: 2,
        hash: key.to_string(),
    })
}

/// Recognize a `mech.stiffness(<node>) >= <limit>` claim in either
/// lowered shape: `lhs`/`op`/`rhs` split, or the WO-19 claim-line form
/// (`op = "require"`, the whole predicate in `rhs`). Returns the
/// queried node and the numeric limit.
fn stiffness_claim(form: &ClaimForm) -> Option<(String, f64)> {
    let ClaimForm::Comparison { lhs, op, rhs } = form else {
        return None;
    };
    let (expr, bound) = if op == ">=" {
        (lhs.trim(), rhs.trim())
    } else if op == "require" {
        let (expr, bound) = rhs.trim().split_once(">=")?;
        (expr.trim(), bound.trim())
    } else {
        return None;
    };
    let node = expr
        .strip_prefix("mech.stiffness(")?
        .split([',', ')'])
        .next()?
        .trim()
        .to_string();
    if node.is_empty() {
        return None;
    }
    let limit = leading_f64(bound)?;
    Some((node, limit))
}

/// Parse the leading float of a bound text (`120 kN/mm` -> `120`); the
/// unit tail is L1's business upstream -- this static tier compares
/// magnitudes in the declared unit of the spring constants.
fn leading_f64(text: &str) -> Option<f64> {
    let end = text
        .find(|c: char| !(c.is_ascii_digit() || "+-.eE_".contains(c)))
        .unwrap_or(text.len());
    text[..end].parse().ok()
}

/// Build the spring network from an obligation's `given.loads`
/// entries: `<name>: spring(<a>, <b>, k=<f>)` and
/// `<name>: ground(<node>)`. `None` when no spring entry is present
/// (this tier does not apply).
fn network_from_given(given: &Given) -> Option<StiffnessNetwork> {
    let mut springs = Vec::new();
    let mut grounds = Vec::new();
    for entry in &given.loads {
        let (name, value) = entry.split_once(':').unwrap_or(("", entry));
        let value = value.trim();
        if let Some(inner) = value
            .strip_prefix("spring(")
            .and_then(|r| r.strip_suffix(')'))
        {
            let parts: Vec<&str> = inner.split(',').map(str::trim).collect();
            let [a, b, k_item] = parts.as_slice() else {
                tracing::debug!(entry = %entry, "malformed spring entry skipped");
                continue;
            };
            let Some(k) = k_item
                .strip_prefix("k=")
                .and_then(|k| k.trim().parse().ok())
            else {
                tracing::debug!(entry = %entry, "spring entry without a numeric k= skipped");
                continue;
            };
            springs.push(Spring {
                name: name.trim().to_string(),
                a: (*a).to_string(),
                b: (*b).to_string(),
                k,
            });
        } else if let Some(inner) = value
            .strip_prefix("ground(")
            .and_then(|r| r.strip_suffix(')'))
        {
            grounds.push(inner.trim().to_string());
        }
    }
    if springs.is_empty() {
        return None;
    }
    Some(StiffnessNetwork {
        system: "given".to_string(),
        grounds,
        springs,
    })
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
    use regolith_diag::codes;
    use regolith_oblig::{Claim, ClaimForm, EvidenceCache, Given, Obligation, Status};

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
                refs: vec![],
            },
            hints: vec![],
            sweep: None,
            payloads: vec![],
        }
    }

    /// A `mech.stiffness(...)` obligation in the WO-19 claim-line
    /// shape, with the spring network in `given.loads`: two series
    /// springs (200, 300) grounded at `base`, so `k_eff = 120` at
    /// `tip`.
    fn stiffness_obligation(limit: &str) -> Obligation {
        Obligation {
            claim: Claim {
                name: Some("k_tip".to_string()),
                form: ClaimForm::Comparison {
                    lhs: "k_tip".to_string(),
                    op: "require".to_string(),
                    rhs: format!("mech.stiffness(tip) >= {limit}"),
                },
                forall: vec![],
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: vec![],
                model_pin: None,
            },
            subject_ref: "blake3:cafe".to_string(),
            given: Given {
                materials: vec![],
                loads: vec![
                    "s1: spring(base, mid, k=200)".to_string(),
                    "s2: spring(mid, tip, k=300)".to_string(),
                    "g: ground(base)".to_string(),
                ],
                backing: vec![],
                refs: vec![],
            },
            hints: vec![],
            sweep: None,
            payloads: vec![],
        }
    }

    // frob:tests crates/regolith-lower/src/discharge.rs::discharge_static kind="unit"
    #[test]
    fn fat_margin_stiffness_claim_discharges_statically() {
        // WO-23 acceptance: k_eff = 120 against a limit of 50 clears
        // the 5% model band by a wide margin -> Discharged, at L2,
        // with no harness in the loop.
        let graph = ContractGraph::default();
        let obligations = vec![stiffness_obligation("50 kN/mm")];
        let mut cache = EvidenceCache::new();
        let outcome = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        assert!(outcome.diagnostics.is_empty(), "{:?}", outcome.diagnostics);
        assert_eq!(outcome.evidence.len(), 1);
        assert_eq!(outcome.evidence[0].status, Status::Discharged);
        assert_eq!(outcome.evidence[0].model_id, "l2_stiffness_network");
    }

    #[test]
    fn thin_margin_stiffness_claim_defers_to_the_harness() {
        // WO-23 acceptance: k_eff = 120 against a limit of 118 is
        // inside the 5% model band (118 * 1.05 > 120) -> Indeterminate
        // at L2, NOT violated.
        let graph = ContractGraph::default();
        let obligations = vec![stiffness_obligation("118")];
        let mut cache = EvidenceCache::new();
        let outcome = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        assert_eq!(outcome.evidence.len(), 1);
        assert_eq!(outcome.evidence[0].status, Status::Indeterminate);
        assert_eq!(outcome.evidence[0].model_id, "l2_stiffness_network");
    }

    #[test]
    fn stiffness_far_below_the_limit_is_still_never_violated_at_l2() {
        // The lumped network is a LOWER bound: a low estimate defers,
        // it never disproves (the true stiffness may be higher).
        let graph = ContractGraph::default();
        let obligations = vec![stiffness_obligation("5000")];
        let mut cache = EvidenceCache::new();
        let outcome = discharge_static(&obligations, &graph, &mut cache, "registry@1");
        assert_eq!(outcome.evidence.len(), 1);
        assert_eq!(outcome.evidence[0].status, Status::Indeterminate);
    }

    #[test]
    fn singular_network_is_a_diagnostic_and_no_evidence() {
        // A network with no ground: singular, E0440 through the
        // outcome, the obligation left honestly undischarged.
        let graph = ContractGraph::default();
        let mut ob = stiffness_obligation("50");
        ob.given.loads.retain(|l| !l.contains("ground"));
        let mut cache = EvidenceCache::new();
        let outcome = discharge_static(&[ob], &graph, &mut cache, "registry@1");
        assert!(outcome.evidence.is_empty());
        assert_eq!(outcome.diagnostics.len(), 1);
        assert_eq!(outcome.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn stiffness_tier_ignores_claims_without_a_network() {
        // A stiffness claim with no spring entries in given.loads is
        // NOT this tier's business: left undischarged, no evidence
        // invented.
        let graph = ContractGraph::default();
        let mut ob = stiffness_obligation("50");
        ob.given.loads.clear();
        let mut cache = EvidenceCache::new();
        let outcome = discharge_static(&[ob], &graph, &mut cache, "registry@1");
        assert!(outcome.evidence.is_empty());
        assert!(outcome.diagnostics.is_empty());
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

        let ev_v1 = discharge_static(&obligations, &graph, &mut cache, "registry@1").evidence;
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

        let ev_v2 = discharge_static(&obligations, &graph, &mut cache, "registry@2").evidence;
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

        let first = discharge_static(&obligations, &graph, &mut cache, "registry@1").evidence;
        let second = discharge_static(&obligations, &graph, &mut cache, "registry@1").evidence;
        assert_eq!(
            first, second,
            "same version must reproduce the same evidence"
        );
    }
}
