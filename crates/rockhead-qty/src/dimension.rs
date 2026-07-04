//! Physical dimensions: the fixed vector of seven SI base-dimension
//! exponents (AD-9 -- rational exponents, not integer).
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 1.
//! Dimensional analysis runs at parse time; arithmetic between
//! incompatible dimensions is an error, never a solver input.

use num_rational::Ratio;
use serde::{Deserialize, Serialize};

use crate::BASE_DIMENSIONS;

/// A base-dimension exponent. Rational (AD-9): noise density
/// (`nV/sqrt(Hz)`) is genuine half-integer territory the elec track
/// needs, so integer exponents are insufficient.
pub type Exponent = Ratio<i32>;

/// The seven SI base dimensions, in the fixed order used by the
/// exponent vector. Index order is normative: it is the serialization
/// order and the hash input order (AD-6).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BaseDimension {
    /// Length (metre).
    Length,
    /// Mass (kilogram).
    Mass,
    /// Time (second).
    Time,
    /// Electric current (ampere).
    Current,
    /// Thermodynamic temperature (kelvin).
    Temperature,
    /// Amount of substance (mole).
    Amount,
    /// Luminous intensity (candela).
    LuminousIntensity,
}

impl BaseDimension {
    /// The fixed-order list of all base dimensions; index equals the
    /// exponent-vector slot.
    #[must_use]
    pub const fn all() -> [BaseDimension; BASE_DIMENSIONS] {
        [
            BaseDimension::Length,
            BaseDimension::Mass,
            BaseDimension::Time,
            BaseDimension::Current,
            BaseDimension::Temperature,
            BaseDimension::Amount,
            BaseDimension::LuminousIntensity,
        ]
    }

    /// This dimension's slot in the exponent vector.
    #[must_use]
    pub const fn index(self) -> usize {
        self as usize
    }
}

/// An immutable dimension value: the exponent of each base dimension.
/// `Eq` is intentional -- dimensions are discrete and exactly
/// comparable (the `==` ban is on continuous *quantities*, not on
/// dimensions).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Dimension {
    exps: [Exponent; BASE_DIMENSIONS],
}

impl Dimension {
    /// The dimensionless dimension (all exponents zero): ratios, counts,
    /// gains, plain numbers.
    #[must_use]
    pub fn dimensionless() -> Self {
        Dimension {
            exps: [Ratio::from_integer(0); BASE_DIMENSIONS],
        }
    }

    /// The unit dimension of a single base (exponent one, rest zero).
    #[must_use]
    pub fn base(base: BaseDimension) -> Self {
        let mut exps = [Ratio::from_integer(0); BASE_DIMENSIONS];
        exps[base.index()] = Ratio::from_integer(1);
        Dimension { exps }
    }

    /// Construct directly from an exponent vector (base-dimension order).
    #[must_use]
    pub fn from_exponents(exps: [Exponent; BASE_DIMENSIONS]) -> Self {
        Dimension { exps }
    }

    /// The exponent of `base` in this dimension.
    #[must_use]
    pub fn exponent(&self, base: BaseDimension) -> Exponent {
        self.exps[base.index()]
    }

    /// True when every base exponent is zero.
    #[must_use]
    pub fn is_dimensionless(&self) -> bool {
        self.exps.iter().all(|e| *e == Ratio::from_integer(0))
    }

    /// Product of two dimensions: exponents add (`N/m * m` -> `N`).
    #[must_use]
    pub fn mul(&self, other: &Dimension) -> Dimension {
        let mut exps = self.exps;
        for (slot, rhs) in exps.iter_mut().zip(other.exps.iter()) {
            *slot += *rhs;
        }
        Dimension { exps }
    }

    /// Quotient of two dimensions: exponents subtract.
    #[must_use]
    pub fn div(&self, other: &Dimension) -> Dimension {
        let mut exps = self.exps;
        for (slot, rhs) in exps.iter_mut().zip(other.exps.iter()) {
            *slot -= *rhs;
        }
        Dimension { exps }
    }

    /// This dimension raised to a rational power (exponents scale).
    #[must_use]
    pub fn pow(&self, power: Exponent) -> Dimension {
        let mut exps = self.exps;
        for slot in &mut exps {
            *slot *= power;
        }
        Dimension { exps }
    }
}

#[cfg(test)]
mod tests {
    use super::{BaseDimension, Dimension, Exponent};
    use num_rational::Ratio;

    fn length() -> Dimension {
        Dimension::base(BaseDimension::Length)
    }
    fn force() -> Dimension {
        // kg . m . s^-2
        Dimension::from_exponents([
            Ratio::from_integer(1),
            Ratio::from_integer(1),
            Ratio::from_integer(-2),
            Ratio::from_integer(0),
            Ratio::from_integer(0),
            Ratio::from_integer(0),
            Ratio::from_integer(0),
        ])
    }

    #[test]
    fn dimensionless_is_all_zero() {
        assert!(Dimension::dimensionless().is_dimensionless());
        assert!(!length().is_dimensionless());
    }

    #[test]
    fn stiffness_times_length_is_force() {
        // stiffness N/m = force / length; (N/m) * m == N
        let stiffness = force().div(&length());
        assert_eq!(stiffness.mul(&length()), force());
    }

    #[test]
    fn div_then_mul_round_trips() {
        assert_eq!(force().div(&length()).mul(&length()), force());
    }

    #[test]
    fn pow_scales_exponents() {
        let area = length().pow(Ratio::from_integer(2));
        assert_eq!(area.exponent(BaseDimension::Length), Ratio::from_integer(2));
    }

    #[test]
    fn rational_exponent_survives_round_trip() {
        // sqrt(Hz) = time^-1/2 dimension component
        let root_hz = Dimension::base(BaseDimension::Time).pow(Ratio::new(-1, 2));
        let json = serde_json::to_string(&root_hz).unwrap();
        let back: Dimension = serde_json::from_str(&json).unwrap();
        assert_eq!(root_hz, back);
        assert_eq!(back.exponent(BaseDimension::Time), Exponent::new(-1, 2));
    }
}
