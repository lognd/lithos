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

use crate::quantity::{convert, Qty, QuantityError};
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
    pub fn new(lo: &Qty, hi: &Qty) -> Result<Interval, QuantityError> {
        if lo.dimension() != hi.dimension() {
            return Err(QuantityError::IncompatibleDimensions {
                left: lo.dimension(),
                right: hi.dimension(),
            });
        }
        let hi_in_lo_unit = convert(hi.magnitude(), hi.unit(), lo.unit());
        let (a, b) = if lo.magnitude() <= hi_in_lo_unit {
            (lo.magnitude(), hi_in_lo_unit)
        } else {
            (hi_in_lo_unit, lo.magnitude())
        };
        Ok(Interval {
            lo: a,
            hi: b,
            unit: lo.unit().clone(),
        })
    }

    /// Symmetric tolerance `center +- tol` (`tol` a quantity of the same
    /// dimension).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn plus_minus(center: &Qty, tol: &Qty) -> Result<Interval, QuantityError> {
        if center.dimension() != tol.dimension() {
            return Err(QuantityError::IncompatibleDimensions {
                left: center.dimension(),
                right: tol.dimension(),
            });
        }
        let tol_mag = convert(tol.magnitude(), tol.unit(), center.unit()).abs();
        Ok(Interval {
            lo: (center.magnitude() - tol_mag).next_down(),
            hi: (center.magnitude() + tol_mag).next_up(),
            unit: center.unit().clone(),
        })
    }

    /// Percentage tolerance `center +- p%` (`3.3V +- 5%`).
    #[must_use]
    pub fn plus_minus_percent(center: &Qty, percent: f64) -> Interval {
        let mag = center.magnitude();
        let a = mag * (1.0 - percent / 100.0);
        let b = mag * (1.0 + percent / 100.0);
        let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
        Interval {
            lo: lo.next_down(),
            hi: hi.next_up(),
            unit: center.unit().clone(),
        }
    }

    /// Scale an interval by a scalar factor range: `[k1, k2] * x`.
    #[must_use]
    pub fn scaled(x: &Qty, k1: f64, k2: f64) -> Interval {
        let mag = x.magnitude();
        let a = k1 * mag;
        let b = k2 * mag;
        let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
        Interval {
            lo: lo.next_down(),
            hi: hi.next_up(),
            unit: x.unit().clone(),
        }
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
    pub fn add(&self, other: &Interval) -> Result<Interval, QuantityError> {
        if self.unit.dimension != other.unit.dimension {
            return Err(QuantityError::IncompatibleDimensions {
                left: self.unit.dimension,
                right: other.unit.dimension,
            });
        }
        let other_lo = convert(other.lo, &other.unit, &self.unit);
        let other_hi = convert(other.hi, &other.unit, &self.unit);
        Ok(Interval {
            lo: (self.lo + other_lo).next_down(),
            hi: (self.hi + other_hi).next_up(),
            unit: self.unit.clone(),
        })
    }

    /// Interval difference `[a,b] - [c,d] = [a-d, b-c]`, outward-rounded.
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn sub(&self, other: &Interval) -> Result<Interval, QuantityError> {
        if self.unit.dimension != other.unit.dimension {
            return Err(QuantityError::IncompatibleDimensions {
                left: self.unit.dimension,
                right: other.unit.dimension,
            });
        }
        let other_lo = convert(other.lo, &other.unit, &self.unit);
        let other_hi = convert(other.hi, &other.unit, &self.unit);
        Ok(Interval {
            lo: (self.lo - other_hi).next_down(),
            hi: (self.hi - other_lo).next_up(),
            unit: self.unit.clone(),
        })
    }

    /// Multiply by a scalar interval (dimensionless `[k1,k2]`): the four
    /// products' min/max, outward-rounded.
    #[must_use]
    pub fn mul_scalar_interval(&self, k1: f64, k2: f64) -> Interval {
        let products = [self.lo * k1, self.lo * k2, self.hi * k1, self.hi * k2];
        let lo = products.iter().copied().fold(f64::INFINITY, f64::min);
        let hi = products.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        Interval {
            lo: lo.next_down(),
            hi: hi.next_up(),
            unit: self.unit.clone(),
        }
    }

    /// True when `q` lies within `[lo, hi]` (dimension-checked).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] on dimension mismatch.
    pub fn contains(&self, q: &Qty) -> Result<bool, QuantityError> {
        if self.unit.dimension != q.dimension() {
            return Err(QuantityError::IncompatibleDimensions {
                left: self.unit.dimension,
                right: q.dimension(),
            });
        }
        let mag = convert(q.magnitude(), q.unit(), &self.unit);
        Ok(self.lo <= mag && mag <= self.hi)
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
        fn add_is_monotone_in_containment(a in -100.0f64..100.0, w in 0.0f64..50.0) {
            let x = Interval::new(&metres(a), &metres(a + w)).unwrap();
            let sum = x.add(&x).unwrap();
            // [a,a+w]+[a,a+w] = [2a, 2a+2w] contains 2a
            proptest::prop_assert!(sum.contains(&metres(2.0 * a)).unwrap());
        }
    }

    // AD-6 core safety property: outward rounding must never produce a
    // computed interval that excludes a true real-arithmetic corner
    // value. `add`/`sub` on [a,b]+[c,d] must contain every corner sum
    // (a+c, a+d, b+c, b+d) resp. difference (a-c, a-d, b-c, b-d).
    proptest::proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(256))]

        #[test]
        fn add_contains_all_true_corners(
            a in -1.0e6f64..1.0e6, w1 in 0.0f64..1.0e6,
            c in -1.0e6f64..1.0e6, w2 in 0.0f64..1.0e6,
        ) {
            let b = a + w1;
            let d = c + w2;
            let x = Interval::new(&metres(a), &metres(b)).unwrap();
            let y = Interval::new(&metres(c), &metres(d)).unwrap();
            let sum = x.add(&y).unwrap();
            for corner in [a + c, a + d, b + c, b + d] {
                proptest::prop_assert!(
                    sum.contains(&metres(corner)).unwrap(),
                    "add({a}..{b}, {c}..{d}) = {:?}..{:?} must contain corner {corner}",
                    sum.lo().magnitude(), sum.hi().magnitude(),
                );
            }
        }

        #[test]
        fn sub_contains_all_true_corners(
            a in -1.0e6f64..1.0e6, w1 in 0.0f64..1.0e6,
            c in -1.0e6f64..1.0e6, w2 in 0.0f64..1.0e6,
        ) {
            let b = a + w1;
            let d = c + w2;
            let x = Interval::new(&metres(a), &metres(b)).unwrap();
            let y = Interval::new(&metres(c), &metres(d)).unwrap();
            let diff = x.sub(&y).unwrap();
            for corner in [a - c, a - d, b - c, b - d] {
                proptest::prop_assert!(
                    diff.contains(&metres(corner)).unwrap(),
                    "sub({a}..{b}, {c}..{d}) = {:?}..{:?} must contain corner {corner}",
                    diff.lo().magnitude(), diff.hi().magnitude(),
                );
            }
        }

        #[test]
        fn mul_scalar_interval_contains_all_true_corners(
            a in -1.0e6f64..1.0e6, w in 0.0f64..1.0e6,
            k1 in -1.0e3f64..1.0e3, kw in 0.0f64..1.0e3,
        ) {
            let b = a + w;
            let k2 = k1 + kw;
            let x = Interval::new(&metres(a), &metres(b)).unwrap();
            let product = x.mul_scalar_interval(k1, k2);
            for corner in [a * k1, a * k2, b * k1, b * k2] {
                proptest::prop_assert!(
                    product.contains(&metres(corner)).unwrap(),
                    "mul_scalar_interval({a}..{b}, {k1}..{k2}) = {:?}..{:?} must contain corner {corner}",
                    product.lo().magnitude(), product.hi().magnitude(),
                );
            }
        }

        #[test]
        fn plus_minus_produces_ordered_bounds(center in -1.0e6f64..1.0e6, tol in 0.0f64..1.0e6) {
            let c = metres(center);
            let t = metres(tol);
            let iv = Interval::plus_minus(&c, &t).unwrap();
            proptest::prop_assert!(iv.lo().magnitude() <= iv.hi().magnitude());
        }

        #[test]
        fn plus_minus_percent_produces_ordered_bounds(center in -1.0e6f64..1.0e6, percent in -500.0f64..500.0) {
            let c = metres(center);
            let iv = Interval::plus_minus_percent(&c, percent);
            proptest::prop_assert!(iv.lo().magnitude() <= iv.hi().magnitude());
        }

        #[test]
        fn scaled_produces_ordered_bounds(x in -1.0e6f64..1.0e6, k1 in -1.0e3f64..1.0e3, k2 in -1.0e3f64..1.0e3) {
            let q = metres(x);
            let iv = Interval::scaled(&q, k1, k2);
            proptest::prop_assert!(iv.lo().magnitude() <= iv.hi().magnitude());
        }
    }
}
