//! The rowan language binding: lossless red/green CST over
//! [`SyntaxKind`] (AD-3). Every source byte lives in the tree, so the
//! formatter, precise spans, and error-resilient trees come for free.

use crate::syntax_kind::SyntaxKind;

/// The regolith language marker for rowan's generic trees.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum RegolithLanguage {}

impl rowan::Language for RegolithLanguage {
    type Kind = SyntaxKind;

    fn kind_from_raw(raw: rowan::SyntaxKind) -> SyntaxKind {
        SyntaxKind::from_raw(raw.0)
    }

    fn kind_to_raw(kind: SyntaxKind) -> rowan::SyntaxKind {
        rowan::SyntaxKind(kind as u16)
    }
}

/// A node in the concrete syntax tree.
pub type SyntaxNode = rowan::SyntaxNode<RegolithLanguage>;
/// A token in the concrete syntax tree.
pub type SyntaxToken = rowan::SyntaxToken<RegolithLanguage>;
/// Either a node or a token.
pub type SyntaxElement = rowan::SyntaxElement<RegolithLanguage>;
