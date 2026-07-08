//! Folding ranges (WO-38 deliverable 5): CST block/node ancestry, no
//! second grammar. One folding range per top-level declaration body.

use lsp_types::{FoldingRange, FoldingRangeKind};
use regolith_syntax::ast::{AstNode, Decl};

use crate::position::LineIndex;

/// Folding ranges over every top-level declaration in `text`.
#[must_use]
pub fn folding_ranges(text: &str, index: &LineIndex) -> Vec<FoldingRange> {
    let path = camino::Utf8PathBuf::from("<ls>");
    let parse = regolith_syntax::parse(text, &path);
    parse
        .syntax()
        .children()
        .filter_map(Decl::cast)
        .filter_map(|decl| fold_for(&decl, index))
        .collect()
}

/// A decl's own span becomes a `Region` fold, when it spans more than
/// one line (folding a single line is a no-op the client should not
/// need to filter itself).
fn fold_for(decl: &Decl, index: &LineIndex) -> Option<FoldingRange> {
    let range = decl.syntax().text_range();
    let start = index.position(usize::from(range.start()));
    let end = index.position(usize::from(range.end()));
    if start.line >= end.line {
        return None;
    }
    Some(FoldingRange {
        start_line: start.line,
        start_character: Some(start.character),
        end_line: end.line,
        end_character: Some(end.character),
        kind: Some(FoldingRangeKind::Region),
        collapsed_text: None,
    })
}

#[cfg(test)]
mod tests {
    use super::folding_ranges;
    use crate::position::LineIndex;

    #[test]
    fn multiline_decl_folds() {
        let text = "part Widget:\n    mass: 5 g\n    volume: 2 cm3\n";
        let index = LineIndex::new(text);
        let folds = folding_ranges(text, &index);
        assert_eq!(folds.len(), 1);
        assert_eq!(folds[0].start_line, 0);
        assert!(folds[0].end_line >= 2);
    }
}
