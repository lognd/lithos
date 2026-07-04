//! Semantic layer: entity database, queries, ownership/borrows,
//! stages/scopes, monomorphization, symmetry, sketch ledger.
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`.
//! WO-07..11 fill this in; WO-01 anchors the crate in the layering.

/// True when the semantic layer is wired (placeholder for WO-07).
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
