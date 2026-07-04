//! Pipeline inspection dumps backing `rockhead debug tokens|cst|ast`
//! (AD-13 / DX contract 5: intermediate states are always inspectable).
//!
//! Plain-text, deterministic renderings of each stage for goldens and
//! human debugging. stdout is data (these strings); logs go to stderr.

use camino::Utf8PathBuf;

/// The pipeline stage to dump.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stage {
    /// Raw + layout token stream.
    Tokens,
    /// The lossless CST (indented S-expression form).
    Cst,
    /// The typed AST view tree.
    Ast,
}

/// Render `stage` of parsing `source` (belonging to `file`) as a stable
/// plain-text dump.
#[must_use]
pub fn dump(_stage: Stage, _source: &str, _file: &Utf8PathBuf) -> String {
    todo!("STUB WO-05: render the requested stage deterministically for debug + goldens")
}
