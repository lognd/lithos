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

use regolith_diag::{codes, Diagnostic};
use regolith_qty::{Cause, Qty, Resolution, Unit};
use regolith_syntax::walk::{Direction, Segment, Walk};
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
    /// The labeled implicit return edge of a planar `close` (`d:
    /// close`), when the walk has one: recorded for the payload (the
    /// close edge is an unconstrained 2-DOF vector -- the closure gap
    /// itself), NOT a [`ClosureSegment`]. [`close_walk`] treats the
    /// explicit segments as the full loop; solving a problem whose
    /// close edge absorbs the gap is the solver's next increment.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub close_edge: Option<String>,
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

    // A problem whose planar close edge is a separate labeled 2-DOF
    // vector (WO-51 promotion output) is NOT the explicit-loop shape
    // this solve models -- refusing honestly beats a spurious E0441
    // (the gap the close edge would absorb is not an inconsistency).
    if let Some(edge) = &sketch.close_edge {
        tracing::debug!(
            close_edge = %edge,
            "closure with an implicit close edge; solving it is the next increment"
        );
        return solution;
    }

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

/// The outcome of promoting a parsed profile walk into the typed
/// closure problem (WO-51 deliverable 1, D150 labels): promoted, or a
/// NAMED reason this increment's surface cannot express it -- recorded
/// so the emission pass reports it, never a silent skip.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WalkPromotion {
    /// The walk promoted into a typed closure problem.
    Promoted(SketchClosure),
    /// The walk is outside the v1 promotion surface, with the reason.
    Unsupported {
        /// What exactly the surface cannot express (names the step).
        reason: String,
    },
}

/// Promote a parsed walk into the typed [`SketchClosure`] payload:
/// each straight cardinal segment becomes a [`ClosureSegment`] whose
/// heading comes from its direction word (`right`=0, `up`=90,
/// `left`=180, `down`=270 -- the exact-cosine cardinal path, INV-10)
/// and whose length comes from the D150 label-bound `constraints:`
/// item (`a.length = 80mm` pins; `= free` or no item is a free length
/// named `<label>.length`). A labeled planar `close` is recorded as
/// [`SketchClosure::close_edge`].
///
/// Outside the surface (each a named [`WalkPromotion::Unsupported`]):
/// arcs, non-cardinal lines (`tangent`, `angled`), revolve closure
/// (`close via axis`), expression constraints (`dia 20mm / 2`), a
/// pinned close-edge length (needs the close-edge solve increment),
/// mixed units, and a twice-pinned segment. A constraint naming an
/// UNBOUND segment is skipped here: that is E0442's business
/// (`regolith-sem` `check_label_bindings`), reported once, not twice.
#[must_use]
pub fn sketch_closure_from_walk(profile: &str, walk: &Walk) -> WalkPromotion {
    let span = tracing::info_span!("solve.sketch.promote", profile);
    let _enter = span.enter();

    if walk.via_axis {
        return unsupported(profile, "closes `via axis` (revolve closure, not a planar loop)");
    }

    // Headings first: every explicit segment must be a straight
    // cardinal line for the closure condition to be linear over it.
    let mut names: Vec<String> = Vec::new();
    let mut headings: Vec<f64> = Vec::new();
    for (i, ws) in walk.segments.iter().enumerate() {
        let step = i + 1;
        let heading = match &ws.seg {
            Segment::Arc { .. } => {
                return unsupported(
                    profile,
                    &format!("step {step} is an arc (closure is nonlinear in the bulge)"),
                );
            }
            Segment::Line(dir) => match dir {
                Some(Direction::Right) => 0.0,
                Some(Direction::Up) => 90.0,
                Some(Direction::Left) => 180.0,
                Some(Direction::Down) => 270.0,
                other => {
                    return unsupported(
                        profile,
                        &format!(
                            "step {step} is a line without a cardinal direction word \
                             ({other:?})"
                        ),
                    );
                }
            },
        };
        names.push(
            ws.label
                .clone()
                .unwrap_or_else(|| format!("_{step}")),
        );
        headings.push(heading);
    }

    // Length bindings from the label-bound `constraints:` items.
    let mut lengths: Vec<SegmentLength> = names
        .iter()
        .map(|n| SegmentLength::Free(format!("{n}.length")))
        .collect();
    let mut pinned_seen: Vec<bool> = vec![false; names.len()];
    let mut unit: Option<Unit> = None;
    for item in &walk.constraints {
        let Some((base, rhs)) = length_item(item) else {
            continue;
        };
        if walk.close_label.as_deref() == Some(base) {
            return unsupported(
                profile,
                &format!(
                    "constraint `{item}` pins the close edge `{base}` (the close-edge \
                     solve is the next increment)"
                ),
            );
        }
        let Some(idx) = names.iter().position(|n| n == base) else {
            // Unbound segment name: E0442 (check_label_bindings) owns
            // the report; promoting must not double-count it.
            tracing::debug!(profile, base, "length item names no bound segment; E0442 owns it");
            continue;
        };
        if rhs == "free" {
            continue; // already Free by default, declared explicitly
        }
        if pinned_seen[idx] {
            return unsupported(
                profile,
                &format!("segment `{base}` has more than one length pin (inconsistent by construction)"),
            );
        }
        let Some((value, item_unit)) = pinned_quantity(rhs) else {
            return unsupported(
                profile,
                &format!("constraint `{item}` is not a plain quantity (expression constraints are out of this increment)"),
            );
        };
        match &unit {
            None => unit = Some(item_unit),
            Some(u) if *u == item_unit => {}
            Some(u) => {
                return unsupported(
                    profile,
                    &format!(
                        "mixed pinned units (`{}` vs `{}`)",
                        u.symbol, item_unit.symbol
                    ),
                );
            }
        }
        lengths[idx] = SegmentLength::Pinned(value);
        pinned_seen[idx] = true;
    }

    let segments = names
        .into_iter()
        .zip(headings)
        .zip(lengths)
        .map(|((name, angle_deg), length)| ClosureSegment {
            name,
            angle_deg,
            length,
        })
        .collect();

    let closure = SketchClosure {
        profile: profile.to_string(),
        unit: unit.unwrap_or_else(Unit::dimensionless),
        segments,
        close_edge: if walk.closes {
            walk.close_label.clone()
        } else {
            None
        },
    };
    tracing::info!(
        profile,
        segments = closure.segments.len(),
        close_edge = ?closure.close_edge,
        "walk promoted to a typed sketch closure (WO-51/D150)"
    );
    WalkPromotion::Promoted(closure)
}

