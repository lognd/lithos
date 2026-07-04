//! Contract IR: interfaces, matings, ledgers, budgets, L2 arithmetic.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. WO-12 fills
//! this in; WO-01 anchors the crate in the layering.

/// True when the contract IR is wired (placeholder for WO-12).
#[must_use]
pub fn ready() -> bool {
    false
}

#[cfg(test)]
mod tests {
    #[test]
    fn placeholder_not_ready() {
        assert!(!super::ready());
    }
}
