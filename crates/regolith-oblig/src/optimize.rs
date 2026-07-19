//! `OptimizationTrace`/`ChoicePoint` wire shapes (WO-55 deliverable 1;
//! toolchain/28-optimization.md; D159/D160).
//!
//! AD-30's ledger rule: the optimization engine proposes candidates and
//! evaluates them ONLY through the real pipeline (`build`/`staged_build`
//! plus discharge) -- there is no private scoring path.
//!
//! This module defines the wire shapes only, mirroring the `cost.rs`/
//! `frame.rs` precedent. `OptimizationTrace` is the search's audit
//! surface, checkpoint, and resume input; `ChoicePoint` is the D161
//! `by select` candidate set a discrete decision lowers to. Both are
//! payload kinds on the D96 ref channel (`optimize.trace`,
//! `optimize.choice`); the orchestrator (`regolith.orchestrator.
//! optimize`, Python) is the only writer.
//!
//! Determinism (AD-6/INV-30): every collection here is an ordered `Vec`
//! in enumeration/insertion order, never a `HashMap`, so
//! [`OptimizationTrace::content_digest`] is byte-stable across builds of
//! the same sources + seed + budget.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use regolith_util::canon::{content_address, EncodeError};

/// Domain tag folded into every `OptimizationTrace` content address
/// (AD-18): keeps a trace digest from colliding with any other payload
/// kind even if the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#optimize
pub const OPTIMIZATION_TRACE_DOMAIN_TAG: &str = "optimize.trace";

/// Domain tag folded into every `ChoicePoint` content address (AD-18).
// frob:doc docs/modules/regolith-oblig.md#optimize
pub const CHOICE_POINT_DOMAIN_TAG: &str = "optimize.choice";

/// How a search run ended (charter sec. 1.8, D162): never silently
/// "successful" -- `Converged` is the only arm claiming a real fixpoint,
/// and neither arm ever claims global optimality (charter sec. 4, "the
/// engine reports the best candidate FOUND within budget").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#optimize
pub enum TerminationStatus {
    /// The driver reached a fixpoint (discrete: no candidate improves on
    /// the incumbent and the domain is exhausted; continuous: the
    /// strategy's own convergence criterion fired) strictly inside the
    /// declared budget.
    Converged,
    /// The declared evaluation/wall-clock budget was exhausted before a
    /// fixpoint; the trace still carries the best FEASIBLE candidate
    /// found so far (an honest partial result, never an exception).
    BudgetExhausted,
    /// Every candidate in the domain was proven infeasible (a violated
    /// obligation with no unexplored alternative); there is no winner.
    Infeasible,
}

/// One named component of the declared objective (regolith/03 sec. 2,
/// regolith/12 sec. 4): a per-variable `minimize`/`maximize` direction,
/// or one entry of a `policy: minimize` lexicographic list. Order in the
/// enclosing `Vec` IS the lexicographic priority (AD-6): index 0 is
/// compared first, ties broken by index 1, and so on -- never a
/// re-sortable set.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#optimize
pub enum ObjectiveDirection {
    /// Lower is better.
    Minimize,
    /// Higher is better.
    Maximize,
}

/// One evaluated candidate's record in the trace (charter sec. 1.4): the
/// assignment tried, the resulting objective vector (in the declared
/// lexicographic order), a short verdict summary, and the evidence
/// digests the discharge pass produced -- the audit trail linking a
/// trace entry back to the real evidence store rows that justify it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#optimize
pub struct CandidateEntry {
    /// The proposed assignment: `(slot, value)` pairs in the order the
    /// strategy/driver assigned them (never a `HashMap` -- AD-6).
    pub assignment: Vec<(String, String)>,
    /// The objective vector read off this candidate's evaluation, one
    /// entry per declared `ObjectiveDirection` (same order, same length
    /// as the run's declared objective list).
    pub objective_vector: Vec<f64>,
    /// True iff every demand this candidate touches was dischargeable
    /// (charter sec. 1.3's feasibility gate, applied strictly first).
    pub feasible: bool,
    /// A short human-readable verdict summary (diagnostics only, never
    /// re-parsed).
    pub verdict_summary: String,
    /// The evidence digests this candidate's discharge pass produced (in
    /// discharge-emission order), so the trace can be cross-checked
    /// against `EvidenceStore` rows without re-running anything.
    pub evidence_digests: Vec<String>,
}

