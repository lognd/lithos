//! The lumped stiffness network (WO-23): the L2 solve behind
//! `mech.stiffness(...)` claims -- joint/member stiffnesses assembled
//! into a scalar spring network, solved for effective stiffness at a
//! node so fat-margin stiffness claims discharge statically.
//!
//! Regolith reference: `docs/spec/hematite/03-contracts-and-assemblies.md`
//! sec. 4 item 3 ("stiffness network from promised stiffnesses +
//! connection models ... conservative by construction"). One scalar
//! DOF per node (the lumped L2 abstraction); the full vector problem
//! is harness physics (AD-1). Because the lumped network is a
//! CONSERVATIVE (lower-bound) stiffness estimate, this solve can
//! discharge a `>=` claim with fat margin but can never prove one
//! violated -- a thin margin defers to the harness as indeterminate.

use regolith_diag::{codes, Diagnostic};
use regolith_util::IndexMap;
use serde::{Deserialize, Serialize};

use super::{residual_tol, solve_verified, OutwardBounds};

/// One lumped spring between two named nodes.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-ir.md#solve
pub struct Spring {
    /// Spring name (the mating/member it models).
    pub name: String,
    /// First endpoint node.
    pub a: String,
    /// Second endpoint node.
    pub b: String,
    /// Spring stiffness (must be finite and positive).
    pub k: f64,
}

/// A lumped scalar spring network: springs in source order plus the
/// grounded (fixed) node names.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-ir.md#solve
pub struct StiffnessNetwork {
    /// The system/assembly the network was assembled from.
    pub system: String,
    /// Grounded node names (zero displacement).
    pub grounds: Vec<String>,
    /// Springs in source order (AD-6: fixed assembly order).
    pub springs: Vec<Spring>,
}

/// The effective-stiffness solve result. `k_eff` is `None` when a
/// diagnostic prevented the solve; it is never non-finite.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-ir.md#solve
pub struct StiffnessSolution {
    /// Effective stiffness at the queried node, outward-rounded.
    pub k_eff: Option<OutwardBounds>,
    /// Singular/disconnected-network and bad-input diagnostics.
    pub diagnostics: Vec<Diagnostic>,
}

/// Solve the network for the effective stiffness at node `at`: apply a
/// unit force there, solve `K u = f` over the free nodes, and return
/// `1 / u_at`, outward-rounded (AD-6).
///
/// Free-node indexing is insertion order over the springs' endpoints
/// (source order, never hash order). A singular stiffness matrix -- a
/// free node with no load path to ground -- is an `E0440` diagnostic,
/// as are a non-positive/non-finite spring constant, an unknown query
/// node, and a grounded query node. Never a panic, never NaN.
#[must_use]
// frob:doc docs/modules/regolith-ir.md#solve
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn effective_stiffness(net: &StiffnessNetwork, at: &str) -> StiffnessSolution {
    let span = tracing::info_span!("solve.stiffness", system = %net.system, at);
    let _enter = span.enter();

    let mut solution = StiffnessSolution::default();

    for s in &net.springs {
        if !(s.k.is_finite() && s.k > 0.0) {
            tracing::warn!(spring = %s.name, k = s.k, "non-positive or non-finite stiffness");
            solution.diagnostics.push(Diagnostic::error(
                codes::SINGULAR_SYSTEM,
                format!(
                    "stiffness network for `{}`: spring `{}` has a non-positive or \
                     non-finite stiffness ({}); the network solve cannot run",
                    net.system, s.name, s.k
                ),
            ));
            return solution;
        }
    }

    // Free nodes in first-appearance (source) order: IndexMap so no
    // hash-iteration order can reach the output (AD-6).
    let mut index: IndexMap<&str, usize> = IndexMap::new();
    for s in &net.springs {
        for node in [s.a.as_str(), s.b.as_str()] {
            if !net.grounds.iter().any(|g| g == node) && !index.contains_key(node) {
                let slot = index.len();
                index.insert(node, slot);
            }
        }
    }

    let Some(&at_idx) = index.get(at) else {
        let reason = if net.grounds.iter().any(|g| g == at) {
            "it is grounded (its stiffness to ground is not a network property)"
        } else {
            "no spring connects it"
        };
        tracing::info!(at, reason, "queried node is not a free network node");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "stiffness network for `{}`: cannot evaluate stiffness at `{at}`: {reason}",
                net.system
            ),
        ));
        return solution;
    };

    // Standard scalar stiffness assembly, springs in source order.
    let n = index.len();
    let mut k = faer::Mat::<f64>::zeros(n, n);
    for s in &net.springs {
        let ia = index.get(s.a.as_str()).copied();
        let ib = index.get(s.b.as_str()).copied();
        match (ia, ib) {
            (Some(i), Some(j)) => {
                k[(i, i)] += s.k;
                k[(j, j)] += s.k;
                k[(i, j)] -= s.k;
                k[(j, i)] -= s.k;
            }
            (Some(i), None) | (None, Some(i)) => k[(i, i)] += s.k,
            (None, None) => {}
        }
    }

    let mut f = vec![0.0f64; n];
    f[at_idx] = 1.0;

    let Some(u) = solve_verified(&k, &f, residual_tol(1.0)) else {
        tracing::info!("singular stiffness matrix (node disconnected from ground)");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "stiffness network for `{}`: the network is singular -- some free node has \
                 no load path to ground; every node must be connected to a grounded node",
                net.system
            ),
        ));
        return solution;
    };

    // K is positive definite when connected, so u_at > 0; guard anyway
    // (no non-finite value may escape, AD-6).
    let u_at = u[at_idx];
    let k_eff = 1.0 / u_at;
    let Some(bounds) = (u_at > 0.0).then(|| OutwardBounds::around(k_eff)).flatten() else {
        tracing::warn!(u_at, "non-physical displacement from the network solve");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "stiffness network for `{}`: the solve produced a non-physical displacement \
                 at `{at}`; the network is ill-conditioned",
                net.system
            ),
        ));
        return solution;
    };

    tracing::info!(k_eff, "effective stiffness computed");
    solution.k_eff = Some(bounds);
    solution
}

