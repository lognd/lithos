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
//! Building a [`SketchClosure`] from a parsed
//! [`regolith_syntax::walk::Walk`] landed with WO-51 (the D150
//! walk-step name labels supplied the missing syntax-level binding):
//! see [`sketch_closure_from_walk`]. The promotion covers straight
//! cardinal walks; everything it cannot express comes back as a NAMED
//! [`WalkPromotion::Unsupported`] reason (arcs -- their closure
//! condition is nonlinear in the bulge -- revolve `close via axis`,
//! non-cardinal lines, expression constraints), never a silent skip.

pub use crate::sketch::{
    sketch_closure_from_walk, ClosureSegment, SegmentLength, SketchClosure, WalkPromotion,
};
use regolith_diag::{codes, Diagnostic};
use regolith_qty::{Cause, Qty, Resolution};

use super::{residual_tol, solve_verified, OutwardBounds};

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

/// The closed-form chord displacement of a tangent arc of radius `r`
/// between two cardinal headings (F123/D231/WO116-F1): the turn angle
/// `phi` is the unsigned angle between the incoming tangent heading
/// (`heading_deg`) and the outgoing one (`next_heading_deg`); the
/// elementary fillet identity in the incoming-tangent frame is
/// `(r*sin(phi), sign*r*(1-cos(phi)))` where `sign` comes from the
/// declared bulge side (`left` = the arc bulges to the CCW-left of
/// travel, `right` = CW). That local vector is then rotated into the
/// global frame by `heading_deg` (tangent-forward = local x,
/// CCW-perpendicular-left = local y). No iteration: `phi`, `sin`,
/// `cos` are the only transcendental inputs, all deterministic given
/// the two headings this walk already carries.
fn arc_chord(heading_deg: f64, next_heading_deg: f64, r: f64, bulge: &str) -> (f64, f64) {
    let raw = (next_heading_deg - heading_deg).rem_euclid(360.0);
    let phi_deg = raw.min(360.0 - raw);
    let sign = if bulge == "left" { 1.0 } else { -1.0 };
    let phi = phi_deg.to_radians();
    let local = (r * phi.sin(), sign * r * (1.0 - phi.cos()));
    let (cx, cy) = direction(heading_deg);
    let (px, py) = (-cy, cx); // CCW-left perpendicular of the tangent
    (local.0 * cx + local.1 * px, local.0 * cy + local.1 * py)
}

/// Sum the pinned/arc segment vectors into the closure gap and collect
/// the free columns, in walk order (AD-6). A radius-captured tangent
/// arc (F123/D231/WO116-F1) contributes its closed-form chord
/// displacement ([`arc_chord`]); a radius-less arc still contributes
/// nothing (unchanged WO-104 status quo: realizer-only geometry,
/// never a fabricated straight chord). Extracted from [`close_walk`]
/// to keep that function under the workspace line-count lint.
#[allow(clippy::type_complexity)]
fn accumulate_gap_and_free(sketch: &SketchClosure) -> ([f64; 2], f64, Vec<(&str, &str, f64, f64)>) {
    let mut gap = [0.0f64; 2];
    let mut scale = 0.0f64;
    let mut free: Vec<(&str, &str, f64, f64)> = Vec::new();
    let n = sketch.segments.len();
    for (i, seg) in sketch.segments.iter().enumerate() {
        if let Some(arc) = &seg.arc {
            if let Some(r) = arc.radius {
                let next_heading = sketch.segments[(i + 1) % n].angle_deg;
                let (dx, dy) = arc_chord(seg.angle_deg, next_heading, r, &arc.bulge);
                gap[0] += dx;
                gap[1] += dy;
                scale = scale.max(r.abs());
            }
            continue;
        }
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
            // A bounded free length is optimizer territory (WO-97), not
            // a closure unknown the linear solve pins: it behaves like a
            // `Free` here, sized by the optimizer, not this pass. Inert
            // per D205/D209 -- no promotion emits it yet.
            SegmentLength::Bounded { .. } => {
                free.push((seg.name.as_str(), seg.name.as_str(), cx, cy));
            }
        }
    }
    (gap, scale, free)
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

    if let Some(diag) = non_finite_diagnostic(sketch) {
        solution.diagnostics.push(*diag);
        return solution;
    }

    // WO-62 D171/AD-32 increment: a labeled close edge is an
    // unconstrained 2-DOF vector -- BY DEFINITION it absorbs the full
    // closure gap, so it never shares the non-close-edge exact/free
    // solve below.
    if sketch.close_edge.is_some() {
        return close_edge_solution(sketch, solution);
    }

    // Closure gap from the pinned segments (and radius-captured arcs,
    // F123/D231/WO116-F1), in walk order (AD-6), and the free columns
    // in walk order.
    let (gap, scale, free) = accumulate_gap_and_free(sketch);
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

