//! Profile static checks (WO-11 ledger half): branch-pin completeness
//! and the sketch DOF ledger. NO constraint solving.
//!
//! Substrate reference: `docs/mech/02` sec. 5. The walk AST comes from
//! `rockhead_syntax::walk`. This module runs the two static checks and
//! models exports as placeless datums exposed ONLY through an
//! instantiation context (feature-first re-anchoring): referencing an
//! export through the profile value rather than a feature is an error
//! with the anchoring rule's message.

use rockhead_diag::Diagnostic;
use rockhead_syntax::walk::Walk;
use serde::{Deserialize, Serialize};

/// The sketch degree-of-freedom ledger: entity freedoms minus applied
/// constraints. The remainder must be zero or accounted for by declared
/// free variables (value sources).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DofLedger {
    /// Total freedoms contributed by the walk's entities.
    pub freedoms: i64,
    /// Total constraints applied.
    pub constraints: i64,
    /// Count of declared free variables absorbing residual DOF.
    pub declared_free: i64,
}

impl DofLedger {
    /// The residual DOF: `freedoms - constraints - declared_free`. Zero
    /// means fully constrained; positive means under-constrained.
    #[must_use]
    pub fn residual(&self) -> i64 {
        self.freedoms - self.constraints - self.declared_free
    }

    /// True when the sketch closes (residual is zero).
    #[must_use]
    pub fn is_closed(&self) -> bool {
        self.residual() == 0
    }
}

/// Compute the DOF ledger for a walk (counts freedoms and constraints
/// from the segment/constraint structure).
#[must_use]
pub fn compute_ledger(_walk: &Walk, _declared_free: i64) -> DofLedger {
    todo!("STUB WO-11: sum segment freedoms, subtract constraint items; record declared free vars")
}

/// Check branch-pin completeness: every discrete solver branch (arc
/// side, tangency choice) must be pinned, else a diagnostic listing the
/// unpinned joints.
#[must_use]
pub fn check_branch_pins(_walk: &Walk) -> Vec<Diagnostic> {
    todo!("STUB WO-11: find arcs/joins whose discrete branch is unpinned; list them in an E-diag")
}

/// Check the DOF ledger closes (residual zero or via declared free
/// variables); a leftover DOF is a diagnostic.
#[must_use]
pub fn check_ledger_closes(_ledger: &DofLedger) -> Vec<Diagnostic> {
    todo!("STUB WO-11: residual != 0 -> under/over-constrained diagnostic with the DOF count")
}

/// The instantiation context through which a profile's exports (placeless
/// datums) are reached. Exports are feature-first re-anchored: reaching
/// an export through the profile value directly is rejected.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InstantiationContext {
    /// The feature that anchors the instantiation.
    pub anchor_feature: String,
    /// The export names available in this context.
    pub exports: Vec<String>,
}

impl InstantiationContext {
    /// Resolve an export by name within this context.
    ///
    /// # Errors
    /// Returns a diagnostic (the anchoring-rule message) if the export is
    /// referenced without a feature anchor. Boxed: `Diagnostic` is large
    /// relative to the `Ok` value.
    pub fn resolve_export(&self, _name: &str) -> Result<String, Box<Diagnostic>> {
        todo!("STUB WO-11: return the anchored datum, or the export-anchoring-rule diagnostic")
    }
}

#[cfg(test)]
mod tests {
    use super::DofLedger;

    #[test]
    fn residual_and_closure() {
        let closed = DofLedger {
            freedoms: 6,
            constraints: 6,
            declared_free: 0,
        };
        assert_eq!(closed.residual(), 0);
        assert!(closed.is_closed());

        let free = DofLedger {
            freedoms: 6,
            constraints: 5,
            declared_free: 1,
        };
        assert!(free.is_closed());

        let leftover = DofLedger {
            freedoms: 6,
            constraints: 4,
            declared_free: 0,
        };
        assert_eq!(leftover.residual(), 2);
        assert!(!leftover.is_closed());
    }
}
