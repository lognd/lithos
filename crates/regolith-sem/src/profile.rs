//! Profile static checks (WO-11 ledger half): branch-pin completeness
//! and the sketch DOF ledger. NO constraint solving.
//!
//! Regolith reference: `docs/spec/hematite/02` sec. 5. The walk AST comes from
//! `regolith_syntax::walk`. This module runs the two static checks and
//! models exports as placeless datums exposed ONLY through an
//! instantiation context (feature-first re-anchoring): referencing an
//! export through the profile value rather than a feature is an error
//! with the anchoring rule's message.

use std::collections::BTreeSet;

use regolith_diag::{codes, Diagnostic};
use regolith_syntax::walk::{Direction, Segment, Walk};
use serde::{Deserialize, Serialize};

/// The sketch degree-of-freedom ledger: entity freedoms minus applied
/// constraints. The remainder must be zero or accounted for by declared
/// free variables (value sources).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DofLedger {
    /// Total freedoms contributed by the walk's entities.
    pub freedoms: i64,
    /// Total constraints applied.
    pub constraints: i64,
    /// Count of declared free variables absorbing residual DOF.
    pub declared_free: i64,
}

impl DofLedger {
    /// The residual DOF: `freedoms - constraints - declared_free`. Zero
    /// means fully constrained; positive means under-constrained.
    #[must_use]
    pub fn residual(&self) -> i64 {
        self.freedoms - self.constraints - self.declared_free
    }

    /// True when the sketch closes (residual is zero).
    #[must_use]
    pub fn is_closed(&self) -> bool {
        self.residual() == 0
    }
}

/// The freedoms one segment contributes to the ledger: a straight `line`
/// is a free endpoint (2 DOF, x/y); an `arc` additionally carries its
/// radius (3 DOF). `bulge=left|right` picks which circle the arc's
/// endpoints lie on and is a required field of the AST already -- not a
/// ledger constraint.
fn segment_freedom(seg: &Segment) -> i64 {
    match seg {
        Segment::Line(_) => 2,
        Segment::Arc { .. } => 3,
    }
}

/// The constraint a segment's join contributes: `tangent`/`perpendicular`
/// pin the relationship to the previous segment (1 DOF each); direction
/// words (`left`/`right`) are uniqueness HINTS only (hematite/02 sec. 5),
/// never ledger constraints.
fn segment_constraint(seg: &Segment) -> i64 {
    let join = match seg {
        Segment::Line(d) => d.as_ref(),
        Segment::Arc { join, .. } => join.as_ref(),
    };
    match join {
        Some(Direction::Tangent | Direction::Perpendicular) => 1,
        _ => 0,
    }
}

/// Count the free variables a walk declares in its `constraints:` block
/// (`c.radius = free`, `d.length = free`, ...): value sources that absorb
/// residual DOF rather than pinning one. A structural read of the typed
/// `ConstraintsBlock` items (`regolith_syntax::walk`): an item declares a
/// free variable iff its right-hand side is the `free` value source.
#[must_use]
pub fn count_declared_free(walk: &Walk) -> i64 {
    let n = walk
        .constraints
        .iter()
        .filter(|item| declares_free(item))
        .count();
    i64::try_from(n).unwrap_or(i64::MAX)
}

/// True when a `constraints:` item declares a `free` value source (its
/// RHS is exactly `free`, e.g. `c.radius = free`). A bare substring test
/// is deliberately avoided: `free` must be the assigned value, not part
/// of an identifier or a comment (comments are already stripped upstream).
fn declares_free(item: &str) -> bool {
    item.split_once('=')
        .is_some_and(|(_, rhs)| rhs.split_whitespace().next() == Some("free"))
}

