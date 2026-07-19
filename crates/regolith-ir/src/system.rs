//! System-node L2 checks: boundary subsumption (INV-7), target/reserve
//! additivity (INV-8), and the system-flow ledger (INV-15).
//!
//! Regolith reference: `docs/spec/regolith/04-contracts.md` sec. 4-6,
//! `docs/spec/regolith/13-invariants.md` INV-7/8/15. Each check runs over a
//! populated [`SystemNode`] and returns `regolith-diag` diagnostics
//! (values, AD-7). Every check is CONSERVATIVE: it flags a violation
//! only from data the source actually declared, and leaves anything it
//! cannot compare (a non-numeric envelope, a mismatched unit, a nominal
//! reserve draw) indeterminate rather than asserting balance.

use regolith_diag::{codes, Diagnostic};
use regolith_util::IndexSet;

use crate::nodes::{BoundaryEntry, SystemNode};

/// INV-7 boundary subsumption: an imported/child artifact arrives proven
/// under its OWN `boundary:`; for every boundary quantity both the child
/// and this enclosing node declare, the enclosing node's envelope must be
/// CONTAINED in the child's proven envelope (regolith/04 sec. 6 --
/// containment is uniformly the safe direction because boundary entries
/// are tolerated envelopes). A wider enclosing envelope means the child
/// would be used outside what it was proven under: `E0407`.
#[must_use]
// frob:doc docs/modules/regolith-ir.md#system
// frob:invariant INV-007
pub fn check_boundary_subsumption(node: &SystemNode) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for (child_name, child_entries) in &node.child_boundaries {
        for parent in &node.boundary {
            let Some(child) = child_entries.iter().find(|c| c.name == parent.name) else {
                continue;
            };
            if let Some(reason) = envelope_escapes(parent, child) {
                tracing::info!(
                    system = %node.name,
                    child = %child_name,
                    quantity = %parent.name,
                    reason,
                    "enclosing boundary is not contained in the child's proven envelope (INV-7)"
                );
                diags.push(Diagnostic::error(
                    codes::BOUNDARY_NOT_SUBSUMED,
                    format!(
                        "system `{}`: its `{}` boundary ({}) is not contained in the proven \
                         boundary of `{}` ({}); evidence cannot transfer outside the envelope it \
                         was proven in",
                        node.name, parent.name, parent.raw, child_name, child.raw
                    ),
                ));
            }
        }
    }
    diags
}

/// Whether the enclosing `parent` envelope escapes the child's proven
/// envelope for the same quantity. Only comparable when both carry
/// numeric bounds in the SAME unit; an incomparable pair is `None` (left
/// indeterminate -- INV-7 never assumes containment it cannot prove).
/// Returns a short reason string when the parent is wider on either end.
fn envelope_escapes(parent: &BoundaryEntry, child: &BoundaryEntry) -> Option<&'static str> {
    if parent.unit != child.unit {
        return None;
    }
    let (plo, phi, clo, chi) = (parent.lo?, parent.hi?, child.lo?, child.hi?);
    if plo < clo {
        Some("its lower bound is below the child's")
    } else if phi > chi {
        Some("its upper bound is above the child's")
    } else {
        None
    }
}

/// INV-8 reserve accounting: build targets are additive overlays that
/// consume only declared reserves; exceeding a reserve is `E0432`-family,
/// naming the target (regolith/04 sec. 6). For each reserve with a
/// quantified magnitude, the numeric draws every target declares against
/// it are summed; a sum over the reserve is over-allocation. Nominal
/// draws (`draws: reserves`) carry no magnitude and are not summed -- the
/// check bites only on quantified over-allocation it can prove.
#[must_use]
// frob:doc docs/modules/regolith-ir.md#system
// frob:invariant INV-008
pub fn check_target_reserves(node: &SystemNode) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for reserve in &node.reserves {
        let Some(available) = reserve.amount else {
            continue;
        };
        let mut total = 0.0;
        let mut drawers: Vec<String> = Vec::new();
        for target in &node.target_nodes {
            for draw in &target.draws {
                if draw.name == reserve.name {
                    if let Some(amount) = draw.amount {
                        total += amount;
                        drawers.push(format!("{} ({amount})", target.name));
                    }
                }
            }
        }
        if !drawers.is_empty() && total > available {
            tracing::info!(
                system = %node.name,
                reserve = %reserve.name,
                total,
                available,
                "target draws exceed a declared reserve (INV-8 over-allocation)"
            );
            diags.push(Diagnostic::error(
                codes::BUDGET_CANNOT_CLOSE,
                format!(
                    "reserve `{}` of system `{}` is over-allocated: targets draw {total} against \
                     a reserve of {available} (drawers: {})",
                    reserve.name,
                    node.name,
                    drawers.join(", ")
                ),
            ));
        }
    }
    diags
}

