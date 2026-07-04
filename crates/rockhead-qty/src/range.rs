//! Half-open positional ranges `[i .. j]` over semantically ordered
//! discrete positions (bus bits, memory addresses).
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 3.
//! A `Range` is NOT an [`crate::Interval`] and never implicitly
//! converts to one: intervals are continuous closed values, ranges are
//! half-open discrete addressing. Keeping them distinct types is the
//! enforcement (WO-03 acceptance: not interchangeable).

use serde::{Deserialize, Serialize};

use crate::quantity::Qty;

/// A position in a positional range: either a plain integer index (bus
/// bit) or an address-valued quantity (`flash[0 .. 32kB]`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RangePos {
    /// A non-negative integer index (a bit position).
    Index(u64),
    /// An address-valued quantity (a storage or memory offset).
    Address(Qty),
}

/// A half-open range `[start .. end)`. `end` is optional: an absent end
/// means "to the extent's end" (`[1MB ..]`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Range {
    /// Inclusive start position.
    pub start: RangePos,
    /// Exclusive end position, or `None` for open-right (to extent end).
    pub end: Option<RangePos>,
}

impl Range {
    /// A closed-ended half-open range `[start .. end)`.
    #[must_use]
    pub fn new(start: RangePos, end: RangePos) -> Range {
        Range {
            start,
            end: Some(end),
        }
    }

    /// An open-right range `[start ..]` (to the extent's end).
    #[must_use]
    pub fn open(start: RangePos) -> Range {
        Range { start, end: None }
    }

    /// True when the range has no explicit end (open right).
    #[must_use]
    pub fn is_open(&self) -> bool {
        self.end.is_none()
    }

    /// The count of integer positions in a closed integer range
    /// (`[0 .. 3]` -> 3). `None` for open or address-valued ranges.
    #[must_use]
    pub fn index_len(&self) -> Option<u64> {
        todo!("STUB WO-03: (end - start) for Index..Index; None otherwise")
    }
}

#[cfg(test)]
mod tests {
    use super::{Range, RangePos};

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
}
