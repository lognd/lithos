//! End-to-end exercise of the crate from outside: build a `Claim`, wrap
//! it in an `Obligation`, run the `decide_margin` discharge rule to
//! produce `Evidence`, and round-trip the result through an
//! `EvidenceCache` -- the WO-13 claim -> obligation -> evidence -> cache
//! chain this crate exists to carry, driven entirely through `pub` API
//! (no `crate::` internal access), per TEST003 (min one integration
//! test per crate interface).
// frob:tests crates/regolith-oblig/src kind="integration"

use regolith_oblig::{
    decide_margin, Claim, ClaimForm, Coverage, Evidence, EvidenceCache, Given, Obligation, Status,
};

fn sample_obligation() -> Obligation {
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
            refs: vec![],
        },
        hints: vec![],
        sweep: None,
        payloads: vec![],
    }
}

#[test]
fn obligation_discharges_to_cached_evidence_end_to_end() {
    let obligation = sample_obligation();
    let key = obligation.evidence_cache_key("model-registry@1.0.0");

    // The margin rule this crate ships (WO-13): a model computed
    // value=90, eps=2 against limit=100 discharges with margin 8.
    let status = decide_margin(90.0, 2.0, 100.0);
    assert_eq!(status, Status::Discharged);

    let evidence = Evidence {
        status,
        value_bits: 90.0_f64.to_bits(),
        eps_bits: 2.0_f64.to_bits(),
        margin_bits: 8.0_f64.to_bits(),
        model_id: "toy_budget_sum".to_string(),
        coverage: Coverage::full(),
        cost: 1,
        hash: obligation.content_hash(),
    };

    let mut cache = EvidenceCache::new();
    cache.insert(key.clone(), evidence.clone());

    let hit = cache
        .get(&key)
        .expect("evidence must be retrievable by its own cache key");
    assert_eq!(hit.status, Status::Discharged);
    assert!((hit.coverage.fraction() - 1.0).abs() < f64::EPSILON);

    // Cache round-trips through JSON (the interchange format, WO-13).
    let json = serde_json::to_string(&cache).unwrap();
    let back: EvidenceCache = serde_json::from_str(&json).unwrap();
    assert_eq!(back.get(&key), Some(&evidence));
}

#[test]
fn violated_and_indeterminate_stay_distinct_end_to_end() {
    // value + eps exceeds limit provably -> Violated, never conflated
    // with Indeterminate in any surface (the honesty guarantee this
    // crate's `evidence` module documents).
    assert_eq!(decide_margin(150.0, 1.0, 100.0), Status::Violated);
    // Straddling the limit within eps -> genuinely unresolved.
    assert_eq!(decide_margin(99.0, 5.0, 100.0), Status::Indeterminate);
    assert_ne!(Status::Violated, Status::Indeterminate);
}
