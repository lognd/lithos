//! The diagnostic code registry: stable substrate-wide code families.
//!
//! Substrate reference: `docs/substrate/09-build-and-lockfile.md`
//! sec. 4. Codes are DATA, defined once here, never inline literals
//! anywhere else. Families are shared across both languages; only the
//! human message is domain-specific.

use std::fmt;

use serde::{Deserialize, Serialize};

/// A diagnostic code family. The hundreds digit of the numeric code
/// (`E03xx` -> [`Family::References`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Family {
    /// `E01xx` -- parse, types, units, grammar (incompatible quantities,
    /// `==` on continuous).
    Parse,
    /// `E03xx` -- references, ownership, structure.
    References,
    /// `E04xx` -- contracts (capability vs demand, ledgers, budgets).
    Contracts,
    /// `E05xx` -- instances and symmetry.
    Instances,
    /// `E06xx` -- rule packs (DFM / DRC / ERC), with rule provenance.
    RulePacks,
    /// `E07xx` -- evidence (indeterminate discharge, release assumptions).
    Evidence,
}

impl Family {
    /// The numeric base of this family (`E03xx` -> `300`).
    #[must_use]
    pub const fn base(self) -> u16 {
        match self {
            Family::Parse => 100,
            Family::References => 300,
            Family::Contracts => 400,
            Family::Instances => 500,
            Family::RulePacks => 600,
            Family::Evidence => 700,
        }
    }
}

/// A stable diagnostic code: a family plus its within-family offset.
/// Renders as `E0301` (family base + offset, zero-padded to four
/// digits).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DiagCode {
    /// The owning family.
    pub family: Family,
    /// Offset within the family (`E0301` -> `1`).
    pub offset: u16,
}

impl DiagCode {
    /// Construct a code in `family` at `offset`.
    #[must_use]
    pub const fn new(family: Family, offset: u16) -> DiagCode {
        DiagCode { family, offset }
    }

    /// The full numeric code (`E0301` -> `301`).
    #[must_use]
    pub const fn number(self) -> u16 {
        self.family.base() + self.offset
    }
}

impl fmt::Display for DiagCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "E{:04}", self.number())
    }
}

/// The registry of named codes the checks refer to by symbol. Every
/// code a check emits MUST be declared here (WO-06 ground rule: codes
/// are data). Grows as each later WO adds its checks.
pub mod codes {
    use super::{DiagCode, Family};

    /// `E0101` -- arithmetic between incompatible quantities.
    pub const INCOMPATIBLE_QUANTITIES: DiagCode = DiagCode::new(Family::Parse, 1);
    /// `E0102` -- `==` used on a continuous quantity (equality ban).
    pub const EQUALITY_ON_CONTINUOUS: DiagCode = DiagCode::new(Family::Parse, 2);
    /// `E0301` -- an entity query matched more than one entity.
    pub const AMBIGUOUS_SELECTION: DiagCode = DiagCode::new(Family::References, 1);
    /// `E0302` -- conflicting borrow of an owned region.
    pub const BORROW_CONFLICT: DiagCode = DiagCode::new(Family::References, 2);
    /// `E0304` -- a change that alters an entity's structure class.
    pub const STRUCTURE_CLASS_CHANGE: DiagCode = DiagCode::new(Family::References, 4);
    /// `E0410` -- a demanded capability exceeds the supplied one.
    pub const CAPABILITY_VS_DEMAND: DiagCode = DiagCode::new(Family::Contracts, 10);
    /// `E0420` -- a ledger imbalance (DOF / driver / domain-crossing).
    pub const LEDGER_IMBALANCE: DiagCode = DiagCode::new(Family::Contracts, 20);
    /// `E0432` -- a budget cannot close at its worst-case corner.
    pub const BUDGET_CANNOT_CLOSE: DiagCode = DiagCode::new(Family::Contracts, 32);
    /// `E0501` -- positional index used where a domain is required.
    pub const INDEX_VS_DOMAIN: DiagCode = DiagCode::new(Family::Instances, 1);
    /// `E0502` -- `any` over a broken (non-uniform) orbit.
    pub const BROKEN_ORBIT_ANY: DiagCode = DiagCode::new(Family::Instances, 2);
}

#[cfg(test)]
mod tests {
    use super::codes;
    use super::{DiagCode, Family};

    #[test]
    fn code_renders_zero_padded() {
        assert_eq!(codes::AMBIGUOUS_SELECTION.to_string(), "E0301");
        assert_eq!(codes::BUDGET_CANNOT_CLOSE.to_string(), "E0432");
        assert_eq!(codes::INCOMPATIBLE_QUANTITIES.to_string(), "E0101");
        assert_eq!(codes::BROKEN_ORBIT_ANY.to_string(), "E0502");
    }

    #[test]
    fn family_base_maps_hundreds_digit() {
        assert_eq!(Family::Evidence.base(), 700);
        assert_eq!(DiagCode::new(Family::Evidence, 3).number(), 703);
    }

    #[test]
    fn code_round_trips_json() {
        let json = serde_json::to_string(&codes::BORROW_CONFLICT).unwrap();
        let back: DiagCode = serde_json::from_str(&json).unwrap();
        assert_eq!(back, codes::BORROW_CONFLICT);
    }
}
