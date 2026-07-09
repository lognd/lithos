//! L1 static checks: syntax-adjacent semantic rejections that run once
//! per parse, over the freshly built CST (AD-7: diagnostics are data,
//! never `Err`).
//!
//! Regolith reference: `docs/spec/regolith/02-quantity-core.md` sec. 1/3
//! (dimensional arithmetic, `[a, b]` vs `[i .. j]`) and WO-05
//! acceptance: `1 mm + 1 s`-shaped dimension mismatches
//! ([`regolith_diag::codes::INCOMPATIBLE_QUANTITIES`]), `==` on a
//! continuous (unit-bearing) quantity
//! ([`regolith_diag::codes::EQUALITY_ON_CONTINUOUS`]), and interval/
//! range confusion ([`regolith_diag::codes::INTERVAL_RANGE_CONFUSION`])
//! are each rejected with a spanned E01xx diagnostic. These are
//! syntactic checks over the parsed expression shape (unit dimensions,
//! operator, bracket separators); they do not need name resolution, so
//! they belong beside the parser rather than in `regolith-sem`.
//!
//! Logarithmic-unit sums (regolith/02 sec. 5a, INV-17): a `+`/`-` chain
//! over `dB`-family literals is legal iff at most one reference survives
//! cancellation; `dBm + dBm` dies here with
//! [`regolith_diag::codes::ILLEGAL_LOG_SUM`].

