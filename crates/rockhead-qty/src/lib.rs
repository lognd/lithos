//! Quantity core: dimensions, units, intervals, log views, value
//! sources.
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` and
//! `docs/substrate/03-value-sources.md`. Dimension exponents are
//! rational (AD-9); intervals round outward (AD-6); resolved values
//! carry a `Cause` (INV-21). This crate is the keystone: both modeling
//! languages and the harness depend on it and it depends on nothing but
//! `rockhead-util`.
//!
//! Module map: WO-02 lands `dimension`, `unit`, `quantity`, `decl`,
//! `count`; WO-03 adds intervals/ranges; WO-04 adds value sources.

pub mod corner;
pub mod count;
pub mod decl;
pub mod dimension;
pub mod interval;
pub mod monomorphize;
pub mod quantity;
pub mod range;
pub mod resolution;
pub mod unit;
pub mod value_source;
pub mod window;

pub use corner::{CheckDirection, Corner, CornerInputs};
pub use count::Count;
pub use decl::{Namespace, QuantityDecl, TensorRank};
pub use dimension::{BaseDimension, Dimension, Exponent};
pub use interval::Interval;
pub use monomorphize::{monomorphize, DiscretePoint, DomainConstraint, InstantiationPoint};
pub use quantity::{Qty, QuantityError};
pub use range::{Range, RangePos};
pub use resolution::{Cause, Resolution};
pub use unit::{si_prefix_exponent, Scale, Unit, UnitError};
pub use value_source::{Comparator, Direction, DiscreteSet, DomainSpec, Literal, ValueSource};
pub use window::Window;

/// Number of base dimensions in the fixed dimension vector (AD-9).
/// Length, mass, time, current, temperature, amount, luminous
/// intensity -- SI's seven.
pub const BASE_DIMENSIONS: usize = 7;

#[cfg(test)]
mod tests {
    use super::BASE_DIMENSIONS;

    #[test]
    fn seven_base_dimensions() {
        assert_eq!(BASE_DIMENSIONS, 7);
    }
}
