//! Walk bodies: the elaborated form of the WO-05 opaque profile islands
//! (WO-11 grammar half). A walk is a pen-path sketch: segments, joins,
//! holes, regions, constraints, and exports.
//!
//! Substrate reference: `docs/mech/02` sec. 5. The constraint vocabulary
//! is the closed SolveSpace-equivalent set (mech/07 OPEN-5, D65); NO
//! solving happens here -- this module records structure for the static
//! ledger (rockhead-sem `profile`). Direction words are recorded as
//! uniqueness hints; that a hint disambiguates is checked at solve time.

use crate::cst::SyntaxNode;

/// A direction word annotating a segment (a uniqueness hint, validated
/// at solve time, recorded here).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Direction {
    /// Turn/curve to the left.
    Left,
    /// Turn/curve to the right.
    Right,
    /// Continue tangent to the previous segment.
    Tangent,
    /// Meet the previous segment perpendicularly.
    Perpendicular,
}

/// One segment of the walk.
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

/// A named hole nested one level inside the walk (`hole <name>:`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Hole {
    /// Hole name.
    pub name: String,
    /// The hole's own segments (one nesting level only).
    pub segments: Vec<Segment>,
}

/// A parsed walk body.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Walk {
    /// The `from <datum>` anchor name.
    pub from_datum: String,
    /// The ordered segments.
    pub segments: Vec<Segment>,
    /// Whether the walk closes (`close [via axis]`).
    pub closes: bool,
    /// Nested holes (one level).
    pub holes: Vec<Hole>,
    /// Named region expressions.
    pub regions: Vec<String>,
    /// Constraint items (closed SolveSpace-equivalent set), as text.
    pub constraints: Vec<String>,
    /// Exported placeless datum names.
    pub exports: Vec<String>,
}

/// Elaborate a walk-body opaque island (a CST node of kind
/// `OpaqueIsland`) into a typed [`Walk`].
///
/// Returns `None` if the node is not a walk island. Ambiguities against
/// the spec must be escalated to the design log, not invented (WO-11).
///
/// NOTE (scope): WO-05's bootstrap pass records every declaration body
/// as one undifferentiated `OpaqueIsland` (see the WO-05 report note),
/// so no line/word-level walk grammar exists in the CST yet to drive a
/// structural parse. This elaborator is therefore a line-oriented text
/// scan over the island's reconstructed text rather than a CST walk; it
/// covers the vocabulary in the Deliverables list (`from`, `line`,
/// `arc`, `bulge=`, joins, `close`, one level of `hole <name>:`,
/// `regions:`/`constraints:`/`exports:` sections) but is not a
/// substitute for a real sub-grammar. Revisit once WO-05 grows
/// statement-level nodes for walk bodies specifically.
#[must_use]
pub fn parse_walk(island: &SyntaxNode) -> Option<Walk> {
    // Scans the node's raw text line-by-line (nested `walk:` bodies are
    // now parsed as structured statement blocks, cycle 11, but their
    // text is unchanged -- the CST is lossless). Returns `None` when the
    // text carries no walk content, so a non-walk node is rejected.
    let text = island.text().to_string();

    let mut from_datum = String::new();
    let mut segments = Vec::new();
    let mut closes = false;
    let mut holes: Vec<Hole> = Vec::new();
    let mut regions = Vec::new();
    let mut constraints = Vec::new();
    let mut exports = Vec::new();
    let mut current_hole: Option<Hole> = None;
    let mut section: Option<&str> = None;

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(rest) = line.strip_prefix("from ") {
            from_datum = rest.trim().to_string();
        } else if let Some(rest) = line.strip_prefix("hole ") {
            if let Some(prev) = current_hole.take() {
                holes.push(prev);
            }
            current_hole = Some(Hole {
                name: rest.trim().trim_end_matches(':').trim().to_string(),
                segments: Vec::new(),
            });
        } else if line.starts_with("line") {
            let seg = Segment::Line(direction_word(line));
            push_segment(&mut current_hole, &mut segments, seg);
        } else if line.starts_with("arc") {
            let bulge = if line.contains("bulge=right") {
                Direction::Right
            } else {
                Direction::Left
            };
            let join = if line.contains("tangent") {
                Some(Direction::Tangent)
            } else if line.contains("perpendicular") {
                Some(Direction::Perpendicular)
            } else {
                None
            };
            push_segment(
                &mut current_hole,
                &mut segments,
                Segment::Arc { bulge, join },
            );
        } else if line.starts_with("close") {
            closes = true;
        } else if line == "regions:" {
            section = Some("regions");
        } else if line == "constraints:" {
            section = Some("constraints");
        } else if line == "exports:" {
            section = Some("exports");
        } else {
            match section {
                Some("regions") => regions.push(line.trim_end_matches(':').to_string()),
                Some("constraints") => constraints.push(line.to_string()),
                Some("exports") => exports.push(line.trim_end_matches(':').to_string()),
                _ => {}
            }
        }
    }
    if let Some(h) = current_hole.take() {
        holes.push(h);
    }

    // No walk content at all -> this node is not a walk (replaces the
    // old OpaqueIsland kind guard now that walk bodies are structured).
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
        holes,
        regions,
        constraints,
        exports,
    })
}