/// Log and wrap one named unsupported-promotion reason.
fn unsupported(profile: &str, reason: &str) -> WalkPromotion {
    tracing::info!(profile, reason, "walk outside the v1 promotion surface");
    WalkPromotion::Unsupported {
        reason: format!("profile `{profile}`: {reason}"),
    }
}

/// Split a `constraints:` item of the shape `<base>.length = <rhs>`
/// into `(base, rhs)`; `None` for every other constraint form (they
/// are ledger refs, not closure lengths).
fn length_item(item: &str) -> Option<(&str, &str)> {
    let (lhs, rhs) = item.split_once('=')?;
    let lhs = lhs.trim();
    let base = lhs.strip_suffix(".length")?;
    let base_ok = !base.is_empty()
        && !base.as_bytes()[0].is_ascii_digit()
        && base
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_');
    if base_ok {
        Some((base, rhs.trim()))
    } else {
        None
    }
}

/// Parse a plain quantity literal (`80mm`, `8.5mm`, `120`) into its
/// magnitude and unit; `None` for anything with operators, spaces, or
/// an unregistered unit suffix (those are named unsupported reasons).
fn pinned_quantity(text: &str) -> Option<(f64, Unit)> {
    let split = text
        .find(|c: char| !(c.is_ascii_digit() || c == '.' || c == '-'))
        .unwrap_or(text.len());
    let (num, suffix) = text.split_at(split);
    let value: f64 = num.parse().ok()?;
    if suffix.is_empty() {
        return Some((value, Unit::dimensionless()));
    }
    if !suffix.chars().all(|c| c.is_ascii_alphanumeric()) {
        return None;
    }
    Unit::parse_atom(suffix).ok().map(|u| (value, u))
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
}

/// WO-51 deliverable 1: the Walk -> SketchClosure promotion, unit
/// cases plus snapshot tests over the REAL corpus profiles (the walks
/// regolith-sem's WO-11 acceptance fixtures exercise).
#[cfg(test)]
mod promotion_tests {
    use super::{close_walk, sketch_closure_from_walk, SegmentLength, WalkPromotion};
    use camino::Utf8PathBuf;
    use regolith_syntax::syntax_kind::SyntaxKind;
    use regolith_syntax::walk::parse_walk;

    /// Every profile walk in `src`, promoted, under its decl's name.
    fn promote_all(src: &str) -> Vec<WalkPromotion> {
        use regolith_syntax::ast::{AstNode, Decl};
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
        let mut out = Vec::new();
        for node in parse
            .syntax()
            .descendants()
            .filter(|n| n.kind() == SyntaxKind::Decl)
        {
            if let Some(walk) = parse_walk(&node) {
                let name = Decl::cast(node)
                    .and_then(|d| d.name())
                    .unwrap_or_else(|| "p".to_string());
                out.push(sketch_closure_from_walk(&name, &walk));
            }
        }
        out
    }

    fn promote_one(src: &str) -> WalkPromotion {
        let mut all = promote_all(src);
        assert_eq!(all.len(), 1, "exactly one profile walk expected");
        all.remove(0)
    }