/// WO-62 D171/AD-32: the labeled-close-edge solve. A close edge
/// consumes both closure equations itself and contributes no equation
/// to solve any OTHER free explicit segment: zero remaining explicit
/// frees closes trivially (any pinned-segment gap is exactly what the
/// close edge is); one or more explicit free lengths alongside it is
/// under-constrained -- `E0447`, naming the residual segment(s) and
/// the missing constraint class (never a silent skip, never guessing
/// a value for the free length). `sketch.close_edge` must be `Some`.
fn close_edge_solution(sketch: &SketchClosure, mut solution: SketchSolution) -> SketchSolution {
    let edge = sketch
        .close_edge
        .as_deref()
        .expect("close_edge_solution called with no close edge");
    let free_names: Vec<&str> = sketch
        .segments
        .iter()
        .filter(|s| s.arc.is_none())
        .filter_map(|s| match &s.length {
            SegmentLength::Free(_) | SegmentLength::Bounded { .. } => Some(s.name.as_str()),
            SegmentLength::Pinned(_) => None,
        })
        .collect();
    if free_names.is_empty() {
        let gap = closure_gap(sketch);
        let residual = (gap[0] * gap[0] + gap[1] * gap[1]).sqrt();
        tracing::info!(
            close_edge = %edge,
            residual,
            "close edge absorbs the closure gap (WO-62 D171)"
        );
        solution.residual = OutwardBounds::around(residual);
        return solution;
    }
    tracing::info!(
        close_edge = %edge,
        free = ?free_names,
        "close edge already absorbs both closure equations; explicit free \
         length(s) have nothing left to solve them (E0447)"
    );
    solution.diagnostics.push(Diagnostic::error(
        codes::SKETCH_CLOSE_EDGE_UNDERCONSTRAINED,
        format!(
            "sketch `{}`: the close edge `{edge}` is an unconstrained 2-DOF \
             vector that already absorbs both closure equations, so segment(s) \
             {} have no equation left to determine their length -- assert an \
             explicit length (missing constraint class: segment length) or \
             remove the `close` label",
            sketch.profile,
            free_names
                .iter()
                .map(|n| format!("`{n}`"))
                .collect::<Vec<_>>()
                .join(", "),
        ),
    ));
    solution
}

