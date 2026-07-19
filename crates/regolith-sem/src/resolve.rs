//! L1 name/type resolution: the minimal semantic primitive the
//! checks-over-real-input invariants need -- deciding, for a bare NAME
//! referenced in an expression, the quantity class of the symbol it
//! resolves to.
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! sec. 2 (static name resolution on the pre-realization IR, WO-08) and
//! `docs/spec/regolith/02-quantity-core.md` sec. 2 (`==` on a continuous
//! quantity is a compile error). INV-17 phrases that ban as ABSOLUTE:
//! the syntactic L1 pass in `regolith-syntax` can only decide it when an
//! operand is spelled as a unit-bearing LITERAL (`a == 5mm`); the
//! name-resolved case (`a == b`, both declared continuous) has no unit
//! token to key on and is completed HERE, where a declaration's field
//! types are known (FE-8).
//!
//! Deliberately narrow: this resolves only the quantity class of a
//! declaration's own directly-declared fields (`a: 1mm` -> continuous,
//! `n: 3` -> discrete/count). Cross-decl and query-resolved operands are
//! out of FE-8's scope; anything unclassifiable is [`QuantityClass::Unknown`]
//! and never triggers the ban (no false positives on discrete `Count`
//! operands, which legitimately use `==`).

use camino::Utf8PathBuf;
use regolith_diag::codes::EQUALITY_ON_CONTINUOUS;
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_syntax::ast::{AstNode, Decl};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_util::IndexMap;

