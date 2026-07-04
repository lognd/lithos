//! Closed intervals `[a, b]`: the source-of-truth representation for
//! tolerances, scatter, environment ranges, and process corners.
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 3
//! (interval-vs-range rule) and `docs/substrate/07` sec. 5 (corner
//! discipline). Interval arithmetic rounds OUTWARD (AD-6) so a computed
//! bound never excludes a physically reachable value; bounds are `f64`
//! carrying a shared `Unit`, like [`crate::Qty`]. NOT interconvertible
//! with [`crate::Range`] -- that is a distinct positional type.
//!
//! No `PartialEq` on the continuous form (the equality ban, sec. 2):
//! comparisons go through containment and tolerance forms.

use serde::{Deserialize, Serialize};

use crate::quantity::{Qty, QuantityError};
use crate::unit::Unit;

/// A closed interval `[lo, hi]` (`lo <= hi`) of a single quantity,
/// expressed in one unit.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Interval {
    lo: f64,
    hi: f64,
    unit: Unit,
}

impl Interval {
    /// Build `[lo, hi]` from two quantities of the same dimension. The
    /// result is expressed in `lo`'s unit.
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] when the bounds differ
    /// in dimension.
    pub fn new(_lo: &Qty, _hi: &Qty) -> Result<Interval, QuantityError> {
        todo!("STUB WO-03: dimension guard + convert hi into lo's unit + order lo<=hi")
    }

    /// Symmetric tolerance `center +- tol` (`tol` a quantity of the same
    /// dimension).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn plus_minus(_center: &Qty, _tol: &Qty) -> Result<Interval, QuantityError> {
        todo!("STUB WO-03: [center-tol, center+tol], outward-rounded")
    }

    /// Percentage tolerance `center +- p%` (`3.3V +- 5%`).
    #[must_use]
    pub fn plus_minus_percent(_center: &Qty, _percent: f64) -> Interval {
        todo!("STUB WO-03: [center*(1-p/100), center*(1+p/100)], outward-rounded")
    }

    /// Scale an interval by a scalar factor range: `[k1, k2] * x`.
    #[must_use]
    pub fn scaled(_x: &Qty, _k1: f64, _k2: f64) -> Interval {
        todo!("STUB WO-03: [k1*x, k2*x] with outward rounding and sign handling")
    }

    /// The lower bound as a quantity.
    #[must_use]
    pub fn lo(&self) -> Qty {
        Qty::new(self.lo, self.unit.clone())
    }

    /// The upper bound as a quantity.
    #[must_use]
    pub fn hi(&self) -> Qty {
        Qty::new(self.hi, self.unit.clone())
    }

    /// The unit the bounds are expressed in.
    #[must_use]
    pub fn unit(&self) -> &Unit {
        &self.unit
    }

    /// Interval sum `[a,b] + [c,d] = [a+c, b+d]`, outward-rounded.
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn add(&self, _other: &Interval) -> Result<Interval, QuantityError> {
        todo!("STUB WO-03: outward-rounded endpoint sum with dimension guard")
    }

    /// Interval difference `[a,b] - [c,d] = [a-d, b-c]`, outward-rounded.
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn sub(&self, _other: &Interval) -> Result<Interval, QuantityError> {
        todo!("STUB WO-03: outward-rounded cross-endpoint difference")
    }

    /// Multiply by a scalar interval (dimensionless `[k1,k2]`): the four
    /// products' min/max, outward-rounded.
    #[must_use]
    pub fn mul_scalar_interval(&self, _k1: f64, _k2: f64) -> Interval {
        todo!("STUB WO-03: min/max of the four endpoint products, outward-rounded")
    }

    /// True when `q` lies within `[lo, hi]` (dimension-checked).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn contains(&self, _q: &Qty) -> Result<bool, QuantityError> {
        todo!("STUB WO-03: convert q into self.unit, compare against bounds")
    }
}

#[cfg(test)]
mod tests {
    use super::Interval;
    use crate::dimension::{BaseDimension, Dimension};
    use crate::quantity::Qty;
    use crate::unit::Unit;
    use num_rational::Ratio;

    fn metres(x: f64) -> Qty {
        Qty::new(
            x,
            Unit {
                symbol: "m".to_string(),
                dimension: Dimension::base(BaseDimension::Length),
                scale: Ratio::from_integer(1),
                offset: Ratio::from_integer(0),
            },
        )
    }

    #[test]
    #[ignore = "WO-03 impl: Interval::new body pending"]
    fn interval_bounds_round_trip() {
        let iv = Interval::new(&metres(2.0), &metres(8.0)).unwrap();
        assert_eq!(iv.lo().magnitude().to_bits(), 2.0_f64.to_bits());
        assert_eq!(iv.hi().magnitude().to_bits(), 8.0_f64.to_bits());
    }

    // Property: sum widths add and are outward-rounded (containment
    // monotone). Wired now; un-ignored when the arithmetic lands.
    proptest::proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(32))]
        #[test]
        #[ignore = "WO-03 impl: interval arithmetic pending"]
        fn add_is_monotone_in_containment(a in -100.0f64..100.0, w in 0.0f64..50.0) {
            let x = Interval::new(&metres(a), &metres(a + w)).unwrap();
            let sum = x.add(&x).unwrap();
            // [a,a+w]+[a,a+w] = [2a, 2a+2w] contains 2a
            proptest::prop_assert!(sum.contains(&metres(2.0 * a)).unwrap());
        }
    }
}