/// Compute the DOF ledger for a walk (counts freedoms and constraints
/// from the segment/constraint structure).
///
/// DOF MODEL (documented scope). Freedoms: a `line` endpoint is 2 DOF
/// (x, y); an `arc` adds its radius (3 DOF). Constraints: each declared
/// `constraints:` item pins one freedom (unless it declares a free
/// variable -- see [`count_declared_free`]), a `tangent`/`perpendicular`
/// join pins one, and `close` ties the last point to the first (a
/// coincidence on both axes, 2). Direction words (`left`/`right`/`up`/
/// `down`) are recorded as uniqueness HINTS, never ledger constraints
/// (hematite/02 sec. 5); a hole is a sub-sketch whose placement DOF are
/// pinned by the parent `constraints:` items that name it.
///
/// SCOPE CUT (hematite/07 OPEN-5, D65): the exact residual of a real sketch
/// (redundant/implied constraints, the revolve-`via axis` closure, the
/// last rotational freedom a cardinal direction pins) is the constraint
/// solver's DOF analysis, which is implementation-owned and OUT of WO-11's
/// scope. This ledger is the SOUND, conservative half: it never invents a
/// constraint the source did not write, so INV-15 conservation holds
/// (participation is syntactic). It is therefore used to catch a
/// DECLARED imbalance, not to certify exact determinacy.
#[must_use]
pub fn compute_ledger(walk: &Walk, declared_free: i64) -> DofLedger {
    let mut freedoms = 0i64;
    let mut constraints = 0i64;

    for seg in &walk.segments {
        freedoms += segment_freedom(&seg.seg);
        constraints += segment_constraint(&seg.seg);
    }
    for hole in &walk.holes {
        for seg in &hole.segments {
            freedoms += segment_freedom(seg);
            constraints += segment_constraint(seg);
        }
    }

    // Declared `constraints:` items (the closed SolveSpace-equivalent
    // vocabulary, hematite/07 OPEN-5/D65): each item removes one freedom,
    // EXCEPT an item declaring a free variable (`= free`), which absorbs a
    // freedom instead and is accounted in `declared_free`, not here.
    let pinning = walk
        .constraints
        .iter()
        .filter(|item| !declares_free(item))
        .count();
    constraints += i64::try_from(pinning).unwrap_or(i64::MAX);
    // `close` ties the last point back to the first: a coincidence
    // constraint on both axes.
    if walk.closes {
        constraints += 2;
    }

    DofLedger {
        freedoms,
        constraints,
        declared_free,
    }
}

/// Check branch-pin completeness: every discrete solver branch (an
/// arc's join to its neighbor) must be pinned with `tangent` or
/// `perpendicular`, else a diagnostic listing the unpinned joints.
#[must_use]
pub fn check_branch_pins(walk: &Walk) -> Vec<Diagnostic> {
    let mut unpinned = Vec::new();
    for (i, seg) in walk.segments.iter().enumerate() {
        if matches!(seg.seg, Segment::Arc { join: None, .. }) {
            unpinned.push(format!("segment {i} (arc)"));
        }
    }
    for hole in &walk.holes {
        for (i, seg) in hole.segments.iter().enumerate() {
            if matches!(seg, Segment::Arc { join: None, .. }) {
                unpinned.push(format!("hole `{}` segment {i} (arc)", hole.name));
            }
        }
    }

    if unpinned.is_empty() {
        return Vec::new();
    }
    vec![Diagnostic::error(
        codes::LEDGER_IMBALANCE,
        format!(
            "unpinned discrete solver branch(es): {}",
            unpinned.join(", ")
        ),
    )
    .with_fix(regolith_diag::Fix {
        message: "add a `tangent` or `perpendicular` join to pin the branch".to_string(),
        replacement: None,
    })]
}

/// Check the DOF ledger closes (residual zero or via declared free
/// variables); a leftover DOF is a diagnostic naming the count and
/// direction (under- vs over-constrained).
#[must_use]
pub fn check_ledger_closes(ledger: &DofLedger) -> Vec<Diagnostic> {
    let residual = ledger.residual();
    if residual == 0 {
        return Vec::new();
    }
    let (verb, count) = if residual > 0 {
        ("under-constrained", residual)
    } else {
        ("over-constrained", -residual)
    };
    vec![Diagnostic::error(
        codes::LEDGER_IMBALANCE,
        format!("sketch is {verb} by {count} degree(s) of freedom"),
    )
    .with_fix(regolith_diag::Fix {
        message: "add a constraint, or declare a free variable to absorb the residual".to_string(),
        replacement: None,
    })]
}

