//! The hand-written, event-based recursive-descent parser with Pratt
//! expressions and layout-anchored error recovery (AD-3).
//!
//! Substrate reference: `docs/substrate/08`, `docs/mech/02`,
//! `docs/elec/07`, and `examples/` (the concrete target corpus). The
//! parser emits events that a builder folds into a rowan tree; error
//! recovery syncs on INDENT/DEDENT so one bad statement never eats the
//! file (diagnostics stay batch-emitted, substrate/09 sec. 4).
//!
//! Domain payloads (walk bodies, `on <event>:` bodies, continuous
//! relations) parse to [`SyntaxKind::OpaqueIsland`] in this WO:
//! structure recorded, semantics deferred (WO-11 / behavioral).

use camino::Utf8PathBuf;
use rockhead_diag::Diagnostic;
use rowan::GreenNode;

use crate::cst::SyntaxNode;

/// The result of parsing one source file: a lossless green tree plus
/// any diagnostics. A parse ALWAYS produces a tree (error-resilient);
/// diagnostics are data, not failure (AD-7).
#[derive(Debug, Clone)]
pub struct Parse {
    green: GreenNode,
    diagnostics: Vec<Diagnostic>,
}

impl Parse {
    /// The typed root node of the parse.
    #[must_use]
    pub fn syntax(&self) -> SyntaxNode {
        SyntaxNode::new_root(self.green.clone())
    }

    /// Diagnostics collected during parsing (may be non-empty even for a
    /// usable tree).
    #[must_use]
    pub fn diagnostics(&self) -> &[Diagnostic] {
        &self.diagnostics
    }
}

/// Parse a source string belonging to `file` into a [`Parse`].
///
/// Runs lex -> layout -> parse. The `file` path anchors diagnostic
/// spans. Never panics on any input (the fuzz invariant, AD-3).
#[must_use]
pub fn parse(_source: &str, _file: &Utf8PathBuf) -> Parse {
    todo!(
        "STUB WO-05: lex -> layout -> event parser -> GreenNode; opaque islands for domain bodies"
    )
}

#[cfg(test)]
mod tests {
    // The acceptance corpus (every examples/ file parses to an AST with
    // goldens under tests/golden/ast/, plus E01xx rejection of 1V+1A,
    // == on continuous, and [a,b]/[i..j] misuse) lands with the parser
    // body. Grammar.ebnf is authored in the same WO; escalate example
    // ambiguities to the design log rather than inventing.
    #[test]
    #[ignore = "WO-05 impl: parse body + examples/ goldens pending"]
    fn examples_parse() {}
}