/// The full search trail (charter sec. 1.4): checkpoint, audit surface,
/// and `--resume` input in one content-addressed value.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#optimize
pub struct OptimizationTrace {
    /// The driver's identity (`"optimize_discrete"`, `"optimize_continuous.
    /// golden_section"`, `"optimize_continuous.nelder_mead"`, ...).
    pub strategy_id: String,
    /// The strategy implementation's version string (INV-30: a strategy
    /// version bump is itself a declared input to the determinism
    /// argument -- the same seed replayed against a newer version is
    /// honestly a different run, never silently compared).
    pub strategy_version: String,
    /// The deterministic seed this run was driven with.
    pub seed: u64,
    /// The declared evaluation budget (max evaluations), MANDATORY at
    /// invocation (charter sec. 1.8).
    pub budget_declared: u64,
    /// The number of evaluations actually spent (`<= budget_declared`
    /// unless the run converged exactly on the last one).
    pub budget_spent: u64,
    /// The declared objective, in lexicographic priority order.
    pub objective: Vec<ObjectiveDirection>,
    /// Every candidate evaluated this run, in evaluation order.
    pub candidates: Vec<CandidateEntry>,
    /// Nogood cache keys recorded during this run (D75 cross-referenced
    /// -- the search-memory side of the trace, not the trace's own
    /// identity: two runs that explore the same domain in the same order
    /// record the same keys regardless of cache pre-population).
    pub nogood_keys: Vec<String>,
    /// The index into `candidates` of the winning (best feasible)
    /// candidate, or `None` when `termination == Infeasible`.
    pub winner: Option<usize>,
    /// How the run ended (never silently "done" -- see
    /// [`TerminationStatus`]).
    pub termination: TerminationStatus,
}

impl OptimizationTrace {
    /// The content digest identifying this trace (AD-6/AD-18): the
    /// canonical encoding of every field, domain-separated from every
    /// other payload kind. INV-30's "byte-identical trace" claim is
    /// exactly "this digest is stable given identical sources + seed +
    /// budget + strategy version".
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#optimize
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(OPTIMIZATION_TRACE_DOMAIN_TAG, self)
    }
}

/// The D161 `by select(...)` discrete decision, lowered (charter sec.
/// 2): a subject, its closed candidate list (each already independently
/// statically checked), and the policy context the discrete driver reads
/// to order/cut exploration. WO-56 lowers `impl ... by select(...)` onto
/// this shape; this crate only defines the wire shape.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#optimize
pub struct ChoicePoint {
    /// The subject (part/block/interface) this choice resolves.
    pub subject_id: String,
    /// The closed candidate reference list, in declared order (one
    /// candidate is a legal, degenerate choice point -- charter sec. 2).
    pub candidate_refs: Vec<String>,
    /// Free-form policy context (e.g. which `prefer`/`forbid` rows apply
    /// here), diagnostics only -- the driver's own objective extraction
    /// is the actual mechanism, this field never re-encodes it.
    pub policy_context: String,
}

impl ChoicePoint {
    /// The content digest identifying this choice point (AD-6/AD-18).
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder.
    // frob:doc docs/modules/regolith-oblig.md#optimize
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(CHOICE_POINT_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_trace() -> OptimizationTrace {
        OptimizationTrace {
            strategy_id: "optimize_discrete".to_string(),
            strategy_version: "1".to_string(),
            seed: 42,
            budget_declared: 100,
            budget_spent: 3,
            objective: vec![ObjectiveDirection::Minimize],
            candidates: vec![CandidateEntry {
                assignment: vec![("choice.a".to_string(), "vendor_ti".to_string())],
                objective_vector: vec![1.5],
                feasible: true,
                verdict_summary: "all demands dischargeable".to_string(),
                evidence_digests: vec!["blake3:aa".to_string()],
            }],
            nogood_keys: vec!["blake3:bb".to_string()],
            winner: Some(0),
            termination: TerminationStatus::Converged,
        }
    }

    #[test]
    fn optimization_trace_round_trips_json() {
        let trace = sample_trace();
        let json = serde_json::to_string(&trace).unwrap();
        let back: OptimizationTrace = serde_json::from_str(&json).unwrap();
        assert_eq!(back, trace);
    }

    // frob:tests crates/regolith-oblig/src/optimize.rs::ChoicePoint.content_digest kind="unit"
    // frob:tests crates/regolith-oblig/src/optimize.rs::OptimizationTrace.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let trace = sample_trace();
        let d1 = trace.content_digest().unwrap();
        let d2 = trace.content_digest().unwrap();
        assert_eq!(d1, d2, "same value hashes the same way twice");

        let mut other = sample_trace();
        other.seed = 43;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "changing the seed must change the digest"
        );
    }

    #[test]
    fn choice_point_round_trips_json_and_digests() {
        let cp = ChoicePoint {
            subject_id: "decoder.impl".to_string(),
            candidate_refs: vec!["ebi_a".to_string(), "ebi_b".to_string()],
            policy_context: "minimize total_cost".to_string(),
        };
        let json = serde_json::to_string(&cp).unwrap();
        let back: ChoicePoint = serde_json::from_str(&json).unwrap();
        assert_eq!(back, cp);
        assert!(cp.content_digest().is_ok());
    }

    #[test]
    fn termination_status_round_trips_every_arm() {
        for status in [
            TerminationStatus::Converged,
            TerminationStatus::BudgetExhausted,
            TerminationStatus::Infeasible,
        ] {
            let json = serde_json::to_string(&status).unwrap();
            let back: TerminationStatus = serde_json::from_str(&json).unwrap();
            assert_eq!(back, status);
        }
    }
}
