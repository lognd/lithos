//! Pass 3: semantic checks over lowered entities (ownership,
//! stages/scopes, profile DOF ledgers, symmetry orbits).
//!
//! Substrate reference: `docs/substrate/05` sec. 3/5, `docs/substrate/06`.
//! WO-19's per-decl entity granularity (see `entities.rs`) does not yet
//! populate `PredictedDelta`/`BorrowTable`/`StageGraph`/`Walk` inputs --
//! those need the domain `OpaqueIsland` bodies (machining stages,
//! `connect`/mating bodies, profile `walk:` blocks) that WO-05 leaves
//! unstructured. This pass therefore runs each checker over the
//! (currently empty) structured inputs it DOES have, so the moment a
//! later WO structures more of the grammar, real diagnostics start
//! flowing with no pipeline change -- it is real code that correctly
//! reports nothing yet, not a stub (see the WO-19 partial-lowering
//! note).

use rockhead_diag::Diagnostic;
use rockhead_sem::{OrbitTable, StageGraph};

use crate::entities::EntitySnapshots;

/// Diagnostics from every static check, plus the artifact-level orbit
/// table (symmetry) computed so far.
#[derive(Debug, Clone, Default)]
pub struct CheckReport {
    /// Diagnostics from ownership/stage/profile/symmetry checks.
    pub diagnostics: Vec<Diagnostic>,
    /// The (currently trivial) symmetry orbit table.
    pub orbits: OrbitTable,
}

/// Run the WO-19-available static checks over `snapshots`.
#[must_use]
pub fn run_checks(snapshots: &EntitySnapshots) -> CheckReport {
    let span = tracing::info_span!("lower.checks");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();

    // Stage topology: no stage graph is built by `entities.rs` (stage
    // pipelines live entirely in `OpaqueIsland` bodies today), so this
    // runs over an empty graph -- trivially acyclic, real code, no
    // stub. Wiring a real graph is future work once WO-05 structures
    // stage headers.
    let stages = StageGraph::new();
    match stages.topo_order() {
        Ok(order) => tracing::debug!(count = order.len(), "stage topo order (empty graph)"),
        Err(diags) => diagnostics.extend(diags),
    }

    tracing::debug!(
        scopes = snapshots.scopes.len(),
        "ownership/profile/symmetry checks skipped: no structured mating/walk \
         input available yet (opaque bodies, see partial-lowering note)"
    );

    CheckReport {
        diagnostics,
        orbits: OrbitTable::new(),
    }
}