use camino::Utf8PathBuf;
use regolith_diag::codes::{
    EQUALITY_ON_CONTINUOUS, ILLEGAL_LOG_SUM, INCOMPATIBLE_QUANTITIES, INTERVAL_RANGE_CONFUSION,
    RUN_MISSING_ENDPOINT,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_qty::{log_sum_reference, LogTerm, LogUnit, Sign, Unit};
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
        SyntaxKind::RunStmt => check_run_endpoints(node, file, out),
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
///
/// FE-8: this only recognizes a continuous operand spelled as a
/// unit-bearing LITERAL. `a == b` between two continuous *names* carries
/// no unit token, so it escapes this syntactic pass (correctly -- this
/// pass has no name resolution and MUST NOT flag every `name == name`,
/// since discrete `Count` operands legitimately use `==`). INV-17
/// phrases the `==` ban as absolute, and the name-resolved case is now
/// completed where declared-quantity types are known:
/// `regolith_sem::resolve::check_equality_ban` builds a per-declaration
/// field-type table and fires E0102 for `a == b` when both names resolve
/// continuous. It runs in the lowering pipeline's `lower.checks` pass, so
/// the two halves of the ban never double-fire (this half keys on a unit
/// literal, that half on two `NameRef` operands).
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

/// Strip enclosing `ParenExpr` wrappers, returning the inner node.
fn strip_parens(node: &SyntaxNode) -> SyntaxNode {
    let mut n = node.clone();
    while n.kind() == SyntaxKind::ParenExpr {
        let Some(inner) = n.children().next() else {
            break;
        };
        n = inner;
    }
    n
}

/// Flatten a `+`/`-` chain into signed logarithmic terms, distributing
/// `sign` down the tree (a subtraction flips its right subtree). Returns
/// `Some` only when the WHOLE subtree is a `+`/`-` chain over log-unit
/// literals -- any non-log leaf (or another operator) yields `None`, so
/// the log-sum check never fires on an ordinary dimensional expression.
fn log_terms(node: &SyntaxNode, sign: Sign) -> Option<Vec<LogTerm>> {
    let n = strip_parens(node);
    if n.kind() == SyntaxKind::BinExpr {
        let op = bin_operator(&n)?;
        if !matches!(op, SyntaxKind::Plus | SyntaxKind::Minus) {
            return None;
        }
        let operands: Vec<SyntaxNode> = n.children().collect();
        let [lhs, rhs] = operands.as_slice() else {
            return None;
        };
        let mut terms = log_terms(lhs, sign)?;
        let rhs_sign = if op == SyntaxKind::Minus {
            sign.flip()
        } else {
            sign
        };
        terms.extend(log_terms(rhs, rhs_sign)?);
        return Some(terms);
    }
    if n.kind() == SyntaxKind::UnaryExpr {
        let has_minus = n
            .children_with_tokens()
            .filter_map(NodeOrToken::into_token)
            .any(|t| t.kind() == SyntaxKind::Minus);
        if has_minus {
            // The unary minus here is the LITERAL's sign (a negative
            // magnitude, e.g. a -110dBm sensitivity), not the chain's
            // `+`/`-` operator -- it does NOT flip which side of the
            // sum this term cancels on, so `sign` passes through
            // unchanged (contrast the `Minus` operator case above,
            // which DOES flip its rhs subtree).
            let inner = n.children().next()?;
            return log_terms(&inner, sign);
        }
        return None;
    }
    let text = quantity_unit_text(&n)?;
    let unit = LogUnit::parse(&text)?;
    Some(vec![LogTerm { sign, unit }])
}

/// True when `node` is the OUTERMOST node of a `+`/`-` chain (its parent
/// is not itself a `+`/`-` `BinExpr`) -- the log-sum check runs once
/// there, over the whole flattened chain, rather than per sub-node.
fn is_top_of_additive_chain(node: &SyntaxNode) -> bool {
    let Some(parent) = node.parent() else {
        return true;
    };
    if parent.kind() != SyntaxKind::BinExpr {
        return true;
    }
    !matches!(
        bin_operator(&parent),
        Some(SyntaxKind::Plus | SyntaxKind::Minus)
    )
}

/// The logarithmic-unit sum legality check (regolith/02 sec. 5a): a
/// `+`/`-` chain over `dB`-family literals is legal iff at most one
/// reference survives cancellation. `dBm + dBm` (two powers) and an
/// uncancelled subtracted reference are E0104.
fn check_log_sum(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    if !is_top_of_additive_chain(node) {
        return;
    }
    let Some(terms) = log_terms(node, Sign::Add) else {
        return;
    };
    if let Err(err) = log_sum_reference(&terms) {
        out.push(
            Diagnostic::error(
                ILLEGAL_LOG_SUM,
                format!("illegal logarithmic-unit sum: {err}"),
            )
            .with_span(LabeledSpan::new(
                node_span(node, file),
                "log sum has no valid linear-product dimension",
            )),
        );
    }
}

/// `1 mm + 1 s`-shaped dimension mismatches (E0101), `==` on a
/// continuous quantity (E0102), and illegal `dB`-family sums (E0104).
fn check_bin_expr(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    check_log_sum(node, file, out);
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

/// A `run <name>: from <ep> to <ep>` header (D99, WO-34 deliverable 1)
/// missing either endpoint keyword (E0106). Parse-time structural
/// validation only: the header is recorded whole (see `RunStmt`'s doc
/// comment), so this reads the header line's own text for the two
/// keywords rather than resolving the endpoint refs -- that resolution
/// is elaboration's job (WO-34 deliverable 2), out of this grammar's
/// scope.
fn check_run_endpoints(node: &SyntaxNode, file: &Utf8PathBuf, out: &mut Vec<Diagnostic>) {
    let header = node
        .text()
        .to_string()
        .lines()
        .next()
        .unwrap_or("")
        .to_string();
    let header = match header.find('#') {
        Some(i) => &header[..i],
        None => &header,
    };
    let has_from = header.split_whitespace().any(|w| w == "from");
    let has_to = header.split_whitespace().any(|w| w == "to");
    if !has_from || !has_to {
        out.push(
            Diagnostic::error(
                RUN_MISSING_ENDPOINT,
                "a `run` declares its routed path between two endpoints: the header must \
                 spell both `from <ep>` and `to <ep>`",
            )
            .with_span(LabeledSpan::new(
                node_span(node, file),
                "missing endpoint here",
            )),
        );
    }
}

/// `[a, b]` vs `[i .. j]` confusion (E0103, regolith/02 sec. 3): a
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
    use regolith_diag::codes::{
        EQUALITY_ON_CONTINUOUS, ILLEGAL_LOG_SUM, INCOMPATIBLE_QUANTITIES, INTERVAL_RANGE_CONFUSION,
        RUN_MISSING_ENDPOINT,
    };

    fn diag_codes(src: &str) -> Vec<String> {
        let file = Utf8PathBuf::from("t.hema");
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
    fn volt_plus_amp_is_incompatible_quantities() {
        // FE-7: `V`/`A` now both resolve, so `1V + 1A` fires the precise
        // INCOMPATIBLE_QUANTITIES (E0101), not an unknown-unit condition.
        let codes = diag_codes("board b:\n    x: 1V + 1A\n");
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
    fn two_reference_log_sum_is_flagged() {
        // FE-1 / INV-17: dBm + dBm = mW^2, not a power -- E0104.
        let codes = diag_codes("board b:\n    p: 1dBm + 1dBm\n");
        assert!(codes.contains(&ILLEGAL_LOG_SUM.to_string()), "{codes:?}");
    }

    #[test]
    fn link_budget_log_sum_is_clean() {
        // FE-1: dBm + dBi - dB is a legal power (the link budget).
        let codes = diag_codes("board b:\n    p: 1dBm + 1dBi - 1dB\n");
        assert!(!codes.contains(&ILLEGAL_LOG_SUM.to_string()), "{codes:?}");
    }

    #[test]
    fn reference_difference_log_sum_is_clean() {
        // dBm - dBm cancels to a ratio (P_rx - P_sens) -- legal.
        let codes = diag_codes("board b:\n    m: 1dBm - 1dBm\n");
        assert!(!codes.contains(&ILLEGAL_LOG_SUM.to_string()), "{codes:?}");
    }

    #[test]
    fn negative_literal_two_reference_log_sum_is_flagged() {
        // The common link-budget spelling of two powers: `30dBm +
        // -110dBm`. A unary minus on the log-unit literal must NOT let
        // the term escape the flatten -- both are powers, so this is
        // still E0104 (regression test for the false-negative found in
        // examples/systems/sdr_transceiver/negative/db_illegal.cupr).
        let codes = diag_codes("board b:\n    p: 30dBm + -110dBm\n");
        assert!(codes.contains(&ILLEGAL_LOG_SUM.to_string()), "{codes:?}");
    }

    #[test]
    fn equality_between_two_bare_names_is_not_flagged_syntactically() {
        // FE-8: `a == b` between two continuous NAMES carries no unit
        // token, so this syntactic pass cannot decide it (discrete Count
        // operands legitimately use `==`). It is intentionally NOT flagged
        // here; the name-resolved completion of INV-17's `==` ban belongs
        // to regolith-sem (see `is_continuous_quantity`'s TODO(FE-8)).
        let codes = diag_codes("part p:\n    x: a == b\n");
        assert!(
            !codes.contains(&EQUALITY_ON_CONTINUOUS.to_string()),
            "two bare names must not be flagged by the syntactic pass: {codes:?}"
        );
    }

    #[test]
    fn run_missing_endpoint_is_flagged() {
        let codes =
            diag_codes("harness H:\n    run r: from a.x\n        along b\n        bundle g\n");
        assert!(
            codes.contains(&RUN_MISSING_ENDPOINT.to_string()),
            "{codes:?}"
        );
    }

    #[test]
    fn run_with_both_endpoints_is_clean() {
        let codes = diag_codes(
            "harness H:\n    run r: from a.x to b.y\n        along c\n        bundle g\n",
        );
        assert!(
            !codes.contains(&RUN_MISSING_ENDPOINT.to_string()),
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
