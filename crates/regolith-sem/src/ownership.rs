//! Ownership and borrow checking: the anti-toponaming machinery. Single
//! ownership, borrows, merge signs, and region conflicts -- all on
//! predicted deltas, before any realizer exists.
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! sec. 3 and `docs/spec/regolith/06` sec. 2. A borrow conflict is reported
//! BIDIRECTIONALLY -- at the modifier AND at the borrower (SEAM-1,
//! hematite/03 sec. 2.1). Same-sign overlaps auto-merge (ownership demanded
//! lazily); mixed-sign overlap in one scope is a hard error. Elec
//! binding: one driver per net is ownership; `arbitrate` is a declared
//! join.

use regolith_diag::{codes, Diagnostic};
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
    /// (at the modifier and at the borrower), both E0302 (SEAM-1,
    /// hematite/03 sec. 2.1).
    #[must_use]
    pub fn check_conflict(&self, modifier: &str, delta: &PredictedDelta) -> Vec<Diagnostic> {
        let touched: Vec<EntityId> = delta
            .modifies
            .iter()
            .chain(delta.regions_touched.iter())
            .copied()
            .collect();

        let mut diags = Vec::new();
        for borrow in &self.borrows {
            let conflicts = touched.iter().any(|id| borrow.entities.contains(id));
            if !conflicts {
                continue;
            }
            diags.push(Diagnostic::error(
                codes::BORROW_CONFLICT,
                format!(
                    "`{modifier}` modifies entities borrowed by `{}`",
                    borrow.borrower
                ),
            ));
            diags.push(Diagnostic::error(
                codes::BORROW_CONFLICT,
                format!(
                    "`{}` holds a borrow that `{modifier}` later modifies",
                    borrow.borrower
                ),
            ));
        }
        diags
    }

    /// Analyse overlapping same-scope deltas: same-sign overlap
    /// auto-merges (returns no diagnostic; ownership demanded lazily --
    /// only if a later query touches the contested region); mixed-sign
    /// overlap in one scope is a hard error suggesting `merge(a before
    /// b)` or rescoping.
    #[must_use]
    pub fn merge_analysis(
        &self,
        a: (&str, MergeSign, &PredictedDelta),
        b: (&str, MergeSign, &PredictedDelta),
    ) -> Vec<Diagnostic> {
        let (name_a, sign_a, delta_a) = a;
        let (name_b, sign_b, delta_b) = b;

        let touched_a: Vec<EntityId> = delta_a
            .modifies
            .iter()
            .chain(delta_a.regions_touched.iter())
            .copied()
            .collect();
        let touched_b: Vec<EntityId> = delta_b
            .modifies
            .iter()
            .chain(delta_b.regions_touched.iter())
            .copied()
            .collect();
        let overlaps = touched_a.iter().any(|id| touched_b.contains(id));

        if !overlaps || sign_a == sign_b {
            return Vec::new();
        }

        vec![Diagnostic::error(
            codes::BORROW_CONFLICT,
            format!("`{name_a}` and `{name_b}` overlap with opposing effects in one scope"),
        )
        .with_fix(regolith_diag::Fix {
            message: format!("merge(`{name_a}` before `{name_b}`)"),
            replacement: None,
        })
        .with_fix(regolith_diag::Fix {
            message: format!("rescope `{name_a}` or `{name_b}` into a separate `then` scope"),
            replacement: None,
        })]
    }

    /// Re-evaluate borrows after a `rebind()` (drops stale borrows so a
    /// query taken after a modifier is legal).
    pub fn rebind(&mut self, borrower: &str) {
        self.borrows.retain(|b| b.borrower != borrower);
    }
}

/// Check the single-driver rule for a net (elec ownership binding): one
/// driving construct per net unless a declared `arbitrate` join exists.
/// Multiple drivers without arbitration is an E03xx (multiple drivers),
/// naming every driver.
#[must_use]
pub fn check_single_driver(
    _net: EntityId,
    drivers: &[String],
    arbitrated: bool,
) -> Vec<Diagnostic> {
    if arbitrated || drivers.len() <= 1 {
        return Vec::new();
    }
    let names = drivers.join(", ");
    vec![Diagnostic::error(
        codes::AMBIGUOUS_SELECTION,
        format!("net has multiple drivers without arbitration: {names}"),
    )
    .with_fix(regolith_diag::Fix {
        message: "declare `arbitrate` to join the drivers".to_string(),
        replacement: None,
    })]
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