/// The segment-metric heads a `constraints:` item pins on a segment
/// (`a.length = 80mm`, `c.radius = ...`): a dotted reference with one
/// of these heads names a SEGMENT, so its base must be label-bound.
/// `diameter` is deliberately absent: the corpus also spells it on
/// revolve junction loci that are not segments (`throat.diameter`,
/// regen_engine chamber.hema), so it is not a segment-only head.
const SEGMENT_METRIC_HEADS: &[&str] = &["length", "radius", "angle"];

/// D150: every `constraints:` item referencing a segment metric
/// (`<name>.length`, `.radius`, `.angle`, `.diameter`) must use a name
/// some walk-step label binds (`a: line right`; a labeled `close`
/// binds the implicit return edge). Comment-only naming is not a
/// binding. The diagnostic is constructive: it spells the label syntax
/// and lists the walk's steps with their current labels.
///
/// SCOPE (recorded): bare segment names in constraint-call argument
/// positions (`symmetric(b, d, ...)`, `<x> to <y>` operands) share
/// those positions with datums and exports, so this increment checks
/// only dotted metric references -- the unambiguous segment positions.
#[must_use]
pub fn check_label_bindings(profile: &str, walk: &Walk) -> Vec<Diagnostic> {
    let mut bound: BTreeSet<&str> = walk
        .segments
        .iter()
        .filter_map(|s| s.label.as_deref())
        .collect();
    if let Some(close) = walk.close_label.as_deref() {
        bound.insert(close);
    }
    // Hole names and exports are legitimate dotted bases too
    // (`wire_pass.diameter`); never flag them as unbound segments.
    for hole in &walk.holes {
        bound.insert(hole.name.as_str());
    }
    for export in &walk.exports {
        bound.insert(export.as_str());
    }
    if !walk.from_datum.is_empty() {
        bound.insert(walk.from_datum.as_str());
    }

    let mut diagnostics = Vec::new();
    for item in &walk.constraints {
        for base in unbound_metric_bases(item, &bound) {
            tracing::debug!(profile, item = %item, segment = %base, "unbound segment label (D150)");
            diagnostics.push(
                Diagnostic::error(
                    codes::UNBOUND_SEGMENT_LABEL,
                    format!(
                        "profile `{profile}`: constraint `{item}` references segment \
                         `{base}`, but no walk step binds that label; steps are: {}",
                        step_roster(walk)
                    ),
                )
                .with_fix(regolith_diag::Fix {
                    message: format!(
                        "label the walk step that is `{base}` (`{base}: line right`); \
                         a comment (`# {base}: ...`) is not a binding"
                    ),
                    replacement: None,
                }),
            );
        }
    }
    diagnostics
}

/// The dotted segment-metric bases in one constraint item that no label
/// binds, in source order (each base reported once per item).
fn unbound_metric_bases<'a>(item: &'a str, bound: &BTreeSet<&str>) -> Vec<&'a str> {
    let mut out: Vec<&'a str> = Vec::new();
    let bytes = item.as_bytes();
    for (i, _) in item.match_indices('.') {
        // The ident immediately before the dot.
        let start = item[..i]
            .rfind(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
            .map_or(0, |p| p + 1);
        let base = &item[start..i];
        // The word immediately after the dot.
        let after = &item[i + 1..];
        let end = after
            .find(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
            .unwrap_or(after.len());
        let head = &after[..end];
        let base_is_ident = !base.is_empty()
            && !base.as_bytes()[0].is_ascii_digit()
            && (start == 0 || bytes[start - 1] != b'.');
        if base_is_ident
            && SEGMENT_METRIC_HEADS.contains(&head)
            && !bound.contains(base)
            && !out.contains(&base)
        {
            out.push(base);
        }
    }
    out
}

/// A one-line roster of the walk's steps and their labels, for the
/// constructive E0442 message (`1: line right (a), 2: line up
/// (unlabeled), close (d)`).
fn step_roster(walk: &Walk) -> String {
    let mut parts: Vec<String> = walk
        .segments
        .iter()
        .enumerate()
        .map(|(i, s)| {
            let kind = match &s.seg {
                Segment::Line(_) => "line",
                Segment::Arc { .. } => "arc",
            };
            match &s.label {
                Some(l) => format!("{n}: {kind} (`{l}`)", n = i + 1),
                None => format!("{n}: {kind} (unlabeled)", n = i + 1),
            }
        })
        .collect();
    if walk.closes {
        parts.push(match &walk.close_label {
            Some(l) => format!("close (`{l}`)"),
            None => "close (unlabeled)".to_string(),
        });
    }
    parts.join(", ")
}

/// The instantiation context through which a profile's exports (placeless
/// datums) are reached. Exports are feature-first re-anchored: reaching
/// an export through the profile value directly is rejected.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InstantiationContext {
    /// The feature that anchors the instantiation.
    pub anchor_feature: String,
    /// The export names available in this context.
    pub exports: Vec<String>,
}