/// INV-15 system-flow ledger: every `flows:` edge endpoint must be a
/// declared participant (an intent, boundary, or reserve name collected
/// into `flow_endpoints`); a flow to or from an undeclared endpoint is
/// participation outside the ledger -- a conservation leak, `E0420`
/// (regolith/13 INV-15: nothing participates outside the ledger).
#[must_use]
// frob:doc docs/modules/regolith-ir.md#system
// frob:invariant INV-015
pub fn check_flow_ledger(node: &SystemNode) -> Vec<Diagnostic> {
    let declared: IndexSet<&str> = node.flow_endpoints.iter().map(String::as_str).collect();
    let mut diags = Vec::new();
    for edge in &node.flows {
        for (role, name) in [("source", &edge.from), ("destination", &edge.to)] {
            if !declared.contains(name.as_str()) {
                tracing::info!(
                    system = %node.name,
                    endpoint = %name,
                    role,
                    "flow endpoint is not a declared ledger participant (INV-15 leak)"
                );
                diags.push(Diagnostic::error(
                    codes::LEDGER_IMBALANCE,
                    format!(
                        "flow `{} -> {}` in system `{}`: {role} `{name}` is not a declared \
                         participant (intent/boundary/reserve); nothing may participate outside \
                         the flow ledger",
                        edge.from, edge.to, node.name
                    ),
                ));
            }
        }
    }
    diags
}

/// EOPEN-15 rule 1: the realization ledger. Every compute intent
/// (`node.compute_intents`) must be realized by EXACTLY ONE workload
/// across the system's computers -- a ledger, like flows (cuprite/05
/// sec. 1). Zero realizers is NOT flagged here: rule 3 completes it by
/// allocation (a derived workload), the sound default this check must
/// not race with. Two-or-more realizers of the same intent IS a
/// violation, `E0433`, naming both sides.
#[must_use]
// frob:doc docs/modules/regolith-ir.md#system
pub fn check_realization_ledger(node: &SystemNode) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for intent in &node.compute_intents {
        let realizers: Vec<&str> = node
            .workloads
            .iter()
            .filter(|w| !w.derived && w.realizes.iter().any(|r| r == intent))
            .map(|w| w.name.as_str())
            .collect();
        if realizers.len() > 1 {
            tracing::info!(
                system = %node.name,
                intent = %intent,
                realizers = ?realizers,
                "compute intent realized by more than one workload (EOPEN-15 rule 1)"
            );
            diags.push(Diagnostic::error(
                codes::REALIZATION_NOT_EXACTLY_ONE,
                format!(
                    "system `{}`: compute intent `{}` is realized by {} workloads ({}); every \
                     compute intent must be realized by exactly one workload",
                    node.name,
                    intent,
                    realizers.len(),
                    realizers.join(", ")
                ),
            ));
        }
    }
    diags
}

#[cfg(test)]
mod tests {
    use super::{
        check_boundary_subsumption, check_flow_ledger, check_realization_ledger,
        check_target_reserves,
    };
    use crate::nodes::{BoundaryEntry, FlowEdge, Reserve, SystemNode, Target, Workload};
    use regolith_diag::codes;

    fn node() -> SystemNode {
        SystemNode {
            name: "Sys".to_string(),
            is_system: true,
            parts: Vec::new(),
            boundary_datums: Vec::new(),
            connects: Vec::new(),
            matings: Vec::new(),
            budgets: Vec::new(),
            targets: Vec::new(),
            config_vars: Vec::new(),
            boundary: Vec::new(),
            child_boundaries: Vec::new(),
            reserves: Vec::new(),
            flows: Vec::new(),
            flow_endpoints: Vec::new(),
            target_nodes: Vec::new(),
            workloads: Vec::new(),
            compute_intents: Vec::new(),
        }
    }

    fn workload(name: &str, realizes: &[&str]) -> Workload {
        Workload {
            name: name.to_string(),
            kind: "loop".to_string(),
            realizes: realizes.iter().map(|s| (*s).to_string()).collect(),
            derived: false,
        }
    }

    fn entry(name: &str, lo: f64, hi: f64, unit: &str) -> BoundaryEntry {
        BoundaryEntry {
            name: name.to_string(),
            lo: Some(lo),
            hi: Some(hi),
            unit: Some(unit.to_string()),
            raw: format!("[{lo}{unit}, {hi}{unit}]"),
        }
    }

    // frob:tests crates/regolith-ir/src/system.rs::check_boundary_subsumption kind="unit"
    #[test]
    fn boundary_within_child_is_clean() {
        let mut n = node();
        n.boundary = vec![entry("ambient", -10.0, 50.0, "degC")];
        n.child_boundaries = vec![(
            "imu".to_string(),
            vec![entry("ambient", -40.0, 85.0, "degC")],
        )];
        assert!(check_boundary_subsumption(&n).is_empty());
    }

