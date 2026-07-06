//! Logarithmic unit views (`dB`, `dBm`, `dBi`, `dBc`, ...): decibel
//! spellings that VIEW an underlying linear quantity.
//!
//! Regolith reference: `docs/regolith/02-quantity-core.md` sec. 5a
//! (SETTLED, closes SOPEN-5) and INV-17 (regolith/13). Log units are
//! views of linear quantities: the stored, solved, and cached value is
//! always LINEAR; a `dB`-family unit only affects parsing/printing plus
//! ONE extra L1 legality check. Because the view is strictly monotone,
//! interval corners commute with it -- corner discipline and margin math
//! run in linear space untouched.
//!
//! The one legality rule (sec. 5a): **sum legality == linear product
//! legality**. A sum of log terms is legal iff, after cancelling
//! subtracted references against added ones, at most one referenced term
//! remains. `dBm + dBi - dB` is a power; `dBm + dBm` is a compile error
//! (the linear product mW^2 is not a power) -- the classic link-budget
//! bug, dead at L1. An uncancelled *subtracted* reference (an inverse
//! dimension) is likewise rejected.

use thiserror::Error;

use crate::dimension::Dimension;
use crate::unit::Unit;

/// The additive sign a log term carries in a sum-of-logs expression.
/// A subtracted term inverts the corresponding linear factor.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sign {
    /// An added term (`+`): its linear factor multiplies.
    Add,
    /// A subtracted term (`-`): its linear factor divides (inverse).
    Sub,
}

impl Sign {
    /// Flip the sign (a `-` distributes onto the right operand of a
    /// subtraction when a `+`/`-` chain is flattened).
    #[must_use]
    pub fn flip(self) -> Sign {
        match self {
            Sign::Add => Sign::Sub,
            Sign::Sub => Sign::Add,
        }
    }
}

/// A logarithmic unit view: a decibel spelling, the linear-domain factor
/// (`10` for power/energy ratios, `20` for field/amplitude ratios), and
/// an optional reference. Unreferenced views (`dB`/`dBc`/`dBi`) view a
/// dimensionless ratio; referenced views (`dBm`/`dBW`/`dBuV`) view a
/// quantity of the reference's dimension.
#[derive(Debug, Clone, PartialEq)]
pub struct LogUnit {
    /// ASCII spelling as written in source (`dB`, `dBm`, `dBuV`).
    pub symbol: String,
    /// Linear-domain factor: `x_dB = factor * log10(linear / reference)`.
    pub factor: i32,
    /// The reference quantity for a referenced view (`dBm` -> `mW`), or
    /// `None` for an unreferenced ratio view (`dB`/`dBc`/`dBi`).
    pub reference: Option<Unit>,
    /// The linear SI magnitude of the 0-dB reference point (1 mW = 1e-3
    /// W for `dBm`; `1.0` for a pure ratio).
    pub reference_si_value: f64,
}

/// One row of the fixed log-unit table: symbol, factor, reference unit
/// symbol (or `None` for a ratio view).
type LogRow = (&'static str, i32, Option<&'static str>);

/// The fixed log-unit table (regolith/02 sec. 5a). Unreferenced ratio
/// views use factor 10 (power ratios); `dBuV` is a field/amplitude view
/// (factor 20). References are ordinary unit-table content, so they are
/// parsed through [`Unit::parse_atom`] and extend like any unit.
const LOG_TABLE: &[LogRow] = &[
    ("dB", 10, None),
    ("dBc", 10, None),
    ("dBi", 10, None),
    ("dBm", 10, Some("mW")),
    ("dBW", 10, Some("W")),
    ("dBuV", 20, Some("uV")),
];

/// A failure evaluating the log-sum reference algebra (regolith/02
/// sec. 5a). An error VALUE (AD-7): the L1 check turns it into a
/// diagnostic; it is never a panic or bare exception.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum LogError {
    /// More than one referenced term survives cancellation: the linear
    /// product is not a single-reference quantity (`dBm + dBm` = mW^2).
    #[error("log sum leaves more than one reference: the linear product is not a valid quantity")]
    TwoReferences,
    /// A subtracted reference did not cancel against an added one: the
    /// linear quotient has an inverse dimension (`dB - dBm` = 1/mW).
    #[error("log sum has an uncancelled subtracted reference (an inverse dimension)")]
    UncancelledInverse,
}

/// The outcome of a legal log-sum: either a dimensionless ratio (no
/// surviving reference) or a referenced quantity of the surviving
/// reference's dimension.
#[derive(Debug, Clone, PartialEq)]
pub enum LogSumResult {
    /// No reference survived: the sum views a dimensionless ratio.
    Ratio,
    /// Exactly one reference survived: the sum views a quantity of that
    /// reference's dimension (a `dBm` sum stays a power).
    Referenced(Unit),
}