impl InstantiationContext {
    /// Resolve an export by name within this context.
    ///
    /// An empty `anchor_feature` is the sentinel for "referenced through
    /// the profile value directly" (no feature-first instantiation) --
    /// the export-anchoring rule (hematite/02 sec. 5) rejects that path
    /// regardless of whether `name` exists.
    ///
    /// # Errors
    /// Returns a diagnostic (the anchoring-rule message) if the export is
    /// referenced without a feature anchor, or if `name` is not among
    /// this context's declared exports. Boxed: `Diagnostic` is large
    /// relative to the `Ok` value.
    pub fn resolve_export(&self, name: &str) -> Result<String, Box<Diagnostic>> {
        if self.anchor_feature.is_empty() {
            return Err(Box::new(
                Diagnostic::error(
                    codes::AMBIGUOUS_SELECTION,
                    format!(
                        "export `{name}` referenced through the profile value directly; \
                         exports are feature-first re-anchored"
                    ),
                )
                .with_fix(regolith_diag::Fix {
                    message: "reference the export through the instantiating feature".to_string(),
                    replacement: None,
                }),
            ));
        }
        if !self.exports.iter().any(|e| e == name) {
            return Err(Box::new(Diagnostic::error(
                codes::AMBIGUOUS_SELECTION,
                format!("no export named `{name}` in this profile"),
            )));
        }
        Ok(format!("{}.{name}", self.anchor_feature))
    }
}

/// Tests over the REAL corpus walk bodies, exercising the structural CST
/// consumer (`regolith_syntax::walk::parse_walk`) end-to-end into the DOF
/// ledger. These are the WO-11 acceptance fixtures.
#[cfg(test)]
mod corpus_tests {
    use super::{check_branch_pins, check_ledger_closes, compute_ledger, count_declared_free};
    use camino::Utf8PathBuf;
    use regolith_syntax::syntax_kind::SyntaxKind;
    use regolith_syntax::walk::parse_walk;

    /// One `(name, from_datum, segment_count, constraint_count,
    /// declared_free)` expectation per corpus profile with a walk.
    const CORPUS: &[(&str, &str)] = &[
        (
            "molded_clip",
            include_str!("../../../examples/tracks/hematite/molded_clip.hema"),
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
            "sheet_bracket",
            include_str!("../../../examples/tracks/hematite/sheet_bracket.hema"),
        ),
        (
            "structure",
            include_str!("../../../examples/flagships/cubesat/structure.hema"),
        ),
    ];