/// The pinned-segment vector sum, in walk order (AD-6), PLUS every
/// radius-captured tangent arc's closed-form chord contribution
/// (F123/D231/WO116-F1 -- see [`arc_chord`]): the gap a close edge
/// absorbs when no explicit free length remains to solve. A
/// radius-less arc still contributes nothing (unchanged WO-104 status
/// quo: realizer-only geometry, never a fabricated straight chord).
fn closure_gap(sketch: &SketchClosure) -> [f64; 2] {
    let mut gap = [0.0f64; 2];
    let n = sketch.segments.len();
    for (i, seg) in sketch.segments.iter().enumerate() {
        if let Some(arc) = &seg.arc {
            if let Some(r) = arc.radius {
                let next_heading = sketch.segments[(i + 1) % n].angle_deg;
                let (dx, dy) = arc_chord(seg.angle_deg, next_heading, r, &arc.bulge);
                gap[0] += dx;
                gap[1] += dy;
            }
            continue;
        }
        if let SegmentLength::Pinned(len) = &seg.length {
            let (cx, cy) = direction(seg.angle_deg);
            gap[0] += len * cx;
            gap[1] += len * cy;
        }
    }
    gap
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

/// The E0440 diagnostic for the first segment with a non-finite angle
/// or pinned length; `None` when all inputs are finite (boxed:
/// `Diagnostic` is large relative to the happy path).
fn non_finite_diagnostic(sketch: &SketchClosure) -> Option<Box<Diagnostic>> {
    let bad = sketch
        .segments
        .iter()
        .find(|s| {
            !s.angle_deg.is_finite()
                || matches!(s.length, SegmentLength::Pinned(l) if !l.is_finite())
        })
        .map(|s| s.name.clone())?;
    tracing::warn!(segment = %bad, "non-finite sketch input");
    Some(Box::new(Diagnostic::error(
        codes::SINGULAR_SYSTEM,
        format!(
            "sketch closure for `{}`: segment `{bad}` has a non-finite angle or \
             length; the closure solve cannot run",
            sketch.profile
        ),
    )))
}

#[cfg(test)]
mod tests {
    use super::{close_walk, ClosureSegment, SegmentLength, SketchClosure};
    use crate::sketch::ArcGeometry;
    use regolith_diag::codes;
    use regolith_qty::Unit;

    fn seg(name: &str, angle: f64, length: SegmentLength) -> ClosureSegment {
        ClosureSegment {
            name: name.to_string(),
            angle_deg: angle,
            length,
            arc: None,
        }
    }

    /// A tangent-arc segment (F123/D231/WO116-F1): a captured radius,
    /// carried with no linear `length` unknown of its own (the closure
    /// solve derives its chord from the neighboring headings + radius,
    /// never from `length`).
    fn arc_seg(name: &str, tangent_heading: f64, bulge: &str, radius: f64) -> ClosureSegment {
        ClosureSegment {
            name: name.to_string(),
            angle_deg: tangent_heading,
            length: SegmentLength::Pinned(0.0),
            arc: Some(ArcGeometry {
                bulge: bulge.to_string(),
                join: Some("tangent".to_string()),
                radius: Some(radius),
            }),
        }
    }

    /// A "stadium"/racetrack profile (F123 acceptance fixture): two
    /// straight edges of equal length joined by two 180-degree tangent
    /// arcs of radius `r` -- closes EXACTLY regardless of `r` (the two
    /// semicircle chords cancel by symmetry), so it is the simplest
    /// nontrivial exercise of the closed-form arc-closure math.
    fn stadium(top_len: f64, bottom_len: f64, r: f64) -> SketchClosure {
        SketchClosure {
            profile: "Stadium".to_string(),
            unit: Unit::dimensionless(),
            close_edge: None,
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(top_len)),
                arc_seg("b", 0.0, "right", r),
                seg("c", 180.0, SegmentLength::Pinned(bottom_len)),
                arc_seg("d", 180.0, "right", r),
            ],
        }
    }

    #[test]
    fn radius_captured_tangent_arc_closes_exactly() {
        // F123/D231/WO116-F1: the closed-form fillet identity, not a
        // fabricated skip -- the stadium closes with zero residual for
        // any radius once both straight legs agree.
        for r in [3.0, 6.0, 40.0] {
            let sol = close_walk(&stadium(40.0, 40.0, r));
            assert!(sol.diagnostics.is_empty(), "r={r}: {:?}", sol.diagnostics);
            let res = sol.residual.expect("residual computed");
            assert!(res.lo <= 1e-6 && res.hi >= -1e-6, "r={r}: {res:?}");
        }
    }

    #[test]
    fn radius_captured_tangent_arc_reports_the_existing_inconsistency_diagnostic() {
        // A non-closing walk (straight legs disagree) still gets the
        // EXISTING E0441 diagnostic -- never a fabricated closure just
        // because arcs are now part of the sum.
        let sol = close_walk(&stadium(40.0, 30.0, 6.0));
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(sol.diagnostics[0].code, codes::SKETCH_RESIDUAL_INCONSISTENT);
        let res = sol.residual.expect("residual computed");
        assert!(res.lo <= 10.0 && 10.0 <= res.hi, "{res:?}");
    }

    #[test]
    fn radius_less_arc_still_contributes_nothing_unchanged() {
        // The WO-104 status quo, unchanged: an arc with NO captured
        // radius is realizer-only geometry, never a fabricated chord.
        let mut sk = stadium(40.0, 40.0, 6.0);
        sk.segments[1].arc.as_mut().unwrap().radius = None;
        sk.segments[3].arc.as_mut().unwrap().radius = None;
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        let res = sol.residual.expect("residual computed");
        // Only the two straight legs contribute; they cancel exactly.
        assert!(res.lo <= 1e-9 && res.hi >= -1e-9, "{res:?}");
    }

    fn rectangle(left_len: f64) -> SketchClosure {
        SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::dimensionless(),
            close_edge: None,
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
            close_edge: None,
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
            close_edge: None,
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
            close_edge: None,
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
            close_edge: None,
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
            close_edge: None,
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
            close_edge: None,
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

    /// WO-62 D171/AD-32 fixture (over-constrained sibling: `E0441`
    /// above; this is the under-constrained close-edge case): a
    /// labeled close edge already absorbs both closure equations, so
    /// a still-`free` explicit segment has nothing left to determine
    /// it -- E0447, naming the residual segment.
    #[test]
    fn close_edge_with_a_free_segment_is_underconstrained() {
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::parse_atom("mm").expect("mm registered"),
            close_edge: Some("d".to_string()),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(80.0)),
                seg("b", 90.0, SegmentLength::Pinned(50.0)),
                seg("c", 180.0, SegmentLength::Free("c.length".to_string())),
            ],
        };
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(
            sol.diagnostics[0].code,
            codes::SKETCH_CLOSE_EDGE_UNDERCONSTRAINED
        );
        assert!(
            sol.diagnostics[0].message.contains('c'),
            "{:?}",
            sol.diagnostics
        );
        assert!(sol.resolutions.is_empty());
    }

    /// The closing sibling: every explicit segment pinned, the close
    /// edge absorbs the residual with no diagnostic -- the shape
    /// `sheet_bracket.hema` now uses (WO-62 deliverable 2).
    #[test]
    fn close_edge_with_all_segments_pinned_absorbs_the_gap() {
        let sk = SketchClosure {
            profile: "Plate".to_string(),
            unit: Unit::parse_atom("mm").expect("mm registered"),
            close_edge: Some("d".to_string()),
            segments: vec![
                seg("a", 0.0, SegmentLength::Pinned(80.0)),
                seg("b", 90.0, SegmentLength::Pinned(50.0)),
                seg("c", 180.0, SegmentLength::Pinned(80.0)),
            ],
        };
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty(), "{:?}", sol.diagnostics);
        assert!(sol.resolutions.is_empty());
        let r = sol.residual.unwrap();
        assert!(r.lo <= 50.0 && 50.0 <= r.hi, "{r:?}");
    }
}
