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

use rockhead_oblig::{decide_margin, ClaimForm, Evidence, EvidenceCache, Obligation, Status};

/// Discharge the toy-model subset of `obligations` against `cache`,
/// inserting fresh results and reusing cache hits.
#[must_use]
pub fn discharge_static(
    obligations: &[Obligation],
    _graph: &crate::contracts::ContractGraph,
    cache: &mut EvidenceCache,
) -> Vec<Evidence> {
    let span = tracing::info_span!("lower.discharge");
    let _enter = span.enter();

    let mut evidence = Vec::new();

    for obligation in obligations {
        let key = obligation.content_hash();
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
