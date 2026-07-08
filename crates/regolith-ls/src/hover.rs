//! Hover (WO-38 deliverable 7), STATIC half only: kind word + resolved
//! declaration signature, read off the real CST. The artifact-fed half
//! (D111: resolved value + Cause, claim obligation status/margin/
//! evidence tier, record provenance from `.regolith/`) is NOT
//! implemented in this pass -- every hover here carries the
//! "(no build artifacts)" tail unconditionally, which is the correct
//! degraded form but never the BUILT form (tracked as a gap; see the
//! WO-38 dispatch report).

use lsp_types::{Hover, HoverContents, MarkupContent, MarkupKind, Position};
use regolith_syntax::ast::{AstNode, Decl};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::position::LineIndex;

/// Hover text for the declaration enclosing `position`, if any.
#[must_use]
pub fn hover_at(text: &str, index: &LineIndex, position: Position) -> Option<Hover> {
    let offset = index.offset(position);
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    let token = parse
        .syntax()
        .token_at_offset(rowan::TextSize::try_from(offset).ok()?)
        .right_biased()?;
    let decl = token.parent_ancestors().find_map(Decl::cast)?;
    let name = decl.name()?;
    let kind_word = decl.kind_keyword().map_or("declaration", keyword_label);
    let range = decl.syntax().text_range();
    let value = format!("**{kind_word} {name}**\n\n(no build artifacts)");
    Some(Hover {
        contents: HoverContents::Markup(MarkupContent {
            kind: MarkupKind::Markdown,
            value,
        }),
        range: Some(index.range(usize::from(range.start()), usize::from(range.end()))),
    })
}

/// Same label table as `symbols::keyword_label` (kept local: hover's
/// label vocabulary may grow domain prose the outline never needs).
fn keyword_label(kind: SyntaxKind) -> &'static str {
    match kind {
        SyntaxKind::PartKw => "part",
        SyntaxKind::ProfileKw => "profile",
        SyntaxKind::InterfaceKw => "interface",
        SyntaxKind::MatingKw => "mating",
        SyntaxKind::AssemblyKw => "assembly",
        SyntaxKind::SystemKw => "system",
        SyntaxKind::QuantityKw => "quantity",
        SyntaxKind::SignatureKw => "signature",
        SyntaxKind::NamespaceKw => "namespace",
        SyntaxKind::ImportKw => "import",
        _ => "declaration",
    }
}

#[cfg(test)]
mod tests {
    use super::hover_at;
    use crate::position::LineIndex;
    use lsp_types::{HoverContents, MarkupContent};

    #[test]
    fn hover_over_a_decl_name_shows_kind_and_no_artifacts_tail() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("Widget").unwrap());
        let hover = hover_at(text, &index, pos).expect("hover over a decl name");
        let HoverContents::Markup(MarkupContent { value, .. }) = hover.contents else {
            panic!("expected markup contents");
        };
        assert!(value.contains("part Widget"));
        assert!(value.contains("(no build artifacts)"));
    }

    #[test]
    fn hover_outside_any_decl_is_none() {
        let text = "\n\n";
        let index = LineIndex::new(text);
        assert!(hover_at(text, &index, index.position(0)).is_none());
    }
}
