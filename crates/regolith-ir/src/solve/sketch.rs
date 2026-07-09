//! Exact sketch residual closure (WO-23): the numeric half the WO-11
//! conservative DOF ledger deliberately left out -- flag an
//! EXACTLY-constrained-but-inconsistent walk (nonzero closure
//! residual, `E0441`) and resolve `free` lengths with Cause-typed
//! resolutions (INV-21).
//!
//! Regolith reference: `docs/spec/hematite/02` sec. 5,
//! `docs/spec/hematite/07-open-questions.md` OPEN-5/D65 (language surface
//! closed; the solver is implementation-owned). The closure condition
//! of a closed straight-segment walk is linear in the segment lengths
//! (`sum L_i * dir_i = 0`), so free lengths solve by a small
//! least-squares system -- deterministic, no iteration (AD-6).
//! Cardinal directions (multiples of 90 degrees) use EXACT direction
//! cosines so cross-platform libm differences never reach the lockfile
//! (INV-10); arbitrary angles use `f64::sin_cos` and are documented as
//! platform-follows-libm until a corpus fixture needs them.
//!
//! SCOPE (recorded, not hidden): building a [`SketchClosure`] from a
//! parsed [`regolith_syntax::walk::Walk`] is blocked on grammar-level
//! segment naming -- corpus walks name segments only in comments and
//! carry lengths as constraint text with no syntax-level binding
//! (WO-11 grammar surface). Callers construct the typed problem;
//! arcs are likewise out of this increment (their closure condition
//! is nonlinear in the bulge).

use regolith_diag::{codes, Diagnostic};
use regolith_qty::{Cause, Qty, Resolution, Unit};
use serde::{Deserialize, Serialize};

use super::{residual_tol, solve_verified, OutwardBounds};

/// A segment length: pinned by a constraint, or a declared `free`
/// parameter the closure solve resolves (INV-21).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SegmentLength {
    /// Pinned to a constraint value.
    Pinned(f64),
    /// Declared `free`; the payload is the parameter name the
    /// resolution is recorded under (`c.length`).
    Free(String),
}

/// One straight segment of a closed walk: its heading and length.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClosureSegment {
    /// Segment name (for diagnostics).
    pub name: String,
    /// Heading in degrees, counterclockwise from +x (`0` = right,
    /// `90` = up -- the walk's cardinal direction words).
    pub angle_deg: f64,
    /// The segment length: pinned or free.
    pub length: SegmentLength,
}

/// The typed closure problem for one profile walk.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SketchClosure {
    /// The profile the walk belongs to (names diagnostics/resolutions).
    pub profile: String,
    /// The unit pinned lengths are expressed in (resolved free lengths
    /// carry it too).
    pub unit: Unit,
    /// Segments in walk order (AD-6: fixed summation order).
    pub segments: Vec<ClosureSegment>,
}

/// The closure solve result. Diagnostics are values (AD-7); resolved
/// free lengths are INV-21 Cause-typed resolutions.
#[derive(Debug, Clone, Default)]
pub struct SketchSolution {
    /// The residual magnitude after closure (outward-rounded); `None`
    /// when the solve could not run.
    pub residual: Option<OutwardBounds>,
    /// One resolution per resolved `free` length, in segment order.
    pub resolutions: Vec<Resolution>,
    /// Inconsistency (`E0441`) and rank (`E0440`) diagnostics.
    pub diagnostics: Vec<Diagnostic>,
}

/// The exact direction cosines of a heading: multiples of 90 degrees
/// map to exact `(+-1, 0)` / `(0, +-1)` pairs so cardinal walks are
/// bit-identical across platforms (INV-10); other headings fall back
/// to libm `sin_cos`.
// Exact float equality is the POINT here: a heading written as a
// cardinal multiple of 90 must take the exact-cosine path, and any
// other bit pattern falls through to libm -- an epsilon would silently
// snap near-cardinal headings and change the answer.
#[allow(clippy::float_cmp)]
fn direction(angle_deg: f64) -> (f64, f64) {
    let norm = angle_deg.rem_euclid(360.0);
    if norm == 0.0 {
        (1.0, 0.0)
    } else if norm == 90.0 {
        (0.0, 1.0)
    } else if norm == 180.0 {
        (-1.0, 0.0)
    } else if norm == 270.0 {
        (0.0, -1.0)
    } else {
        let (sin, cos) = angle_deg.to_radians().sin_cos();
        (cos, sin)
    }
}

