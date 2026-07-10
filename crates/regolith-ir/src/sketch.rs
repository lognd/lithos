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
pub enum SegmentLength {
    /// Pinned to a constraint value.
    Pinned(f64),
    /// Declared `free`; the payload is the parameter name the
    /// resolution is recorded under (`c.length`).
    Free(String),
}

/// One straight segment of a closed walk: its heading and length.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
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
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
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
        return unsupported(
            profile,
            "closes `via axis` (revolve closure, not a planar loop)",
        );
    }
    let (names, headings) = match cardinal_headings(profile, walk) {
        Ok(pair) => pair,
        Err(p) => return *p,
    };
    let (lengths, unit) = match bind_lengths(profile, walk, &names) {
        Ok(pair) => pair,
        Err(p) => return *p,
    };

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

/// The name + cardinal heading of every explicit segment: each must be
/// a straight cardinal line for the closure condition to be linear
/// over it (an unlabeled step is named `_<step>`). `Err` is the boxed
/// named unsupported reason (boxed: the promotion is large relative
/// to the loop state).
#[allow(clippy::type_complexity)]
fn cardinal_headings(
    profile: &str,
    walk: &Walk,
) -> Result<(Vec<String>, Vec<f64>), Box<WalkPromotion>> {
    let mut names: Vec<String> = Vec::new();
    let mut headings: Vec<f64> = Vec::new();
    for (i, ws) in walk.segments.iter().enumerate() {
        let step = i + 1;
        let heading = match &ws.seg {
            Segment::Arc { .. } => {
                return Err(Box::new(unsupported(
                    profile,
                    &format!("step {step} is an arc (closure is nonlinear in the bulge)"),
                )));
            }
            Segment::Line(dir) => match dir {
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
            },
        };
        names.push(ws.label.clone().unwrap_or_else(|| format!("_{step}")));
        headings.push(heading);
    }
    Ok((names, headings))
}

/// Bind each named segment's length from the D150 label-bound
/// `constraints:` items: a plain-quantity `<name>.length = <qty>` pins
/// it (unit-consistent across the walk); `= free` or no item leaves it
/// a free length named `<name>.length`. A constraint naming an UNBOUND
/// segment is skipped (E0442's business -- reported once, not twice);
/// a close-edge pin, expression, mixed unit, or double pin is the
/// boxed named unsupported reason.
#[allow(clippy::type_complexity)]
fn bind_lengths(
    profile: &str,
    walk: &Walk,
    names: &[String],
) -> Result<(Vec<SegmentLength>, Option<Unit>), Box<WalkPromotion>> {
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
        let Some((value, item_unit)) = pinned_quantity(rhs) else {
            return Err(Box::new(unsupported(
                profile,
                &format!(
                    "constraint `{item}` is not a plain quantity (expression constraints \
                     are out of this increment)"
                ),
            )));
        };
        match &unit {
            None => unit = Some(item_unit),
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
                include_str!("../../../examples/systems/cubesat/structure.hema"),
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
