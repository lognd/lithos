//! Rigid-body statics (WO-23): the planar free-body reaction solve
//! over the assembly connection graph -- matings become supports with
//! constraint directions, and the computed reactions feed interface
//! load envelopes so promise obligations carry REAL computed loads.
//!
//! Regolith reference: `docs/hematite/03-contracts-and-assemblies.md`
//! sec. 4 item 2 ("rigid statics on the connection graph = the
//! free-body diagram; reactions per interface checked against rated
//! envelopes"). The determinate fast path only: a statically
//! indeterminate assembly defers to the stiffness network (item 3),
//! reported as a diagnostic, never guessed at.

use regolith_diag::{codes, Diagnostic};
use serde::{Deserialize, Serialize};

use super::{residual_tol, solve_verified, OutwardBounds};

/// One planar reaction direction a support (mating) constrains: the
/// spelling of a mating's `dof_removed` entries this solve recognizes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReactionDir {
    /// A horizontal force reaction.
    Fx,
    /// A vertical force reaction.
    Fy,
    /// An in-plane moment reaction.
    Mz,
}

impl ReactionDir {
    /// Parse a mating `dof_removed` label (`fx`/`fy`/`mz`, any case)
    /// into a reaction direction; `None` for labels this planar solve
    /// does not model (they stay the DOF ledger's business).
    #[must_use]
    pub fn parse(label: &str) -> Option<ReactionDir> {
        match label.trim().to_ascii_lowercase().as_str() {
            "fx" => Some(ReactionDir::Fx),
            "fy" => Some(ReactionDir::Fy),
            "mz" => Some(ReactionDir::Mz),
            _ => None,
        }
    }

    /// The canonical lowercase label (`fx`/`fy`/`mz`).
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            ReactionDir::Fx => "fx",
            ReactionDir::Fy => "fy",
            ReactionDir::Mz => "mz",
        }
    }
}

/// A support point derived from one mating: its in-plane position and
/// the reaction directions its removed DOF constrain.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Support {
    /// The mating this support comes from (names the reaction).
    pub mating: String,
    /// In-plane x position of the support point.
    pub x: f64,
    /// In-plane y position of the support point.
    pub y: f64,
    /// The reaction directions constrained here, in source order.
    pub dirs: Vec<ReactionDir>,
}

/// One external applied load: a force and moment acting at a point.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AppliedLoad {
    /// Load name (for the diagnostic and the fed envelope entry).
    pub name: String,
    /// Horizontal force component.
    pub fx: f64,
    /// Vertical force component.
    pub fy: f64,
    /// Applied in-plane moment.
    pub mz: f64,
    /// x position of the point of application.
    pub x: f64,
    /// y position of the point of application.
    pub y: f64,
}

/// The planar statics problem for one assembly: supports (from
/// matings, in source order) and applied loads (in source order).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StaticsProblem {
    /// The system/assembly node this problem was built from.
    pub system: String,
    /// Supports in mating source order (AD-6: fixed assembly order).
    pub supports: Vec<Support>,
    /// External loads in source order.
    pub loads: Vec<AppliedLoad>,
}

/// One computed reaction component, outward-rounded (AD-6).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Reaction {
    /// The mating that carries this reaction.
    pub mating: String,
    /// The constrained direction.
    pub dir: ReactionDir,
    /// The computed reaction magnitude with outward bounds.
    pub bounds: OutwardBounds,
}

/// The statics solve result: reactions (empty when the solve could not
/// run) plus any diagnostics. Diagnostics are values (AD-7).
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct StaticsSolution {
    /// Computed reactions in support source order, direction order.
    pub reactions: Vec<Reaction>,
    /// Under/over-determinacy and singularity diagnostics.
    pub diagnostics: Vec<Diagnostic>,
}

