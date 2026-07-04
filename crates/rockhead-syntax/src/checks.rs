//! L1 static checks: syntax-adjacent semantic rejections that run once
//! per parse, over the freshly built CST (AD-7: diagnostics are data,
//! never `Err`).
//!
//! Substrate reference: `docs/substrate/02-quantity-core.md` sec. 1/3
//! (dimensional arithmetic, `[a, b]` vs `[i .. j]`) and WO-05
//! acceptance: `1 mm + 1 s`-shaped dimension mismatches
//! ([`rockhead_diag::codes::INCOMPATIBLE_QUANTITIES`]), `==` on a
//! continuous (unit-bearing) quantity
//! ([`rockhead_diag::codes::EQUALITY_ON_CONTINUOUS`]), and interval/
//! range confusion ([`rockhead_diag::codes::INTERVAL_RANGE_CONFUSION`])
//! are each rejected with a spanned E01xx diagnostic. These are
//! syntactic checks over the parsed expression shape (unit dimensions,
//! operator, bracket separators); they do not need name resolution, so
//! they belong beside the parser rather than in `rockhead-sem`.
//!
//! Known gap (recorded, not silently dropped): `rockhead-qty`'s seed
//! unit table (`crates/rockhead-qty/src/unit.rs`) does not yet include
//! `V` (volt), `W` (watt), or `Hz`, though substrate/02 sec. 1 lists
//! `voltage: V` in the seed quantity set. A literal `1V + 1A` therefore
//! resolves as an *unknown unit* rather than an *incompatible
//! quantity*; both are still reported as E01xx diagnostics (via a
//! parse/layout diagnostic path), but the more specific
//! [`rockhead_diag::codes::INCOMPATIBLE_QUANTITIES`] code cannot fire
//! until `rockhead-qty` (WO-02, a different crate, out of this WO's
//! touch-scope) adds those units. See the WO-05 report for the
//! escalation.

use camino::Utf8PathBuf;
use rockhead_diag::codes::{
    EQUALITY_ON_CONTINUOUS, INCOMPATIBLE_QUANTITIES, INTERVAL_RANGE_CONFUSION,
};
use rockhead_diag::{Diagnostic, LabeledSpan, Span};
use rockhead_qty::Unit;
use rowan::NodeOrToken;

use crate::cst::SyntaxNode;
use crate::syntax_kind::SyntaxKind;

/// Run every L1 check over `root` (a freshly parsed `File`), producing
/// spanned diagnostics anchored at `file`.
#[must_use]
pub fn run(root: &SyntaxNode, file: &Utf8PathBuf) -> Vec<Diagnostic> {
    let mut out = Vec::new();
    walk(root, file, &mut out);
    out
}

/// Depth-first walk over every node, dispatching each check by kind.
fn walk(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    match node.kind() {
        SyntaxKind::BinExpr => check_bin_expr(node, file, out),
        SyntaxKind::IntervalExpr | SyntaxKind::RangeExpr => check_bracket(node, file, out),
        _ => {}
    }
    for child in node.children() {
        walk(&child, file, out);
    }
}

