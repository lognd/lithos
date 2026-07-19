// frob:waive TEST003 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
//! Contract IR: interfaces, matings, ledgers, budgets, L2 arithmetic.
//!
//! Regolith reference: `docs/spec/regolith/04-contracts.md`, `docs/spec/hematite/03`,
//! `docs/spec/cuprite/02` sec. 4a. This is the implementation-free contract
//! graph and its checks: the level (L2) where a system verifies with
//! zero artifacts. Ledgers and conformance run on these nodes before any
//! impl or realizer exists (WO-12).

pub mod block_requirement;
pub mod budget;
pub mod conformance;
pub mod feature_program;
pub mod ledger;
pub mod nodes;
pub mod sketch;
#[cfg(feature = "solve")]
pub mod solve;
pub mod system;
pub mod test_decl;

pub use block_requirement::{BlockRequirement, CapabilityDemand};
pub use budget::{close_budget, Contribution};
pub use conformance::{
    check_capability_vs_demand, check_param_match, check_refinement, check_role_kind, Capability,
};
pub use feature_program::{FeatureOp, FeatureProgram, ResolvedFeatureParam};
pub use ledger::{ElecLedger, Ledger, MechLedger};
pub use nodes::{
    BoundaryEntry, Budget, FlowEdge, Frame, Impl, Interface, Mating, ParamKind, PromiseSlot,
    Reserve, SystemNode, Target, Workload,
};
pub use sketch::{sketch_closure_from_walk, SketchClosure, WalkPromotion};
pub use system::{
    check_boundary_subsumption, check_flow_ledger, check_realization_ledger, check_target_reserves,
};
pub use test_decl::{TestDeclPayload, TestExpectationPayload};
