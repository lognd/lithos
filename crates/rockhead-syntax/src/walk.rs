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
#[must_use]
pub fn parse_walk(_island: &SyntaxNode) -> Option<Walk> {
    todo!("STUB WO-11: elaborate the profile island CST into Walk (segments/holes/regions/exports)")
}

#[cfg(test)]
mod tests {
    use super::{Direction, Segment, Walk};

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
