//! The typed sketch payload (WO-51): the closure-problem data types
//! and the Walk -> SketchClosure promotion over D150 name labels.
//!
//! UNCONDITIONAL (not behind the `solve` feature): these are payload
//! DATA -- `FeatureProgram` carries them into `BuildPayload` (schemars
//! single-sourcing, AD-11) -- while the numeric residual solve over
//! them ([`crate::solve::sketch::close_walk`], WO-23) stays behind
//! `solve`. Promotion covers straight cardinal walks; everything the
//! surface cannot express comes back as a NAMED
//! [`WalkPromotion::Unsupported`] reason (arcs -- their closure
//! condition is nonlinear in the bulge -- revolve `close via axis`,
//! non-cardinal lines, expression constraints), never a silent skip.

use regolith_qty::Unit;
use regolith_syntax::walk::{Direction, Segment, Walk};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A segment length: pinned by a constraint, or a declared `free`
/// parameter the closure solve resolves (INV-21).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-ir.md#sketch
pub enum SegmentLength {
    /// Pinned to a constraint value.
    Pinned(f64),
    /// Declared `free`; the payload is the parameter name the
    /// resolution is recorded under (`c.length`).
    Free(String),
    /// A `free` length constrained to `[lo, hi]` with an optimize
    /// `direction` (`b.length = in [3mm, 8mm] minimize`): the bounded
    /// sketch-segment slot the optimizer sizes (D205/D209). Carried
    /// INERT by WO-104 -- nothing in this crate emits or consumes it yet
    /// (the promotion surface still produces only `Pinned`/`Free`); WO-97
    /// is the consumer. Mirrors `removal::SlotValue::Bounded` at the
    /// sketch-length level. `lo`/`hi` are magnitudes in the enclosing
    /// [`SketchClosure::unit`]; `cause` is `planner` (INV-21).
    Bounded {
        /// Lower bound magnitude, in the closure's unit.
        lo: f64,
        /// Upper bound magnitude, in the closure's unit.
        hi: f64,
        /// The optimize direction, `minimize` or `maximize`
        /// (the `regolith_qty` `Direction` vocabulary, spelled as a
        /// stable string so no JsonSchema dependency crosses crates).
        direction: String,
    },
}

/// The geometry of a tangent/perpendicular arc segment (WO-104): an
/// `arc tangent, bulge=left` step of a profile walk. Present only on
/// arc segments; a straight cardinal segment carries `None`. The
/// REALIZER builds a real arc edge from the join + bulge + the arc's
/// endpoints (OCP `RadiusArc`/`TangentArc`); the linear closure solve
/// ([`crate::solve::sketch::close_walk`]) adds NO contribution for an
/// arc segment (its closure is nonlinear in the bulge radius -- sizing
/// a free arc is a separate increment), so the arc is carried for
/// geometry, never sized by a fabricated straight chord.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-ir.md#sketch
pub struct ArcGeometry {
    /// The bulge side as spelled (`left`/`right`).
    pub bulge: String,
    /// The join word (`tangent`/`perpendicular`), when spelled.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub join: Option<String>,
    /// The arc's radius (SCHEMA_VERSION 30, D231/WO116-F1): captured
    /// from a `<name>.radius = <qty>` constraint item (`bind_lengths`'s
    /// sibling capture, alongside `.length`). `None` when the walk
    /// never pins the radius -- promotion then reports the arc as
    /// [`WalkPromotion::Unsupported`] rather than let the closure solve
    /// silently ignore its real geometric contribution (never a
    /// fabricated closure).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub radius: Option<f64>,
}

/// One segment of a closed walk: its heading and length, plus (WO-104)
/// its arc geometry when the step is an `arc` rather than a straight
/// cardinal line. A straight segment carries `arc: None` and is the
/// only kind the linear closure solve sums.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-ir.md#sketch
pub struct ClosureSegment {
    /// Segment name (for diagnostics).
    pub name: String,
    /// Heading in degrees, counterclockwise from +x (`0` = right,
    /// `90` = up -- the walk's cardinal direction words). For an arc
    /// segment this is the START tangent heading (the previous
    /// segment's heading), recorded for realizer edge construction.
    pub angle_deg: f64,
    /// The segment length: pinned or free.
    pub length: SegmentLength,
    /// The arc geometry when this step is an `arc` (WO-104); `None` for
    /// a straight cardinal line.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub arc: Option<ArcGeometry>,
}