    #[test]
    fn labeled_cardinal_walk_promotes_with_pins_frees_and_close_edge() {
        // The sheet_bracket shape: labels bind the constraint pins,
        // an unpinned segment is a free length, `d: close` records
        // the implicit return edge.
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from left_edge\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20c: line left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20d: close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 80mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = 50mm\n";
        let WalkPromotion::Promoted(sk) = promote_one(src) else {
            panic!("expected a promoted closure");
        };
        assert_eq!(sk.segments.len(), 3);
        assert_eq!(sk.unit.symbol, "mm");
        assert_eq!(sk.segments[0].name, "a");
        assert_eq!(sk.segments[0].angle_deg, 0.0);
        assert_eq!(sk.segments[0].length, SegmentLength::Pinned(80.0));
        assert_eq!(sk.segments[1].angle_deg, 90.0);
        assert_eq!(
            sk.segments[2].length,
            SegmentLength::Free("c.length".to_string())
        );
        assert_eq!(sk.close_edge.as_deref(), Some("d"));
        // The close-edge shape is refused by the explicit-loop solve
        // (honest silence, never a spurious E0441).
        let sol = close_walk(&sk);
        assert!(sol.diagnostics.is_empty());
        assert!(sol.residual.is_none());
    }

    #[test]
    fn declared_free_and_unbound_names_are_handled() {
        // `= free` stays free; a constraint naming an UNBOUND segment
        // is skipped here (E0442 owns that report -- one report, not
        // two).
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = free\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20zz.length = 9mm\n";
        let WalkPromotion::Promoted(sk) = promote_one(src) else {
            panic!("expected a promoted closure");
        };
        assert_eq!(
            sk.segments[0].length,
            SegmentLength::Free("a.length".to_string())
        );
        assert_eq!(
            sk.segments[1].length,
            SegmentLength::Free("b.length".to_string())
        );
    }

    #[test]
    fn arcs_via_axis_and_expressions_are_named_unsupported_reasons() {
        let arc = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n";
        let WalkPromotion::Unsupported { reason } = promote_one(arc) else {
            panic!("arc walks are outside the surface");
        };
        assert!(reason.contains("arc"), "{reason}");

        let via = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from front\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line down\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close via axis\n";
        let WalkPromotion::Unsupported { reason } = promote_one(via) else {
            panic!("revolve closure is outside the surface");
        };
        assert!(reason.contains("via axis"), "{reason}");

        let expr = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from front\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line down\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = dia 20mm / 2\n";
        let WalkPromotion::Unsupported { reason } = promote_one(expr) else {
            panic!("expression constraints are outside the surface");
        };
        assert!(reason.contains("not a plain quantity"), "{reason}");
    }

    #[test]
    fn mixed_units_and_double_pins_are_refused_by_name() {
        let mixed = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 80mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = 2cm\n";
        assert!(matches!(
            promote_one(mixed),
            WalkPromotion::Unsupported { .. }
        ));

        let double = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 80mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 90mm\n";
        let WalkPromotion::Unsupported { reason } = promote_one(double) else {
            panic!("double pins are outside the surface");
        };
        assert!(reason.contains("more than one length pin"), "{reason}");
    }

    /// Snapshot the promotion outcome of every corpus profile walk
    /// (WO-51 deliverable 1's acceptance shape): cardinal sheet
    /// profiles promote; arc/revolve profiles come back as NAMED
    /// unsupported reasons -- zero silent gaps.
    #[test]
    fn corpus_profile_promotions_snapshot() {
        let corpus: &[(&str, &str)] = &[
            (
                "sheet_bracket",
                include_str!("../../../../examples/tracks/hematite/sheet_bracket.hema"),
            ),
            (
                "pillow_block",
                include_str!("../../../../examples/tracks/hematite/pillow_block.hema"),
            ),
            (
                "torch_igniter",
                include_str!("../../../../examples/tracks/hematite/torch_igniter.hema"),
            ),
            (
                "gear_reducer",
                include_str!("../../../../examples/tracks/hematite/gear_reducer.hema"),
            ),
            (
                "molded_clip",
                include_str!("../../../../examples/tracks/hematite/molded_clip.hema"),
            ),
            (
                "cubesat_structure",
                include_str!("../../../../examples/systems/cubesat/structure.hema"),
            ),
        ];
        let mut outcomes: Vec<(String, WalkPromotion)> = Vec::new();
        for (name, src) in corpus {
            for (i, p) in promote_all(src).into_iter().enumerate() {
                outcomes.push((format!("{name}[{i}]"), p));
            }
        }
        assert!(outcomes.len() >= 8, "corpus walks found: {}", outcomes.len());
        let json = serde_json::to_string_pretty(&outcomes).expect("promotions serialize");
        insta::assert_snapshot!("corpus_walk_promotions", json);
    }
}