/// The resolved quantity class of a declared symbol -- the axis the
/// `==` ban turns on (regolith/02 sec. 2: continuous quantities forbid
/// exact equality; discrete counts permit it).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
// frob:doc docs/modules/regolith-sem.md#resolve
pub enum QuantityClass {
    /// A unit-bearing continuous quantity (`1mm`, `3.3V`): `==` is banned.
    Continuous,
    /// A discrete count / unitless integer (`3`): `==` is legal.
    Discrete,
    /// Not statically classifiable at this pass (an expression, a query,
    /// an opaque value): never triggers the ban.
    Unknown,
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

/// Classify a field's value node into a [`QuantityClass`]: a unit-bearing
/// `QuantityLit` (a `Number` immediately followed by a unit `Ident`) is
/// continuous; anything else is [`QuantityClass::Unknown`] (a bare
/// integer never reaches here as a node -- it is a lone `Number` token,
/// so `Field::value` yields `None` for it -- which is why counts fall to
/// `Unknown` and are simply never banned).
#[must_use]
// frob:doc docs/modules/regolith-sem.md#resolve
pub fn classify_value(node: &SyntaxNode) -> QuantityClass {
    let n = strip_parens(node);
    if n.kind() != SyntaxKind::QuantityLit {
        return QuantityClass::Unknown;
    }
    let has_unit = n
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .any(|t| t.kind() == SyntaxKind::Ident);
    if has_unit {
        QuantityClass::Continuous
    } else {
        QuantityClass::Discrete
    }
}

/// The declared quantity class of every directly-declared field of a
/// declaration, keyed by field name (source order). The name-resolution
/// table the `==` ban consults.
#[must_use]
// frob:doc docs/modules/regolith-sem.md#resolve
pub fn field_classes(decl: &Decl) -> IndexMap<String, QuantityClass> {
    let mut table: IndexMap<String, QuantityClass> = IndexMap::new();
    for field in decl.fields() {
        if let Some(value) = field.value() {
            table.insert(field.name(), classify_value(&value));
        }
    }
    table
}

/// The bare-name text a `NameRef` node references (its first `Ident`
/// token), or `None` for any other node shape.
fn name_ref_text(node: &SyntaxNode) -> Option<String> {
    if node.kind() != SyntaxKind::NameRef {
        return None;
    }
    node.children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

/// The operator token kind of a `BinExpr` (the comparator/arithmetic
/// token directly between its operands).
fn bin_operator(node: &SyntaxNode) -> Option<SyntaxKind> {
    node.children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
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

/// The name-resolved completion of INV-17's `==` ban for one declaration
/// (FE-8): flag every `a == b` whose BOTH operands are bare NAMES that
/// resolve, via this declaration's field table, to continuous quantities.
///
/// This is the complement of the syntactic pass in `regolith-syntax`
/// (which handles the unit-bearing-LITERAL operand case); the two never
/// double-fire, because this one requires both operands to be `NameRef`s
/// (never literals). Discrete/count and unclassifiable operands are left
/// alone (no false positive on legal `Count` equality).
#[must_use]
// frob:doc docs/modules/regolith-sem.md#resolve
pub fn check_equality_ban(decl: &Decl, file: &Utf8PathBuf) -> Vec<Diagnostic> {
    let span = tracing::debug_span!("sem.equality_ban", subject = decl.name());
    let _enter = span.enter();

    let classes = field_classes(decl);
    let mut out = Vec::new();

    for node in decl.syntax().descendants() {
        if node.kind() != SyntaxKind::BinExpr {
            continue;
        }
        if bin_operator(&node) != Some(SyntaxKind::EqEqTok) {
            continue;
        }
        let operands: Vec<SyntaxNode> = node.children().collect();
        let [lhs, rhs] = operands.as_slice() else {
            continue;
        };
        let (Some(ln), Some(rn)) = (
            name_ref_text(&strip_parens(lhs)),
            name_ref_text(&strip_parens(rhs)),
        ) else {
            continue;
        };
        let lc = classes.get(&ln).copied().unwrap_or(QuantityClass::Unknown);
        let rc = classes.get(&rn).copied().unwrap_or(QuantityClass::Unknown);
        tracing::debug!(lhs = %ln, ?lc, rhs = %rn, ?rc, "resolved `==` operand classes");
        if lc == QuantityClass::Continuous && rc == QuantityClass::Continuous {
            tracing::info!(lhs = %ln, rhs = %rn, "INV-17: `==` on two continuous names -> E0102");
            let range = node.text_range();
            let sp = Span::new(file.clone(), range.start().into(), range.end().into());
            out.push(
                Diagnostic::error(
                    EQUALITY_ON_CONTINUOUS,
                    format!(
                        "`==` compares continuous quantities `{ln}` and `{rn}` for exact \
                         equality; use an interval or tolerance instead"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "continuous equality here")),
            );
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::check_equality_ban;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::EQUALITY_ON_CONTINUOUS;
    use regolith_syntax::ast::{AstNode, File};

    fn codes(src: &str) -> Vec<String> {
        let path = Utf8PathBuf::from("t.hema");
        let parse = regolith_syntax::parse(src, &path);
        let file = File::cast(parse.syntax()).expect("root is a File");
        file.decls()
            .iter()
            .flat_map(|d| check_equality_ban(d, &path))
            .map(|d| d.code.to_string())
            .collect()
    }

    // frob:tests crates/regolith-sem/src/resolve.rs::classify_value kind="unit"
    // frob:tests crates/regolith-sem/src/resolve.rs::field_classes kind="unit"
    // frob:tests crates/regolith-sem/src/resolve.rs::check_equality_ban kind="unit"
    #[test]
    fn equality_between_two_continuous_names_is_flagged() {
        // FE-8: `a` and `b` both resolve to continuous quantities, so
        // `a == b` fires the name-resolved E0102 ban INV-17 demands.
        let got = codes("part p:\n    a: 1mm\n    b: 2mm\n    eq: a == b\n");
        assert!(
            got.contains(&EQUALITY_ON_CONTINUOUS.to_string()),
            "two continuous names must fire: {got:?}"
        );
    }

    #[test]
    fn equality_involving_a_count_is_not_flagged() {
        // FE-8: `n` is a bare integer count (discrete); `n == 3` must NOT
        // fire -- exact equality is legal on discrete counts.
        let got = codes("part p:\n    n: 3\n    eq: n == 3\n");
        assert!(
            !got.contains(&EQUALITY_ON_CONTINUOUS.to_string()),
            "a count equality must not fire: {got:?}"
        );
    }

    #[test]
    fn equality_between_two_count_names_is_not_flagged() {
        // Both operands are names, but they resolve to discrete counts,
        // not continuous quantities: no ban.
        let got = codes("part p:\n    n: 3\n    m: 4\n    eq: n == m\n");
        assert!(
            !got.contains(&EQUALITY_ON_CONTINUOUS.to_string()),
            "two count names must not fire: {got:?}"
        );
    }
}