/// Close a walk exactly: sum pinned segment vectors, solve the free
/// lengths against the closure gap, and check the final residual.
///
/// Outcomes, by the number of `free` lengths `m`:
/// - `m == 0` (exactly constrained): a residual beyond tolerance is
///   the NEW inconsistency diagnostic, `E0441` -- the DOF ledger
///   balances but the constraint values contradict each other.
/// - `m <= 2`: the free lengths are solved (least squares against the
///   2 closure equations); dependent free directions are `E0440`, a
///   leftover residual or a negative resolved length is `E0441`, and
///   each resolved length lands as a `Resolution` with
///   `cause: topology(...)` (INV-21).
/// - `m > 2`: under-constrained -- the WO-11 ledger already owns that
///   report; this solve stays silent (logged, no diagnostics).
///
/// Non-finite inputs are `E0440`. Never a panic, never NaN out.
#[must_use]
pub fn close_walk(sketch: &SketchClosure) -> SketchSolution {
    let span = tracing::info_span!("solve.sketch", profile = %sketch.profile);
    let _enter = span.enter();

    let mut solution = SketchSolution::default();

    if let Some(bad) = first_non_finite(sketch) {
        tracing::warn!(segment = %bad, "non-finite sketch input");
        solution.diagnostics.push(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "sketch closure for `{}`: segment `{bad}` has a non-finite angle or \
                 length; the closure solve cannot run",
                sketch.profile
            ),
        ));
        return solution;
    }

    // Closure gap from the pinned segments, in walk order (AD-6), and
    // the free columns in walk order.
    let mut gap = [0.0f64; 2];
    let mut scale = 0.0f64;
    let mut free: Vec<(&str, &str, f64, f64)> = Vec::new();
    for seg in &sketch.segments {
        let (cx, cy) = direction(seg.angle_deg);
        match &seg.length {
            SegmentLength::Pinned(len) => {
                gap[0] += len * cx;
                gap[1] += len * cy;
                scale = scale.max(len.abs());
            }
            SegmentLength::Free(param) => {
                free.push((seg.name.as_str(), param.as_str(), cx, cy));
            }
        }
    }
    let tol = residual_tol(scale);

    let m = free.len();
    if m > 2 {
        // Under-constrained: the conservative DOF ledger (WO-11) owns
        // this report; re-flagging here would double-count it.
        tracing::debug!(
            free = m,
            "more free lengths than closure equations; ledger owns it"
        );
        return solution;
    }

    let resolved = match solve_free_lengths(&sketch.profile, &free, gap) {
        Ok(lengths) => lengths,
        Err(diag) => {
            solution.diagnostics.push(*diag);
            return solution;
        }
    };

    // Final residual with the resolved lengths substituted back in.
    let mut rx = gap[0];
    let mut ry = gap[1];
    for ((_, _, cx, cy), len) in free.iter().zip(&resolved) {
        rx += len * cx;
        ry += len * cy;
    }
    let residual = (rx * rx + ry * ry).sqrt();

    if residual > tol {
        tracing::info!(residual, tol, "exactly-constrained walk does not close");
        solution.diagnostics.push(Diagnostic::error(
            codes::SKETCH_RESIDUAL_INCONSISTENT,
            format!(
                "sketch `{}` is exactly constrained but does not close: the declared \
                 constraint values leave a closure residual of {residual} {unit} -- the \
                 constraints are mutually inconsistent",
                sketch.profile,
                unit = sketch.unit.symbol,
            ),
        ));
        solution.residual = OutwardBounds::around(residual);
        return solution;
    }

    for ((name, param, _, _), len) in free.iter().zip(&resolved) {
        if *len < 0.0 {
            tracing::info!(segment = name, length = len, "negative resolved length");
            solution.diagnostics.push(Diagnostic::error(
                codes::SKETCH_RESIDUAL_INCONSISTENT,
                format!(
                    "sketch `{}`: closing the walk forces `{param}` to a negative length \
                     ({len} {unit}); the declared constraints are mutually inconsistent",
                    sketch.profile,
                    unit = sketch.unit.symbol,
                ),
            ));
            solution.residual = OutwardBounds::around(residual);
            return solution;
        }
    }

    for ((_, param, _, _), len) in free.iter().zip(&resolved) {
        let resolution = Resolution::new(
            Qty::new(*len, sketch.unit.clone()),
            Cause::Topology(format!("sketch_close({}.{param})", sketch.profile)),
        );
        tracing::info!(param, length = len, "resolved free sketch length (INV-21)");
        solution.resolutions.push(resolution);
    }

    solution.residual = OutwardBounds::around(residual);
    solution
}

