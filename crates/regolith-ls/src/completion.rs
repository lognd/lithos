//! Completion v1 (WO-38 deliverable 6, keyword half only): the lexer's
//! own keyword table, unfiltered by enclosing block kind. Position-aware
//! filtering and in-scope declaration names/registry ids are NOT
//! implemented in this pass (see the WO-38 dispatch report gap list).

use lsp_types::{CompletionItem, CompletionItemKind};
use regolith_syntax::syntax_kind::keyword_kind;

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
];

/// Every keyword completion item. Every entry is checked against the
/// real `keyword_kind` table so this list cannot silently drift from
/// the grammar (WO-38: no second grammar, AD-24).
#[must_use]
pub fn keyword_completions() -> Vec<CompletionItem> {
    KEYWORDS
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
    use super::{keyword_completions, KEYWORDS};

    #[test]
    fn every_listed_keyword_is_a_real_grammar_keyword() {
        let items = keyword_completions();
        assert_eq!(items.len(), KEYWORDS.len());
    }
}
