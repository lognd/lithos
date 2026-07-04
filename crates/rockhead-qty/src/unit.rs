//! Units: a symbol carrying a dimension and an exact conversion to SI
//! base, plus SI-prefix parsing and multiplicative unit algebra.
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 1
//! (ASCII unit spellings: `mm`, `N/m`, `degC`, `ohm`, `bit/s`, `ops`).
//! Scale factors are exact rationals (AD-9) so conversions never drift.

use num_rational::Ratio;
use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::dimension::Dimension;

/// An exact conversion factor to SI base units. Rational so unit
/// algebra is closed and drift-free (AD-9).
pub type Scale = Ratio<i64>;

/// A unit: an ASCII symbol, its dimension, its exact scale to SI base,
/// and an additive offset (nonzero only for offset temperatures such
/// as `degC`). A value in this unit is `magnitude * scale + offset` in
/// SI base.
///
/// Continuous `Unit`s carry no `PartialEq` on magnitude; `Unit` itself
/// is comparable because a unit is a discrete descriptor, not a
/// continuous quantity (the `==` ban lives on `Qty`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Unit {
    /// ASCII spelling as written in source (`mm`, `N/m`, `degC`).
    pub symbol: String,
    /// The physical dimension this unit measures.
    pub dimension: Dimension,
    /// Exact multiplicative factor to SI base units.
    pub scale: Scale,
    /// Additive offset to SI base (zero for all multiplicative units;
    /// `273.15` for `degC`). Offset units may only be used where the
    /// spec permits absolute temperatures.
    pub offset: Scale,
}

/// Failure parsing or composing a unit expression.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum UnitError {
    /// The base-unit symbol (after stripping any SI prefix) is not in
    /// the unit table.
    #[error("unknown unit symbol: `{0}`")]
    UnknownSymbol(String),
    /// An SI prefix was applied to a unit that forbids prefixing (for
    /// example an offset unit such as `degC`).
    #[error("unit `{0}` may not take an SI prefix")]
    PrefixNotAllowed(String),
    /// Composing offset units multiplicatively is meaningless.
    #[error("offset unit `{0}` has no multiplicative algebra")]
    OffsetInAlgebra(String),
}

impl Unit {
    /// A dimensionless unit of unit scale (a pure number / ratio).
    #[must_use]
    pub fn dimensionless() -> Unit {
        Unit {
            symbol: "1".to_string(),
            dimension: Dimension::dimensionless(),
            scale: Scale::from_integer(1),
            offset: Scale::from_integer(0),
        }
    }

    /// True when this unit has a nonzero additive offset (`degC`).
    #[must_use]
    pub fn is_offset(&self) -> bool {
        self.offset != Scale::from_integer(0)
    }

    /// Parse a possibly-prefixed atomic unit symbol (`kN`, `uF`,
    /// `mohm`, `mm`). Compound expressions (`N/m`, `bit/s`) are parsed
    /// by [`Unit::parse_expr`].
    ///
    /// # Errors
    /// Returns [`UnitError`] when the symbol is unknown or an offset
    /// unit is prefixed.
    pub fn parse_atom(_symbol: &str) -> Result<Unit, UnitError> {
        todo!("WO-02: SI-prefix split + unit-table lookup")
    }

    /// Parse a full multiplicative unit expression (`N/m`, `bit/s`,
    /// `kg.m/s2`). The dimension and scale are derived from the atoms.
    ///
    /// # Errors
    /// Returns [`UnitError`] on any unknown atom or misuse of offset
    /// units in algebra.
    pub fn parse_expr(_expr: &str) -> Result<Unit, UnitError> {
        todo!("WO-05 hook: full expression grammar; WO-02 does the atom + one operator")
    }

    /// Multiplicative product of two units (dimensions multiply, scales
    /// multiply, symbols compose).
    ///
    /// # Errors
    /// Returns [`UnitError::OffsetInAlgebra`] if either operand is an
    /// offset unit.
    pub fn mul(&self, other: &Unit) -> Result<Unit, UnitError> {
        if self.is_offset() {
            return Err(UnitError::OffsetInAlgebra(self.symbol.clone()));
        }
        if other.is_offset() {
            return Err(UnitError::OffsetInAlgebra(other.symbol.clone()));
        }
        Ok(Unit {
            symbol: format!("{}.{}", self.symbol, other.symbol),
            dimension: self.dimension.mul(&other.dimension),
            scale: self.scale * other.scale,
            offset: Scale::from_integer(0),
        })
    }

