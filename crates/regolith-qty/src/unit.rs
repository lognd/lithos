//! Units: a symbol carrying a dimension and an exact conversion to SI
//! base, plus SI-prefix parsing and multiplicative unit algebra.
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 1
//! (ASCII unit spellings: `mm`, `N/m`, `degC`, `ohm`, `bit/s`, `ops`).
//! Scale factors are exact rationals (AD-9) so conversions never drift.

use num_rational::Ratio;
use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::dimension::{Dimension, Exponent};
use crate::BASE_DIMENSIONS;

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

// WO-19 (AD-5 schema surface): same escalated simplification as
// `Dimension`'s manual impl (`Scale = Ratio<i64>` has no upstream
// `JsonSchema`) -- a loose opaque-object schema, not a derive through
// the exact rational representation.
impl schemars::JsonSchema for Unit {
    fn schema_name() -> String {
        "Unit".to_string()
    }

    fn json_schema(_gen: &mut schemars::gen::SchemaGenerator) -> schemars::schema::Schema {
        schemars::schema::Schema::Object(schemars::schema::SchemaObject {
            instance_type: Some(schemars::schema::InstanceType::Object.into()),
            ..Default::default()
        })
    }
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

/// One row of the fixed unit table: symbol, base-dimension exponent
/// vector (numerator only; all denominators are 1 -- the seed units
/// are all integer-exponent), exact scale (num/den), exact offset
/// (num/den).
type UnitRow = (&'static str, [i32; BASE_DIMENSIONS], (i64, i64), (i64, i64));

/// The fixed, unprefixed unit table (substrate/02 sec. 1 seed set):
/// SI base atoms (mass uses `g`, since `kg` arises from the `k` prefix
/// on `g`, the standard SI convention), one offset unit (`degC`), a
/// handful of coherent derived units, and the dimensionless counting
/// units. Exponent order matches [`BaseDimension::all`]: length, mass,
/// time, current, temperature, amount, luminous intensity.
const UNIT_TABLE: &[UnitRow] = &[
    ("m", [1, 0, 0, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("g", [0, 1, 0, 0, 0, 0, 0], (1, 1000), (0, 1)),
    ("s", [0, 0, 1, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("A", [0, 0, 0, 1, 0, 0, 0], (1, 1), (0, 1)),
    ("K", [0, 0, 0, 0, 1, 0, 0], (1, 1), (0, 1)),
    ("mol", [0, 0, 0, 0, 0, 1, 0], (1, 1), (0, 1)),
    ("cd", [0, 0, 0, 0, 0, 0, 1], (1, 1), (0, 1)),
    // Offset unit: Celsius, additive 273.15 K, no prefixing (guarded
    // by `is_offset()` at the call site).
    ("degC", [0, 0, 0, 0, 1, 0, 0], (1, 1), (27315, 100)),
    // Coherent derived units (scale 1 relative to SI base).
    ("N", [1, 1, -2, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("ohm", [2, 1, -3, -2, 0, 0, 0], (1, 1), (0, 1)),
    ("F", [-2, -1, 4, 2, 0, 0, 0], (1, 1), (0, 1)),
    ("V", [2, 1, -3, -1, 0, 0, 0], (1, 1), (0, 1)),
    ("W", [2, 1, -3, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("Hz", [0, 0, -1, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("J", [2, 1, -2, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("Pa", [-1, 1, -2, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("H", [2, 1, -2, -2, 0, 0, 0], (1, 1), (0, 1)),
    ("T", [0, 1, -2, -1, 0, 0, 0], (1, 1), (0, 1)),
    ("S", [-2, -1, 3, 2, 0, 0, 0], (1, 1), (0, 1)),
    // Dimensionless counting/information units.
    ("bit", [0, 0, 0, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("ops", [0, 0, 0, 0, 0, 0, 0], (1, 1), (0, 1)),
    ("1", [0, 0, 0, 0, 0, 0, 0], (1, 1), (0, 1)),
];

/// Look up an unprefixed base-unit symbol in the fixed unit table
/// (substrate/02 sec. 1 seed set). Returns `None` for unknown symbols;
/// callers try SI-prefix stripping before giving up.
fn base_unit(symbol: &str) -> Option<Unit> {
    let (_, exps, scale, offset) = UNIT_TABLE.iter().find(|(name, ..)| *name == symbol)?;
    let mut ratios = [Ratio::from_integer(0); BASE_DIMENSIONS];
    for (slot, exp) in ratios.iter_mut().zip(exps.iter()) {
        *slot = Ratio::from_integer(*exp);
    }
    Some(Unit {
        symbol: symbol.to_string(),
        dimension: Dimension::from_exponents(ratios),
        scale: Scale::new(scale.0, scale.1),
        offset: Scale::new(offset.0, offset.1),
    })
}

/// The exact scale factor of an SI decimal prefix (`k` -> 1000, `u` ->
/// 1/1000000), as a rational so it never drifts (AD-9).
fn prefix_scale(exponent: i32) -> Scale {
    if exponent >= 0 {
        Scale::from_integer(10_i64.pow(u32::try_from(exponent).unwrap_or(0)))
    } else {
        Scale::new(1, 10_i64.pow(u32::try_from(-exponent).unwrap_or(0)))
    }
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
    pub fn parse_atom(symbol: &str) -> Result<Unit, UnitError> {
        // Trailing integer exponent suffix (`m2`, `s2`, `mm3`): the atom
        // is its base symbol raised to that integer power (AD-9 rational
        // exponents), so spec units like `W/m2` and `kg/s2` are
        // expressible (FE-4). Stripped first; the base symbol (no
        // trailing digit) re-enters this function on the non-exponent
        // path, so there is no unbounded recursion. Offset units (`degC`)
        // have no power algebra, mirroring `mul`/`div`'s guard.
        let base_sym = symbol.trim_end_matches(|c: char| c.is_ascii_digit());
        if base_sym.len() < symbol.len() && !base_sym.is_empty() {
            if let Ok(exp) = symbol[base_sym.len()..].parse::<i32>() {
                let base = Unit::parse_atom(base_sym)?;
                if base.is_offset() {
                    return Err(UnitError::OffsetInAlgebra(symbol.to_string()));
                }
                return Ok(Unit {
                    symbol: symbol.to_string(),
                    dimension: base.dimension.pow(Exponent::from_integer(exp)),
                    scale: base.scale.pow(exp),
                    offset: Scale::from_integer(0),
                });
            }
        }
        // An unprefixed match wins outright (covers bare atoms and the
        // rare case where a prefix letter is also a full unit symbol).
        if let Some(base) = base_unit(symbol) {
            return Ok(Unit {
                symbol: symbol.to_string(),
                ..base
            });
        }
        // Try stripping a 2-letter prefix (`da`) then a 1-letter prefix,
        // longest first so `da` is not mistaken for `d` + `a...`.
        for prefix_len in [2usize, 1usize] {
            if symbol.len() <= prefix_len {
                continue;
            }
            let (prefix, rest) = symbol.split_at(prefix_len);
            let Some(exponent) = si_prefix_exponent(prefix) else {
                continue;
            };
            let Some(base) = base_unit(rest) else {
                continue;
            };
            if base.is_offset() {
                return Err(UnitError::PrefixNotAllowed(symbol.to_string()));
            }
            return Ok(Unit {
                symbol: symbol.to_string(),
                dimension: base.dimension,
                scale: base.scale * prefix_scale(exponent),
                offset: base.offset,
            });
        }
        Err(UnitError::UnknownSymbol(symbol.to_string()))
    }

    /// Parse a full multiplicative unit expression (`N/m`, `bit/s`,
    /// `W/m2`, `kg/s2`). Each side is a single atom, which may carry a
    /// trailing integer exponent (`m2`, `s2`); the dimension and scale
    /// are derived from the atoms. Multi-operator expressions
    /// (`kg.m/s2`) remain the WO-05 full-grammar hook.
    ///
    /// # Errors
    /// Returns [`UnitError`] on any unknown atom or misuse of offset
    /// units in algebra.
    pub fn parse_expr(expr: &str) -> Result<Unit, UnitError> {
        // WO-02 scope: at most one binary operator (`/` or `.`); the
        // full precedence/parenthesized grammar is the WO-05 hook.
        if let Some(idx) = expr.find('/') {
            let lhs = Unit::parse_atom(&expr[..idx])?;
            let rhs = Unit::parse_atom(&expr[idx + 1..])?;
            return lhs.div(&rhs);
        }
        if let Some(idx) = expr.find('.') {
            let lhs = Unit::parse_atom(&expr[..idx])?;
            let rhs = Unit::parse_atom(&expr[idx + 1..])?;
            return lhs.mul(&rhs);
        }
        Unit::parse_atom(expr)
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
    use super::{base_unit, si_prefix_exponent, Unit, UnitError};
    use crate::dimension::{BaseDimension, Dimension, Exponent};
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
    fn parses_prefixed_atoms() {
        assert_eq!(
            Unit::parse_atom("kN").unwrap().scale,
            Ratio::from_integer(1000)
        );
        assert!(Unit::parse_atom("uF").is_ok());
        assert!(Unit::parse_atom("mohm").is_ok());
    }

    #[test]
    fn parses_electrical_and_derived_units() {
        // The corpus (.cupr electrical content) uses these; each must
        // resolve with the right dimension so `1V + 1A` is a genuine
        // dimension mismatch rather than an unknown-unit condition.
        for sym in [
            "V", "W", "Hz", "MHz", "kHz", "mW", "uH", "MPa", "J", "T", "S",
        ] {
            assert!(Unit::parse_atom(sym).is_ok(), "{sym} should parse");
        }
        assert_ne!(
            Unit::parse_atom("V").unwrap().dimension,
            Unit::parse_atom("A").unwrap().dimension,
            "volt and ampere must differ in dimension"
        );
    }

    #[test]
    fn parses_unit_exponent_suffixes() {
        // FE-4: a trailing integer exponent makes area/rate units like
        // `W/m2` and `kg/s2` expressible (substrate/02 sec. 1 heat_flux).
        let m2 = Unit::parse_atom("m2").expect("m2 parses");
        assert_eq!(
            m2.dimension,
            metre().dimension.pow(Exponent::from_integer(2)),
            "m2 is length squared"
        );
        let heat_flux = Unit::parse_expr("W/m2").expect("W/m2 parses");
        assert_eq!(
            heat_flux.dimension,
            Unit::parse_atom("W").unwrap().dimension.div(&m2.dimension),
            "W/m2 is power per area"
        );
        let kg_per_s2 = Unit::parse_expr("kg/s2").expect("kg/s2 parses");
        assert_eq!(
            kg_per_s2.dimension,
            Unit::parse_atom("kg")
                .unwrap()
                .dimension
                .div(&Unit::parse_atom("s2").unwrap().dimension),
            "kg/s2 is mass per time squared"
        );
        // A prefixed base still exponentiates (`mm2` = milli-metre area).
        assert!(Unit::parse_atom("mm2").is_ok());
        // An exponent on an offset unit has no power algebra.
        assert!(matches!(
            Unit::parse_atom("degC2"),
            Err(UnitError::OffsetInAlgebra(_))
        ));
    }

    // The fixed multiplicative (non-offset) atomic base-unit symbols
    // eligible for the round-trip/algebra properties below. `degC` is
    // excluded (offset units reject multiplicative algebra by design).
    const MULTIPLICATIVE_BASE_SYMBOLS: &[&str] = &[
        "m", "g", "s", "A", "K", "mol", "cd", "N", "ohm", "F", "V", "W", "Hz", "J", "Pa", "H", "T",
        "S", "bit", "ops", "1",
    ];

    proptest::proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(256))]

        // parse_atom on any known base-unit symbol succeeds and always
        // reports the same dimension as a direct lookup (no drift
        // between the parse path and the table).
        #[test]
        fn parse_atom_round_trips_dimension(idx in 0usize..MULTIPLICATIVE_BASE_SYMBOLS.len()) {
            let sym = MULTIPLICATIVE_BASE_SYMBOLS[idx];
            let parsed = Unit::parse_atom(sym).unwrap();
            let looked_up = base_unit(sym).unwrap();
            proptest::prop_assert_eq!(parsed.dimension, looked_up.dimension);
        }

        // (unit * other) / other returns to the original unit's dimension:
        // the multiplicative algebra is closed and self-inverse on
        // dimension, for any pair of non-offset base units.
        #[test]
        fn mul_then_div_returns_to_original_dimension(
            i in 0usize..MULTIPLICATIVE_BASE_SYMBOLS.len(),
            j in 0usize..MULTIPLICATIVE_BASE_SYMBOLS.len(),
        ) {
            let a = Unit::parse_atom(MULTIPLICATIVE_BASE_SYMBOLS[i]).unwrap();
            let b = Unit::parse_atom(MULTIPLICATIVE_BASE_SYMBOLS[j]).unwrap();
            let product = a.mul(&b).unwrap();
            let back = product.div(&b).unwrap();
            proptest::prop_assert_eq!(back.dimension, a.dimension);
        }
    }
}
