//! Walk bodies: the elaborated form of the WO-05 opaque profile islands
//! (WO-11 grammar half). A walk is a pen-path sketch: segments, joins,
//! holes, regions, constraints, and exports.
//!
//! Regolith reference: `docs/spec/hematite/02` sec. 5. The constraint vocabulary
//! is the closed SolveSpace-equivalent set (hematite/07 OPEN-5, D65); NO
//! solving happens here -- this module records structure for the static
//! ledger (regolith-sem `profile`). Direction words are recorded as
//! uniqueness hints; that a hint disambiguates is checked at solve time.

use crate::cst::SyntaxNode;
use crate::syntax_kind::SyntaxKind;

/// A direction word annotating a segment (a uniqueness hint, validated
/// at solve time, recorded here).
// frob:doc docs/modules/regolith-syntax.md#walk
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Direction {
    /// Turn/curve to the left.
    Left,
    /// Turn/curve to the right.
    Right,
    /// Head up (cardinal word; recorded for the closure promotion, D150).
    Up,
    /// Head down (cardinal word; recorded for the closure promotion, D150).
    Down,
    /// Continue tangent to the previous segment.
    Tangent,
    /// Meet the previous segment perpendicularly.
    Perpendicular,
}

/// One segment of the walk.
// frob:doc docs/modules/regolith-syntax.md#walk
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Segment {
    /// A straight `line` with an optional direction word.
    Line(Option<Direction>),
    /// An `arc` with a bulge side and optional join word.
    Arc {
        /// `bulge=left|right`.
        bulge: Direction,
        /// Optional tangent/perpendicular join.
        join: Option<Direction>,
    },
}

/// One walk step's segment with its optional leading name label
/// (`a: line right`, D150): the syntax-level binding `constraints:`
/// items reference (`a.length = 80mm`). Unlabeled steps stay legal.
// frob:doc docs/modules/regolith-syntax.md#walk
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalkSegment {
    /// The D150 name label, when the step spells one (`a:`).
    pub label: Option<String>,
    /// The segment itself.
    pub seg: Segment,
}

/// A named hole nested one level inside the walk (`hole <name>:`).
// frob:doc docs/modules/regolith-syntax.md#walk
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Hole {
    /// Hole name.
    pub name: String,
    /// The hole's own segments (one nesting level only).
    pub segments: Vec<Segment>,
}

/// A parsed walk body.
// frob:doc docs/modules/regolith-syntax.md#walk
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Walk {
    /// The `from <datum>` anchor name.
    pub from_datum: String,
    /// The ordered segments, each with its optional D150 name label.
    pub segments: Vec<WalkSegment>,
    /// Whether the walk closes (`close [via axis]`).
    pub closes: bool,
    /// Whether the close is the revolve-centerline form (`close via
    /// axis`): the walk closes through the axis, not by a planar
    /// return edge (the closure promotion treats the two differently).
    pub via_axis: bool,
    /// The optional D150 name label on the `close` step (`d: close`):
    /// the implicit return edge is a real, constrainable segment.
    pub close_label: Option<String>,
    /// Nested holes (one level).
    pub holes: Vec<Hole>,
    /// Named region expressions.
    pub regions: Vec<String>,
    /// Constraint items (closed SolveSpace-equivalent set), as text.
    pub constraints: Vec<String>,
    /// Exported placeless datum names.
    pub exports: Vec<String>,
}

