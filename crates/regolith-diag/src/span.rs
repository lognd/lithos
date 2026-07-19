//! Source spans: a byte range in a named source file, optionally
//! labelled, used to anchor diagnostics to source (AD-7 renderer).
//!
//! Regolith reference: `docs/spec/regolith/09-build-and-lockfile.md`
//! sec. 4. Byte offsets are the fidelity currency; the renderer
//! (annotate-snippets) turns them into line/column snippets. Paths are
//! `Utf8PathBuf` (AD-12 -- Windows-safe, UTF-8-checked).

use camino::Utf8PathBuf;
use serde::{Deserialize, Serialize};

/// A half-open byte range `[start, end)` within a source file.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-diag.md#span
pub struct Span {
    /// The source file the range points into.
    pub file: Utf8PathBuf,
    /// Inclusive start byte offset.
    pub start: usize,
    /// Exclusive end byte offset.
    pub end: usize,
}

impl Span {
    /// Construct a span over `[start, end)` in `file`.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#span
    pub fn new(file: impl Into<Utf8PathBuf>, start: usize, end: usize) -> Span {
        Span {
            file: file.into(),
            start,
            end,
        }
    }
}

/// A span plus the short label the renderer prints beside it
/// ("this quantity is a voltage", "borrowed here").
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-diag.md#span
pub struct LabeledSpan {
    /// Where in source this annotation points.
    pub span: Span,
    /// The one-line label rendered against the underline.
    pub label: String,
}

impl LabeledSpan {
    /// Attach `label` to `span`.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#span
    pub fn new(span: Span, label: impl Into<String>) -> LabeledSpan {
        LabeledSpan {
            span,
            label: label.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{LabeledSpan, Span};

    #[test]
    fn span_round_trips_json() {
        let s = LabeledSpan::new(Span::new("a.cupr", 10, 15), "here");
        let json = serde_json::to_string(&s).unwrap();
        let back: LabeledSpan = serde_json::from_str(&json).unwrap();
        assert_eq!(back, s);
    }
}