/// The unit text of a `QuantityLit` node (`Number` token immediately
/// followed by its unit `Ident`), or `None` for a bare (unitless)
/// number.
fn quantity_unit_text(node: &SyntaxNode) -> Option<String> {
    if node.kind() != SyntaxKind::QuantityLit {
        return None;
    }
    node.children_with_tokens()
        .filter_map(NodeOrToken::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

/// True if `node` is (or, once parens are stripped, wraps) a
/// unit-bearing `QuantityLit` -- the syntactic notion of "continuous
/// quantity" this L1 pass can decide without name resolution.
fn is_continuous_quantity(node: &SyntaxNode) -> bool {
    let mut n = node.clone();
    while n.kind() == SyntaxKind::ParenExpr {
        let Some(inner) = n.children().next() else {
            return false;
        };
        n = inner;
    }
    quantity_unit_text(&n).is_some()
}

/// A direct `QuantityLit` child's resolved [`Unit`], if the operand is
/// exactly a unit-bearing literal (no deeper resolution -- see the
/// module docs' known-gap note for unresolvable unit spellings).
fn quantity_unit(node: &SyntaxNode) -> Option<Unit> {
    let mut n = node.clone();
    while n.kind() == SyntaxKind::ParenExpr {
        n = n.children().next()?;
    }
    let text = quantity_unit_text(&n)?;
    Unit::parse_expr(&text).ok()
}

fn node_span(node: &SyntaxNode, file: &Utf8PathBuf) -> Span {
    let range = node.text_range();
    Span::new(file.clone(), range.start().into(), range.end().into())
}

/// The operator token of a `BinExpr` (the first comparator/arithmetic
/// token that is a direct child, i.e. not part of either operand).
fn bin_operator(node: &SyntaxNode) -> Option<SyntaxKind> {
    // Operands are themselves nodes; the operator is the lone token
    // directly between them among this node's children.
    node.children_with_tokens()
        .filter_map(NodeOrToken::into_token)
        .map(|t| t.kind())
        .find(|k| {
            matches!(
                k,
                SyntaxKind::Plus
                    | SyntaxKind::Minus
                    | SyntaxKind::Star
                    | SyntaxKind::Slash
                    | SyntaxKind::Lt
                    | SyntaxKind::Gt
                    | SyntaxKind::LtEq
                    | SyntaxKind::GtEq
                    | SyntaxKind::EqEqTok
                    | SyntaxKind::Eq
            )
        })
}

/// `1 mm + 1 s`-shaped dimension mismatches (E0101) and `==` on a
/// continuous quantity (E0102).
fn check_bin_expr(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    let Some(op) = bin_operator(node) else { return };
    let operands: Vec<SyntaxNode> = node.children().collect();
    let [lhs, rhs] = operands.as_slice() else {
        return;
    };

    if op == SyntaxKind::EqEqTok && (is_continuous_quantity(lhs) || is_continuous_quantity(rhs)) {
        out.push(
            Diagnostic::error(
                EQUALITY_ON_CONTINUOUS,
                "`==` compares a continuous quantity for exact equality; use an interval or tolerance instead",
            )
            .with_span(LabeledSpan::new(node_span(node, file), "continuous equality here")),
        );
    }

    if matches!(op, SyntaxKind::Plus | SyntaxKind::Minus) {
        if let (Some(lu), Some(ru)) = (quantity_unit(lhs), quantity_unit(rhs)) {
            if lu.dimension != ru.dimension {
                out.push(
                    Diagnostic::error(
                        INCOMPATIBLE_QUANTITIES,
                        format!(
                            "cannot add/subtract incompatible quantities: `{}` vs `{}`",
                            lu.symbol, ru.symbol
                        ),
                    )
                    .with_span(LabeledSpan::new(
                        node_span(node, file),
                        "incompatible dimensions here",
                    )),
                );
            }
        }
    }
}

/// A `RangeExpr` endpoint literal is malformed for an integer index
/// range: it carries a unit, or its numeric text contains a decimal
/// point (a fractional index has no meaning).
fn range_endpoint_is_misused(node: &SyntaxNode) -> bool {
    if let Some(unit) = quantity_unit_text(node) {
        let _ = unit;
        return true;
    }
    node.children_with_tokens()
        .filter_map(NodeOrToken::into_token)
        .any(|t| t.kind() == SyntaxKind::Number && t.text().contains('.'))
}

/// `[a, b]` vs `[i .. j]` confusion (E0103, substrate/02 sec. 3): a
/// bracket that mixed both separators, or a `[i .. j]` range whose
/// endpoint is not a bare (unitless, integer-shaped) literal.
fn check_bracket(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    let has_comma = node
        .children_with_tokens()
        .filter_map(NodeOrToken::into_token)
        .any(|t| t.kind() == SyntaxKind::Comma);
    let has_dotdot = node
        .children_with_tokens()
        .filter_map(NodeOrToken::into_token)
        .any(|t| t.kind() == SyntaxKind::DotDot);

    if has_comma && has_dotdot {
        out.push(
            Diagnostic::error(
                INTERVAL_RANGE_CONFUSION,
                "mixes `[a, b]` interval and `[i .. j]` range separators in one bracket",
            )
            .with_span(LabeledSpan::new(
                node_span(node, file),
                "which form was meant?",
            )),
        );
        return;
    }

    if node.kind() == SyntaxKind::RangeExpr {
        for endpoint in node.children() {
            if range_endpoint_is_misused(&endpoint) {
                out.push(
                    Diagnostic::error(
                        INTERVAL_RANGE_CONFUSION,
                        "`[i .. j]` index ranges take bare integer endpoints, not unit-bearing or fractional quantities (use `[a, b]` for a real interval)",
                    )
                    .with_span(LabeledSpan::new(
                        node_span(&endpoint, file),
                        "not a bare integer index",
                    )),
                );
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::parser::parse;
    use camino::Utf8PathBuf;
    use rockhead_diag::codes::{
        EQUALITY_ON_CONTINUOUS, INCOMPATIBLE_QUANTITIES, INTERVAL_RANGE_CONFUSION,
    };

    fn diag_codes(src: &str) -> Vec<String> {
        let file = Utf8PathBuf::from("t.hem");
        let parse = parse(src, &file);
        parse
            .diagnostics()
            .iter()
            .map(|d| d.code.to_string())
            .collect()
    }

    #[test]
    fn incompatible_quantities_are_flagged() {
        let codes = diag_codes("part p:\n    x: 1mm + 1s\n");
        assert!(
            codes.contains(&INCOMPATIBLE_QUANTITIES.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn compatible_quantities_are_not_flagged() {
        let codes = diag_codes("part p:\n    x: 1mm + 2mm\n");
        assert!(
            !codes.contains(&INCOMPATIBLE_QUANTITIES.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn equality_on_continuous_quantity_is_flagged() {
        let codes = diag_codes("part p:\n    x: y == 5mm\n");
        assert!(
            codes.contains(&EQUALITY_ON_CONTINUOUS.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn mixed_interval_range_bracket_is_flagged() {
        let codes = diag_codes("part p:\n    x: [1, 2 .. 3]\n");
        assert!(
            codes.contains(&INTERVAL_RANGE_CONFUSION.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn unit_bearing_range_endpoint_is_flagged() {
        let codes = diag_codes("part p:\n    x: [1mm .. 3]\n");
        assert!(
            codes.contains(&INTERVAL_RANGE_CONFUSION.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn plain_interval_and_range_are_clean() {
        let codes = diag_codes("part p:\n    a: [1mm, 2mm]\n    b: [0 .. 3]\n");
        assert!(
            !codes.contains(&INTERVAL_RANGE_CONFUSION.to_string()),
            "{codes:?}"
        );
    }
}
