//! Formatting (WO-38 deliverable 5): the existing canonicalizing
//! formatter, whole document, thin delegation to `regolith_api::format`
//! (the one formatter, AD-4).

use lsp_types::{Position, TextEdit};

use crate::position::LineIndex;

/// Format `text` and return the single whole-document `TextEdit` that
/// replaces it with its canonical spelling, or `None` if already
/// canonical (no-op edit).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#formatting
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn format_document(text: &str, index: &LineIndex) -> Option<TextEdit> {
    let formatted = regolith_api::format(text);
    if formatted == text {
        return None;
    }
    let end = index.position(text.len());
    Some(TextEdit {
        range: lsp_types::Range {
            start: Position::new(0, 0),
            end,
        },
        new_text: formatted,
    })
}

#[cfg(test)]
mod tests {
    use super::format_document;
    use crate::position::LineIndex;

    // frob:tests crates/regolith-ls/src/formatting.rs::format_document kind="unit"
    #[test]
    fn already_canonical_text_yields_no_edit() {
        let text = regolith_api::format("part Widget:\n    mass: 5 g\n");
        let index = LineIndex::new(&text);
        assert!(format_document(&text, &index).is_none());
    }
}