#[cfg(test)]
mod tests {
    use super::{effective_stiffness, Spring, StiffnessNetwork};
    use regolith_diag::codes;

    fn spring(name: &str, a: &str, b: &str, k: f64) -> Spring {
        Spring {
            name: name.to_string(),
            a: a.to_string(),
            b: b.to_string(),
            k,
        }
    }

    /// Two springs in series, base grounded: `k_eff = (1/200 + 1/300)^-1
    /// = 120` at the tip (the hand calculation).
    fn series() -> StiffnessNetwork {
        StiffnessNetwork {
            system: "Mount".to_string(),
            grounds: vec!["base".to_string()],
            springs: vec![
                spring("s1", "base", "mid", 200.0),
                spring("s2", "mid", "tip", 300.0),
            ],
        }
    }

    // frob:tests crates/regolith-ir/src/solve/stiffness.rs::effective_stiffness kind="unit"
    #[test]
    fn series_springs_match_the_hand_calculation() {
        let sol = effective_stiffness(&series(), "tip");
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        let k = sol.k_eff.unwrap();
        assert!(k.lo <= 120.0 && 120.0 <= k.hi, "[{}, {}]", k.lo, k.hi);
    }

    #[test]
    fn parallel_springs_sum() {
        let net = StiffnessNetwork {
            system: "Par".to_string(),
            grounds: vec!["base".to_string()],
            springs: vec![
                spring("s1", "base", "tip", 200.0),
                spring("s2", "base", "tip", 300.0),
            ],
        };
        let sol = effective_stiffness(&net, "tip");
        let k = sol.k_eff.unwrap();
        assert!(k.lo <= 500.0 && 500.0 <= k.hi);
    }

    #[test]
    fn solve_is_bit_reproducible() {
        // INV-10: identical network, identical bits.
        let a = effective_stiffness(&series(), "tip");
        let b = effective_stiffness(&series(), "tip");
        assert_eq!(a, b);
    }

    #[test]
    fn disconnected_node_is_singular_not_a_panic() {
        let net = StiffnessNetwork {
            system: "Island".to_string(),
            grounds: vec!["base".to_string()],
            springs: vec![
                spring("s1", "base", "mid", 200.0),
                // `island_a`-`island_b` have no path to ground.
                spring("s2", "island_a", "island_b", 100.0),
            ],
        };
        let sol = effective_stiffness(&net, "island_a");
        assert!(sol.k_eff.is_none());
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn non_positive_stiffness_is_a_diagnostic() {
        let mut net = series();
        net.springs[0].k = -5.0;
        let sol = effective_stiffness(&net, "tip");
        assert!(sol.k_eff.is_none());
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn unknown_and_grounded_query_nodes_are_diagnostics() {
        for at in ["ghost", "base"] {
            let sol = effective_stiffness(&series(), at);
            assert!(sol.k_eff.is_none(), "at={at}");
            assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
        }
    }
}
