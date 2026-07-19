//! `DiagnosticSink`: batch collection with dedup and deterministic
//! ordering. Never-first-error-stops is a property of the sink, not of
//! per-check discipline (WO-06 goal).
//!
//! Regolith reference: `docs/spec/regolith/09-build-and-lockfile.md`
//! sec. 4 (batch-emitted with cross-references). Ordering is
//! deterministic (AD-6): by primary span (file, then offset), ties
//! broken by code number, so the same source always renders the same
//! blast radius.

use crate::diagnostic::Diagnostic;
use crate::Severity;

/// Collects diagnostics from every check in a pass, then yields them in
/// a stable order for rendering. Checks push into it and keep going;
/// the caller decides success from whether any error was collected.
#[derive(Debug, Default)]
// frob:doc docs/modules/regolith-diag.md#sink
pub struct DiagnosticSink {
    diagnostics: Vec<Diagnostic>,
}

impl DiagnosticSink {
    /// A fresh, empty sink.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#sink
    pub fn new() -> DiagnosticSink {
        DiagnosticSink {
            diagnostics: Vec::new(),
        }
    }

    /// Record one diagnostic. Never short-circuits the caller.
    // frob:doc docs/modules/regolith-diag.md#sink
    pub fn emit(&mut self, diagnostic: Diagnostic) {
        self.diagnostics.push(diagnostic);
    }

    /// True when at least one collected diagnostic is an error (the
    /// build-fails predicate).
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#sink
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn has_errors(&self) -> bool {
        self.diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
    }

    /// Number of collected diagnostics.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#sink
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn len(&self) -> usize {
        self.diagnostics.len()
    }

    /// True when nothing has been collected.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#sink
    pub fn is_empty(&self) -> bool {
        self.diagnostics.is_empty()
    }

    /// Consume the sink and return its diagnostics deduplicated and in
    /// deterministic order (AD-6): by primary span (file, start), then
    /// by code number. Diagnostics without a span sort last.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#sink
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn finish(self) -> Vec<Diagnostic> {
        let mut diagnostics = self.diagnostics;
        diagnostics.sort_by(|a, b| {
            let key_a = a.primary_span();
            let key_b = b.primary_span();
            match (key_a, key_b) {
                (Some(span_a), Some(span_b)) => span_a
                    .file
                    .cmp(&span_b.file)
                    .then(span_a.start.cmp(&span_b.start))
                    .then(a.code.number().cmp(&b.code.number())),
                (Some(_), None) => std::cmp::Ordering::Less,
                (None, Some(_)) => std::cmp::Ordering::Greater,
                (None, None) => a.code.number().cmp(&b.code.number()),
            }
        });
        diagnostics.dedup();
        diagnostics
    }
}

#[cfg(test)]
mod tests {
    use super::DiagnosticSink;
    use crate::code::codes;
    use crate::diagnostic::Diagnostic;

    // frob:tests crates/regolith-diag/src/sink.rs::DiagnosticSink.len kind="unit"
    // frob:tests crates/regolith-diag/src/sink.rs::DiagnosticSink.has_errors kind="unit"
    #[test]
    fn sink_collects_without_short_circuit() {
        let mut sink = DiagnosticSink::new();
        assert!(sink.is_empty());
        sink.emit(Diagnostic::error(codes::BORROW_CONFLICT, "first"));
        sink.emit(Diagnostic::warning(codes::EQUALITY_ON_CONTINUOUS, "second"));
        assert_eq!(sink.len(), 2);
        assert!(sink.has_errors());
    }

    // frob:tests crates/regolith-diag/src/sink.rs::DiagnosticSink.finish kind="unit"
    #[test]
    fn finish_orders_and_dedups() {
        let mut sink = DiagnosticSink::new();
        sink.emit(Diagnostic::error(codes::BORROW_CONFLICT, "dup"));
        sink.emit(Diagnostic::error(codes::BORROW_CONFLICT, "dup"));
        assert_eq!(sink.finish().len(), 1);
    }
}
