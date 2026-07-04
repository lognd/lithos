//! The implementation-free contract graph: the IR nodes at L2, the
//! level where a system verifies with zero artifacts.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`, `docs/mech/03`,
//! `docs/elec/02` sec. 4a. Interfaces carry demands and promise slots
//! (value sources); impls bind roles as queries and may only NARROW
//! promises (widening is rejected, WO-12 / conformance); matings name
//! sides and remove/keep DOF; system/assembly nodes carry budgets,
//! reserves, targets, and config variables.

use rockhead_qty::ValueSource;
use rockhead_sem::Query;
use serde::{Deserialize, Serialize};

/// A reference frame an interface or mating is expressed in.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Frame {
    /// Frame name.
    pub name: String,
    /// The datum the frame anchors to.
    pub datum: String,
}

/// A named promise slot on an interface: a value the interface promises,
/// backed by a value source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromiseSlot {
    /// Slot name (`stiffness`, `i_max`).
    pub name: String,
    /// The value source deciding the promised value.
    pub value: ValueSource,
}

/// Distinguishes compile-time interface parameters (`<params>`,
/// monomorphizing) from runtime promise/demand fields (`params:`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParamKind {
    /// `<params>`: compile-time type parameters (monomorphized).
    Type,
    /// `params:`: runtime demand/promise fields.
    Field,
}

/// A contract interface: roles, demands, and promise slots.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Interface {
    /// Interface name.
    pub name: String,
    /// Role names the interface exposes.
    pub roles: Vec<String>,
    /// Demand field names (what the interface requires of its context).
    pub demands: Vec<String>,
    /// Promise slots (what it guarantees), each a value source.
    pub promises: Vec<PromiseSlot>,
    /// The `spec:` body, kept as an opaque island reference (WO-05).
    pub spec_island: Option<String>,
}

/// An implementation of an interface: role bindings as queries plus
/// inline promise refinement (narrowing only).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Impl {
    /// The interface this implements.
    pub interface: String,
    /// Role name -> the query that binds it.
    pub role_bindings: Vec<(String, Query)>,
    /// Inline promise refinements (must narrow, never widen; checked in
    /// `conformance`).
    pub refinements: Vec<PromiseSlot>,
}

/// A mating between two artifacts: named sides, alignment, and the DOF it
/// removes and keeps.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mating {
    /// Mating name.
    pub name: String,
    /// The two (or more) named sides.
    pub sides: Vec<String>,
    /// Alignment record (reuses the WO-05 align AST, kept as text here).
    pub align: Option<String>,
    /// Degrees of freedom removed by the mating.
    pub dof_removed: Vec<String>,
    /// Degrees of freedom deliberately kept.
    pub dof_kept: Vec<String>,
    /// Coupled quantities across the mating.
    pub couples: Vec<String>,
    /// Preload value source, if any.
    pub preload: Option<ValueSource>,
    /// Physical effects, as signature references (harness contracts).
    pub effects: Vec<String>,
}

/// A budget declared at a system/assembly node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Budget {
    /// Budget name (`mass`, `energy`, `noise`).
    pub name: String,
    /// The limit value source.
    pub limit: ValueSource,
    /// Reserve held back for targets.
    pub reserve: Option<ValueSource>,
}

/// A system or assembly node: parts, boundary datums, connections,
/// budgets, reserves, targets, and config variables.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemNode {
    /// Node name.
    pub name: String,
    /// Whether this is a system (true) or an assembly (false).
    pub is_system: bool,
    /// Contained part/child names.
    pub parts: Vec<String>,
    /// Boundary datums (`at=` anchors).
    pub boundary_datums: Vec<String>,
    /// Connections between parts.
    pub connects: Vec<String>,
    /// Declared budgets.
    pub budgets: Vec<Budget>,
    /// Named targets (build variants).
    pub targets: Vec<String>,
    /// Config variables, namespaced by their exposer.
    pub config_vars: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::{Interface, ParamKind, PromiseSlot};
    use rockhead_qty::ValueSource;

    #[test]
    fn interface_round_trips_json() {
        let iface = Interface {
            name: "seat".to_string(),
            roles: vec!["bore".to_string()],
            demands: vec!["stiffness".to_string()],
            promises: vec![PromiseSlot {
                name: "runout".to_string(),
                value: ValueSource::Free,
            }],
            spec_island: None,
        };
        let json = serde_json::to_string(&iface).unwrap();
        let back: Interface = serde_json::from_str(&json).unwrap();
        assert_eq!(back.name, "seat");
        assert_eq!(back.promises.len(), 1);
    }

    #[test]
    fn param_kind_distinguishes_type_and_field() {
        assert_ne!(ParamKind::Type, ParamKind::Field);
    }
}