/// A single signed term in a sum-of-logs expression.
#[derive(Debug, Clone)]
pub struct LogTerm {
    /// Whether this term is added or subtracted.
    pub sign: Sign,
    /// The log unit the term is expressed in.
    pub unit: LogUnit,
}

impl LogUnit {
    /// Parse a decibel unit spelling into its view, or `None` if the
    /// symbol is not a known log unit. References are resolved through
    /// the ordinary unit table.
    #[must_use]
    pub fn parse(symbol: &str) -> Option<LogUnit> {
        let (sym, factor, reference) = LOG_TABLE.iter().find(|(name, ..)| *name == symbol)?;
        let (reference, reference_si_value) = match reference {
            Some(ref_sym) => {
                let unit = Unit::parse_atom(ref_sym).ok()?;
                let si = ratio_to_f64(unit.scale);
                (Some(unit), si)
            }
            None => (None, 1.0),
        };
        Some(LogUnit {
            symbol: (*sym).to_string(),
            factor: *factor,
            reference,
            reference_si_value,
        })
    }

    /// The reference's physical dimension, or `None` for an unreferenced
    /// ratio view. Cancellation in the sum algebra pairs references by
    /// this dimension.
    #[must_use]
    pub fn reference_dimension(&self) -> Option<Dimension> {
        self.reference.as_ref().map(|u| u.dimension)
    }

    /// Convert a value expressed in this dB view to its stored LINEAR
    /// magnitude in SI base units: `reference * 10^(db / factor)`.
    #[must_use]
    pub fn to_linear_si(&self, db: f64) -> f64 {
        self.reference_si_value * 10.0_f64.powf(db / f64::from(self.factor))
    }

    /// View a stored LINEAR SI magnitude back through this dB unit:
    /// `factor * log10(linear / reference)`. Inverse of
    /// [`LogUnit::to_linear_si`] (round-trips up to float precision).
    #[must_use]
    pub fn from_linear_si(&self, linear_si: f64) -> f64 {
        f64::from(self.factor) * (linear_si / self.reference_si_value).log10()
    }
}

/// Evaluate the reference legality of a sum of log terms (regolith/02
/// sec. 5a). Cancels each subtracted reference against an added one of
/// the same dimension; the sum is legal iff at most one added reference
/// survives with no uncancelled subtracted reference.
///
/// # Errors
/// [`LogError::TwoReferences`] when more than one added reference
/// survives (`dBm + dBm`); [`LogError::UncancelledInverse`] when a
/// subtracted reference has no added partner (`dB - dBm`).
pub fn log_sum_reference(terms: &[LogTerm]) -> Result<LogSumResult, LogError> {
    // Split surviving references by sign, pairing by dimension. Each
    // subtracted reference cancels one added reference of equal
    // dimension (the linear quotient is a ratio).
    let mut added: Vec<Unit> = Vec::new();
    let mut subtracted: Vec<Dimension> = Vec::new();
    for term in terms {
        let Some(reference) = term.unit.reference.clone() else {
            continue; // ratio view (dB/dBc/dBi): no reference to track.
        };
        match term.sign {
            Sign::Add => added.push(reference),
            Sign::Sub => subtracted.push(reference.dimension),
        }
    }
    for sub_dim in subtracted {
        match added.iter().position(|u| u.dimension == sub_dim) {
            Some(idx) => {
                added.swap_remove(idx);
            }
            None => return Err(LogError::UncancelledInverse),
        }
    }
    if added.len() > 1 {
        return Err(LogError::TwoReferences);
    }
    match added.into_iter().next() {
        Some(reference) => Ok(LogSumResult::Referenced(reference)),
        None => Ok(LogSumResult::Ratio),
    }
}

/// Exact-rational scale to `f64` (mirrors `quantity::ratio_to_f64`; the
/// reference SI magnitude of a log unit is a small SI-prefix factor).
#[allow(
    clippy::cast_precision_loss,
    reason = "log-unit reference scales are small SI-prefix rationals; f64 is exact for them"
)]
fn ratio_to_f64(r: crate::unit::Scale) -> f64 {
    *r.numer() as f64 / *r.denom() as f64
}

#[cfg(test)]
mod tests {
    use super::{log_sum_reference, LogError, LogSumResult, LogTerm, LogUnit, Sign};

    fn term(symbol: &str, sign: Sign) -> LogTerm {
        LogTerm {
            sign,
            unit: LogUnit::parse(symbol).unwrap(),
        }
    }

