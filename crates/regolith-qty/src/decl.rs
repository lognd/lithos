//! Quantity declarations and namespaces: the typed vocabulary of
//! physical quantities the two languages share.
//!
//! Regolith reference: `docs/spec/regolith/02-quantity-core.md` sec. 1.
//! Namespaces are shared across domains (a thermal quantity means the
//! same thing in a mechanical and an electrical claim) -- the hook for
//! cross-domain contracts.

use serde::{Deserialize, Serialize};

use crate::unit::Unit;

/// The tensor rank of a quantity's value.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-qty.md#decl
pub enum TensorRank {
    /// A single scalar magnitude (`stiffness: N/m`).
    Scalar,
    /// A rank-1 vector (`displacement: m`).
    Vector,
    /// A rank-n tensor (`stress: Pa, tensor(2)`).
    Tensor(u8),
    /// A complex scalar, frequency-indexed (`impedance: ohm`).
    Complex,
}

/// A shared quantity namespace. Seeded from the spec; shared across
/// domains so cross-domain contracts refer to one vocabulary.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-qty.md#decl
pub enum Namespace {
    /// Mechanical quantities (stress, displacement, stiffness).
    Mech,
    /// Electrical quantities (voltage, current, impedance, energy).
    Elec,
    /// Thermal quantities (temperature, heat flux).
    Thermo,
    /// Geometric quantities (length, angle, area).
    Geom,
    /// Information quantities (data rate, storage, op rate).
    Info,
    /// Manufacturing quantities (process capability).
    Mfg,
    /// Civil quantities (occupancy/egress, envelope, structural
    /// serviceability -- D145, calcite/02 sec. 9).
    Civil,
}

impl Namespace {
    /// The seeded namespaces, in declaration order.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#decl
    pub const fn all() -> [Namespace; 7] {
        [
            Namespace::Mech,
            Namespace::Elec,
            Namespace::Thermo,
            Namespace::Geom,
            Namespace::Info,
            Namespace::Mfg,
            Namespace::Civil,
        ]
    }

    /// The lowercase spelling used in source (`mech`, `elec`, ...).
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#decl
    pub const fn as_str(self) -> &'static str {
        match self {
            Namespace::Mech => "mech",
            Namespace::Elec => "elec",
            Namespace::Thermo => "thermo",
            Namespace::Geom => "geom",
            Namespace::Info => "info",
            Namespace::Mfg => "mfg",
            Namespace::Civil => "civil",
        }
    }
}

/// A declared quantity: its name, owning namespace, canonical unit, and
/// tensor rank (`quantity stress: Pa, tensor(2)`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-qty.md#decl
pub struct QuantityDecl {
    /// Bare name within the namespace (`stress`, `voltage`).
    pub name: String,
    /// The owning namespace.
    pub namespace: Namespace,
    /// The declared canonical unit.
    pub unit: Unit,
    /// The tensor rank of values of this quantity.
    pub rank: TensorRank,
}

#[cfg(test)]
mod tests {
    use super::{Namespace, QuantityDecl, TensorRank};
    use crate::dimension::Dimension;
    use crate::unit::Unit;
    use num_rational::Ratio;

    // frob:tests crates/regolith-qty/src/decl.rs::Namespace.as_str kind="unit"
    #[test]
    fn seven_namespaces_seeded() {
        assert_eq!(Namespace::all().len(), 7);
        assert_eq!(Namespace::Info.as_str(), "info");
        assert_eq!(Namespace::Civil.as_str(), "civil");
    }

    #[test]
    fn tensor_rank_round_trips_json() {
        let json = serde_json::to_string(&TensorRank::Tensor(2)).unwrap();
        let back: TensorRank = serde_json::from_str(&json).unwrap();
        assert_eq!(back, TensorRank::Tensor(2));
    }

    #[test]
    fn quantity_decl_round_trips_json() {
        let decl = QuantityDecl {
            name: "stress".to_string(),
            namespace: Namespace::Mech,
            unit: Unit {
                symbol: "Pa".to_string(),
                dimension: Dimension::dimensionless(),
                scale: Ratio::from_integer(1),
                offset: Ratio::from_integer(0),
            },
            rank: TensorRank::Tensor(2),
        };
        let json = serde_json::to_string(&decl).unwrap();
        let back: QuantityDecl = serde_json::from_str(&json).unwrap();
        assert_eq!(back, decl);
    }
}