/// Solve planar rigid-body equilibrium (`sum Fx = sum Fy = sum Mz = 0`,
/// moments about the origin) for the support reactions.
///
/// Determinacy is checked first: fewer than three reaction unknowns is
/// an under-constrained mechanism, more is a statically indeterminate
/// assembly (both E0420-family, the existing ledger vocabulary --
/// hematite/03 sec. 4: the stiffness network owns the redundant case).
/// Exactly three unknowns whose directions are still dependent (e.g.
/// all reaction lines concurrent) is the NUMERIC-rank case, `E0440`.
/// Non-finite inputs and non-finite solutions are also `E0440`: no NaN
/// ever escapes (AD-6).
#[must_use]
pub fn solve_rigid_statics(problem: &StaticsProblem) -> StaticsSolution {
    let span = tracing::info_span!("solve.statics", system = %problem.system);
    let _enter = span.enter();

    let mut solution = StaticsSolution::default();

    if let Some(bad) = first_non_finite(problem) {
        tracing::warn!(input = %bad, "non-finite statics input");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "rigid statics for `{}`: input `{bad}` is not a finite number; \
                 the reaction solve cannot run",
                problem.system
            ),
        ));
        return solution;
    }

    // Unknown order is FIXED: supports in mating source order, then each
    // support's directions in their declared order (AD-6).
    let unknowns: Vec<(&str, ReactionDir, f64, f64)> = problem
        .supports
        .iter()
        .flat_map(|s| s.dirs.iter().map(|d| (s.mating.as_str(), *d, s.x, s.y)))
        .collect();

    let n = unknowns.len();
    if n < 3 {
        tracing::info!(
            unknowns = n,
            "under-constrained: fewer reactions than equations"
        );
        solution.diagnostics.push(Diagnostic::error(
            codes::LEDGER_IMBALANCE,
            format!(
                "rigid statics for `{}`: only {n} reaction component(s) constrain 3 planar \
                 equilibrium equations; the assembly is an under-constrained mechanism",
                problem.system
            ),
        ));
        return solution;
    }
    if n > 3 {
        tracing::info!(
            unknowns = n,
            "statically indeterminate: more reactions than equations"
        );
        solution.diagnostics.push(Diagnostic::error(
            codes::LEDGER_IMBALANCE,
            format!(
                "rigid statics for `{}`: {n} reaction components over-constrain 3 planar \
                 equilibrium equations (statically indeterminate); route the load path \
                 through the stiffness network (`redundant(<dof>)`) instead",
                problem.system
            ),
        ));
        return solution;
    }

    // Equilibrium rows: sum Fx, sum Fy, sum Mz about the origin. A
    // reaction R at (x, y) contributes (1, 0, -y) for Fx, (0, 1, x) for
    // Fy, and (0, 0, 1) for Mz.
    let mut a = faer::Mat::<f64>::zeros(3, 3);
    for (j, (_, dir, x, y)) in unknowns.iter().enumerate() {
        let col = match dir {
            ReactionDir::Fx => [1.0, 0.0, -y],
            ReactionDir::Fy => [0.0, 1.0, *x],
            ReactionDir::Mz => [0.0, 0.0, 1.0],
        };
        for (i, v) in col.iter().enumerate() {
            a[(i, j)] = *v;
        }
    }

    // Applied-load sums in source order (AD-6: fixed summation order).
    let mut b = [0.0f64; 3];
    for load in &problem.loads {
        b[0] -= load.fx;
        b[1] -= load.fy;
        b[2] -= load.x * load.fy - load.y * load.fx + load.mz;
    }

    let b_norm = b.iter().fold(0.0f64, |m, v| m.max(v.abs()));
    let Some(x) = solve_verified(&a, &b, residual_tol(b_norm)) else {
        tracing::info!("singular equilibrium matrix (concurrent/dependent reactions)");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "rigid statics for `{}`: the 3 reaction directions are dependent (e.g. all \
                 reaction lines concurrent), so equilibrium cannot determine them; \
                 reposition or redirect a support",
                problem.system
            ),
        ));
        return solution;
    };

    for ((mating, dir, _, _), value) in unknowns.iter().zip(&x) {
        // `solve_verified` guarantees finiteness, so `around` cannot
        // fail here; keep the guard total anyway (no NaN escapes).
        let Some(bounds) = OutwardBounds::around(*value) else {
            continue;
        };
        tracing::debug!(mating, dir = dir.label(), value, "computed reaction");
        solution.reactions.push(Reaction {
            mating: (*mating).to_string(),
            dir: *dir,
            bounds,
        });
    }

    solution
}

