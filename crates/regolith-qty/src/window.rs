//! `Window`: a demanded containment window `within [lo, hi]` -- a value
//! the design must land inside, distinct from an asserted `Interval`.
//!
//! Regolith reference: `docs/spec/regolith/03-value-sources.md` sec. 1.
//! An [`crate::Interval`] is the scatter/range the author *asserts*; a
//! `Window` is the band the design is *required* to satisfy (a flexure
//! stiffness that must be neither too stiff nor too soft; an oscillator
//! band). Kept a separate type so the two intents never silently mix
//! (WO-03 acceptance: not interchangeable with Interval).

use serde::{Deserialize, Serialize};

use crate::unit::Unit;

/// A demanded window `within [lo, hi]` (`lo <= hi`) in one unit.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Window {
    lo: f64,
    hi: f64,
    unit: Unit,
}

impl Window {
    /// Construct a demanded window from raw magnitudes and a unit.
    #[must_use]
    pub fn new(lo: f64, hi: f64, unit: Unit) -> Window {
        Window { lo, hi, unit }
    }

    /// Lower magnitude of the demanded band.
    #[must_use]
    pub fn lo(&self) -> f64 {
        self.lo
    }

    /// Upper magnitude of the demanded band.
    #[must_use]
    pub fn hi(&self) -> f64 {
        self.hi
    }

    /// The unit the band is expressed in.
    #[must_use]
    pub fn unit(&self) -> &Unit {
        &self.unit
    }
}

#[cfg(test)]
mod tests {
    use super::Window;
    use crate::unit::Unit;

    #[test]
    fn window_round_trips_json() {
        let w = Window::new(0.8, 1.6, Unit::dimensionless());
        let json = serde_json::to_string(&w).unwrap();
        let back: Window = serde_json::from_str(&json).unwrap();
        assert_eq!(back.lo().to_bits(), 0.8_f64.to_bits());
        assert_eq!(back.hi().to_bits(), 1.6_f64.to_bits());
    }
}