    /// Multiplicative quotient of two units.
    ///
    /// # Errors
    /// Returns [`UnitError::OffsetInAlgebra`] if either operand is an
    /// offset unit.
    pub fn div(&self, other: &Unit) -> Result<Unit, UnitError> {
        if self.is_offset() {
            return Err(UnitError::OffsetInAlgebra(self.symbol.clone()));
        }
        if other.is_offset() {
            return Err(UnitError::OffsetInAlgebra(other.symbol.clone()));
        }
        Ok(Unit {
            symbol: format!("{}/{}", self.symbol, other.symbol),
            dimension: self.dimension.div(&other.dimension),
            scale: self.scale / other.scale,
            offset: Scale::from_integer(0),
        })
    }
}

/// The SI decimal prefix table (symbol -> power-of-ten exponent).
/// ASCII spellings only: `u` is micro (no Greek), per the spec's
/// ASCII-only rule.
#[must_use]
pub fn si_prefix_exponent(prefix: &str) -> Option<i32> {
    let exp = match prefix {
        "T" => 12,
        "G" => 9,
        "M" => 6,
        "k" => 3,
        "h" => 2,
        "da" => 1,
        "d" => -1,
        "c" => -2,
        "m" => -3,
        "u" => -6,
        "n" => -9,
        "p" => -12,
        "f" => -15,
        _ => return None,
    };
    Some(exp)
}

#[cfg(test)]
mod tests {
    use super::{si_prefix_exponent, Unit, UnitError};
    use crate::dimension::{BaseDimension, Dimension};
    use num_rational::Ratio;

    fn newton() -> Unit {
        Unit {
            symbol: "N".to_string(),
            dimension: Dimension::from_exponents([
                Ratio::from_integer(1),
                Ratio::from_integer(1),
                Ratio::from_integer(-2),
                Ratio::from_integer(0),
                Ratio::from_integer(0),
                Ratio::from_integer(0),
                Ratio::from_integer(0),
            ]),
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        }
    }
    fn metre() -> Unit {
        Unit {
            symbol: "m".to_string(),
            dimension: Dimension::base(BaseDimension::Length),
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        }
    }
    fn deg_c() -> Unit {
        Unit {
            symbol: "degC".to_string(),
            dimension: Dimension::base(BaseDimension::Temperature),
            scale: Ratio::from_integer(1),
            offset: Ratio::new(27315, 100),
        }
    }

    #[test]
    fn prefixes_are_ascii_powers_of_ten() {
        assert_eq!(si_prefix_exponent("k"), Some(3));
        assert_eq!(si_prefix_exponent("u"), Some(-6));
        assert_eq!(si_prefix_exponent("m"), Some(-3));
        assert_eq!(si_prefix_exponent("x"), None);
    }

    #[test]
    fn newton_per_metre_has_stiffness_dimension() {
        let stiffness = newton().div(&metre()).unwrap();
        // (N/m) * m == N dimension
        let back = stiffness.mul(&metre()).unwrap();
        assert_eq!(back.dimension, newton().dimension);
    }

    #[test]
    fn offset_units_reject_algebra() {
        assert_eq!(
            deg_c().mul(&metre()),
            Err(UnitError::OffsetInAlgebra("degC".to_string()))
        );
        assert!(deg_c().is_offset());
        assert!(!newton().is_offset());
    }

    #[test]
    fn unit_round_trips_json() {
        let n = newton();
        let json = serde_json::to_string(&n).unwrap();
        let back: Unit = serde_json::from_str(&json).unwrap();
        assert_eq!(n, back);
    }

    #[test]
    #[ignore = "WO-02 impl: prefix parsing pending todo!() body"]
    fn parses_prefixed_atoms() {
        assert_eq!(Unit::parse_atom("kN").unwrap().scale, Ratio::from_integer(1000));
        assert!(Unit::parse_atom("uF").is_ok());
        assert!(Unit::parse_atom("mohm").is_ok());
    }
}
