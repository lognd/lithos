//! Pass 5b (WO-23): rigid statics over each system node's matings,
//! feeding computed reaction envelopes into obligations' `given.loads`
//! so promise obligations carry REAL computed loads, not declared-only
//! ones.
//!
//! Regolith reference: `docs/hematite/03-contracts-and-assemblies.md`
//! sec. 4 item 2, `docs/hematite/05-lowering.md` (L2 solves). The
//! solve itself lives in `regolith_ir::solve::statics` (AD-1:
//! deterministic compiler work); this pass only extracts the problem
//! from the contract graph and folds results into the obligations.
//!
//! DATA FORMATS (this WO-19-era increment, until `connect` bodies are
//! structurally lowered -- see the partial-lowering note in
//! `contracts.rs`): a mating is a support when its `align` text is
//! `at(<x>, <y>)` and its `dof_removed` entries name planar reaction
//! directions (`fx`/`fy`/`mz`); applied loads are mating `effects`
//! entries `load(fx=<f>, fy=<f>, mz=<f>, x=<f>, y=<f>)` (missing
//! components default to zero). A system whose matings carry
//! reaction directions but no parseable positions is SKIPPED (logged,
//! conservative): solving a partial free-body diagram would fabricate
//! reactions.

use regolith_diag::Diagnostic;
use regolith_ir::nodes::{Mating, SystemNode};
use regolith_ir::solve::statics::{
    solve_rigid_statics, AppliedLoad, Reaction, ReactionDir, StaticsProblem, Support,
};
use regolith_oblig::Obligation;

use crate::contracts::ContractGraph;

/// What the statics feed did: diagnostics from the solves plus the
/// count of envelope entries appended (for the pipeline log).
#[derive(Debug, Clone, Default)]
pub struct StaticsFeedReport {
    /// Determinacy/singularity diagnostics from each system's solve.
    pub diagnostics: Vec<Diagnostic>,
    /// Total `reaction(...)` entries appended across all obligations.
    pub entries_fed: usize,
}

/// Solve rigid statics for every system with populated matings and
/// append the computed reaction envelopes to `given.loads` of every
/// obligation whose `subject_ref` is that system's snapshot hash
/// (`system_subjects` maps system name -> subject hash). Systems in
/// graph order, matings in source order, reactions in solve order:
/// deterministic end to end (AD-6). INV-1 holds by construction --
/// computed loads are semantic inputs, so obligations fed here hash
/// differently from their declared-only forms.
#[must_use]
pub fn feed_interface_loads(
    graph: &ContractGraph,
    system_subjects: &[(String, String)],
    obligations: &mut [Obligation],
) -> StaticsFeedReport {
    let span = tracing::info_span!("lower.solve", systems = graph.systems.len());
    let _enter = span.enter();

    let mut report = StaticsFeedReport::default();

    for system in &graph.systems {
        if system.matings.is_empty() {
            continue;
        }
        let Some(problem) = statics_problem(system) else {
            tracing::debug!(
                system = %system.name,
                "matings carry no complete planar statics data; statics feed skipped"
            );
            continue;
        };

        let solution = solve_rigid_statics(&problem);
        report.diagnostics.extend(solution.diagnostics);
        if solution.reactions.is_empty() {
            continue;
        }

        let Some((_, subject)) = system_subjects
            .iter()
            .find(|(name, _)| *name == system.name)
        else {
            tracing::debug!(
                system = %system.name,
                "no entity snapshot for system; computed reactions have no obligations to feed"
            );
            continue;
        };

        let lines: Vec<String> = solution.reactions.iter().map(reaction_line).collect();
        for obligation in obligations.iter_mut().filter(|o| &o.subject_ref == subject) {
            obligation.given.loads.extend(lines.iter().cloned());
            report.entries_fed += lines.len();
        }
        tracing::info!(
            system = %system.name,
            reactions = lines.len(),
            "fed computed reaction envelopes into given.loads"
        );
    }

    report
}

/// The `given.loads` text for one computed reaction: outward bounds,
/// ryu-formatted (AD-6 float text discipline).
fn reaction_line(reaction: &Reaction) -> String {
    let mut lo = ryu::Buffer::new();
    let mut hi = ryu::Buffer::new();
    format!(
        "reaction({}.{}) = [{}, {}]",
        reaction.mating,
        reaction.dir.label(),
        lo.format(reaction.bounds.lo),
        hi.format(reaction.bounds.hi),
    )
}

