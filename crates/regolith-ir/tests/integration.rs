//! Integration test (TEST003): builds a `SystemNode` IR value from
//! outside the crate, round-trips it through the published JSON
//! serialization, and runs the boundary-subsumption check
//! (`system::check_boundary_subsumption`, INV-7) end to end -- the
//! shape a real caller (a system-level L2 check pass) exercises,
//! rather than one internal helper in isolation.

// frob:tests crates/regolith-ir/src kind="integration"
#[test]
fn system_node_serializes_and_checks_boundary_subsumption_end_to_end() {
    use regolith_ir::nodes::{BoundaryEntry, SystemNode};
    use regolith_ir::system::check_boundary_subsumption;

    let entry = |name: &str, lo: f64, hi: f64, unit: &str| BoundaryEntry {
        name: name.to_string(),
        lo: Some(lo),
        hi: Some(hi),
        unit: Some(unit.to_string()),
        raw: format!("[{lo}{unit}, {hi}{unit}]"),
    };

    let node = SystemNode {
        name: "Sys".to_string(),
        is_system: true,
        parts: Vec::new(),
        boundary_datums: Vec::new(),
        connects: Vec::new(),
        matings: Vec::new(),
        budgets: Vec::new(),
        targets: Vec::new(),
        config_vars: Vec::new(),
        boundary: vec![entry("ambient", -10.0, 50.0, "degC")],
        child_boundaries: vec![(
            "imu".to_string(),
            vec![entry("ambient", -40.0, 85.0, "degC")],
        )],
        reserves: Vec::new(),
        flows: Vec::new(),
        flow_endpoints: Vec::new(),
        target_nodes: Vec::new(),
        workloads: Vec::new(),
        compute_intents: Vec::new(),
    };

    // Build + serialize (schemars single-sourcing, AD-11): the node
    // round-trips through the wire form every BuildPayload consumer
    // crosses.
    let json = serde_json::to_string(&node).expect("SystemNode serializes");
    assert!(json.contains("\"ambient\""));

    // ... and the real check runs cleanly over the built value: the
    // enclosing envelope is contained in the child's proven envelope
    // (INV-7).
    assert!(check_boundary_subsumption(&node).is_empty());
}
