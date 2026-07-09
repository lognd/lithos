//! Monomorphization of discrete `in [...]` domains into per-point
//! instantiation points, each with a stable identity for caching.
//!
//! Regolith reference: `docs/spec/regolith/03-value-sources.md` sec. 1
//! (integer domains monomorphize) and sec. 4 (structure boundaries as
//! domain constraints). `variant` axes are externally-chosen: every
//! point must verify, none is optimizer-picked. The structure-boundary
//! hook here is DATA ONLY (WO-04): later passes intersect domains with
//! structure-preserving regions.

use serde::{Deserialize, Serialize};

use crate::value_source::DiscreteSet;

/// One point of a monomorphized discrete domain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DiscretePoint {
    /// A concrete integer instantiation.
    Int(i64),
    /// A concrete enum/variant instantiation.
    Enum(String),
}

/// An instantiation point: a concrete value plus a stable identity used
/// as the cache key for per-point checks.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InstantiationPoint {
    /// Position of this point within the enumerated domain (source order).
    pub index: usize,
    /// The concrete value at this point.
    pub value: DiscretePoint,
    /// Stable per-point identity for caching (INV-1 content key input).
    pub identity: String,
}

/// The structure-boundary hook (DATA ONLY, WO-04): names a boundary
/// whose structure-preserving region a later pass intersects the domain
/// with. No logic here -- just the shape the callback slot carries.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DomainConstraint {
    /// The named structure boundary (mech fillet face, elec mode edge).
    pub boundary: String,
}

/// Expand a discrete set into its instantiation points. `external`
/// marks a variant axis (all points must verify); it does not change
/// the expansion, only how callers treat the points.
#[must_use]
pub fn monomorphize(set: &DiscreteSet, _external: bool) -> Vec<InstantiationPoint> {
    match set {
        DiscreteSet::Ints(members) => members
            .iter()
            .enumerate()
            .map(|(index, value)| InstantiationPoint {
                index,
                value: DiscretePoint::Int(*value),
                identity: format!("{index}@{value}"),
            })
            .collect(),
        DiscreteSet::Enum(members) => members
            .iter()
            .enumerate()
            .map(|(index, value)| InstantiationPoint {
                index,
                value: DiscretePoint::Enum(value.clone()),
                identity: format!("{index}@{value}"),
            })
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::{DiscretePoint, DomainConstraint, InstantiationPoint};

    #[test]
    fn instantiation_point_round_trips_json() {
        let p = InstantiationPoint {
            index: 0,
            value: DiscretePoint::Int(2),
            identity: "n@2".to_string(),
        };
        let json = serde_json::to_string(&p).unwrap();
        let back: InstantiationPoint = serde_json::from_str(&json).unwrap();
        assert_eq!(back, p);
    }

    #[test]
    fn domain_constraint_is_data_only() {
        let c = DomainConstraint {
            boundary: "regulator.mode_edge".to_string(),
        };
        let json = serde_json::to_string(&c).unwrap();
        let back: DomainConstraint = serde_json::from_str(&json).unwrap();
        assert_eq!(back, c);
    }
}
