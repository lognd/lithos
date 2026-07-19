//! The L2 numeric solves the compiler owns (WO-23): rigid-body
//! statics, the lumped stiffness network, and exact sketch residual
//! closure. Feature-gated `solve`; `faer` is scoped here only.
//!
//! Regolith reference: `docs/spec/hematite/05-lowering.md` (L2 solves),
//! `docs/spec/hematite/03-contracts-and-assemblies.md` sec. 4 items 1-3,
//! `docs/spec/regolith/13-invariants.md` INV-10/INV-15. These are compiler
//! passes with bit-reproducible outputs (AD-6), NOT harness physics
//! (AD-1): fixed source-order summation, no hash-map iteration, and
//! outward-rounded bounds on every computed value. Singular or
//! ill-conditioned systems are DIAGNOSTICS (values, AD-7) -- never a
//! panic, and no NaN/non-finite value ever escapes a solve (the
//! canonical encoder rejects non-finite; these modules keep that true
//! by construction).

pub mod sketch;
pub mod statics;
pub mod stiffness;

use serde::{Deserialize, Serialize};

/// A computed scalar with outward-rounded bounds (AD-6): the true
/// value of the solved quantity lies within `[lo, hi]`, both finite.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-ir.md#solve
pub struct OutwardBounds {
    /// Lower bound (rounded down one ULP from the computed value).
    pub lo: f64,
    /// Upper bound (rounded up one ULP from the computed value).
    pub hi: f64,
}

impl OutwardBounds {
    /// Wrap a computed finite value in one-ULP outward bounds; `None`
    /// when the value is NaN or infinite (the caller converts that into
    /// a singular-system diagnostic, never lets it escape).
    #[must_use]
    // frob:doc docs/modules/regolith-ir.md#solve
    pub fn around(value: f64) -> Option<OutwardBounds> {
        if !value.is_finite() {
            return None;
        }
        Some(OutwardBounds {
            lo: value.next_down(),
            hi: value.next_up(),
        })
    }
}

/// Solve `a * x = b` (dense, square) by partial-pivot LU and verify the
/// solution: every component finite AND the residual `a*x - b` within
/// `tol` (infinity norm). Returns `None` for a singular or
/// ill-conditioned system -- the caller emits the E0440 diagnostic.
/// Single-threaded `faer` (no rayon feature), fixed assembly order:
/// bit-reproducible per AD-6.
fn solve_verified(coeffs: &faer::Mat<f64>, rhs: &[f64], tol: f64) -> Option<Vec<f64>> {
    use faer::linalg::solvers::Solve;

    let dim = rhs.len();
    debug_assert_eq!(coeffs.nrows(), dim);
    debug_assert_eq!(coeffs.ncols(), dim);

    let mut rhs_mat = faer::Mat::<f64>::zeros(dim, 1);
    for (row, value) in rhs.iter().enumerate() {
        rhs_mat[(row, 0)] = *value;
    }
    let solved = coeffs.partial_piv_lu().solve(&rhs_mat);

    let mut out = Vec::with_capacity(dim);
    for row in 0..dim {
        let component = solved[(row, 0)];
        if !component.is_finite() {
            tracing::debug!(component = row, "solve produced a non-finite component");
            return None;
        }
        out.push(component);
    }

    // Residual check: LU on a numerically singular matrix can return
    // finite garbage instead of NaN; the residual catches that case.
    for row in 0..dim {
        let mut residual = -rhs[row];
        for (col, x) in out.iter().enumerate() {
            residual += coeffs[(row, col)] * x;
        }
        if residual.abs() > tol {
            tracing::debug!(row, residual, tol, "solve residual exceeds tolerance");
            return None;
        }
    }

    Some(out)
}

/// The default relative residual tolerance for [`solve_verified`]:
/// scaled by the problem's magnitude by each caller.
const RESIDUAL_REL_TOL: f64 = 1e-9;

/// The residual tolerance for a problem whose right-hand side has
/// infinity norm `b_norm`: relative above 1, absolute below.
fn residual_tol(b_norm: f64) -> f64 {
    RESIDUAL_REL_TOL * b_norm.max(1.0)
}

#[cfg(test)]
mod tests {
    use super::{residual_tol, solve_verified, OutwardBounds};

    // frob:tests crates/regolith-ir/src/solve/mod.rs::OutwardBounds.around kind="unit"
    #[test]
    fn outward_bounds_straddle_the_value() {
        let b = OutwardBounds::around(1.5).unwrap();
        assert!(b.lo < 1.5 && 1.5 < b.hi);
    }

    #[test]
    fn outward_bounds_reject_non_finite() {
        assert!(OutwardBounds::around(f64::NAN).is_none());
        assert!(OutwardBounds::around(f64::INFINITY).is_none());
    }

    #[test]
    fn solve_verified_solves_a_diagonal_system() {
        let mut a = faer::Mat::<f64>::zeros(2, 2);
        a[(0, 0)] = 2.0;
        a[(1, 1)] = 4.0;
        let x = solve_verified(&a, &[2.0, 8.0], residual_tol(8.0)).unwrap();
        assert_eq!(x, vec![1.0, 2.0]);
    }

    #[test]
    fn solve_verified_rejects_a_singular_system() {
        let mut a = faer::Mat::<f64>::zeros(2, 2);
        a[(0, 0)] = 1.0;
        a[(0, 1)] = 2.0;
        a[(1, 0)] = 2.0;
        a[(1, 1)] = 4.0;
        assert!(solve_verified(&a, &[1.0, 3.0], residual_tol(3.0)).is_none());
    }
}