    #[test]
    fn log_units_parse_and_carry_references() {
        assert!(LogUnit::parse("dB").unwrap().reference.is_none());
        assert!(LogUnit::parse("dBi").unwrap().reference.is_none());
        assert!(LogUnit::parse("dBm").unwrap().reference.is_some());
        assert_eq!(LogUnit::parse("dBuV").unwrap().factor, 20);
        assert!(LogUnit::parse("nope").is_none());
    }

    #[test]
    fn two_referenced_powers_is_illegal() {
        // dBm + dBm == linear mW^2, not a power -- the link-budget bug.
        let terms = [term("dBm", Sign::Add), term("dBm", Sign::Add)];
        assert_eq!(log_sum_reference(&terms), Err(LogError::TwoReferences));
    }

    #[test]
    fn link_budget_sum_is_a_power() {
        // p_tx + g_ant - l_path (dBm + dBi - dB) is a power (dBm).
        let terms = [
            term("dBm", Sign::Add),
            term("dBi", Sign::Add),
            term("dB", Sign::Sub),
        ];
        match log_sum_reference(&terms).unwrap() {
            LogSumResult::Referenced(u) => {
                assert_eq!(
                    u.dimension,
                    LogUnit::parse("dBm").unwrap().reference.unwrap().dimension
                );
            }
            LogSumResult::Ratio => panic!("expected a referenced power"),
        }
    }

    #[test]
    fn difference_of_references_is_a_ratio() {
        // p_rx - p_sens (dBm - dBm) cancels to a ratio (dB).
        let terms = [term("dBm", Sign::Add), term("dBm", Sign::Sub)];
        assert_eq!(log_sum_reference(&terms).unwrap(), LogSumResult::Ratio);
    }

    #[test]
    fn uncancelled_subtracted_reference_is_illegal() {
        // dB - dBm == 1/mW, an inverse dimension -- rejected.
        let terms = [term("dB", Sign::Add), term("dBm", Sign::Sub)];
        assert_eq!(log_sum_reference(&terms), Err(LogError::UncancelledInverse));
    }

    #[test]
    fn pure_ratio_sum_is_a_ratio() {
        let terms = [
            term("dBi", Sign::Add),
            term("dB", Sign::Sub),
            term("dBc", Sign::Add),
        ];
        assert_eq!(log_sum_reference(&terms).unwrap(), LogSumResult::Ratio);
    }

    #[test]
    fn single_reference_survives() {
        let terms = [term("dBm", Sign::Add)];
        assert!(matches!(
            log_sum_reference(&terms).unwrap(),
            LogSumResult::Referenced(_)
        ));
    }

    #[test]
    fn sum_legality_is_commutative_in_operand_order() {
        // Reordering added/subtracted terms cannot change legality: the
        // reference multiset is the same (linear multiplication commutes).
        let forward = [
            term("dBm", Sign::Add),
            term("dBi", Sign::Add),
            term("dB", Sign::Sub),
        ];
        let shuffled = [
            term("dB", Sign::Sub),
            term("dBm", Sign::Add),
            term("dBi", Sign::Add),
        ];
        assert_eq!(log_sum_reference(&forward), log_sum_reference(&shuffled));
    }

    #[test]
    fn linear_db_round_trip() {
        // Stored LINEAR is the source of truth; the dB view round-trips.
        let dbm = LogUnit::parse("dBm").unwrap();
        for db in [-90.0, -30.0, 0.0, 10.0, 33.0] {
            let linear = dbm.to_linear_si(db);
            let back = dbm.from_linear_si(linear);
            assert!((back - db).abs() < 1e-9, "round-trip {db} -> {back}");
        }
        // 0 dBm is exactly 1 mW = 1e-3 W in SI.
        assert!((dbm.to_linear_si(0.0) - 1e-3).abs() < 1e-18);
        // +30 dBm is 1 W.
        assert!((dbm.to_linear_si(30.0) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn view_is_strictly_monotone_so_corners_commute() {
        // A strictly monotone view means interval corners commute with
        // it: larger dB <-> larger linear, so a corner picked in linear
        // space is the same corner in the dB view (regolith/02 sec. 5a).
        let dbm = LogUnit::parse("dBm").unwrap();
        let lo = dbm.to_linear_si(-90.0);
        let hi = dbm.to_linear_si(-30.0);
        assert!(lo < hi);
        assert!(dbm.from_linear_si(lo) < dbm.from_linear_si(hi));
    }

    #[test]
    fn field_view_round_trips_at_factor_twenty() {
        let dbuv = LogUnit::parse("dBuV").unwrap();
        let linear = dbuv.to_linear_si(20.0); // 20 dBuV = 10x = 10 uV
        assert!((dbuv.from_linear_si(linear) - 20.0).abs() < 1e-9);
    }
}
