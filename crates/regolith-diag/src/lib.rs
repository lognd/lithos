//! Diagnostic model and the single diagnostic renderer (AD-7).
//!
//! Regolith reference: `docs/spec/regolith/09-build-and-lockfile.md`
//! sec. 4 (batch-emitted, cross-referenced diagnostics) and
//! `docs/spec/regolith/05-ownership-and-queries.md` sec. 6 (matched
//! entities + concrete fixes). There is exactly ONE renderer in the
//! whole toolchain and it lives here (annotate-snippets); the Python
//! side prints returned strings verbatim, never re-renders.
//!
//! User-facing failures are diagnostics (data), not `Err` (AD-7):
//! checks return `Result<T, Vec<Diagnostic>>`; collection and batching
//! are the [`sink::DiagnosticSink`]'s job, never per-check effort.

pub mod code;
pub mod diagnostic;
pub mod render;
pub mod sink;
pub mod span;

pub use code::{codes, DiagCode, Family};
pub use diagnostic::{Diagnostic, Fix, MatchedEntity, RelatedRef, Replacement};
pub use render::{render, render_batch, ColorMode};
pub use sink::DiagnosticSink;
pub use span::{LabeledSpan, Span};

use serde::{Deserialize, Serialize};

/// Severity of a diagnostic. User-facing failures are diagnostics
/// (data), not `Err` (AD-7).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// Blocks a successful build.
    Error,
    /// Advisory; does not block.
    Warning,
}

#[cfg(test)]
mod tests {
    use super::Severity;

    #[test]
    fn severity_serializes_snake_case() {
        let json = serde_json::to_string(&Severity::Error).unwrap();
        assert_eq!(json, "\"error\"");
    }
}