/// Solve the free lengths against the closure gap by least squares:
/// normal equations `(A^T A) x = A^T (-gap)` where A's columns are the
/// free direction cosines -- exact for two determinate frees,
/// minimizing for one overdetermined free. An empty free set is the
/// trivial empty solution. Dependent free directions make the system
/// singular: the `E0440` diagnostic comes back as `Err` (boxed:
/// `Diagnostic` is large relative to the `Ok` value).
fn solve_free_lengths(
    profile: &str,
    free: &[(&str, &str, f64, f64)],
    gap: [f64; 2],
) -> Result<Vec<f64>, Box<Diagnostic>> {
    let m = free.len();
    if m == 0 {
        return Ok(Vec::new());
    }
    let mut normal = faer::Mat::<f64>::zeros(m, m);
    let mut rhs = vec![0.0f64; m];
    for (i, (_, _, cxi, cyi)) in free.iter().enumerate() {
        for (j, (_, _, cxj, cyj)) in free.iter().enumerate() {
            normal[(i, j)] = cxi * cxj + cyi * cyj;
        }
        rhs[i] = -(cxi * gap[0] + cyi * gap[1]);
    }
    let rhs_norm = rhs.iter().fold(0.0f64, |acc, v| acc.max(v.abs()));
    solve_verified(&normal, &rhs, residual_tol(rhs_norm)).ok_or_else(|| {
        tracing::info!("dependent free directions (singular closure system)");
        Box::new(Diagnostic::error(
            codes::SINGULAR_SYSTEM,
            format!(
                "sketch closure for `{profile}`: the free lengths ({}) act along dependent \
                 directions, so closure cannot determine them",
                free.iter()
                    .map(|(_, param, _, _)| *param)
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
        ))
    })
}

/// The first segment with a non-finite angle or pinned length, named
/// for the diagnostic; `None` when all inputs are finite.
fn first_non_finite(sketch: &SketchClosure) -> Option<String> {
    sketch
        .segments
        .iter()
        .find(|s| {
            !s.angle_deg.is_finite()
                || matches!(s.length, SegmentLength::Pinned(l) if !l.is_finite())
        })
        .map(|s| s.name.clone())
}

#[cfg(test)]
mod tests {
    use super::{close_walk, ClosureSegment, SegmentLength, SketchClosure};
    use regolith_diag::codes;
    use regolith_qty::Unit;

    fn seg(name: &str, angle: f64, length: SegmentLength) -> ClosureSegment {
        ClosureSegment {
            name: name.to_string(),
            angle_deg: angle,
            length,
        }
    }

    fn rectangle(left_len: f64) -> SketchClosure {
        SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(40.0)),
                seg("b", 90.0, SegmentLength::Pinned(20.0)),
                seg("c", 180.0, SegmentLength::Pinned(left_len)),
                seg("d", 270.0, SegmentLength::Pinned(20.0)),
            ],
        }
    }

    #[test]
    fn consistent_rectangle_closes_with_zero_residual() {
        let sol = close_walk(&rectangle(40.0));
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        let r = sol.residual.unwrap();
        assert!(r.lo <= 0.0 && 0.0 <= r.hi);
    }

    #[test]
    fn inconsistent_exactly_constrained_walk_yields_the_new_diagnostic() {
        // The WO-23 acceptance fixture: DOF-balanced (every length
        // pinned) but the values contradict -- top edge 40, bottom
        // return only 30. The residual is 10, E0441.
        let sol = close_walk(&rectangle(30.0));
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SKETCH_RESIDUAL_INCONSISTENT);
        assert!(sol.diagnostics[0].message.contains("does not close"));
        let r = sol.residual.unwrap();
        assert!(r.lo <= 10.0 && 10.0 <= r.hi);
    }

    #[test]
    fn free_lengths_resolve_with_cause_typed_resolutions() {
        // Two frees against two closure equations: c.length must come
        // back 40 and d.length 20, each as an INV-21 resolution.
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(40.0)),
                seg("b", 90.0, SegmentLength::Pinned(20.0)),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
                seg("d", 270.0, SegmentLength::Free("d.length".to_string())),
            ],
        };
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        assert_eq!(sol.resolutions.len(), 2);
        let line = sol.resolutions[0].lockfile_line("c.length");
        assert!(line.contains("40"), "{line}");
        assert!(
            line.contains("topology(sketch_close(Plate.c.length))"),
            "{line}"
        );
        let line = sol.resolutions[1].lockfile_line("d.length");
        assert!(line.contains("20"), "{line}");
    }

    #[test]
    fn one_free_length_resolves_when_consistent() {
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(40.0)),
                seg("b", 90.0, SegmentLength::Pinned(20.0)),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
                seg("d", 270.0, SegmentLength::Pinned(20.0)),
            ],
        };
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        assert_eq!(sol.resolutions.len(), 1);
        assert!(sol.resolutions[0].lockfile_line("c.length").contains("40"));
    }

    #[test]
    fn one_free_length_cannot_absorb_a_perpendicular_gap() {
        // The single free runs along x but the vertical legs disagree:
        // least squares fixes x, the y residual remains -- E0441.
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(40.0)),
                seg("b", 90.0, SegmentLength::Pinned(20.0)),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
                seg("d", 270.0, SegmentLength::Pinned(15.0)),
            ],
        };
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SKETCH_RESIDUAL_INCONSISTENT);
        assert!(sol.resolutions.is_empty());
    }

    #[test]
    fn dependent_free_directions_are_the_rank_case() {
        // Both frees run along x: the closure system is singular, E0440.
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 90.0, SegmentLength::Pinned(20.0)),
                seg("b", 0.0, SegmentLength::Free("b.length".to_string())),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
                seg("d", 270.0, SegmentLength::Pinned(20.0)),
            ],
        };
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn negative_resolved_length_is_inconsistent() {
        // Closing forces `c` to run BACKWARD (negative length): the
        // walk cannot be drawn as declared -- E0441.
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(40.0)),
                seg("b", 90.0, SegmentLength::Pinned(20.0)),
                seg("c", 0.0, SegmentLength::Free("c.length".to_string())),
                seg("d", 270.0, SegmentLength::Pinned(20.0)),
            ],
        };
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SKETCH_RESIDUAL_INCONSISTENT);
        assert!(sol.diagnostics[0].message.contains("negative length"));
        assert!(sol.resolutions.is_empty());
    }

    #[test]
    fn more_than_two_frees_is_the_ledgers_business_not_ours() {
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            segments: vec![
                seg("a", 0.0, SegmentLength::Free("a.length".to_string())),
                seg("b", 90.0, SegmentLength::Free("b.length".to_string())),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
            ],
        };
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty());
        assert!(sol.resolutions.is_empty());
        assert!(sol.residual.is_none());
    }

    #[test]
    fn non_finite_input_is_a_diagnostic() {
        let mut sk = rectangle(40.0);
        sk.segments[0].length = SegmentLength::Pinned(f64::INFINITY);
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SINGULAR_SYSTEM);
    }

    #[test]
    fn solve_is_bit_reproducible() {
        // INV-10: identical walks produce identical residual bits.
        let a = close_walk(&rectangle(30.0));
        let b = close_walk(&rectangle(30.0));
        assert_eq!(a.residual, b.residual);
    }
}
