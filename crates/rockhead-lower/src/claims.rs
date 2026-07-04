//! Pass 5: `RequireClaim` -> `Claim` -> `Obligation`, one per claim
//! line; one `SnapshotRecord` per committed entity scope.
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md` sec.
//! 2, `docs/substrate/13` INV-1 (obligation-key sensitivity). Each
//! `RequireClaim` group's `Field` lines (`subject: predicate`) become
//! one `Obligation` each; `subject_ref` is the enclosing declaration's
//! `EntityDb::snapshot_hash()` (AD-18). Sweep-domain detection
//! (`forall ...`) needs structure this WO's grammar surface does not
//! expose at the claim-line level, so every obligation here is a
//! single-point obligation (`sweep: None`) -- see the WO-19
//! partial-lowering note.

use rockhead_diag::Diagnostic;
use rockhead_oblig::{Claim, ClaimForm, Given, Obligation, SnapshotRecord};
use rockhead_syntax::ast::{AstNode, File};

use crate::checks::CheckReport;
use crate::contracts::ContractGraph;
use crate::entities::EntitySnapshots;
use crate::output::ParsedFile;

/// Every obligation this pass produced, the snapshot records for every
/// committed scope, and any diagnostics.
#[derive(Debug, Clone, Default)]
pub struct ObligationSet {
    /// One obligation per structured claim line.
    pub obligations: Vec<Obligation>,
    /// One record per committed `EntityDb` scope.
    pub snapshots: Vec<SnapshotRecord>,
    /// Diagnostics from claim lowering (currently none -- claim lines
    /// are lowered structurally, with no ambiguity to report yet).
    pub diagnostics: Vec<Diagnostic>,
}

/// Lower every structured `require` group into obligations.
#[must_use]
pub fn build_obligations(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
    _checks: &CheckReport,
    _graph: &ContractGraph,
) -> ObligationSet {
    let span = tracing::info_span!("lower.claims");
    let _enter = span.enter();

    let mut out = ObligationSet::default();

    for (scope, db) in &snapshots.scopes {
        out.snapshots.push(SnapshotRecord {
            scope: scope.clone(),
            hash: db.snapshot_hash(),
        });
    }

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let Some(decl_name) = decl.name() else {
                continue;
            };
            let subject_ref = snapshots
                .scopes
                .get(&decl_name)
                .map(rockhead_sem::EntityDb::snapshot_hash)
                .unwrap_or_default();

            for group in decl.claims() {
                for line in group.claims() {
                    let subject = line.name();
                    let predicate = line
                        .value()
                        .map(|v| v.text().to_string())
                        .unwrap_or_default();

                    let claim = Claim {
                        name: Some(subject.clone()),
                        form: ClaimForm::Comparison {
                            lhs: subject.clone(),
                            op: "require".to_string(),
                            rhs: predicate.trim().to_string(),
                        },
                        forall: Vec::new(),
                        sf: None,
                        scatter_factor: None,
                        trust_floor: None,
                        hints: Vec::new(),
                        model_pin: None,
                    };

                    let obligation = Obligation {
                        claim,
                        subject_ref: subject_ref.clone(),
                        // TODO(BE-2, INV-1): given is unconditionally
                        // empty -- claims differing only in materials/
                        // loads currently hash identically and share
                        // cached evidence. Threading real given values
                        // needs the materials/loads grammar (WO-05
                        // residual). Until then obligation keys are
                        // under-specified; see docs/audit/backend-
                        // conformance.md BE-2.
                        given: Given {
                            materials: Vec::new(),
                            loads: Vec::new(),
                            backing: Vec::new(),
                        },
                        hints: Vec::new(),
                        sweep: None,
                    };

                    tracing::debug!(
                        decl = %decl_name,
                        subject = %subject,
                        hash = %obligation.content_hash(),
                        "built obligation from require claim"
                    );
                    out.obligations.push(obligation);
                }
            }
        }
    }

    out
}