/// Elaborate a profile's walk into a typed [`Walk`] by CONSUMING the
/// typed CST nodes the parser now emits (WO-11 grammar half landed):
/// [`SyntaxKind::WalkBody`] with its [`SyntaxKind::WalkStep`] children,
/// and the sibling [`SyntaxKind::HoleBlock`] / [`SyntaxKind::RegionsBlock`]
/// / [`SyntaxKind::ConstraintsBlock`] / [`SyntaxKind::ExportsBlock`]
/// nodes of the enclosing profile.
///
/// `node` may be the profile `Decl`, the `WalkBody` itself, or any node
/// containing exactly one profile's walk (the whole-file case is not
/// supported -- pass one profile). Returns `None` when no `WalkBody` is
/// reachable (the node is not a profile walk).
///
/// The role of each line is decided by its node KIND, not by scanning a
/// text blob and tracking `regions:`/`constraints:`/`exports:` section
/// headers -- structure comes from the grammar. Only the leaf classification
/// within a single [`WalkStep`] (`from` / `line` / `arc` / `close` and its
/// direction words) reads that one node's own text, since WO-11's grammar
/// records the step as one typed leaf and defers word-level semantics to
/// this ledger half (hematite/07 OPEN-5, D65).
// frob:doc docs/modules/regolith-syntax.md#walk
#[must_use]
pub fn parse_walk(node: &SyntaxNode) -> Option<Walk> {
    let walk_body = if node.kind() == SyntaxKind::WalkBody {
        node.clone()
    } else {
        node.descendants()
            .find(|n| n.kind() == SyntaxKind::WalkBody)?
    };

    // Sibling domain blocks live in the profile body -- the nearest
    // enclosing scope that holds the walk. Prefer the walk's parent
    // (the profile `Decl` body); fall back to the passed node so a
    // caller handing us just the surrounding block still works.
    let scope = walk_body.parent().unwrap_or_else(|| node.clone());

    let mut from_datum = String::new();
    let mut segments = Vec::new();
    let mut closes = false;
    let mut via_axis = false;
    let mut close_label = None;

    for step in walk_body
        .children()
        .filter(|n| n.kind() == SyntaxKind::WalkStep)
    {
        // walk-step = [ ident ":" ] rest-of-line (D150): an optional
        // leading name label binds the step for `constraints:` items.
        let line = node_line(&step);
        let (label, rest) = split_label(&line);
        match classify_step(rest) {
            Step::From(datum) => from_datum = datum,
            Step::Segment(seg) => segments.push(WalkSegment { label, seg }),
            Step::Close => {
                closes = true;
                via_axis = rest.contains("via") && rest.contains("axis");
                close_label = label;
            }
            Step::Other => {}
        }
    }

    // Holes may nest inside the `WalkBody` OR sit as siblings in the
    // profile body (both shapes occur); collect from the scope so either
    // placement is handled.
    let holes: Vec<Hole> = scope
        .descendants()
        .filter(|n| n.kind() == SyntaxKind::HoleBlock)
        .map(|h| parse_hole(&h))
        .collect();

    let regions = block_items(&scope, SyntaxKind::RegionsBlock);
    let constraints = block_items(&scope, SyntaxKind::ConstraintsBlock);
    let exports = block_items(&scope, SyntaxKind::ExportsBlock);

    if from_datum.is_empty()
        && segments.is_empty()
        && holes.is_empty()
        && regions.is_empty()
        && constraints.is_empty()
        && exports.is_empty()
        && !closes
    {
        return None;
    }

    Some(Walk {
        from_datum,
        segments,
        closes,
        via_axis,
        close_label,
        holes,
        regions,
        constraints,
        exports,
    })
}

/// Split an optional leading D150 name label (`a: line right`) off a
/// walk-step line: `[ ident ":" ]` where the ident is a plain name and
/// the colon is NOT line-final (a line-final colon is a block header,
/// e.g. `hole wire_pass:`, which never reaches this function). A line
/// with no such prefix is returned unchanged with no label.
fn split_label(line: &str) -> (Option<String>, &str) {
    let Some((head, rest)) = line.split_once(':') else {
        return (None, line);
    };
    let name = head.trim();
    let rest_trimmed = rest.trim_start();
    let is_ident = !name.is_empty()
        && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
        && !name.starts_with(|c: char| c.is_ascii_digit());
    if is_ident && !rest_trimmed.is_empty() {
        (Some(name.to_string()), rest_trimmed)
    } else {
        (None, line)
    }
}

/// The classification of one [`SyntaxKind::WalkStep`] line.
enum Step {
    /// `from <datum>`: the walk anchor.
    From(String),
    /// A `line`/`arc` segment.
    Segment(Segment),
    /// `close [via axis]`.
    Close,
    /// A step this ledger half does not model.
    Other,
}

/// Classify a single walk step from its own (comment-stripped) line text.
fn classify_step(line: &str) -> Step {
    if let Some(rest) = line.strip_prefix("from ") {
        Step::From(rest.trim().to_string())
    } else if line.starts_with("line") {
        Step::Segment(Segment::Line(direction_word(line)))
    } else if line.starts_with("arc") {
        let bulge = if line.contains("bulge=right") {
            Direction::Right
        } else {
            Direction::Left
        };
        let join = join_word(line);
        Step::Segment(Segment::Arc { bulge, join })
    } else if line.starts_with("close") {
        Step::Close
    } else {
        Step::Other
    }
}