/// Extract the planar statics problem from a system's matings, or
/// `None` when the data is incomplete: no support directions, no
/// applied loads, or a direction-carrying mating without a parseable
/// `at(x, y)` position (a partial free-body diagram is never solved).
fn statics_problem(system: &SystemNode) -> Option<StaticsProblem> {
    let mut supports = Vec::new();
    let mut loads = Vec::new();

    for mating in &system.matings {
        let dirs: Vec<ReactionDir> = mating
            .dof_removed
            .iter()
            .filter_map(|d| ReactionDir::parse(d))
            .collect();
        if !dirs.is_empty() {
            let Some((x, y)) = mating.align.as_deref().and_then(parse_at) else {
                tracing::debug!(
                    mating = %mating.name,
                    "mating removes planar DOF but has no `at(x, y)` position"
                );
                return None;
            };
            supports.push(Support {
                mating: mating.name.clone(),
                x,
                y,
                dirs,
            });
        }
        loads.extend(mating_loads(mating));
    }

    if supports.is_empty() || loads.is_empty() {
        return None;
    }
    Some(StaticsProblem {
        system: system.name.clone(),
        supports,
        loads,
    })
}

/// Parse an `at(<x>, <y>)` position text; `None` on any other shape.
fn parse_at(text: &str) -> Option<(f64, f64)> {
    let inner = text.trim().strip_prefix("at(")?.strip_suffix(')')?;
    let (x, y) = inner.split_once(',')?;
    Some((x.trim().parse().ok()?, y.trim().parse().ok()?))
}