fn push_segment(current_hole: &mut Option<Hole>, segments: &mut Vec<Segment>, seg: Segment) {
    if let Some(h) = current_hole.as_mut() {
        h.segments.push(seg);
    } else {
        segments.push(seg);
    }
}

/// Recognize a uniqueness-hint direction word on a `line`/join clause.
fn direction_word(line: &str) -> Option<Direction> {
    if line.contains("tangent") {
        Some(Direction::Tangent)
    } else if line.contains("perpendicular") {
        Some(Direction::Perpendicular)
    } else if line.contains("left") {
        Some(Direction::Left)
    } else if line.contains("right") {
        Some(Direction::Right)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::{parse_walk, Direction, Segment, Walk};
    use crate::ast::{AstNode, File};
    use camino::Utf8PathBuf;

    #[test]
    fn parse_walk_reads_the_bootstrap_island_text() {
        // Real corpus shape (WO-05 cycle 11): walk content nests under a
        // `walk:` field, whose body the statement grammar keeps as one
        // opaque island (domain payload, out of WO-05 scope; see
        // `parser::Parser::parse_value_and_tail`). The un-nested
        // (pre-cycle-11) fixture shape no longer matches: top-level
        // decl statements are now parsed individually, not merged.
        let src = "profile p:\n\
                    \x20\x20\x20\x20walk:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20line tangent\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20arc bulge=right\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20close\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20regions:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20web\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20exports:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20throat\n";
        let file = Utf8PathBuf::from("t.hem");
        let parse = crate::parser::parse(src, &file);
        let root = File::cast(parse.syntax()).expect("File root");
        let decl = root.decls().first().cloned().expect("one decl");
        let walk_field = decl
            .fields()
            .into_iter()
            .find(|f| f.name() == "walk")
            .expect("decl has a walk: field");
        // Cycle 11: the walk body is a structured nested block now, not
        // an OpaqueIsland; scan the field's text directly.
        let walk = parse_walk(walk_field.syntax()).expect("walk body");
        assert_eq!(walk.from_datum, "origin");
        assert_eq!(walk.segments.len(), 2);
        assert!(matches!(
            walk.segments[0],
            Segment::Line(Some(Direction::Tangent))
        ));
        assert!(matches!(
            walk.segments[1],
            Segment::Arc {
                bulge: Direction::Right,
                ..
            }
        ));
        assert!(walk.closes);
        assert_eq!(walk.regions, vec!["web".to_string()]);
        assert_eq!(walk.exports, vec!["throat".to_string()]);
    }

    #[test]
    fn non_island_node_returns_none() {
        let file = Utf8PathBuf::from("t.hem");
        let parse = crate::parser::parse("part a:\n    x: 1\n", &file);
        assert!(parse_walk(&parse.syntax()).is_none());
    }

    #[test]
    fn walk_structure_builds() {
        let w = Walk {
            from_datum: "origin".to_string(),
            segments: vec![
                Segment::Line(None),
                Segment::Arc {
                    bulge: Direction::Left,
                    join: Some(Direction::Tangent),
                },
            ],
            closes: true,
            holes: Vec::new(),
            regions: vec!["web".to_string()],
            constraints: Vec::new(),
            exports: vec!["throat".to_string()],
        };
        assert_eq!(w.segments.len(), 2);
        assert!(w.closes);
    }
}