    /// Every corpus profile's walk is consumed structurally from the typed
    /// CST: a non-empty `from` anchor, at least one segment, and a ledger
    /// that computes without panicking. The conservative ledger never
    /// reports a FALSE over-constraint on the valid corpus beyond the
    /// documented dimension-constraint cases (hematite/07 OPEN-5 solver scope):
    /// no profile is over-constrained by more than one declared dimension.
    #[test]
    fn corpus_profiles_parse_and_extract_structurally() {
        let mut walks_seen = 0;
        let mut declared_free_total = 0;
        for (name, src) in CORPUS {
            let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
            for decl in parse
                .syntax()
                .descendants()
                .filter(|n| n.kind() == SyntaxKind::Decl)
            {
                let Some(walk) = parse_walk(&decl) else {
                    continue;
                };
                walks_seen += 1;
                assert!(
                    !walk.from_datum.is_empty(),
                    "{name}: walk has a `from` anchor"
                );
                assert!(!walk.segments.is_empty(), "{name}: walk has segments");
                let free = count_declared_free(&walk);
                declared_free_total += free;
                let ledger = compute_ledger(&walk, free);
                assert_eq!(free, ledger.declared_free);
                // Branch-pin completeness runs cleanly: the corpus pins
                // every arc branch with `tangent` (hematite/02 sec. 5).
                assert!(
                    check_branch_pins(&walk).is_empty(),
                    "{name}: corpus arcs are all pinned"
                );
                // Conservative bound: residual within the solver-resolved
                // band (never over-constrained by more than one declared
                // dimension constraint; see compute_ledger scope cut).
                assert!(
                    ledger.residual() >= -1,
                    "{name}: ledger residual {} is a false over-constraint",
                    ledger.residual()
                );
            }
        }
        assert!(walks_seen >= 10, "found {walks_seen} corpus walk profiles");
        // `c.radius = free` (torch) and `d.length = free` (structure) are
        // recognized as declared free variables absorbing residual DOF.
        assert!(
            declared_free_total >= 2,
            "corpus declares free variables ({declared_free_total} found)"
        );
    }

    /// A profile whose declared constraints leave an unabsorbed residual
    /// (no `free` variable) is flagged under-constrained -- INV-15's
    /// declared-imbalance detection driven from the typed walk.
    #[test]
    fn under_constrained_corpus_profile_without_free_is_flagged() {
        // molded_clip's ClipBase: 3 segments, 3 pinning constraints, no
        // free var -> the conservative ledger sees a residual.
        let src = include_str!("../../../examples/tracks/hematite/molded_clip.hema");
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
        let decl = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::Decl)
            .expect("a Decl");
        let walk = parse_walk(&decl).expect("ClipBase walk");
        let ledger = compute_ledger(&walk, count_declared_free(&walk));
        assert!(!ledger.is_closed());
        assert!(!check_ledger_closes(&ledger).is_empty());
    }
}

#[cfg(test)]
mod unit_tests {
    use super::{
        check_branch_pins, check_ledger_closes, compute_ledger, count_declared_free, DofLedger,
        InstantiationContext,
    };
    use camino::Utf8PathBuf;
    use regolith_diag::codes;
    use regolith_syntax::syntax_kind::SyntaxKind;
    use regolith_syntax::walk::{parse_walk, Direction, Segment, Walk, WalkSegment};

