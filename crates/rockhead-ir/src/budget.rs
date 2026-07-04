//! Budget arithmetic (L2): interval sums checked against a limit at the
//! worst-case corner, naming the worst contributors when a budget
//! cannot close (E0432).
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. Sums run in
//! source order with outward-rounded interval arithmetic (AD-6);
//! `locked:` entries are fixed contributions, reserves are held back for
//! targets.

use rockhead_diag::Diagnostic;
use rockhead_qty::Interval;

use crate::nodes::Budget;

/// One named contribution to a budget (an interval-valued draw).
#[derive(Debug, Clone)]
pub struct Contribution {
    /// Contributor name (for the E0432 diagnostic).
    pub name: String,
    /// The interval-valued amount it draws.
    pub amount: Interval,
    /// Whether this is a `locked:` (fixed) entry.
    pub locked: bool,
}

/// Check that a budget closes: the outward-rounded interval sum of the
/// contributions, plus any reserve, stays within the limit at the
/// worst-case corner.
///
/// # Errors
/// Returns an E0432 diagnostic naming the worst contributors when the
/// budget cannot close.
pub fn close_budget(
    _budget: &Budget,
    _contributions: &[Contribution],
) -> Result<(), Vec<Diagnostic>> {
    todo!("STUB WO-12: outward-rounded interval sum vs limit at worst corner; E0432 worst-first")
}

#[cfg(test)]
mod tests {
    // Well-formed close and over-budget E0432 (naming worst contributors)
    // land with the arithmetic; the interval outward-rounding lives in
    // rockhead-qty (WO-03).
    #[test]
    #[ignore = "WO-12 impl: close_budget body pending"]
    fn budget_closes_and_overflows() {}
}
