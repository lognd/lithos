//! The value-source grammar: one union answering "who decides this
//! number?" for every numeric slot in both languages.
//!
//! Regolith reference: `docs/regolith/03-value-sources.md` sec. 1.
//! Five sources: literal, `in [lo, hi]` (bounded freedom), `free`,
//! `derived`, `allocated`. Optimization direction is per-variable and
//! takes NO argument (SOPEN-4). Every IR numeric slot carries one of
//! these; schemars export (WO-18) feeds the generated pydantic models.

use serde::{Deserialize, Serialize};

use crate::interval::Interval;
use crate::quantity::Qty;
use crate::window::Window;

/// A one-sided asserted comparator bound (`>= 80kN/mm`, `<= 30ns`).
/// Comparator literals ARE literals: one-sided asserted truth.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Comparator {
    /// `>= x`.
    AtLeast(Qty),
    /// `<= x`.
    AtMost(Qty),
}

/// A literal value source (the human knows it).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Literal {
    /// A plain quantity (`wall = 4mm`) or an interval scatter
    /// (`3.3V +- 5%`, `[300K, 900K]`).
    Value(Qty),
    /// A scatter interval asserted by the author.
    Scatter(Interval),
    /// A one-sided comparator (`<= 12N`).
    Comparator(Comparator),
    /// A two-sided demanded window (`within [lo, hi]`).
    Window(Window),
}

/// Per-variable secondary optimization objective. Takes no argument
/// (SOPEN-4): global objectives live in `policy:` blocks, not here.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    /// Prefer the smallest satisfying value.
    Minimize,
    /// Prefer the largest satisfying value.
    Maximize,
}

/// A discrete domain the optimizer chooses from (monomorphized).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiscreteSet {
    /// Integer choices (`n = in [2, 6]` -> 2,3,4,5,6).
    Ints(Vec<i64>),
    /// Named enum / variant-axis choices.
    Enum(Vec<String>),
}

/// The domain of an `in [...]` source: a continuous interval or a
/// discrete set.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DomainSpec {
    /// A continuous bounded interval (`in [10uF, 100uF]`).
    Interval(Interval),
    /// A discrete set (monomorphizes to instantiation points).
    Discrete(DiscreteSet),
}

/// One of the five value sources every numeric slot takes.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "source", rename_all = "snake_case")]
pub enum ValueSource {
    /// Asserted truth (`wall = 4mm`, `<= 12N`, `within [lo, hi]`).
    Literal(Literal),
    /// Bounded freedom: the optimizer decides inside hard bounds.
    /// `external` flags an externally-chosen axis (a `variant`): all
    /// points must verify, none is optimizer-picked.
    InDomain {
        /// The hard domain the value must lie in.
        domain: DomainSpec,
        /// Optional per-variable secondary objective.
        direction: Option<Direction>,
        /// True for externally-chosen axes (variant): every point must
        /// verify (WO-04).
        external: bool,
    },
    /// Cheapest legal value per process rules (DFM/DRC decides).
    Free,
    /// A consequence of system-level analysis, pinned; `sf` is the
    /// applied safety factor.
    Derived {
        /// Optional safety factor (`derived(sf=1.5)`).
        sf: Option<f64>,
    },
    /// A share of a named budget or a planner output.
    Allocated {
        /// Optional allocation policy tag.
        policy: Option<String>,
    },
}

#[cfg(test)]
mod tests {
    use super::{Direction, DiscreteSet, DomainSpec, Literal, ValueSource};
    use crate::quantity::Qty;
    use crate::unit::Unit;

    fn round_trip(vs: &ValueSource) -> ValueSource {
        let json = serde_json::to_string(vs).unwrap();
        serde_json::from_str(&json).unwrap()
    }

    #[test]
    fn every_source_variant_round_trips() {
        let variants = vec![
            ValueSource::Literal(Literal::Value(Qty::new(4.0, Unit::dimensionless()))),
            ValueSource::InDomain {
                domain: DomainSpec::Discrete(DiscreteSet::Ints(vec![2, 3, 4, 5, 6])),
                direction: Some(Direction::Minimize),
                external: false,
            },
            ValueSource::Free,
            ValueSource::Derived { sf: Some(1.5) },
            ValueSource::Allocated {
                policy: Some("error_budget".to_string()),
            },
        ];
        for vs in &variants {
            // Round-trips without loss (compared through JSON, since the
            // continuous forms carry no PartialEq).
            let a = serde_json::to_string(vs).unwrap();
            let b = serde_json::to_string(&round_trip(vs)).unwrap();
            assert_eq!(a, b);
        }
    }

    #[test]
    fn direction_takes_no_argument() {
        let json = serde_json::to_string(&Direction::Maximize).unwrap();
        assert_eq!(json, "\"maximize\"");
    }
}