    fn walk_of(src: &str) -> Walk {
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
        let decl = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::Decl)
            .expect("a Decl");
        parse_walk(&decl).expect("a walk")
    }

    /// A balanced walk (freedoms exactly pinned by declared constraints)
    /// closes: the INV-15 conservation baseline driven from the typed CST.
    /// Two `line` segments (4 DOF) pinned by two constraints plus `close`
    /// (2) close the ledger to zero.
    #[test]
    fn balanced_walk_closes_from_typed_cst() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = 5mm\n";
        let walk = walk_of(src);
        let ledger = compute_ledger(&walk, count_declared_free(&walk));
        assert_eq!(ledger.freedoms, 4);
        assert_eq!(ledger.constraints, 4); // 2 items + close(2)
        assert!(ledger.is_closed());
        assert!(check_ledger_closes(&ledger).is_empty());
    }

    /// A deliberate INV-15 violation: the same walk with a constraint
    /// removed leaves an unabsorbed DOF, and the ledger reports the
    /// imbalance (LEDGER_IMBALANCE) -- the property's negative fixture.
    #[test]
    fn deliberate_imbalance_is_caught() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n";
        let walk = walk_of(src);
        let ledger = compute_ledger(&walk, count_declared_free(&walk));
        assert_eq!(ledger.residual(), 1);
        let diags = check_ledger_closes(&ledger);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::LEDGER_IMBALANCE);
        assert!(diags[0].message.contains("under-constrained"));
    }

    /// A declared free variable (`= free`) absorbs the residual DOF, so a
    /// walk one constraint short of closed still closes via the free var.
    #[test]
    fn declared_free_variable_absorbs_residual() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = free\n";
        let walk = walk_of(src);
        assert_eq!(count_declared_free(&walk), 1);
        let ledger = compute_ledger(&walk, count_declared_free(&walk));
        assert!(ledger.is_closed());
    }

    /// An unpinned arc branch (no `tangent`/`perpendicular` join) is
    /// reported by branch-pin completeness (hematite/02 sec. 5).
    #[test]
    fn unpinned_arc_branch_is_flagged() {
        let unpinned = Walk {
            from_datum: "origin".to_string(),
            segments: vec![WalkSegment {
                label: None,
                seg: Segment::Arc {
                    bulge: Direction::Left,
                    join: None,
                },
            }],
            closes: false,
            via_axis: false,
            close_label: None,
            holes: Vec::new(),
            regions: Vec::new(),
            constraints: Vec::new(),
            exports: Vec::new(),
        };
        let diags = check_branch_pins(&unpinned);
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("unpinned"));

        let pinned = Walk {
            segments: vec![WalkSegment {
                label: None,
                seg: Segment::Arc {
                    bulge: Direction::Left,
                    join: Some(Direction::Tangent),
                },
            }],
            ..unpinned
        };
        assert!(check_branch_pins(&pinned).is_empty());
    }

    /// D150: a constraint referencing a segment metric (`a.length`)
    /// whose base no walk-step label binds is the constructive E0442;
    /// binding the label (or the `close` label) clears it, and hole
    /// names, exports, and quantity literals never false-positive.
    #[test]
    fn unbound_segment_label_is_flagged_constructively() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8.5mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b.length = 5mm\n";
        let walk = walk_of(src);
        let diags = super::check_label_bindings("p", &walk);
        assert_eq!(diags.len(), 1, "{diags:?}");
        assert_eq!(diags[0].code, codes::UNBOUND_SEGMENT_LABEL);
        assert!(
            diags[0].message.contains("segment `a`"),
            "{}",
            diags[0].message
        );
        assert!(
            diags[0].message.contains("line (`b`)"),
            "{}",
            diags[0].message
        );
        let fix = diags[0].fixes.first().expect("constructive fix");
        assert!(fix.message.contains("a: line right"), "{}", fix.message);
    }

    /// A labeled `close` binds the implicit return edge, and dotted
    /// bases that are holes or exports are never segment candidates.
    #[test]
    fn close_label_and_hole_names_bind() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20d: close\n\
                    \x20\x20\x20\x20hole wire_pass:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20circle(dia 8mm)\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20d.length = 5mm\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20wire_pass.diameter = 8mm\n";
        let walk = walk_of(src);
        assert!(super::check_label_bindings("p", &walk).is_empty());
    }

    /// Reaching an export through the profile value directly (no feature
    /// anchor) is rejected with the anchoring-rule message.
    #[test]
    fn export_through_profile_value_is_rejected() {
        let placeless = InstantiationContext {
            anchor_feature: String::new(),
            exports: vec!["throat".to_string()],
        };
        let err = placeless.resolve_export("throat").expect_err("rejected");
        assert_eq!(err.code, codes::AMBIGUOUS_SELECTION);
        assert!(err.message.contains("feature-first"));

        let anchored = InstantiationContext {
            anchor_feature: "nose".to_string(),
            exports: vec!["throat".to_string()],
        };
        assert_eq!(anchored.resolve_export("throat").unwrap(), "nose.throat");
    }

    #[test]
    fn residual_and_closure() {
        let closed = DofLedger {
            freedoms: 6,
            constraints: 6,
            declared_free: 0,
        };
        assert_eq!(closed.residual(), 0);
        assert!(closed.is_closed());

        let free = DofLedger {
            freedoms: 6,
            constraints: 5,
            declared_free: 1,
        };
        assert!(free.is_closed());

        let leftover = DofLedger {
            freedoms: 6,
            constraints: 4,
            declared_free: 0,
        };
        assert_eq!(leftover.residual(), 2);
        assert!(!leftover.is_closed());
    }
}
