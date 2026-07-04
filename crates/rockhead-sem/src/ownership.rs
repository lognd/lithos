//! Ownership and borrow checking: the anti-toponaming machinery. Single
//! ownership, borrows, merge signs, and region conflicts -- all on
//! predicted deltas, before any realizer exists.
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`
//! sec. 3 and `docs/substrate/06` sec. 2. A borrow conflict is reported
//! BIDIRECTIONALLY -- at the modifier AND at the borrower (SEAM-1,
//! mech/03 sec. 2.1). Same-sign overlaps auto-merge (ownership demanded
//! lazily); mixed-sign overlap in one scope is a hard error. Elec
//! binding: one driver per net is ownership; `arbitrate` is a declared
//! join.

use rockhead_diag::Diagnostic;
use serde::{Deserialize, Serialize};

use crate::entity::{EntityId, PredictedDelta};

/// The lifetime of a borrow.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BorrowKind {
    /// Query consumption: immutable borrow to the end of the stage.
    StageImmutable,
    /// Impl role binding: permanent borrow for the artifact's lifetime,
    /// across all stages.
    Permanent,
}

/// The sign of a modifying delta, for merge analysis (additive vs
/// subtractive effect on a contested region).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MergeSign {
    /// Adds material / drive (positive contribution).
    Positive,
    /// Removes material / drive (negative contribution).
    Negative,
}

/// One recorded borrow held by a construct.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Borrow {
    /// The entities borrowed.
    pub entities: Vec<EntityId>,
    /// The construct holding the borrow (for the bidirectional report).
    pub borrower: String,
    /// The borrow's lifetime.
    pub kind: BorrowKind,
}

/// The borrow table for a scope: the live borrows a later modifying
/// delta is checked against.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct BorrowTable {
    borrows: Vec<Borrow>,
}

impl BorrowTable {
    /// An empty borrow table.
    #[must_use]
    pub fn new() -> BorrowTable {
        BorrowTable {
            borrows: Vec::new(),
        }
    }

    /// Record a borrow held by a construct.
    pub fn borrow(&mut self, borrow: Borrow) {
        self.borrows.push(borrow);
    }

    /// Check a modifying delta against live borrows: the modified-set x
    /// borrowed-set intersection. Each conflict yields TWO diagnostics
    /// (at the modifier and at the borrower), both E0302.
    #[must_use]
    pub fn check_conflict(&self, _modifier: &str, _delta: &PredictedDelta) -> Vec<Diagnostic> {
        todo!("STUB WO-09: intersect modifies/regions_touched with borrows; bidirectional E0302")
    }

    /// Analyse overlapping same-scope deltas: same-sign overlap
    /// auto-merges (returns no diagnostic; ownership demanded lazily);
    /// mixed-sign overlap is a hard error suggesting `merge(a before b)`
    /// or rescoping.
    #[must_use]
    pub fn merge_analysis(
        &self,
        _a: (&str, MergeSign, &PredictedDelta),
        _b: (&str, MergeSign, &PredictedDelta),
    ) -> Vec<Diagnostic> {
        todo!("STUB WO-09: same-sign -> merge OK; mixed-sign -> hard error with merge/rescope fix")
    }

    /// Re-evaluate borrows after a `rebind()` (drops stale borrows so a
    /// query taken after a modifier is legal).
    pub fn rebind(&mut self, _borrower: &str) {
        todo!("STUB WO-09: drop the borrower's stale borrows so re-selection is legal")
    }
}

/// Check the single-driver rule for a net (elec ownership binding): one
/// driving construct per net unless a declared `arbitrate` join exists.
/// Multiple drivers without arbitration is an E03xx (multiple drivers).
#[must_use]
pub fn check_single_driver(
    _net: EntityId,
    _drivers: &[String],
    _arbitrated: bool,
) -> Vec<Diagnostic> {
    todo!("STUB WO-09: >1 driver && !arbitrated -> multiple-drivers E03xx naming each driver")
}

#[cfg(test)]
mod tests {
    use super::{Borrow, BorrowKind, BorrowTable};
    use crate::entity::EntityId;

    #[test]
    fn borrow_table_records() {
        let mut t = BorrowTable::new();
        t.borrow(Borrow {
            entities: vec![EntityId(1)],
            borrower: "mount".to_string(),
            kind: BorrowKind::Permanent,
        });
        let json = serde_json::to_string(&t).unwrap();
        let back: BorrowTable = serde_json::from_str(&json).unwrap();
        assert_eq!(back, t);
    }
}
