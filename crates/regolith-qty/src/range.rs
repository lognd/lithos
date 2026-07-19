//! Half-open positional ranges `[i .. j]` over semantically ordered
//! discrete positions (bus bits, memory addresses).
//!
//! Regolith reference: `docs/spec/regolith/02-quantity-core.md` sec. 3.
//! A `Range` is NOT an [`crate::Interval`] and never implicitly
//! converts to one: intervals are continuous closed values, ranges are
//! half-open discrete addressing. Keeping them distinct types is the
//! enforcement (WO-03 acceptance: not interchangeable).

use serde::{Deserialize, Serialize};

use crate::quantity::Qty;

/// A position in a positional range: either a plain integer index (bus
/// bit) or an address-valued quantity (`flash[0 .. 32kB]`).
#[derive(Debug, Clone, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-qty.md#range
pub enum RangePos {
    /// A non-negative integer index (a bit position).
    Index(u64),
    /// An address-valued quantity (a storage or memory offset).
    Address(Qty),
}

/// A half-open range `[start .. end)`. `end` is optional: an absent end
/// means "to the extent's end" (`[1MB ..]`).
#[derive(Debug, Clone, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-qty.md#range
pub struct Range {
    /// Inclusive start position.
    pub start: RangePos,
    /// Exclusive end position, or `None` for open-right (to extent end).
    pub end: Option<RangePos>,
}

impl Range {
    /// A closed-ended half-open range `[start .. end)`.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#range
    pub fn new(start: RangePos, end: RangePos) -> Range {
        Range {
            start,
            end: Some(end),
        }
    }

    /// An open-right range `[start ..]` (to the extent's end).
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#range
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn open(start: RangePos) -> Range {
        Range { start, end: None }
    }

    /// True when the range has no explicit end (open right).
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#range
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn is_open(&self) -> bool {
        self.end.is_none()
    }

    /// The count of integer positions in a closed integer range
    /// (`[0 .. 3]` -> 3). `None` for open or address-valued ranges.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#range
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn index_len(&self) -> Option<u64> {
        match (&self.start, &self.end) {
            (RangePos::Index(start), Some(RangePos::Index(end))) => Some(end - start),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{Range, RangePos};

    // frob:tests crates/regolith-qty/src/range.rs::Range.is_open kind="unit"
    // frob:tests crates/regolith-qty/src/range.rs::Range.open kind="unit"
    #[test]
    fn open_range_reports_open() {
        let r = Range::open(RangePos::Index(1));
        assert!(r.is_open());
        let c = Range::new(RangePos::Index(0), RangePos::Index(3));
        assert!(!c.is_open());
    }

    #[test]
    fn range_round_trips_json() {
        let r = Range::new(RangePos::Index(0), RangePos::Index(3));
        let json = serde_json::to_string(&r).unwrap();
        let back: Range = serde_json::from_str(&json).unwrap();
        assert!(!back.is_open());
    }

    // frob:tests crates/regolith-qty/src/range.rs::Range.index_len kind="unit"
    #[test]
    fn index_len_counts_closed_integer_ranges_only() {
        let closed = Range::new(RangePos::Index(0), RangePos::Index(3));
        assert_eq!(closed.index_len(), Some(3));

        let open = Range::open(RangePos::Index(1));
        assert_eq!(open.index_len(), None, "open ranges have no fixed count");

        let addressed = Range::new(
            RangePos::Address(crate::quantity::Qty::new(
                0.0,
                crate::unit::Unit::dimensionless(),
            )),
            RangePos::Index(3),
        );
        assert_eq!(
            addressed.index_len(),
            None,
            "address-valued ends are not countable"
        );
    }
}