/// Parse a [`SyntaxKind::HoleBlock`] into a named [`Hole`]: the name is
/// the header word after `hole`, the segments are whatever `line`/`arc`
/// statements the hole body carries (a dimensioned primitive such as
/// `circle(...)` records no line/arc segment -- its placement DOF are
/// pinned by the parent `constraints:` block, hematite/02 sec. 5).
fn parse_hole(hole: &SyntaxNode) -> Hole {
    let header = node_line(hole);
    let name = header
        .strip_prefix("hole ")
        .unwrap_or(&header)
        .trim()
        .trim_end_matches(':')
        .split_whitespace()
        .next()
        .unwrap_or("")
        .to_string();

    let segments = hole
        .children()
        .map(|c| node_line(&c))
        .filter_map(|line| match classify_step(&line) {
            Step::Segment(seg) => Some(seg),
            _ => None,
        })
        .collect();

    Hole { name, segments }
}

/// The text items of a sibling domain block (`regions:`/`constraints:`/
/// `exports:`) in `scope`: one string per child statement node, in
/// source order. Returns empty when no such block is present.
fn block_items(scope: &SyntaxNode, kind: SyntaxKind) -> Vec<String> {
    scope
        .descendants()
        .find(|n| n.kind() == kind)
        .into_iter()
        .flat_map(|block| {
            block
                .children()
                .map(|c| node_line(&c).trim_end_matches(':').trim().to_string())
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>()
        })
        .collect()
}

/// The first physical line of a node's text, trailing comment and
/// whitespace stripped. A `WalkStep`/statement node spans exactly one
/// logical line, so this is that line's significant text.
fn node_line(node: &SyntaxNode) -> String {
    let text = node.text().to_string();
    let first = text.lines().next().unwrap_or("");
    strip_comment(first).trim().to_string()
}

/// Drop a trailing `# ...` comment from a single line.
fn strip_comment(line: &str) -> &str {
    match line.find('#') {
        Some(i) => &line[..i],
        None => line,
    }
}

/// Recognize a tangent/perpendicular join word on an `arc` step.
fn join_word(line: &str) -> Option<Direction> {
    if line.contains("tangent") {
        Some(Direction::Tangent)
    } else if line.contains("perpendicular") {
        Some(Direction::Perpendicular)
    } else {
        None
    }
}

/// Recognize a uniqueness-hint direction word on a `line` step. Joins
/// (`tangent`/`perpendicular`) take precedence; then cardinal words
/// (`left`/`right`/`up`/`down`, matched as whole words). Cardinal words
/// are recorded as hints here; whether a hint disambiguates is a
/// solve-time question (hematite/02 sec. 5). `up`/`down` are recorded
/// (not just tolerated) since D150's closure promotion reads headings.
fn direction_word(line: &str) -> Option<Direction> {
    join_word(line).or_else(|| {
        line.split_whitespace()
            .map(|w| w.trim_matches(|c: char| !c.is_ascii_alphanumeric() && c != '_'))
            .find_map(|w| match w {
                "left" => Some(Direction::Left),
                "right" => Some(Direction::Right),
                "up" => Some(Direction::Up),
                "down" => Some(Direction::Down),
                _ => None,
            })
    })
}

#[cfg(test)]
mod tests {
    use super::{parse_walk, Direction, Segment, Walk, WalkSegment};
    use crate::syntax_kind::SyntaxKind;
    use camino::Utf8PathBuf;