/// The applied loads a mating's `effects` entries declare: each
/// `load(fx=<f>, fy=<f>, mz=<f>, x=<f>, y=<f>)` entry (components
/// optional, defaulting to zero) becomes one [`AppliedLoad`] named
/// after the mating. Malformed entries are skipped with a log.
fn mating_loads(mating: &Mating) -> Vec<AppliedLoad> {
    let mut out = Vec::new();
    for effect in &mating.effects {
        let Some(inner) = effect
            .trim()
            .strip_prefix("load(")
            .and_then(|rest| rest.strip_suffix(')'))
        else {
            continue;
        };
        let mut load = AppliedLoad {
            name: mating.name.clone(),
            fx: 0.0,
            fy: 0.0,
            mz: 0.0,
            x: 0.0,
            y: 0.0,
        };
        let mut ok = true;
        for item in inner.split(',') {
            let Some((key, value)) = item.split_once('=') else {
                ok = false;
                break;
            };
            let Ok(value) = value.trim().parse::<f64>() else {
                ok = false;
                break;
            };
            match key.trim() {
                "fx" => load.fx = value,
                "fy" => load.fy = value,
                "mz" => load.mz = value,
                "x" => load.x = value,
                "y" => load.y = value,
                other => {
                    tracing::debug!(mating = %mating.name, key = other, "unknown load component");
                    ok = false;
                    break;
                }
            }
        }
        if ok {
            out.push(load);
        } else {
            tracing::debug!(mating = %mating.name, effect = %effect, "malformed load effect skipped");
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::feed_interface_loads;
    use crate::contracts::ContractGraph;
    use regolith_diag::codes;
    use regolith_ir::nodes::{Mating, SystemNode};
    use regolith_oblig::{Claim, ClaimForm, Given, Obligation};

    fn mating(name: &str, align: Option<&str>, dof_removed: &[&str], effects: &[&str]) -> Mating {
        Mating {
            name: name.to_string(),
            sides: Vec::new(),
            align: align.map(str::to_string),
            dof_removed: dof_removed.iter().map(|s| (*s).to_string()).collect(),
            dof_kept: Vec::new(),
            couples: Vec::new(),
            preload: None,
            effects: effects.iter().map(|s| (*s).to_string()).collect(),
        }
    }

    fn system(name: &str, matings: Vec<Mating>) -> SystemNode {
        SystemNode {
            name: name.to_string(),
            is_system: false,
            parts: Vec::new(),
            boundary_datums: Vec::new(),
            connects: Vec::new(),
            matings,
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

    fn obligation(subject_ref: &str) -> Obligation {
        Obligation {
            claim: Claim {
                name: Some("envelope".to_string()),
                form: ClaimForm::Comparison {
                    lhs: "interface_envelope(BoltPattern)".to_string(),
                    op: "require".to_string(),
                    rhs: "loads within rated".to_string(),
                },
                forall: vec![],
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: vec![],
                model_pin: None,
            },
            subject_ref: subject_ref.to_string(),
            given: Given {
                materials: vec![],
                loads: vec!["tip: 1000N down".to_string()],
                backing: vec![],
                refs: vec![],
            },
            hints: vec![],
            sweep: None,
        }
    }

    /// The WO-23 bolted-bracket acceptance fixture, END TO END through
    /// the feed pass: matings carry the supports and the applied load;
    /// the interface envelope obligation ends up carrying the computed
    /// reactions (Ax = 0, Ay = -500, By = 1500 within outward
    /// rounding).
    #[test]
    fn bracket_reactions_land_in_the_envelope_obligations_given_loads() {
        let mut graph = ContractGraph::default();
        graph.systems.push(system(
            "BoltedBracket",
            vec![
                mating("bolt_a", Some("at(0, 0)"), &["fx", "fy"], &[]),
                mating("bolt_b", Some("at(0.2, 0)"), &["fy"], &[]),
                mating("tip", None, &[], &["load(fy=-1000, x=0.3)"]),
            ],
        ));
        let subjects = vec![("BoltedBracket".to_string(), "blake3:bb".to_string())];
        let mut obligations = vec![obligation("blake3:bb"), obligation("blake3:other")];

        let report = feed_interface_loads(&graph, &subjects, &mut obligations);

        assert!(report.diagnostics.is_empty(), "{:?}", report.diagnostics);
        assert_eq!(report.entries_fed, 3);
        let fed = &obligations[0].given.loads;
        assert_eq!(fed.len(), 4, "{fed:?}"); // 1 declared + 3 computed
        assert!(fed[1].starts_with("reaction(bolt_a.fx) = ["), "{}", fed[1]);
        assert!(
            fed[2].starts_with("reaction(bolt_a.fy) = [-500"),
            "{}",
            fed[2]
        );
        assert!(fed[3].starts_with("reaction(bolt_b.fy) = [1"), "{}", fed[3]);
        // The unrelated subject's obligation is untouched.
        assert_eq!(obligations[1].given.loads.len(), 1);
    }

    #[test]
    fn feeding_changes_the_obligation_hash_inv1() {
        // INV-1: computed loads are semantic inputs -- the fed
        // obligation must hash differently from its declared-only form.
        let mut graph = ContractGraph::default();
        graph.systems.push(system(
            "BoltedBracket",
            vec![
                mating("bolt_a", Some("at(0, 0)"), &["fx", "fy"], &[]),
                mating("bolt_b", Some("at(0.2, 0)"), &["fy"], &[]),
                mating("tip", None, &[], &["load(fy=-1000, x=0.3)"]),
            ],
        ));
        let subjects = vec![("BoltedBracket".to_string(), "blake3:bb".to_string())];
        let mut obligations = vec![obligation("blake3:bb")];
        let before = obligations[0].content_hash();
        let _ = feed_interface_loads(&graph, &subjects, &mut obligations);
        assert_ne!(before, obligations[0].content_hash());
    }

    #[test]
    fn solve_diagnostics_surface_through_the_report() {
        // An under-constrained system: the solve's ledger diagnostic
        // must reach the pipeline, and nothing is fed.
        let mut graph = ContractGraph::default();
        graph.systems.push(system(
            "Loose",
            vec![
                mating("pin", Some("at(0, 0)"), &["fy"], &[]),
                mating("tip", None, &[], &["load(fy=-10, x=1)"]),
            ],
        ));
        let subjects = vec![("Loose".to_string(), "blake3:ll".to_string())];
        let mut obligations = vec![obligation("blake3:ll")];

        let report = feed_interface_loads(&graph, &subjects, &mut obligations);

        assert_eq!(report.entries_fed, 0);
        assert_eq!(report.diagnostics.len(), 1);
        assert_eq!(report.diagnostics[0].code, codes::LEDGER_IMBALANCE);
        assert_eq!(obligations[0].given.loads.len(), 1);
    }

    #[test]
    fn a_positionless_support_skips_the_system_conservatively() {
        // A mating that removes planar DOF but carries no at(x, y)
        // position: solving the partial diagram would fabricate
        // reactions, so the system is skipped entirely.
        let mut graph = ContractGraph::default();
        graph.systems.push(system(
            "Partial",
            vec![
                mating("bolt_a", None, &["fx", "fy"], &[]),
                mating("bolt_b", Some("at(0.2, 0)"), &["fy"], &[]),
                mating("tip", None, &[], &["load(fy=-1000, x=0.3)"]),
            ],
        ));
        let subjects = vec![("Partial".to_string(), "blake3:pp".to_string())];
        let mut obligations = vec![obligation("blake3:pp")];

        let report = feed_interface_loads(&graph, &subjects, &mut obligations);

        assert!(report.diagnostics.is_empty());
        assert_eq!(report.entries_fed, 0);
        assert_eq!(obligations[0].given.loads.len(), 1);
    }

    #[test]
    fn empty_matings_are_a_no_op() {
        let mut graph = ContractGraph::default();
        graph.systems.push(system("Bare", Vec::new()));
        let mut obligations = vec![obligation("blake3:xx")];
        let report = feed_interface_loads(&graph, &[], &mut obligations);
        assert!(report.diagnostics.is_empty());
        assert_eq!(report.entries_fed, 0);
    }
}
