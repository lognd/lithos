//! Document symbols / outline (WO-38 deliverable 5): the CST decl tree,
//! read directly off the real parser -- no second grammar.

use lsp_types::{DocumentSymbol, SymbolKind};
use regolith_syntax::ast::{AstNode, Decl};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::position::LineIndex;

/// Every top-level declaration in `text`, as an LSP outline entry.
#[must_use]
pub fn document_symbols(text: &str, index: &LineIndex) -> Vec<DocumentSymbol> {
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    parse
        .syntax()
        .children()
        .filter_map(Decl::cast)
        .filter_map(|decl| decl_symbol(&decl, index))
        .collect()
}

/// One `Decl` node -> one `DocumentSymbol`, when it carries a name.
/// Nested decls (e.g. `hole` blocks are not `Decl`s so no recursion is
/// needed here; a future WO can add it if nested decl kinds appear).
#[allow(deprecated)] // `DocumentSymbol::deprecated` has no replacement in lsp-types 0.97
fn decl_symbol(decl: &Decl, index: &LineIndex) -> Option<DocumentSymbol> {
    let name = decl.name()?;
    let range = index.range(
        usize::from(decl.syntax().text_range().start()),
        usize::from(decl.syntax().text_range().end()),
    );
    let kind_word = decl
        .kind_keyword()
        .map_or("decl", keyword_label)
        .to_string();
    Some(DocumentSymbol {
        name,
        detail: Some(kind_word.clone()),
        kind: symbol_kind_for(decl.kind_keyword()),
        tags: None,
        deprecated: None,
        range,
        selection_range: range,
        children: None,
    })
}

/// Map a declaration keyword to the label shown in `detail`.
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
        _ => "decl",
    }
}

/// Map a declaration keyword to the closest LSP `SymbolKind`. LSP has
/// no domain vocabulary for "part"/"assembly"/etc, so this is a
/// best-effort classification, not a second source of truth (the
/// `detail` field carries the real kind word).
fn symbol_kind_for(kind: Option<SyntaxKind>) -> SymbolKind {
    match kind {
        Some(SyntaxKind::InterfaceKw) => SymbolKind::INTERFACE,
        Some(SyntaxKind::NamespaceKw) => SymbolKind::NAMESPACE,
        Some(SyntaxKind::QuantityKw) => SymbolKind::CONSTANT,
        Some(SyntaxKind::ImportKw) => SymbolKind::MODULE,
        Some(_) => SymbolKind::CLASS,
        None => SymbolKind::OBJECT,
    }
}

#[cfg(test)]
mod tests {
    use super::document_symbols;
    use crate::position::LineIndex;

    #[test]
    fn top_level_parts_become_symbols() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let symbols = document_symbols(text, &index);
        assert_eq!(symbols.len(), 1);
        assert_eq!(symbols[0].name, "Widget");
        assert_eq!(symbols[0].detail.as_deref(), Some("part"));
    }

    #[test]
    fn empty_document_has_no_symbols() {
        let index = LineIndex::new("");
        assert!(document_symbols("", &index).is_empty());
    }
}
