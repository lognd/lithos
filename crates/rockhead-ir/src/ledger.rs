//! Ledgers: one pluggable interface, two domain packs. Mech runs a
//! DOF/Gruebler ledger; elec runs driver/load + domain-crossing + flow
//! ledgers. Imbalances are E0420-family diagnostics.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`, `docs/mech/03`
//! (Gruebler), `docs/elec/02` sec. 4a. The trait keeps the two domains'
//! bookkeeping behind one interface so the system node runs whichever
//! pack its domain provides.

use rockhead_diag::Diagnostic;

use crate::nodes::SystemNode;

/// A domain ledger over a system/assembly node. Returns E0420-family
/// diagnostics for imbalances (over/under-constraint, unfed flow,
/// unbalanced domain crossing).
pub trait Ledger {
    /// The ledger's name (for the diagnostic and the report).
    fn name(&self) -> &'static str;

    /// Run the ledger, returning any imbalance diagnostics.
    fn check(&self, node: &SystemNode) -> Vec<Diagnostic>;
}

/// Mechanical DOF/Gruebler ledger: counts constrained vs free degrees of
/// freedom across matings; double-axial-fixation is an over-constraint.
#[derive(Debug, Default)]
pub struct MechLedger;

impl Ledger for MechLedger {
    fn name(&self) -> &'static str {
        "gruebler"
    }

    fn check(&self, _node: &SystemNode) -> Vec<Diagnostic> {
        todo!("STUB WO-12: Gruebler count over matings; over/under-constraint -> E0420")
    }
}

/// Electrical driver/load + domain-crossing + flow ledger: every net
/// fed, every domain crossing balanced, every flow sourced.
#[derive(Debug, Default)]
pub struct ElecLedger;

impl Ledger for ElecLedger {
    fn name(&self) -> &'static str {
        "driver_load_flow"
    }

    fn check(&self, _node: &SystemNode) -> Vec<Diagnostic> {
        todo!("STUB WO-12: driver/load + domain-crossing + flow balance; unfed flow -> E0420")
    }
}

#[cfg(test)]
mod tests {
    use super::{ElecLedger, Ledger, MechLedger};

    #[test]
    fn ledgers_name_themselves() {
        assert_eq!(MechLedger.name(), "gruebler");
        assert_eq!(ElecLedger.name(), "driver_load_flow");
    }
}
