//! T1 conformance and refinement checking: role-kind by construction,
//! parameter match, capability-vs-demand, and the promise-refinement
//! direction rule.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. Refinement is
//! directional: a refined interface makes TIGHTER demands on itself and
//! STRONGER promises to consumers, so an impl may only NARROW a promise.
//! Widening a promise is rejected (WO-12 acceptance). Capability tables
//! are WO-16 data; a static in-memory pack backs the tests.

use rockhead_diag::Diagnostic;

use crate::nodes::{Impl, Interface, PromiseSlot};

/// Check that an impl's role bindings resolve to entities of the kinds
/// the interface's roles require (role-kind by construction).
#[must_use]
pub fn check_role_kind(_iface: &Interface, _imp: &Impl) -> Vec<Diagnostic> {
    todo!("STUB WO-12: each role binding's query result kind must match the role's declared kind")
}

/// Check that an impl's parameters match the interface's; a binding may
/// pin a free variable but may not conflict with a fixed one.
#[must_use]
pub fn check_param_match(_iface: &Interface, _imp: &Impl) -> Vec<Diagnostic> {
    todo!("STUB WO-12: match params; binding may pin a free var; conflict with a literal -> diag")
}

/// A minimal capability record for the static test pack (WO-16 supplies
/// the real table).
#[derive(Debug, Clone)]
pub struct Capability {
    /// The demand name this capability answers.
    pub demand: String,
    /// Whether the capability meets the demand.
    pub meets: bool,
}

/// Check demanded capabilities against supplied ones (E0410 when a
/// demand exceeds the supply).
#[must_use]
pub fn check_capability_vs_demand(
    _demands: &[String],
    _supplied: &[Capability],
) -> Vec<Diagnostic> {
    todo!("STUB WO-12: for each demand, look up capability; unmet -> E0410 capability-vs-demand")
}

/// Check promise refinement direction: the refined promises must be at
/// least as strong (narrower) as the base. A WIDENED promise is rejected.
#[must_use]
pub fn check_refinement(_base: &[PromiseSlot], _refined: &[PromiseSlot]) -> Vec<Diagnostic> {
    todo!("STUB WO-12: refined promise must narrow base; widening -> refinement-direction diag")
}

#[cfg(test)]
mod tests {
    // Widening rejected / narrowing accepted, double-axial-fixation and
    // unfed-flow E0420 land with the check bodies (WO-12 acceptance).
    #[test]
    #[ignore = "WO-12 impl: conformance + refinement bodies pending"]
    fn refinement_direction_enforced() {}
}
