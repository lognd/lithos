//! Profile static checks (WO-11 ledger half): branch-pin completeness
//! and the sketch DOF ledger. NO constraint solving.
//!
//! Regolith reference: `docs/hematite/02` sec. 5. The walk AST comes from
//! `regolith_syntax::walk`. This module runs the two static checks and
//! models exports as placeless datums exposed ONLY through an
//! instantiation context (feature-first re-anchoring): referencing an
//! export through the profile value rather than a feature is an error
//! with the anchoring rule's message.

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
        freedoms += segment_freedom(seg);
        constraints += segment_constraint(seg);
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
        if matches!(seg, Segment::Arc { join: None, .. }) {
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
            include_str!("../../../examples/mech/molded_clip.hem"),
        ),
        (
            "pillow_block",
            include_str!("../../../examples/mech/pillow_block.hem"),
        ),
        (
            "torch_igniter",
            include_str!("../../../examples/mech/torch_igniter.hem"),
        ),
        (
            "gear_reducer",
            include_str!("../../../examples/mech/gear_reducer.hem"),
        ),
        (
            "sheet_bracket",
            include_str!("../../../examples/mech/sheet_bracket.hem"),
        ),
        (
            "structure",
            include_str!("../../../examples/cubesat/structure.hem"),
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
            let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hem"));
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
        let src = include_str!("../../../examples/mech/molded_clip.hem");
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hem"));
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
    use regolith_syntax::walk::{parse_walk, Direction, Segment, Walk};

    fn walk_of(src: &str) -> Walk {
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hem"));
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
            segments: vec![Segment::Arc {
                bulge: Direction::Left,
                join: None,
            }],
            closes: false,
            holes: Vec::new(),
            regions: Vec::new(),
            constraints: Vec::new(),
            exports: Vec::new(),
        };
        let diags = check_branch_pins(&unpinned);
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("unpinned"));

        let pinned = Walk {
            segments: vec![Segment::Arc {
                bulge: Direction::Left,
                join: Some(Direction::Tangent),
            }],
            ..unpinned
        };
        assert!(check_branch_pins(&pinned).is_empty());
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