/// The typed closure problem for one profile walk.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-ir.md#sketch
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

/// The outcome of promoting a parsed profile walk into the typed
/// closure problem (WO-51 deliverable 1, D150 labels): promoted, or a
/// NAMED reason this increment's surface cannot express it -- recorded
/// so the emission pass reports it, never a silent skip.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-ir.md#sketch
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
// frob:doc docs/modules/regolith-ir.md#sketch
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn sketch_closure_from_walk(profile: &str, walk: &Walk) -> WalkPromotion {
    let span = tracing::info_span!("solve.sketch.promote", profile);
    let _enter = span.enter();

    if walk.via_axis {
        return unsupported(
            profile,
            "closes `via axis` (revolve closure, not a planar loop)",
        );
    }
    let (names, headings, mut arcs) = match cardinal_headings(profile, walk) {
        Ok(triple) => triple,
        Err(p) => return *p,
    };
    let (lengths, unit) = match bind_lengths(profile, walk, &names, &mut arcs) {
        Ok(pair) => pair,
        Err(p) => return *p,
    };

    let segments = names
        .into_iter()
        .zip(headings)
        .zip(lengths)
        .zip(arcs)
        .map(|(((name, angle_deg), length), arc)| ClosureSegment {
            name,
            angle_deg,
            length,
            arc,
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

/// The name + heading + arc geometry of every explicit segment. A
/// straight step must be a cardinal line for the closure condition to
/// be linear over it (an unlabeled step is named `_<step>`); an `arc`
/// step (WO-104) is carried with its bulge/join geometry and the START
/// tangent heading (the previous straight segment's heading), for the
/// realizer to build a real edge -- the linear closure sum skips it.
/// An arc as the FIRST segment (no previous tangent) is still a named
/// unsupported reason. `Err` is the boxed named unsupported reason
/// (boxed: the promotion is large relative to the loop state).
#[allow(clippy::type_complexity)]
fn cardinal_headings(
    profile: &str,
    walk: &Walk,
) -> Result<(Vec<String>, Vec<f64>, Vec<Option<ArcGeometry>>), Box<WalkPromotion>> {
    let mut names: Vec<String> = Vec::new();
    let mut headings: Vec<f64> = Vec::new();
    let mut arcs: Vec<Option<ArcGeometry>> = Vec::new();
    let mut last_heading: Option<f64> = None;
    for (i, ws) in walk.segments.iter().enumerate() {
        let step = i + 1;
        let (heading, arc) = match &ws.seg {
            Segment::Arc { bulge, join } => {
                let Some(tangent) = last_heading else {
                    return Err(Box::new(unsupported(
                        profile,
                        &format!(
                            "step {step} is an arc with no preceding straight segment \
                             (no start tangent to build it from)"
                        ),
                    )));
                };
                let geometry = ArcGeometry {
                    bulge: format!("{bulge:?}").to_lowercase(),
                    join: join.as_ref().map(|j| format!("{j:?}").to_lowercase()),
                    radius: None,
                };
                (tangent, Some(geometry))
            }
            Segment::Line(dir) => {
                let heading = match dir {
                    Some(Direction::Right) => 0.0,
                    Some(Direction::Up) => 90.0,
                    Some(Direction::Left) => 180.0,
                    Some(Direction::Down) => 270.0,
                    other => {
                        return Err(Box::new(unsupported(
                            profile,
                            &format!(
                                "step {step} is a line without a cardinal direction word \
                                 ({other:?})"
                            ),
                        )));
                    }
                };
                last_heading = Some(heading);
                (heading, None)
            }
        };
        names.push(ws.label.clone().unwrap_or_else(|| format!("_{step}")));
        headings.push(heading);
        arcs.push(arc);
    }
    Ok((names, headings, arcs))
}

/// Bind each named segment's length from the D150 label-bound
/// `constraints:` items: a plain-quantity `<name>.length = <qty>` pins
/// it (unit-consistent across the walk); `= in [lo, hi] minimize`
/// (D205/D209, WO-97) makes it an optimizer-sized
/// [`SegmentLength::Bounded`] slot; `= free` or no item leaves it a free
/// length named `<name>.length`. A constraint naming an UNBOUND segment
/// is skipped (E0442's business -- reported once, not twice); a
/// close-edge pin, expression, mixed unit, malformed bounded slot, or
/// double pin is the boxed named unsupported reason.
///
/// Also captures a `<name>.radius = <qty>` item into the matching arc
/// segment's [`ArcGeometry::radius`] (D231/WO116-F1, SCHEMA_VERSION
/// 30): the sibling of the `.length` capture above, but only for a
/// PLAIN pinned quantity -- the F123 closed-form closure this feeds
/// needs a concrete radius, never a `free`/bounded slot (those stay
/// `None`, unchanged from the pre-D231 behavior where the arc is
/// carried for realizer geometry only, never sized by the closure
/// solve). A `.radius` naming a non-arc segment, or a segment radius
/// pinned twice, is the boxed named unsupported reason; unit-unified
/// with the walk's other pinned quantities exactly as `.length` is.
#[allow(clippy::type_complexity)]
fn bind_lengths(
    profile: &str,
    walk: &Walk,
    names: &[String],
    arcs: &mut [Option<ArcGeometry>],
) -> Result<(Vec<SegmentLength>, Option<Unit>), Box<WalkPromotion>> {
    let mut lengths: Vec<SegmentLength> = names
        .iter()
        .map(|n| SegmentLength::Free(format!("{n}.length")))
        .collect();
    let mut pinned_seen: Vec<bool> = vec![false; names.len()];
    let mut radius_seen: Vec<bool> = vec![false; names.len()];
    let mut unit: Option<Unit> = None;
    for item in &walk.constraints {
        if let Some((base, rhs)) = radius_item(item) {
            let Some(idx) = names.iter().position(|n| n == base) else {
                tracing::debug!(
                    profile,
                    base,
                    "radius item names no bound segment; E0442 owns it"
                );
                continue;
            };
            let Some(arc) = arcs[idx].as_mut() else {
                return Err(Box::new(unsupported(
                    profile,
                    &format!("constraint `{item}` pins a radius on `{base}`, a non-arc segment"),
                )));
            };
            if rhs == "free" {
                continue; // stays uncaptured, realizer-geometry-only (pre-D231 behavior)
            }
            if radius_seen[idx] {
                return Err(Box::new(unsupported(
                    profile,
                    &format!(
                        "segment `{base}` has more than one radius pin (inconsistent by construction)"
                    ),
                )));
            }
            // A bounded/expression radius slot is out of THIS increment's
            // scope (D231 grants only the plain-pin capture the F123
            // closed-form solve needs) -- left uncaptured (`None`), same
            // as the pre-D231 status quo, never a fabricated reject.
            if let Some((value, item_unit)) = pinned_quantity(rhs) {
                unify_unit(profile, &mut unit, item_unit)?;
                arc.radius = Some(value);
                radius_seen[idx] = true;
            }
            continue;
        }
        let Some((base, rhs)) = length_item(item) else {
            continue;
        };
        if walk.close_label.as_deref() == Some(base) {
            return Err(Box::new(unsupported(
                profile,
                &format!(
                    "constraint `{item}` pins the close edge `{base}` (the close-edge \
                     solve is the next increment)"
                ),
            )));
        }
        let Some(idx) = names.iter().position(|n| n == base) else {
            // Unbound segment name: E0442 (check_label_bindings) owns
            // the report; promoting must not double-count it.
            tracing::debug!(
                profile,
                base,
                "length item names no bound segment; E0442 owns it"
            );
            continue;
        };
        if rhs == "free" {
            continue; // already Free by default, declared explicitly
        }
        if pinned_seen[idx] {
            return Err(Box::new(unsupported(
                profile,
                &format!(
                    "segment `{base}` has more than one length pin (inconsistent by construction)"
                ),
            )));
        }
        // A bounded optimize slot `= in [lo, hi] minimize` (D205/D209,
        // WO-97): the segment survives promotion as an optimizer-sized
        // `SegmentLength::Bounded`, its bounds unit-unified with the rest
        // of the walk exactly as a plain pin is. Sized later by the
        // continuous optimizer against the owning part's claims -- never
        // pinned to a literal here.
        if let Some((lo, hi, item_unit, direction)) = bounded_slot(profile, item, rhs)? {
            unify_unit(profile, &mut unit, item_unit)?;
            lengths[idx] = SegmentLength::Bounded { lo, hi, direction };
            pinned_seen[idx] = true;
            continue;
        }
        let Some((value, item_unit)) = pinned_quantity(rhs) else {
            return Err(Box::new(unsupported(
                profile,
                &format!(
                    "constraint `{item}` is not a plain quantity (expression constraints \
                     are out of this increment)"
                ),
            )));
        };
        unify_unit(profile, &mut unit, item_unit)?;
        lengths[idx] = SegmentLength::Pinned(value);
        pinned_seen[idx] = true;
    }
    Ok((lengths, unit))
}

/// Log and wrap one named unsupported-promotion reason.
fn unsupported(profile: &str, reason: &str) -> WalkPromotion {
    tracing::info!(profile, reason, "walk outside the v1 promotion surface");
    WalkPromotion::Unsupported {
        reason: format!("profile `{profile}`: {reason}"),
    }
}

/// Split a `constraints:` item of the shape `<base>.radius = <rhs>`
/// into `(base, rhs)` (D231/WO116-F1's sibling of [`length_item`]);
/// `None` for every other constraint form.
fn radius_item(item: &str) -> Option<(&str, &str)> {
    let (lhs, rhs) = item.split_once('=')?;
    let lhs = lhs.trim();
    let base = lhs.strip_suffix(".radius")?;
    let base_ok = !base.is_empty()
        && !base.as_bytes()[0].is_ascii_digit()
        && base.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
    if base_ok {
        Some((base, rhs.trim()))
    } else {
        None
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
        && base.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
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

/// Unify one length item's unit into the walk's single closure unit:
/// the first item sets it; a later item must match. A mismatch is the
/// boxed named unsupported reason (mixed units cannot share one closure
/// coordinate system). Shared by the plain-pin and bounded-slot paths
/// so the rule lives in exactly one place (CLAUDE.md NO DUPLICATION).
fn unify_unit(
    profile: &str,
    unit: &mut Option<Unit>,
    item_unit: Unit,
) -> Result<(), Box<WalkPromotion>> {
    match unit {
        None => *unit = Some(item_unit),
        Some(u) if *u == item_unit => {}
        Some(u) => {
            return Err(Box::new(unsupported(
                profile,
                &format!(
                    "mixed pinned units (`{}` vs `{}`)",
                    u.symbol, item_unit.symbol
                ),
            )));
        }
    }
    Ok(())
}

/// Parse a bounded optimize-slot RHS `in [<lo>, <hi>] <direction>`
/// (`in [3mm, 8mm] minimize`) into `(lo, hi, unit, direction)` -- the
/// D205/D209 bounded sketch-segment slot the continuous optimizer sizes
/// (WO-97), carried as [`SegmentLength::Bounded`]. `Ok(None)` when the
/// RHS is not the `in [..]` shape at all (a plain pin or expression is
/// tried next). `Err` is a boxed NAMED unsupported reason for an `in
/// [..]` that is malformed: a bad direction word, non-plain-quantity or
/// mixed-unit bounds, or a non-positive / inverted range (fail loud, so
/// a typo never silently degrades to a plain-pin attempt).
#[allow(clippy::type_complexity)]
fn bounded_slot(
    profile: &str,
    item: &str,
    rhs: &str,
) -> Result<Option<(f64, f64, Unit, String)>, Box<WalkPromotion>> {
    let Some(after_in) = rhs.strip_prefix("in ") else {
        return Ok(None);
    };
    let after_in = after_in.trim_start();
    let Some(open) = after_in.strip_prefix('[') else {
        return Ok(None);
    };
    let malformed = |reason: &str| -> Box<WalkPromotion> {
        Box::new(unsupported(
            profile,
            &format!("constraint `{item}`: {reason}"),
        ))
    };
    let Some((inside, tail)) = open.split_once(']') else {
        return Err(malformed(
            "bounded slot `in [lo, hi] dir` is missing its `]`",
        ));
    };
    let direction = tail.trim();
    if direction != "minimize" && direction != "maximize" {
        return Err(malformed(
            "bounded slot direction must be `minimize` or `maximize`",
        ));
    }
    let Some((lo_text, hi_text)) = inside.split_once(',') else {
        return Err(malformed(
            "bounded slot `in [lo, hi]` needs two comma-separated bounds",
        ));
    };
    let Some((lo, lo_unit)) = pinned_quantity(lo_text.trim()) else {
        return Err(malformed(
            "bounded slot lower bound is not a plain quantity",
        ));
    };
    let Some((hi, hi_unit)) = pinned_quantity(hi_text.trim()) else {
        return Err(malformed(
            "bounded slot upper bound is not a plain quantity",
        ));
    };
    if lo_unit != hi_unit {
        return Err(malformed("bounded slot bounds have mixed units"));
    }
    if !(lo.is_finite() && hi.is_finite()) || lo < 0.0 || hi <= lo {
        return Err(malformed(
            "bounded slot needs a non-negative, strictly increasing range `[lo, hi]`",
        ));
    }
    Ok(Some((lo, hi, lo_unit, direction.to_string())))
}

/// WO-51 deliverable 1: the Walk -> SketchClosure promotion, unit
/// cases plus snapshot tests over the REAL corpus profiles (the walks
/// regolith-sem's WO-11 acceptance fixtures exercise).
#[cfg(test)]
mod promotion_tests {
    #[cfg(feature = "solve")]
    use crate::solve::sketch::close_walk;

    use super::{sketch_closure_from_walk, SegmentLength, WalkPromotion};
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

    // Exact float equality is deliberate: cardinal headings and pinned
    // lengths are exact constants end to end (the INV-10 exact-cosine
    // contract), so any drift IS the bug this test exists to catch.
    #[allow(clippy::float_cmp)]
    // frob:tests crates/regolith-ir/src/sketch.rs::sketch_closure_from_walk kind="unit"
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
        // The close edge absorbs both closure equations (WO-62
        // D171/AD-32); the still-free segment `c` has nothing left to
        // solve it, so this is the E0447 under-constrained case.
        let sol = close_walk(&sk);
        assert_eq!(sol.diagnostics.len(), 1);
        assert_eq!(
            sol.diagnostics[0].code,
            regolith_diag::codes::SKETCH_CLOSE_EDGE_UNDERCONSTRAINED
        );
        assert!(sol.diagnostics[0].message.contains('c'));
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

    // Exact float equality: the bounds are exact literals end to end.
    #[allow(clippy::float_cmp)]
    #[test]
    fn bounded_optimize_slot_promotes_as_a_bounded_segment() {
        // WO-97 (D205/D209): `b.length = in [3mm, 8mm] minimize` (the
        // `uav_talon` SparCapFlat shape) survives promotion as an
        // optimizer-sized `SegmentLength::Bounded`, unit-unified with the
        // walk's plain pins -- never rejected as an expression.
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from root_edge\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20c: line left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20d: close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 900mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = in [3mm, 8mm] minimize\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20c.length = 900mm\n";
        let WalkPromotion::Promoted(sk) = promote_one(src) else {
            panic!("a bounded optimize slot promotes");
        };
        assert_eq!(sk.unit.symbol, "mm");
        assert_eq!(sk.segments[0].length, SegmentLength::Pinned(900.0));
        assert_eq!(
            sk.segments[1].length,
            SegmentLength::Bounded {
                lo: 3.0,
                hi: 8.0,
                direction: "minimize".to_string(),
            }
        );
        assert_eq!(sk.close_edge.as_deref(), Some("d"));
    }

    #[test]
    fn malformed_bounded_slots_are_named_unsupported_reasons() {
        // A bad direction word and an inverted range each fail loud.
        let bad_dir = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = in [3mm, 8mm] wobble\n";
        let WalkPromotion::Unsupported { reason } = promote_one(bad_dir) else {
            panic!("a bad direction word is unsupported");
        };
        assert!(reason.contains("minimize"), "{reason}");

        let inverted = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = in [8mm, 3mm] minimize\n";
        let WalkPromotion::Unsupported { reason } = promote_one(inverted) else {
            panic!("an inverted range is unsupported");
        };
        assert!(reason.contains("increasing"), "{reason}");
    }

    #[test]
    fn tangent_arc_after_a_line_promotes_with_arc_geometry() {
        // WO-104: an `arc tangent, bulge=left` after a straight segment
        // promotes, carrying its arc geometry for the realizer -- the
        // straight-line-only guard is now arc-AWARE, not a blanket
        // unsupported reason.
        let arc = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n";
        let WalkPromotion::Promoted(sk) = promote_one(arc) else {
            panic!("a tangent arc after a line promotes (arc-aware)");
        };
        assert_eq!(sk.segments.len(), 2);
        assert!(sk.segments[0].arc.is_none(), "the line is not an arc");
        let arc_seg = sk.segments[1].arc.as_ref().expect("segment b is an arc");
        assert_eq!(arc_seg.bulge, "left");
        assert_eq!(arc_seg.join.as_deref(), Some("tangent"));
    }

    #[test]
    fn radius_constraint_captures_into_arc_geometry() {
        // D231/WO116-F1: a `<name>.radius = <qty>` constraint item binds
        // into the matching arc segment's `ArcGeometry.radius` -- the
        // GantryBeam `BeamSection` shape (`c.radius = 6mm`).
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.radius = 6mm\n";
        let WalkPromotion::Promoted(sk) = promote_one(src) else {
            panic!("radius-pinned arc still promotes");
        };
        let arc_seg = sk.segments[1].arc.as_ref().expect("segment b is an arc");
        assert_eq!(arc_seg.radius, Some(6.0));
    }

    #[test]
    fn radius_on_a_non_arc_segment_is_a_named_unsupported_reason() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.radius = 6mm\n";
        let WalkPromotion::Unsupported { reason } = promote_one(src) else {
            panic!("a radius pin on a straight segment must be refused by name");
        };
        assert!(reason.contains("non-arc"), "{reason}");
    }

    #[test]
    fn double_radius_pin_is_a_named_unsupported_reason() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.radius = 6mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.radius = 8mm\n";
        let WalkPromotion::Unsupported { reason } = promote_one(src) else {
            panic!("a segment radius pinned twice must be refused by name");
        };
        assert!(reason.contains("more than one radius pin"), "{reason}");
    }

    #[test]
    fn free_radius_stays_uncaptured_pre_d231_behavior() {
        // A bounded/free radius slot is out of THIS increment's closed-
        // form scope (D231): it stays `None`, exactly the pre-D231
        // status quo (realizer geometry only, never sized by closure).
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.radius = free\n";
        let WalkPromotion::Promoted(sk) = promote_one(src) else {
            panic!("a free-radius arc still promotes")
        };
        assert!(sk.segments[1].arc.as_ref().unwrap().radius.is_none());
    }

    #[test]
    fn leading_arc_via_axis_and_expressions_are_named_unsupported_reasons() {
        // An arc with no preceding straight segment has no start tangent.
        let lead_arc = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: arc tangent, bulge=left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n";
        let WalkPromotion::Unsupported { reason } = promote_one(lead_arc) else {
            panic!("a leading arc has no start tangent");
        };
        assert!(reason.contains("no preceding straight segment"), "{reason}");

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
                include_str!("../../../examples/tracks/hematite/sheet_bracket.hema"),
            ),
            (
                "pillow_block",
                include_str!("../../../examples/tracks/hematite/pillow_block.hema"),
            ),
            (
                "torch_igniter",
                include_str!("../../../examples/tracks/hematite/torch_igniter.hema"),
            ),
            (
                "gear_reducer",
                include_str!("../../../examples/tracks/hematite/gear_reducer.hema"),
            ),
            (
                "molded_clip",
                include_str!("../../../examples/tracks/hematite/molded_clip.hema"),
            ),
            (
                "cubesat_structure",
                include_str!("../../../examples/flagships/cubesat/structure.hema"),
            ),
        ];
        let mut outcomes: Vec<(String, WalkPromotion)> = Vec::new();
        for (name, src) in corpus {
            for (i, p) in promote_all(src).into_iter().enumerate() {
                outcomes.push((format!("{name}[{i}]"), p));
            }
        }
        assert!(
            outcomes.len() >= 8,
            "corpus walks found: {}",
            outcomes.len()
        );
        let json = serde_json::to_string_pretty(&outcomes).expect("promotions serialize");
        insta::assert_snapshot!("corpus_walk_promotions", json);
    }
}
