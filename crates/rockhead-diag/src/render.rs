//! The ONE diagnostic renderer (AD-7): rustc-style constructive output
//! via `annotate-snippets`. No second renderer exists anywhere; the
//! Python side prints these strings verbatim.
//!
//! Substrate reference: `docs/substrate/09-build-and-lockfile.md`
//! sec. 4. Rendering shows the message, the primary and secondary
//! spans as source snippets, the matched-entity table, the 2-3 fixes,
//! and the related cross-references (the "edit blast radius at once").

use crate::diagnostic::Diagnostic;

/// Whether to emit ANSI colour codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ColorMode {
    /// Plain text (goldens, `--json` neighbours, non-tty).
    Plain,
    /// ANSI-coloured (interactive terminal).
    Ansi,
}

/// Render one diagnostic to text, reading the referenced source so the
/// snippet lines can be shown.
///
/// `source_of` maps a file path to its full text; the renderer slices
/// the spans out of it. Returned string is the exact bytes printed --
/// the Python side never re-renders (AD-7).
#[must_use]
pub fn render(
    _diagnostic: &Diagnostic,
    _color: ColorMode,
    _source_of: &dyn Fn(&camino::Utf8Path) -> Option<String>,
) -> String {
    todo!("WO-06: annotate-snippets Renderer; snippet + matched table + fixes + related")
}

/// Render a whole batch (already ordered by the sink) into one string,
/// diagnostics separated by a blank line.
#[must_use]
pub fn render_batch(
    _diagnostics: &[Diagnostic],
    _color: ColorMode,
    _source_of: &dyn Fn(&camino::Utf8Path) -> Option<String>,
) -> String {
    todo!("WO-06: map render() over the batch, blank-line separated")
}

#[cfg(test)]
mod tests {
    use super::{render_batch, ColorMode};
    use crate::code::codes;
    use crate::diagnostic::Diagnostic;
    use crate::span::{LabeledSpan, Span};

    // The acceptance snapshot: three cross-referenced diagnostics
    // rendered as the spec's "edit blast radius at once" shape. Wired
    // now, un-ignored once render() lands (insta snapshot in WO-06).
    #[test]
    #[ignore = "WO-06 impl: render() pending; becomes an insta snapshot"]
    fn three_cross_referenced_diagnostics_render() {
        let src = "supply v(3.3V)\nborrow rail\nborrow rail\n";
        let source_of =
            move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let batch = vec![
            Diagnostic::error(codes::BORROW_CONFLICT, "rail borrowed twice")
                .with_span(LabeledSpan::new(Span::new("eps.cupr", 15, 26), "first borrow")),
            Diagnostic::error(codes::BORROW_CONFLICT, "conflicting borrow")
                .with_span(LabeledSpan::new(Span::new("eps.cupr", 27, 38), "second borrow")),
            Diagnostic::error(codes::CAPABILITY_VS_DEMAND, "rail overcommitted")
                .with_span(LabeledSpan::new(Span::new("eps.cupr", 0, 14), "supplies 3.3V")),
        ];
        let out = render_batch(&batch, ColorMode::Plain, &source_of);
        assert!(out.contains("E0302"));
        assert!(out.contains("E0410"));
    }
}
