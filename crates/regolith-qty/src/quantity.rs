//! `Qty`: a continuous physical quantity value (magnitude x unit) with
//! dimension-checked arithmetic.
//!
//! Regolith reference: `docs/spec/regolith/02-quantity-core.md` sec. 1-2.
//! The equality ban (sec. 2) is enforced structurally: `Qty` has NO
//! `PartialEq`. Comparisons go through explicit tolerance forms
//! (`within`, `equal_within`); the parser rejects `==` on continuous
//! quantities (WO-05 hook). Arithmetic between incompatible dimensions
//! is an error VALUE carrying both dimensions, never an exception.

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::dimension::Dimension;
use crate::unit::{ratio_to_f64, Unit, UnitError};

/// A continuous quantity: a magnitude in a given unit.
///
/// Deliberately NOT `PartialEq`/`Eq` (regolith/02 sec. 2 equality
/// ban). Deriving equality here would reintroduce the exact-float
/// comparison the language forbids; use tolerance forms instead.
#[derive(Debug, Clone, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-qty.md#quantity
pub struct Qty {
    magnitude: f64,
    unit: Unit,
}

// WO-19 (AD-5 schema surface): manual impl mirroring the derive-default
// serde shape (`{"magnitude": <number>, "unit": <Unit>}`); see `Unit`'s
// manual impl for why this crate hand-writes rather than derives.
impl schemars::JsonSchema for Qty {
    fn schema_name() -> String {
        "Qty".to_string()
    }

    fn json_schema(gen: &mut schemars::gen::SchemaGenerator) -> schemars::schema::Schema {
        let mut props = schemars::Map::new();
        props.insert("magnitude".to_string(), gen.subschema_for::<f64>());
        props.insert("unit".to_string(), gen.subschema_for::<Unit>());
        schemars::schema::Schema::Object(schemars::schema::SchemaObject {
            instance_type: Some(schemars::schema::InstanceType::Object.into()),
            object: Some(Box::new(schemars::schema::ObjectValidation {
                properties: props,
                required: ["magnitude".to_string(), "unit".to_string()]
                    .into_iter()
                    .collect(),
                ..Default::default()
            })),
            ..Default::default()
        })
    }
}

/// Failure performing quantity arithmetic. An error VALUE (AD-7): the
/// caller in `regolith-sem` turns it into a diagnostic; it is never a
/// panic or bare exception.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
// frob:doc docs/modules/regolith-qty.md#quantity
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
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn new(magnitude: f64, unit: Unit) -> Qty {
        Qty { magnitude, unit }
    }

    /// The raw magnitude in this quantity's own unit.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn magnitude(&self) -> f64 {
        self.magnitude
    }

    /// This quantity's unit.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn unit(&self) -> &Unit {
        &self.unit
    }

    /// The quantity's physical dimension.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn dimension(&self) -> Dimension {
        self.unit.dimension
    }

    /// Add two quantities. Legal only at equal dimension; the result is
    /// expressed in `self`'s unit (`other` is converted to SI base then
    /// into `self`'s unit).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] when dimensions differ.
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn add(&self, other: &Qty) -> Result<Qty, QuantityError> {
        if self.dimension() != other.dimension() {
            return Err(QuantityError::IncompatibleDimensions {
                left: self.dimension(),
                right: other.dimension(),
            });
        }
        let converted = convert(other.magnitude, &other.unit, &self.unit);
        Ok(Qty::new(self.magnitude + converted, self.unit.clone()))
    }

    /// Subtract two quantities (same rule as [`Qty::add`]).
    ///
    /// # Errors
    /// [`QuantityError::IncompatibleDimensions`] when dimensions differ.
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn sub(&self, other: &Qty) -> Result<Qty, QuantityError> {
        if self.dimension() != other.dimension() {
            return Err(QuantityError::IncompatibleDimensions {
                left: self.dimension(),
                right: other.dimension(),
            });
        }
        let converted = convert(other.magnitude, &other.unit, &self.unit);
        Ok(Qty::new(self.magnitude - converted, self.unit.clone()))
    }

    /// Multiply two quantities: magnitudes multiply, units compose.
    /// Always dimensionally legal.
    ///
    /// # Errors
    /// [`QuantityError::Unit`] if the unit algebra rejects the operands
    /// (offset units).
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn mul(&self, other: &Qty) -> Result<Qty, QuantityError> {
        let unit = self.unit.mul(&other.unit)?;
        Ok(Qty::new(self.magnitude * other.magnitude, unit))
    }

    /// Divide two quantities: magnitudes divide, units compose.
    ///
    /// # Errors
    /// [`QuantityError::Unit`] if the unit algebra rejects the operands.
    // frob:doc docs/modules/regolith-qty.md#quantity
    pub fn div(&self, other: &Qty) -> Result<Qty, QuantityError> {
        let unit = self.unit.div(&other.unit)?;
        Ok(Qty::new(self.magnitude / other.magnitude, unit))
    }
}

