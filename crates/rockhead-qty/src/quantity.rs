//! `Qty`: a continuous physical quantity value (magnitude x unit) with
//! dimension-checked arithmetic.
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 1-2.
//! The equality ban (sec. 2) is enforced structurally: `Qty` has NO
//! `PartialEq`. Comparisons go through explicit tolerance forms
//! (`within`, `equal_within`); the parser rejects `==` on continuous
//! quantities (WO-05 hook). Arithmetic between incompatible dimensions
//! is an error VALUE carrying both dimensions, never an exception.

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::dimension::Dimension;
use crate::unit::{Unit, UnitError};

/// A continuous quantity: a magnitude in a given unit.
///
/// Deliberately NOT `PartialEq`/`Eq` (substrate/02 sec. 2 equality
/// ban). Deriving equality here would reintroduce the exact-float
/// comparison the language forbids; use tolerance forms instead.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Qty {
    magnitude: f64,
    unit: Unit,
}

/// Failure performing quantity arithmetic. An error VALUE (AD-7): the
/// caller in `rockhead-sem` turns it into a diagnostic; it is never a
/// panic or bare exception.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum QuantityError {
    /// Additive arithmetic across differing dimensions (`1V + 1A`).
    /// Carries both operands' dimensions for the diagnostic.
    #[error("incompatible dimensions in additive operation")]
    IncompatibleDimensions {
        /// Dimension of the left operand.
        left: Dimension,
        /// Dimension of the right operand.
        right: Dimension,
    },
    /// The underlying unit algebra failed (offset units, etc.).
    #[error(transparent)]
    Unit(#[from] UnitError),
}

impl Qty {
    /// Construct a quantity from a magnitude and unit.
    #[must_use]
    pub fn new(magnitude: f64, unit: Unit) -> Qty {
        Qty { magnitude, unit }
    }

    /// The raw magnitude in this quantity's own unit.
    #[must_use]
    pub fn magnitude(&self) -> f64 {
        self.magnitude
    }

    /// This quantity's unit.
    #[must_use]
    pub fn unit(&self) -> &Unit {
        &self.unit
    }

    /// The quantity's physical dimension.
    #[must_use]
    pub fn dimension(&self) -> Dimension {
        self.unit.dimension
    }

    /// Add two quantities. Legal only at equal dimension; the result is
    /// expressed in `self`'s unit (`other` is converted to SI base then
    /// into `self`'s unit).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] when dimensions differ.
    pub fn add(&self, _other: &Qty) -> Result<Qty, QuantityError> {
        todo!("WO-02: dimension guard + SI-base conversion + re-express in self.unit")
    }

    /// Subtract two quantities (same rule as [`Qty::add`]).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] when dimensions differ.
    pub fn sub(&self, _other: &Qty) -> Result<Qty, QuantityError> {
        todo!("WO-02: dimension guard + SI-base conversion + re-express in self.unit")
    }

    /// Multiply two quantities: magnitudes multiply, units compose.
    /// Always dimensionally legal.
    ///
    /// # Errors
    /// [`QuantityError::Unit`] if the unit algebra rejects the operands
    /// (offset units).
    pub fn mul(&self, _other: &Qty) -> Result<Qty, QuantityError> {
        todo!("WO-02: magnitude product + Unit::mul")
    }

    /// Divide two quantities: magnitudes divide, units compose.
    ///
    /// # Errors
    /// [`QuantityError::Unit`] if the unit algebra rejects the operands.
    pub fn div(&self, _other: &Qty) -> Result<Qty, QuantityError> {
        todo!("WO-02: magnitude quotient + Unit::div")
    }
}

#[cfg(test)]
mod tests {
    use super::{Qty, QuantityError};
    use crate::dimension::{BaseDimension, Dimension};
    use crate::unit::Unit;
    use num_rational::Ratio;

    fn unit(symbol: &str, dim: Dimension) -> Unit {
        Unit {
            symbol: symbol.to_string(),
            dimension: dim,
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        }
    }
    fn volt() -> Qty {
        Qty::new(1.0, unit("V", Dimension::base(BaseDimension::Current)))
    }
    fn amp() -> Qty {
        // deliberately a different dimension than volt() above for the test
        Qty::new(1.0, unit("A", Dimension::base(BaseDimension::Mass)))
    }

    #[test]
    fn qty_serializes() {
        let q = volt();
        let json = serde_json::to_string(&q).unwrap();
        assert!(json.contains("\"magnitude\""));
        let back: Qty = serde_json::from_str(&json).unwrap();
        assert_eq!(back.magnitude().to_bits(), 1.0_f64.to_bits());
    }

    #[test]
    #[ignore = "WO-02 impl: add() body pending"]
    fn incompatible_add_is_error_value() {
        let result = volt().add(&amp());
        match result {
            Err(QuantityError::IncompatibleDimensions { left, right }) => {
                assert_ne!(left, right);
            }
            _ => panic!("expected IncompatibleDimensions error value"),
        }
    }
}