    /// Real corpus shape: `walk:`, `constraints:`, `regions:`, `exports:`
    /// are SIBLING typed blocks in the profile body (not nested inside the
    /// walk). `parse_walk` consumes the typed nodes structurally, so the
    /// role of each line is decided by its containing block's node kind.
    // frob:tests crates/regolith-syntax/src/walk.rs::parse_walk kind="unit"
    #[test]
    fn parse_walk_consumes_typed_sibling_blocks() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line tangent\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20arc tangent, bulge=right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n\
                    \x20\x20\x20\x20regions:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20web: interior\n\
                    \x20\x20\x20\x20exports:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20throat: datum\n";
        let file = Utf8PathBuf::from("t.hema");
        let parse = crate::parser::parse(src, &file);
        let decl = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::Decl)
            .expect("a profile Decl node");
        let walk = parse_walk(&decl).expect("walk body");
        assert_eq!(walk.from_datum, "origin");
        assert_eq!(walk.segments.len(), 2);
        assert!(matches!(
            walk.segments[0].seg,
            Segment::Line(Some(Direction::Tangent))
        ));
        assert!(matches!(
            walk.segments[1].seg,
            Segment::Arc {
                bulge: Direction::Right,
                join: Some(Direction::Tangent),
            }
        ));
        assert!(walk.closes);
        assert_eq!(walk.constraints, vec!["a.length = 8mm".to_string()]);
        assert_eq!(walk.regions, vec!["web: interior".to_string()]);
        assert_eq!(walk.exports, vec!["throat: datum".to_string()]);
    }

    /// A `WalkBody` node alone still resolves its sibling blocks via its
    /// parent scope, so callers may hand us either the `Decl` or the walk.
    #[test]
    fn parse_walk_accepts_the_walk_body_node_directly() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n";
        let file = Utf8PathBuf::from("t.hema");
        let parse = crate::parser::parse(src, &file);
        let walk_body = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::WalkBody)
            .expect("a typed WalkBody node");
        let walk = parse_walk(&walk_body).expect("walk body");
        assert_eq!(walk.from_datum, "origin");
        assert_eq!(walk.segments.len(), 1);
        assert_eq!(walk.constraints.len(), 1);
    }

    #[test]
    fn non_island_node_returns_none() {
        let file = Utf8PathBuf::from("t.hema");
        let parse = crate::parser::parse("part a:\n    x: 1\n", &file);
        assert!(parse_walk(&parse.syntax()).is_none());
    }

    #[test]
    fn walk_structure_builds() {
        let w = Walk {
            from_datum: "origin".to_string(),
            segments: vec![
                WalkSegment {
                    label: None,
                    seg: Segment::Line(None),
                },
                WalkSegment {
                    label: Some("b".to_string()),
                    seg: Segment::Arc {
                        bulge: Direction::Left,
                        join: Some(Direction::Tangent),
                    },
                },
            ],
            closes: true,
            via_axis: false,
            close_label: None,
            holes: Vec::new(),
            regions: vec!["web".to_string()],
            constraints: Vec::new(),
            exports: vec!["throat".to_string()],
        };
        assert_eq!(w.segments.len(), 2);
        assert!(w.closes);
    }

    /// D150: a walk step MAY carry a leading name label (`a: line right`);
    /// the label binds the segment for `constraints:` items, and a
    /// labeled `close` names the implicit return edge. Unlabeled steps
    /// mix freely with labeled ones.
    #[test]
    fn labeled_walk_steps_bind_segment_names() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from left_edge\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a: line right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20b: line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line left\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20d: close\n\
                    \x20\x20\x20\x20constraints:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20a.length = 80mm\n";
        let file = Utf8PathBuf::from("t.hema");
        let parse = crate::parser::parse(src, &file);
        let decl = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::Decl)
            .expect("a profile Decl node");
        let walk = parse_walk(&decl).expect("walk body");
        assert_eq!(walk.from_datum, "left_edge");
        assert_eq!(walk.segments.len(), 3);
        assert_eq!(walk.segments[0].label.as_deref(), Some("a"));
        assert!(matches!(
            walk.segments[0].seg,
            Segment::Line(Some(Direction::Right))
        ));
        assert_eq!(walk.segments[1].label.as_deref(), Some("b"));
        assert!(matches!(
            walk.segments[1].seg,
            Segment::Line(Some(Direction::Up))
        ));
        assert_eq!(walk.segments[2].label, None);
        assert!(matches!(
            walk.segments[2].seg,
            Segment::Line(Some(Direction::Left))
        ));
        assert!(walk.closes);
        assert_eq!(walk.close_label.as_deref(), Some("d"));
    }

    /// The cardinal words `up`/`down` are recorded as directions (they
    /// were previously tolerated but unrecorded; the closure promotion
    /// reads headings off them).
    #[test]
    fn up_and_down_direction_words_are_recorded() {
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line up\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line down\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n";
        let file = Utf8PathBuf::from("t.hema");
        let parse = crate::parser::parse(src, &file);
        let walk = parse_walk(
            &parse
                .syntax()
                .descendants()
                .find(|n| n.kind() == SyntaxKind::Decl)
                .expect("decl"),
        )
        .expect("walk");
        assert!(matches!(
            walk.segments[0].seg,
            Segment::Line(Some(Direction::Up))
        ));
        assert!(matches!(
            walk.segments[1].seg,
            Segment::Line(Some(Direction::Down))
        ));
        assert_eq!(walk.close_label, None);
    }
}
