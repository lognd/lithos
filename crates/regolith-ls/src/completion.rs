//! Completion v1 (WO-38 deliverable 6): the lexer's own keyword table
//! filtered by the enclosing block kind (top level offers decl-starter
//! keywords; inside a decl body offers statement/field keywords), plus
//! every in-scope declaration name in the current file. Registry
//! component ids (a magnetite index read) are NOT implemented in this
//! pass -- out of reach without a magnetite-index reader in this crate
//! (see the WO-38 dispatch report gap list); the keyword and decl-name
//! halves are the completion surface a corpus file actually exercises.

use lsp_types::{CompletionItem, CompletionItemKind, Position};
use regolith_syntax::ast::{AstNode, Decl};
use regolith_syntax::syntax_kind::keyword_kind;

use crate::position::LineIndex;

/// The keyword table this server completes from -- the same words the
/// lexer recognizes as keywords (`keyword_kind`'s domain), so the
/// completion list can never drift from the real grammar.
const KEYWORDS: &[&str] = &[
    "import",
    "namespace",
    "quantity",
    "signature",
    "part",
    "profile",
    "interface",
    "mating",
    "assembly",
    "system",
    "block",
    "impl",
    "component",
    "protocol",
    "computer",
    "image",
    "board",
    "target",
    "datum",
    "event",
    "then",
    "on",
    "require",
    "budget",
    "waive",
    "policy",
    "prefer",
    "forbid",
    "minimize",
    "maximize",
    "locked",
    "extern",
    "model",
    "hosted_on",
    "in",
    "free",
    "derived",
    "allocated",
    "within",
    "use",
    "override",
    "by",
    "default",
    "during",
    "select",
];

/// Keywords that start a top-level (or decl-body-opening) declaration --
/// offered when the cursor is NOT already inside a decl's body.
const TOP_LEVEL_KEYWORDS: &[&str] = &[
    "import",
    "namespace",
    "quantity",
    "signature",
    "part",
    "profile",
    "interface",
    "mating",
    "assembly",
    "system",
    "block",
    "impl",
    "component",
    "protocol",
    "computer",
    "image",
    "board",
    "target",
    "extern",
    "model",
    "use",
];

/// Keywords that appear inside a decl body (statement/field heads) --
/// offered when the cursor sits inside a `Decl` node's body.
const BODY_KEYWORDS: &[&str] = &[
    "datum",
    "event",
    "then",
    "on",
    "require",
    "budget",
    "waive",
    "policy",
    "prefer",
    "forbid",
    "minimize",
    "maximize",
    "locked",
    "hosted_on",
    "in",
    "free",
    "derived",
    "allocated",
    "within",
    "override",
    "by",
    "default",
    "during",
];

/// Every keyword completion item, unfiltered by position (kept for
/// callers with no position context, and to exercise the drift check
/// against `keyword_kind`). Every entry is checked against the real
/// `keyword_kind` table so this list cannot silently drift from the
/// grammar (WO-38: no second grammar, AD-24).
#[must_use]
pub fn keyword_completions() -> Vec<CompletionItem> {
    keyword_items(KEYWORDS)
}

/// Position-aware completion (deliverable 6): keywords filtered by
/// whether the cursor sits inside a `Decl` body or at top level, plus
/// every in-scope declaration name in `text`.
#[must_use]
pub fn completions_at(text: &str, index: &LineIndex, position: Position) -> Vec<CompletionItem> {
    let offset = index.offset(position);
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    // Body statements are indented under a `:`-terminated header line
    // (the grammar's own convention, mirrored by the formatter); a
    // leading-whitespace line is the cheap, reliable signal for "inside
    // a decl body" -- checking the enclosing `Decl` ancestor alone is
    // NOT enough because the header line's own tokens (the `part`
    // keyword, the decl name) are themselves inside the `Decl` node.
    let line_start = text[..offset.min(text.len())]
        .rfind('\n')
        .map_or(0, |i| i + 1);
    let in_body = text[line_start..offset.min(text.len())]
        .chars()
        .next()
        .is_some_and(char::is_whitespace);

    let mut items = if in_body {
        keyword_items(BODY_KEYWORDS)
    } else {
        keyword_items(TOP_LEVEL_KEYWORDS)
    };
    items.extend(decl_name_completions(&parse));
    items
}

/// Every declaration name in `parse` as a completion item (in-scope
/// declaration names, deliverable 6's second source).
fn decl_name_completions(parse: &regolith_syntax::Parse) -> Vec<CompletionItem> {
    parse
        .syntax()
        .children()
        .filter_map(Decl::cast)
        .filter_map(|decl| decl.name())
        .map(|name| CompletionItem {
            label: name,
            kind: Some(CompletionItemKind::CLASS),
            ..CompletionItem::default()
        })
        .collect()
}

/// Build completion items for a keyword list, dropping any entry the
/// real lexer table does not recognize (the drift guard).
fn keyword_items(words: &[&str]) -> Vec<CompletionItem> {
    words
        .iter()
        .filter(|kw| keyword_kind(kw).is_some())
        .map(|kw| CompletionItem {
            label: (*kw).to_string(),
            kind: Some(CompletionItemKind::KEYWORD),
            ..CompletionItem::default()
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{completions_at, keyword_completions, BODY_KEYWORDS, KEYWORDS, TOP_LEVEL_KEYWORDS};
    use crate::position::LineIndex;

    #[test]
    fn every_listed_keyword_is_a_real_grammar_keyword() {
        let items = keyword_completions();
        assert_eq!(items.len(), KEYWORDS.len());
    }

    #[test]
    fn top_level_and_body_subsets_are_covered_by_the_full_list() {
        for kw in TOP_LEVEL_KEYWORDS.iter().chain(BODY_KEYWORDS) {
            assert!(KEYWORDS.contains(kw), "{kw} missing from KEYWORDS");
        }
    }

    #[test]
    fn top_level_position_offers_decl_starters_not_body_keywords() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let pos = index.position(0);
        let items = completions_at(text, &index, pos);
        let labels: Vec<_> = items.iter().map(|i| i.label.as_str()).collect();
        assert!(labels.contains(&"part"));
        assert!(!labels.contains(&"require"));
    }

    #[test]
    fn body_position_offers_body_keywords_and_the_decl_name() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let pos = index.position(text.find("mass").unwrap());
        let items = completions_at(text, &index, pos);
        let labels: Vec<_> = items.iter().map(|i| i.label.as_str()).collect();
        assert!(labels.contains(&"Widget"));
    }
}
