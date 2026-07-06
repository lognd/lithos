//! The diagnostic code registry: stable regolith-wide code families.
//!
//! Regolith reference: `docs/regolith/09-build-and-lockfile.md`
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
    /// `E0103` -- a `[a, b]` interval and a `[i .. j]` index range were
    /// confused: both separators in one bracket, or a range endpoint
    /// carrying a unit/fractional literal (regolith/02 sec. 3).
    pub const INTERVAL_RANGE_CONFUSION: DiagCode = DiagCode::new(Family::Parse, 3);
    /// `E0104` -- an illegal logarithmic-unit sum: after cancelling
    /// subtracted references against added ones, more than one reference
    /// survives (`dBm + dBm`) or a subtracted reference is uncancelled
    /// (regolith/02 sec. 5a; the linear product/quotient is not a valid
    /// quantity).
    pub const ILLEGAL_LOG_SUM: DiagCode = DiagCode::new(Family::Parse, 4);
    /// `E0105` -- a combinational (instantaneous `=`) cycle entirely
    /// within one clock/continuous domain, with no converter or register
    /// delta to break it (an algebraic loop, INV-16). A cross-domain edge
    /// always passes through a converter (a ZOH delta by type), so no
    /// zero-delay cycle can cross the continuous/discrete boundary; this
    /// code flags only a within-domain loop the source actually declares.
    pub const COMBINATIONAL_CYCLE: DiagCode = DiagCode::new(Family::Parse, 5);
    /// `E0301` -- an entity query matched more than one entity.
    pub const AMBIGUOUS_SELECTION: DiagCode = DiagCode::new(Family::References, 1);
    /// `E0302` -- conflicting borrow of an owned region.
    pub const BORROW_CONFLICT: DiagCode = DiagCode::new(Family::References, 2);
    /// `E0304` -- a change that alters an entity's structure class.
    pub const STRUCTURE_CLASS_CHANGE: DiagCode = DiagCode::new(Family::References, 4);
    /// `E0407` -- an enclosing system's boundary envelope is not
    /// contained in an imported/child artifact's proven boundary
    /// (boundary subsumption, INV-7).
    pub const BOUNDARY_NOT_SUBSUMED: DiagCode = DiagCode::new(Family::Contracts, 7);
    /// `E0410` -- a demanded capability exceeds the supplied one.
    pub const CAPABILITY_VS_DEMAND: DiagCode = DiagCode::new(Family::Contracts, 10);
    /// `E0420` -- a ledger imbalance (DOF / driver / domain-crossing).
    pub const LEDGER_IMBALANCE: DiagCode = DiagCode::new(Family::Contracts, 20);
    /// `E0432` -- a budget cannot close at its worst-case corner.
    pub const BUDGET_CANNOT_CLOSE: DiagCode = DiagCode::new(Family::Contracts, 32);
    /// `E0433` -- a compute intent is realized by other than exactly one
    /// workload (zero or two-or-more), naming both sides (cuprite/05 sec.
    /// 1 rule 1, EOPEN-15's realization ledger).
    pub const REALIZATION_NOT_EXACTLY_ONE: DiagCode = DiagCode::new(Family::Contracts, 33);
    /// `E0440` -- a numeric L2 solve (rigid statics, stiffness network)
    /// hit a singular or rank-deficient system: an under-determined
    /// support set, a disconnected stiffness network, or an
    /// ill-conditioned assembly (WO-23). Always a diagnostic, never a
    /// panic and never a NaN/non-finite value escaping the solve.
    pub const SINGULAR_SYSTEM: DiagCode = DiagCode::new(Family::Contracts, 40);
    /// `E0441` -- an exactly-constrained sketch (WO-11's conservative
    /// DOF ledger reports residual zero) whose numeric residual closure
    /// does not converge to zero: the declared constraints are
    /// mutually inconsistent, not merely under/over-counted (WO-23,
    /// hematite/07 OPEN-5/D65).
    pub const SKETCH_RESIDUAL_INCONSISTENT: DiagCode = DiagCode::new(Family::Contracts, 41);
    /// `E0501` -- positional index used where a domain is required.
    pub const INDEX_VS_DOMAIN: DiagCode = DiagCode::new(Family::Instances, 1);
    /// `E0502` -- `any` over a broken (non-uniform) orbit.
    pub const BROKEN_ORBIT_ANY: DiagCode = DiagCode::new(Family::Instances, 2);
    /// `E0503` -- a generic declaration is never instantiated (a dead
    /// generic: a monomorphization point-set with no points, INV-11).
    pub const DEAD_GENERIC: DiagCode = DiagCode::new(Family::Instances, 3);
    /// `E0504` -- a use-site generic instantiation supplies the wrong
    /// number of arguments for its declaration, so no static check can
    /// run at that point (an un-expandable instantiation, INV-11).
    pub const GENERIC_ARITY_MISMATCH: DiagCode = DiagCode::new(Family::Instances, 4);
    /// `E0601` -- a rule pack's static rule evaluated `false` against a
    /// matched entity (`pack.rule` provenance, `why:` rendered).
    pub const RULE_VIOLATION: DiagCode = DiagCode::new(Family::RulePacks, 1);
    /// `E0602` -- two attached rule packs declare a rule of the same
    /// qualified name (`pack.rule`): union composition with no priority
    /// arithmetic means a collision is an error, never silent shadowing
    /// (design doc D-C).
    pub const RULE_NAME_COLLISION: DiagCode = DiagCode::new(Family::RulePacks, 2);
    /// `E0603` -- a rule's predicate references a fact no layer (static
    /// entity DB, WO-22/24 realized-fact extraction) provides: a compile
    /// error on the rule itself (design doc D-E), not a deferral.
    pub const RULE_FACT_UNPROVIDED: DiagCode = DiagCode::new(Family::RulePacks, 3);
    /// `E0604` -- a `resolves:` clause names a field that is never
    /// `free` at any use site in the corpus (a stale resolver, mirror of
    /// `E0701`).
    pub const RULE_STALE_RESOLVER: DiagCode = DiagCode::new(Family::RulePacks, 4);
    /// `E0701` -- a declared waiver matched no claim or rule (stale).
    pub const STALE_WAIVER: DiagCode = DiagCode::new(Family::Evidence, 1);
    /// `E0702` -- a waiver carries no mandatory `basis:` (regolith/12
    /// rule 2): an unjustified concession, rejected as an INV-2 ladder
    /// overreach rather than accepted.
    pub const WAIVER_MISSING_BASIS: DiagCode = DiagCode::new(Family::Evidence, 2);
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
        assert_eq!(codes::COMBINATIONAL_CYCLE.to_string(), "E0105");
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
