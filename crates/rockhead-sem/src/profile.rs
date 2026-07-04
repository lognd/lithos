//! Profile static checks (WO-11 ledger half): branch-pin completeness
//! and the sketch DOF ledger. NO constraint solving.
//!
//! Substrate reference: `docs/mech/02` sec. 5. The walk AST comes from
//! `rockhead_syntax::walk`. This module runs the two static checks and
//! models exports as placeless datums exposed ONLY through an
//! instantiation context (feature-first re-anchoring): referencing an
//! export through the profile value rather than a feature is an error
//! with the anchoring rule's message.

use rockhead_diag::{codes, Diagnostic};
use rockhead_syntax::walk::{Direction, Segment, Walk};
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

/// The freedoms one segment contributes to the ledger: a straight `line`
/// is a free endpoint (2 DOF, x/y); an `arc` additionally carries its
/// radius (3 DOF). `bulge=left|right` picks which circle the arc's
/// endpoints lie on and is a required field of the AST already -- not a
/// ledger constraint.
fn segment_freedom(seg: &Segment) -> i64 {
    match seg {
        Segment::Line(_) => 2,
        Segment::Arc { .. } => 3,
    }
}

/// The constraint a segment's join contributes: `tangent`/`perpendicular`
/// pin the relationship to the previous segment (1 DOF each); direction
/// words (`left`/`right`) are uniqueness HINTS only (mech/02 sec. 5),
/// never ledger constraints.
fn segment_constraint(seg: &Segment) -> i64 {
    let join = match seg {
        Segment::Line(d) => d.as_ref(),
        Segment::Arc { join, .. } => join.as_ref(),
    };
    match join {
        Some(Direction::Tangent | Direction::Perpendicular) => 1,
        _ => 0,
    }
}

/// Compute the DOF ledger for a walk (counts freedoms and constraints
/// from the segment/constraint structure).
#[must_use]
pub fn compute_ledger(walk: &Walk, declared_free: i64) -> DofLedger {
    let mut freedoms = 0i64;
    let mut constraints = 0i64;

    for seg in &walk.segments {
        freedoms += segment_freedom(seg);
        constraints += segment_constraint(seg);
    }
    for hole in &walk.holes {
        for seg in &hole.segments {
            freedoms += segment_freedom(seg);
            constraints += segment_constraint(seg);
        }
    }

    // Declared `constraints:` items (the closed SolveSpace-equivalent
    // vocabulary, mech/07 OPEN-5/D65): each item removes one freedom.
    constraints += i64::try_from(walk.constraints.len()).unwrap_or(i64::MAX);
    // `close` ties the last point back to the first: a coincidence
    // constraint on both axes.
    if walk.closes {
        constraints += 2;
    }

    DofLedger {
        freedoms,
        constraints,
        declared_free,
    }
}

/// Check branch-pin completeness: every discrete solver branch (an
/// arc's join to its neighbor) must be pinned with `tangent` or
/// `perpendicular`, else a diagnostic listing the unpinned joints.
#[must_use]
pub fn check_branch_pins(walk: &Walk) -> Vec<Diagnostic> {
    let mut unpinned = Vec::new();
    for (i, seg) in walk.segments.iter().enumerate() {
        if matches!(seg, Segment::Arc { join: None, .. }) {
            unpinned.push(format!("segment {i} (arc)"));
        }
    }
    for hole in &walk.holes {
        for (i, seg) in hole.segments.iter().enumerate() {
            if matches!(seg, Segment::Arc { join: None, .. }) {
                unpinned.push(format!("hole `{}` segment {i} (arc)", hole.name));
            }
        }
    }

    if unpinned.is_empty() {
        return Vec::new();
    }
    vec![Diagnostic::error(
        codes::LEDGER_IMBALANCE,
        format!(
            "unpinned discrete solver branch(es): {}",
            unpinned.join(", ")
        ),
    )
    .with_fix(rockhead_diag::Fix {
        message: "add a `tangent` or `perpendicular` join to pin the branch".to_string(),
        replacement: None,
    })]
}

/// Check the DOF ledger closes (residual zero or via declared free
/// variables); a leftover DOF is a diagnostic naming the count and
/// direction (under- vs over-constrained).
#[must_use]
pub fn check_ledger_closes(ledger: &DofLedger) -> Vec<Diagnostic> {
    let residual = ledger.residual();
    if residual == 0 {
        return Vec::new();
    }
    let (verb, count) = if residual > 0 {
        ("under-constrained", residual)
    } else {
        ("over-constrained", -residual)
    };
    vec![Diagnostic::error(
        codes::LEDGER_IMBALANCE,
        format!("sketch is {verb} by {count} degree(s) of freedom"),
    )
    .with_fix(rockhead_diag::Fix {
        message: "add a constraint, or declare a free variable to absorb the residual".to_string(),
        replacement: None,
    })]
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
    /// An empty `anchor_feature` is the sentinel for "referenced through
    /// the profile value directly" (no feature-first instantiation) --
    /// the export-anchoring rule (mech/02 sec. 5) rejects that path
    /// regardless of whether `name` exists.
    ///
    /// # Errors
    /// Returns a diagnostic (the anchoring-rule message) if the export is
    /// referenced without a feature anchor, or if `name` is not among
    /// this context's declared exports. Boxed: `Diagnostic` is large
    /// relative to the `Ok` value.
    pub fn resolve_export(&self, name: &str) -> Result<String, Box<Diagnostic>> {
        if self.anchor_feature.is_empty() {
            return Err(Box::new(
                Diagnostic::error(
                    codes::AMBIGUOUS_SELECTION,
                    format!(
                        "export `{name}` referenced through the profile value directly; \
                         exports are feature-first re-anchored"
                    ),
                )
                .with_fix(rockhead_diag::Fix {
                    message: "reference the export through the instantiating feature".to_string(),
                    replacement: None,
                }),
            ));
        }
        if !self.exports.iter().any(|e| e == name) {
            return Err(Box::new(Diagnostic::error(
                codes::AMBIGUOUS_SELECTION,
                format!("no export named `{name}` in this profile"),
            )));
        }
        Ok(format!("{}.{name}", self.anchor_feature))
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
