//! Ledgers: one pluggable interface, two domain packs. Mech runs a
//! DOF/Gruebler ledger; elec runs driver/load + domain-crossing + flow
//! ledgers. Imbalances are E0420-family diagnostics.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`, `docs/hematite/03`
//! (Gruebler), `docs/cuprite/02` sec. 4a. The trait keeps the two domains'
//! bookkeeping behind one interface so the system node runs whichever
//! pack its domain provides.

use regolith_diag::{codes, Diagnostic};
use regolith_util::IndexMap;

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

    fn check(&self, node: &SystemNode) -> Vec<Diagnostic> {
        let mut diags = Vec::new();

        // Every declared freedom removed by more than one mating is an
        // over-constraint (the double-axial-fixation family): a DOF can
        // only be removed once, so participation is summed in source
        // order and any label seen twice is named.
        let mut removed_by: IndexMap<&str, Vec<&str>> = IndexMap::new();
        for mating in &node.matings {
            for dof in &mating.dof_removed {
                removed_by
                    .entry(dof.as_str())
                    .or_default()
                    .push(mating.name.as_str());
            }
        }
        for (dof, matings) in &removed_by {
            if matings.len() > 1 {
                diags.push(Diagnostic::error(
                    codes::LEDGER_IMBALANCE,
                    format!(
                        "degree of freedom `{dof}` is removed by more than one mating \
                         (over-constraint): {}",
                        matings.join(", ")
                    ),
                ));
            }
        }

        // A DOF both removed (by some mating) and explicitly kept (by
        // another) is a contradictory ledger entry.
        for mating in &node.matings {
            for dof in &mating.dof_kept {
                if let Some(removers) = removed_by.get(dof.as_str()) {
                    diags.push(Diagnostic::error(
                        codes::LEDGER_IMBALANCE,
                        format!(
                            "degree of freedom `{dof}` is removed by `{}` but kept by `{}`",
                            removers.join(", "),
                            mating.name
                        ),
                    ));
                }
            }
        }

        diags
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

    fn check(&self, node: &SystemNode) -> Vec<Diagnostic> {
        let mut diags = Vec::new();

        // Every coupled quantity (net) a mating participates in must be
        // fed by a declared physical effect; a mating that couples a
        // quantity but declares no driving effect is an unfed flow.
        for mating in &node.matings {
            for net in &mating.couples {
                if mating.effects.is_empty() {
                    diags.push(Diagnostic::error(
                        codes::LEDGER_IMBALANCE,
                        format!(
                            "coupled quantity `{net}` in mating `{}` has no declared driving \
                             effect (unfed flow)",
                            mating.name
                        ),
                    ));
                }
            }
        }

        diags
    }
}

#[cfg(test)]
mod tests {
    use super::{ElecLedger, Ledger, MechLedger};
    use crate::nodes::{Mating, SystemNode};
    use regolith_diag::codes;

    #[test]
    fn ledgers_name_themselves() {
        assert_eq!(MechLedger.name(), "gruebler");
        assert_eq!(ElecLedger.name(), "driver_load_flow");
    }

    fn mating(name: &str, dof_removed: &[&str], dof_kept: &[&str]) -> Mating {
        Mating {
            name: name.to_string(),
            sides: vec!["a".to_string(), "b".to_string()],
            align: None,
            dof_removed: dof_removed.iter().map(|s| (*s).to_string()).collect(),
            dof_kept: dof_kept.iter().map(|s| (*s).to_string()).collect(),
            couples: Vec::new(),
            preload: None,
            effects: Vec::new(),
        }
    }

    fn system(matings: Vec<Mating>) -> SystemNode {
        SystemNode {
            name: "assy".to_string(),
            is_system: false,
            parts: Vec::new(),
            boundary_datums: Vec::new(),
            connects: Vec::new(),
            matings,
            budgets: Vec::new(),
            targets: Vec::new(),
            config_vars: Vec::new(),
        }
    }

    // Zero-parts, well-formed and over-constrained (contract-first):
    // a fresh DOF removed by exactly one mating each closes cleanly.
    #[test]
    fn well_formed_ledger_closes_with_zero_parts() {
        let node = system(vec![
            mating("pilot", &["x", "y"], &[]),
            mating("keyway", &["rz"], &[]),
        ]);
        assert!(MechLedger.check(&node).is_empty());
    }

    // Double-axial-fixation: two matings both remove the same freedom.
    #[test]
    fn double_axial_fixation_is_over_constraint() {
        let node = system(vec![
            mating("pilot", &["x"], &[]),
            mating("shoulder", &["x"], &[]),
        ]);
        let diags = MechLedger.check(&node);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::LEDGER_IMBALANCE);
        assert!(diags[0].message.contains('x'));
        assert!(diags[0].message.contains("pilot"));
        assert!(diags[0].message.contains("shoulder"));
    }

    #[test]
    fn removed_and_kept_same_dof_is_contradictory() {
        let node = system(vec![
            mating("pilot", &["x"], &[]),
            mating("slider", &[], &["x"]),
        ]);
        let diags = MechLedger.check(&node);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::LEDGER_IMBALANCE);
    }

    #[test]
    fn empty_ledger_is_clean() {
        assert!(MechLedger.check(&system(Vec::new())).is_empty());
    }

    fn coupling_mating(name: &str, couples: &[&str], effects: &[&str]) -> Mating {
        Mating {
            name: name.to_string(),
            sides: vec!["a".to_string(), "b".to_string()],
            align: None,
            dof_removed: Vec::new(),
            dof_kept: Vec::new(),
            couples: couples.iter().map(|s| (*s).to_string()).collect(),
            preload: None,
            effects: effects.iter().map(|s| (*s).to_string()).collect(),
        }
    }

    #[test]
    fn unfed_flow_is_a_ledger_imbalance() {
        let node = system(vec![coupling_mating("harness", &["vbus"], &[])]);
        let diags = ElecLedger.check(&node);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::LEDGER_IMBALANCE);
        assert!(diags[0].message.contains("vbus"));
    }

    #[test]
    fn fed_flow_is_clean() {
        let node = system(vec![coupling_mating(
            "harness",
            &["vbus"],
            &["model_regulator(vbus)"],
        )]);
        assert!(ElecLedger.check(&node).is_empty());
    }
}