    #[test]
    fn boundary_wider_than_child_fails() {
        let mut n = node();
        // Enclosing ambient is WIDER than the child's proven envelope.
        n.boundary = vec![entry("ambient", -40.0, 85.0, "degC")];
        n.child_boundaries = vec![(
            "imu".to_string(),
            vec![entry("ambient", -10.0, 50.0, "degC")],
        )];
        let d = check_boundary_subsumption(&n);
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].code, codes::BOUNDARY_NOT_SUBSUMED);
    }

    #[test]
    fn mismatched_unit_is_indeterminate_not_a_false_pass_or_fail() {
        let mut n = node();
        n.boundary = vec![entry("ambient", -40.0, 85.0, "K")];
        n.child_boundaries = vec![(
            "imu".to_string(),
            vec![entry("ambient", -10.0, 50.0, "degC")],
        )];
        assert!(check_boundary_subsumption(&n).is_empty());
    }

    // frob:tests crates/regolith-ir/src/system.rs::check_target_reserves kind="unit"
    #[test]
    fn reserve_within_budget_is_clean() {
        let mut n = node();
        n.reserves = vec![Reserve {
            name: "gpio".to_string(),
            amount: Some(4.0),
            raw: "4".to_string(),
        }];
        n.target_nodes = vec![Target {
            name: "debug".to_string(),
            of_system: "Sys".to_string(),
            draws: vec![Reserve {
                name: "gpio".to_string(),
                amount: Some(3.0),
                raw: "3".to_string(),
            }],
        }];
        assert!(check_target_reserves(&n).is_empty());
    }

    #[test]
    fn reserve_over_allocation_fails() {
        let mut n = node();
        n.reserves = vec![Reserve {
            name: "gpio".to_string(),
            amount: Some(4.0),
            raw: "4".to_string(),
        }];
        n.target_nodes = vec![Target {
            name: "debug".to_string(),
            of_system: "Sys".to_string(),
            draws: vec![Reserve {
                name: "gpio".to_string(),
                amount: Some(5.0),
                raw: "5".to_string(),
            }],
        }];
        let d = check_target_reserves(&n);
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].code, codes::BUDGET_CANNOT_CLOSE);
        assert!(d[0].message.contains("debug"));
    }

    // frob:tests crates/regolith-ir/src/system.rs::check_flow_ledger kind="unit"
    #[test]
    fn flow_between_declared_endpoints_is_clean() {
        let mut n = node();
        n.flow_endpoints = vec!["sense".to_string(), "decide".to_string()];
        n.flows = vec![FlowEdge {
            from: "sense".to_string(),
            to: "decide".to_string(),
        }];
        assert!(check_flow_ledger(&n).is_empty());
    }

    #[test]
    fn flow_to_undeclared_endpoint_is_a_leak() {
        let mut n = node();
        n.flow_endpoints = vec!["sense".to_string(), "decide".to_string()];
        n.flows = vec![FlowEdge {
            from: "decide".to_string(),
            to: "ghost".to_string(),
        }];
        let d = check_flow_ledger(&n);
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].code, codes::LEDGER_IMBALANCE);
        assert!(d[0].message.contains("ghost"));
    }

    // frob:tests crates/regolith-ir/src/system.rs::check_realization_ledger kind="unit"
    #[test]
    fn exactly_one_realization_is_clean() {
        let mut n = node();
        n.compute_intents = vec!["decide".to_string()];
        n.workloads = vec![workload("att", &["decide"])];
        assert!(check_realization_ledger(&n).is_empty());
    }

    #[test]
    fn zero_realization_is_not_a_ledger_violation() {
        // Rule 3 completes an unrealized compute intent by derivation;
        // the ledger check itself must not flag zero realizers.
        let mut n = node();
        n.compute_intents = vec!["decide".to_string()];
        n.workloads = Vec::new();
        assert!(check_realization_ledger(&n).is_empty());
    }

    #[test]
    fn double_realization_is_a_ledger_violation() {
        let mut n = node();
        n.compute_intents = vec!["decide".to_string()];
        n.workloads = vec![
            workload("att", &["decide"]),
            workload("backup", &["decide"]),
        ];
        let d = check_realization_ledger(&n);
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].code, codes::REALIZATION_NOT_EXACTLY_ONE);
        assert!(d[0].message.contains("att"));
        assert!(d[0].message.contains("backup"));
    }

    #[test]
    fn derived_workload_realizer_is_excluded_from_the_ledger_count() {
        // A rule-3 DERIVED workload never itself double-counts against
        // the ledger it exists to satisfy.
        let mut n = node();
        n.compute_intents = vec!["decide".to_string()];
        n.workloads = vec![Workload {
            name: "decide".to_string(),
            kind: "derived".to_string(),
            realizes: vec!["decide".to_string()],
            derived: true,
        }];
        assert!(check_realization_ledger(&n).is_empty());
    }
}
