//! The layout pass: converts leading-whitespace structure into
//! INDENT/DEDENT/NEWLINE tokens so the parser stays context-free
//! (AD-3, Python-style off-side rule).
//!
//! Substrate reference: `docs/substrate/08`. Indentation is spaces
//! only; a tab in indentation is an E01xx diagnostic (WO-06). Blank
//! lines and comment-only lines do not emit layout tokens.

use rockhead_diag::Diagnostic;

use crate::syntax_kind::SyntaxKind;
use crate::token::RawToken;

/// A token after the layout pass: a `SyntaxKind` (raw kinds plus the
/// synthesized Indent/Dedent/Newline) with its source span.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutToken {
    /// The post-layout kind.
    pub kind: SyntaxKind,
    /// Byte span in the original source (synthesized tokens are
    /// zero-width at the relevant offset).
    pub span: std::ops::Range<usize>,
}

/// Run the layout pass over raw tokens, emitting INDENT/DEDENT/NEWLINE
/// and mapping keyword idents. Tab-indentation errors are returned as
/// diagnostics alongside a best-effort token stream (batch discipline).
#[must_use]
pub fn apply_layout(
    _raw: &[(RawToken, std::ops::Range<usize>)],
    _source: &str,
) -> (Vec<LayoutToken>, Vec<Diagnostic>) {
    todo!("STUB WO-05: off-side rule -> INDENT/DEDENT/NEWLINE; keyword mapping; tab E01xx")
}

#[cfg(test)]
mod tests {
    // Behavioural tests land with the implementation (indentation
    // increase -> Indent, dedent to column -> Dedent(s), tab -> E01xx).
    // Wired here so the acceptance surface is visible.
    #[test]
    #[ignore = "WO-05 impl: apply_layout body pending"]
    fn indent_then_dedent() {}
}
