//! Semantic tokens (WO-38 deliverable 5): lexer token kinds + CST
//! classification over the real parse tree -- no second grammar.
//! Legend: `keyword` (declaration/kind words), `number` (quantity
//! literals with units), `string`, `comment`, `variable` (identifiers).

use lsp_types::{SemanticToken, SemanticTokenType, SemanticTokensLegend};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::position::LineIndex;

/// The token-type legend this server declares in `initialize` and every
/// token index below is relative to (order is the wire contract).
// frob:doc docs/modules/regolith-ls.md#semtok
pub const LEGEND: &[SemanticTokenType] = &[
    SemanticTokenType::KEYWORD,
    SemanticTokenType::NUMBER,
    SemanticTokenType::STRING,
    SemanticTokenType::COMMENT,
    SemanticTokenType::VARIABLE,
];

const TY_KEYWORD: u32 = 0;
const TY_NUMBER: u32 = 1;
const TY_STRING: u32 = 2;
const TY_COMMENT: u32 = 3;
const TY_VARIABLE: u32 = 4;

/// Build the semantic-tokens legend for `initialize`'s capability
/// response.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#semtok
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn legend() -> SemanticTokensLegend {
    SemanticTokensLegend {
        token_types: LEGEND.to_vec(),
        token_modifiers: Vec::new(),
    }
}

/// Compute the full delta-encoded semantic token stream for `text`.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#semtok
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn tokens_for(text: &str, index: &LineIndex) -> Vec<SemanticToken> {
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);

    let mut raw = Vec::new();
    for elem in parse.syntax().descendants_with_tokens() {
        let rowan::NodeOrToken::Token(tok) = elem else {
            continue;
        };
        let Some(ty) = token_type(tok.kind()) else {
            continue;
        };
        let range = tok.text_range();
        let start = index.position(usize::from(range.start()));
        let length = u32::try_from(tok.text().len()).unwrap_or(u32::MAX);
        raw.push((start.line, start.character, length, ty));
    }
    raw.sort_by_key(|&(line, col, ..)| (line, col));

    let mut out = Vec::with_capacity(raw.len());
    let (mut prev_line, mut prev_start) = (0u32, 0u32);
    for (line, start, length, ty) in raw {
        let delta_line = line - prev_line;
        let delta_start = if delta_line == 0 {
            start - prev_start
        } else {
            start
        };
        out.push(SemanticToken {
            delta_line,
            delta_start,
            length,
            token_type: ty,
            token_modifiers_bitset: 0,
        });
        prev_line = line;
        prev_start = start;
    }
    out
}

/// Map a leaf `SyntaxKind` to its semantic token-type index, or `None`
/// for kinds not worth highlighting (punctuation, trivia whitespace).
fn token_type(kind: SyntaxKind) -> Option<u32> {
    if is_keyword_kind(kind) {
        return Some(TY_KEYWORD);
    }
    match kind {
        SyntaxKind::Number => Some(TY_NUMBER),
        SyntaxKind::String => Some(TY_STRING),
        SyntaxKind::Comment => Some(TY_COMMENT),
        SyntaxKind::Ident => Some(TY_VARIABLE),
        _ => None,
    }
}

/// True for every keyword `SyntaxKind` (mirrors the `keyword_kind`
/// table in `regolith_syntax::syntax_kind`; kept local because that
/// crate exposes the text->kind map, not an `is_keyword` predicate).
fn is_keyword_kind(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::ImportKw
            | SyntaxKind::NamespaceKw
            | SyntaxKind::QuantityKw
            | SyntaxKind::SignatureKw
            | SyntaxKind::PartKw
            | SyntaxKind::ProfileKw
            | SyntaxKind::InterfaceKw
            | SyntaxKind::MatingKw
            | SyntaxKind::AssemblyKw
            | SyntaxKind::SystemKw
            | SyntaxKind::BlockKw
            | SyntaxKind::ImplKw
            | SyntaxKind::ComponentKw
            | SyntaxKind::ProtocolKw
            | SyntaxKind::ComputerKw
            | SyntaxKind::ImageKw
            | SyntaxKind::BoardKw
            | SyntaxKind::TargetKw
            | SyntaxKind::DatumKw
            | SyntaxKind::EventKw
            | SyntaxKind::ThenKw
            | SyntaxKind::OnKw
            | SyntaxKind::RequireKw
            | SyntaxKind::BudgetKw
            | SyntaxKind::WaiveKw
            | SyntaxKind::PolicyKw
            | SyntaxKind::PreferKw
            | SyntaxKind::ForbidKw
            | SyntaxKind::MinimizeKw
            | SyntaxKind::MaximizeKw
            | SyntaxKind::LockedKw
            | SyntaxKind::ExternKw
            | SyntaxKind::SelectKw
            | SyntaxKind::ModelKw
            | SyntaxKind::HostedOnKw
            | SyntaxKind::InKw
            | SyntaxKind::FreeKw
            | SyntaxKind::DerivedKw
            | SyntaxKind::AllocatedKw
            | SyntaxKind::WithinKw
            | SyntaxKind::UseKw
            | SyntaxKind::OverrideKw
            | SyntaxKind::ByKw
            | SyntaxKind::DefaultKw
            | SyntaxKind::DuringKw
    )
}

#[cfg(test)]
mod tests {
    use super::{legend, tokens_for, LEGEND};
    use crate::position::LineIndex;

    // frob:tests crates/regolith-ls/src/semtok.rs::legend kind="unit"
    #[test]
    fn legend_carries_every_declared_token_type_in_order() {
        let l = legend();
        assert_eq!(l.token_types, LEGEND.to_vec());
    }

    // frob:tests crates/regolith-ls/src/semtok.rs::tokens_for kind="unit"
    #[test]
    fn keywords_and_idents_are_classified() {
        let text = "part Widget:\n    mass: 5 g\n";
        let index = LineIndex::new(text);
        let toks = tokens_for(text, &index);
        assert!(!toks.is_empty());
        // First token on line 0 is the `part` keyword (type 0).
        assert_eq!(toks[0].token_type, 0);
    }

    #[test]
    fn empty_document_has_no_tokens() {
        let index = LineIndex::new("");
        assert!(tokens_for("", &index).is_empty());
    }
}