/// Convert `magnitude` (given in `from`) into the equivalent magnitude
/// expressed in `to`, via each unit's exact scale/offset to SI base.
/// Callers guard dimension compatibility before calling this.
// frob:doc docs/modules/regolith-qty.md#quantity
pub(crate) fn convert(magnitude: f64, from: &Unit, to: &Unit) -> f64 {
    let from_scale = ratio_to_f64(from.scale);
    let from_offset = ratio_to_f64(from.offset);
    let to_scale = ratio_to_f64(to.scale);
    let to_offset = ratio_to_f64(to.offset);
    let si = magnitude * from_scale + from_offset;
    (si - to_offset) / to_scale
}

/// Convert a DELTA (a difference/tolerance, not an absolute position)
/// from `from` into `to`, using scale only -- the additive offset of an
/// offset unit (`degC`) does NOT apply to a difference (a 5 degC
/// tolerance is 5 K-degrees, never 278.15). Use this, not [`convert`],
/// whenever the magnitude is a span rather than a point (FE-5).
// frob:doc docs/modules/regolith-qty.md#quantity
pub(crate) fn convert_delta(magnitude: f64, from: &Unit, to: &Unit) -> f64 {
    let from_scale = ratio_to_f64(from.scale);
    let to_scale = ratio_to_f64(to.scale);
    magnitude * from_scale / to_scale
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

    // frob:tests crates/regolith-qty/src/quantity.rs::Qty.add kind="unit"
    #[test]
    fn incompatible_add_is_error_value() {
        let result = volt().add(&amp());
        match result {
            Err(QuantityError::IncompatibleDimensions { left, right }) => {
                assert_ne!(left, right);
            }
            _ => panic!("expected IncompatibleDimensions error value"),
        }
    }

    // frob:tests crates/regolith-qty/src/quantity.rs::Qty.sub kind="unit"
    // frob:tests crates/regolith-qty/src/quantity.rs::Qty.mul kind="unit"
    // frob:tests crates/regolith-qty/src/quantity.rs::Qty.div kind="unit"
    #[test]
    fn arithmetic_ops_compute_expected_magnitudes() {
        let ten = Qty::new(10.0, unit("V", Dimension::base(BaseDimension::Current)));
        let three = Qty::new(3.0, unit("V", Dimension::base(BaseDimension::Current)));

        let sum = ten.sub(&three).expect("same-dimension sub must be legal");
        assert!((sum.magnitude() - 7.0).abs() < f64::EPSILON);

        // mul/div compose units unconditionally (always dimensionally
        // legal); magnitudes multiply/divide.
        let product = ten.mul(&three).expect("mul is always dimension-legal");
        assert!((product.magnitude() - 30.0).abs() < f64::EPSILON);

        let quotient = ten.div(&three).expect("div is always dimension-legal");
        assert!((quotient.magnitude() - 10.0 / 3.0).abs() < 1e-12);
    }

    // frob:tests crates/regolith-qty/src/quantity.rs::convert_delta kind="unit"
    #[test]
    fn convert_delta_ignores_offset_unlike_convert() {
        use super::{convert, convert_delta};
        // degC has a nonzero SI offset (273.15); a DELTA must not see
        // it, while an absolute `convert` of the same magnitude does.
        let degc = Unit {
            symbol: "degC".to_string(),
            dimension: Dimension::dimensionless(),
            scale: Ratio::from_integer(1),
            offset: Ratio::new(27315, 100),
        };
        let kelvin = unit("K", Dimension::dimensionless());
        let delta = convert_delta(5.0, &degc, &kelvin);
        assert!(
            (delta - 5.0).abs() < f64::EPSILON,
            "a 5 degC span is 5 K-degrees"
        );

        let absolute = convert(5.0, &degc, &kelvin);
        assert!(
            (delta - absolute).abs() > f64::EPSILON,
            "convert (absolute) must differ from convert_delta"
        );
    }
}
