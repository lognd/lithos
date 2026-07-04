//! Contract IR: interfaces, matings, ledgers, budgets, L2 arithmetic.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`, `docs/mech/03`,
//! `docs/elec/02` sec. 4a. This is the implementation-free contract
//! graph and its checks: the level (L2) where a system verifies with
//! zero artifacts. Ledgers and conformance run on these nodes before any
//! impl or realizer exists (WO-12).

pub mod budget;
pub mod conformance;
pub mod ledger;
pub mod nodes;

pub use budget::{close_budget, Contribution};
pub use conformance::{
    check_capability_vs_demand, check_param_match, check_refinement, check_role_kind, Capability,
};
pub use ledger::{ElecLedger, Ledger, MechLedger};
pub use nodes::{
    Budget, Frame, Impl, Interface, Mating, ParamKind, PromiseSlot, SystemNode,
};