/// The first non-finite input in the problem, named for the diagnostic;
/// `None` when all inputs are finite.
fn first_non_finite(problem: &StaticsProblem) -> Option<String> {
    for s in &problem.supports {
        if !s.x.is_finite() || !s.y.is_finite() {
            return Some(format!("support {}", s.mating));
        }
    }
    for l in &problem.loads {
        let vals = [l.fx, l.fy, l.mz, l.x, l.y];
        if vals.iter().any(|v| !v.is_finite()) {
            return Some(format!("load {}", l.name));
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::{solve_rigid_statics, AppliedLoad, ReactionDir, StaticsProblem, Support};
    use regolith_diag::codes;

    /// The WO-23 bolted-bracket acceptance fixture: a bracket bolted at
    /// A (pin: fx + fy) and B (fy only, 0.2 m to the right), loaded
    /// with 1000 N downward at 0.3 m. Hand-calculated reactions:
    /// `Ax = 0`, moments about A give `By = 0.3 * 1000 / 0.2 = 1500 N`,
    /// so `Ay = 1000 - 1500 = -500 N`.
    fn bracket() -> StaticsProblem {
        StaticsProblem {
            system: "BoltedBracket".to_string(),
            supports: vec![
                Support {
                    mating: "bolt_a".to_string(),
                    x: 0.0,
                    y: 0.0,
                    dirs: vec![ReactionDir::Fx, ReactionDir::Fy],
                },
                Support {
                    mating: "bolt_b".to_string(),
                    x: 0.2,
                    y: 0.0,
                    dirs: vec![ReactionDir::Fy],
                },
            ],
            loads: vec![AppliedLoad {
                name: "tip".to_string(),
                fx: 0.0,
                fy: -1000.0,
                mz: 0.0,
                x: 0.3,
                y: 0.0,
            }],
        }
    }

    /// Assert `bounds` contain `expected` within outward rounding.
    fn assert_within(r: &super::Reaction, expected: f64) {
        assert!(
            r.bounds.lo <= expected && expected <= r.bounds.hi,
            "{}.{}: expected {expected} within [{}, {}]",
            r.mating,
            r.dir.label(),
            r.bounds.lo,
            r.bounds.hi
        );
    }

    #[test]
    fn bolted_bracket_matches_the_hand_calculation() {
        let sol = solve_rigid_statics(&bracket());
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        assert_eq!(sol.reactions.len(), 3);
        assert_eq!(sol.reactions[0].mating, "bolt_a");
        assert_within(&sol.reactions[0], 0.0); // Ax
        assert_within(&sol.reactions[1], -500.0); // Ay
        assert_eq!(sol.reactions[2].mating, "bolt_b");
        assert_within(&sol.reactions[2], 1500.0); // By
    }

    #[test]
    fn solve_is_bit_reproducible() {
        // INV-10: two runs over the same problem produce identical bits.
        let a = solve_rigid_statics(&bracket());
        let b = solve_rigid_statics(&bracket());
        assert_eq!(a, b);
    }

    #[test]
    fn under_constrained_is_a_ledger_diagnostic_not_a_panic() {
        let mut p = bracket();
        p.supports[0].dirs = vec![ReactionDir::Fy]; // 2 unknowns < 3
        let sol = solve_rigid_statics(&p);
        assert!(sol.reactions.is_empty());
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::LEDGER_IMBALANCE);
        assert!(sol.diagnostics[0].message.contains("under-constrained"));
    }

    #[test]
    fn indeterminate_defers_to_the_stiffness_network() {
        let mut p = bracket();
        p.supports[1].dirs = vec![ReactionDir::Fx, ReactionDir::Fy]; // 4 unknowns > 3
        let sol = solve_rigid_statics(&p);
        assert!(sol.reactions.is_empty());
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::LEDGER_IMBALANCE);
        assert!(sol.diagnostics[0].message.contains("indeterminate"));
    }

    #[test]
    fn concurrent_reactions_are_the_numeric_rank_case() {
        // Three reaction components all acting at one point with no
        // moment reaction: rank-deficient (the moment equation is
        // unsatisfiable/degenerate), E0440 -- never a panic or NaN.
        let p = StaticsProblem {
            system: "Concurrent".to_string(),
            supports: vec![Support {
                mating: "pin".to_string(),
                x: 0.0,
                y: 0.0,
                dirs: vec![ReactionDir::Fx, ReactionDir::Fy, ReactionDir::Fx],
            }],
            loads: vec![AppliedLoad {
                name: "twist".to_string(),
                fx: 0.0,
                fy: 0.0,
                mz: 10.0,
                x: 0.0,
                y: 0.0,
            }],
        };
        let sol = solve_rigid_statics(&p);
        assert!(sol.reactions.is_empty());
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn non_finite_input_is_a_diagnostic_never_a_nan_output() {
        let mut p = bracket();
        p.loads[0].fy = f64::NAN;
        let sol = solve_rigid_statics(&p);
        assert!(sol.reactions.is_empty());
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn reaction_dir_labels_round_trip() {
        for d in [ReactionDir::Fx, ReactionDir::Fy, ReactionDir::Mz] {
            assert_eq!(ReactionDir::parse(d.label()), Some(d));
        }
        assert_eq!(ReactionDir::parse("axial"), None);
    }
}
