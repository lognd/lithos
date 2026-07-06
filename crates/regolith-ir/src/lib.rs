//! Contract IR: interfaces, matings, ledgers, budgets, L2 arithmetic.
//!
//! Regolith reference: `docs/regolith/04-contracts.md`, `docs/hematite/03`,
//! `docs/cuprite/02` sec. 4a. This is the implementation-free contract
//! graph and its checks: the level (L2) where a system verifies with
//! zero artifacts. Ledgers and conformance run on these nodes before any
//! impl or realizer exists (WO-12).

pub mod budget;
pub mod conformance;
pub mod ledger;
pub mod nodes;
pub mod system;

pub use budget::{close_budget, Contribution};
pub use conformance::{
    check_capability_vs_demand, check_param_match, check_refinement, check_role_kind, Capability,
};
pub use ledger::{ElecLedger, Ledger, MechLedger};
pub use nodes::{
    BoundaryEntry, Budget, FlowEdge, Frame, Impl, Interface, Mating, ParamKind, PromiseSlot,
    Reserve, SystemNode, Target,
};
pub use system::{check_boundary_subsumption, check_flow_ledger, check_target_reserves};
