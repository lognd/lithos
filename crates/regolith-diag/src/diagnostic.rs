//! The `Diagnostic` model: a constructive, cross-referenced error or
//! warning stated in the user's vocabulary.
//!
//! Substrate reference: `docs/substrate/09-build-and-lockfile.md`
//! sec. 4 and `docs/substrate/05-ownership-and-queries.md` sec. 6:
//! show the query, the matched entities with origin and measures, and
//! 2-3 concrete fixes, with cross-references to related diagnostics.

use serde::{Deserialize, Serialize};

use crate::code::DiagCode;
use crate::span::{LabeledSpan, Span};
use crate::Severity;

/// One entity that a failing query matched, shown in the diagnostic's
/// matched-entity table: where it came from and what it measures.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MatchedEntity {
    /// Human origin of the entity ("declared in eps.cupr:12", a path).
    pub origin: String,
    /// The measure pairs that make it a candidate ("voltage = 3.3V").
    pub measures: Vec<String>,
}

/// A structured (not prose) fix suggestion. The renderer turns it into
/// a "help:" line; a future LSP turns it into a code action.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Fix {
    /// One-line description of the suggested change.
    pub message: String,
    /// Optional concrete replacement span + text (edit the LSP applies).
    pub replacement: Option<Replacement>,
}

/// A concrete textual edit backing a [`Fix`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Replacement {
    /// The span to replace.
    pub span: Span,
    /// The text to put there.
    pub text: String,
}

/// A cross-reference to another diagnostic in the same batch (the
/// "edit blast radius" links, `check --explain`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RelatedRef {
    /// The related diagnostic's code.
    pub code: DiagCode,
    /// Why it is related ("this borrow conflicts with the one above").
    pub note: String,
    /// Where the related diagnostic anchors.
    pub span: Span,
}

/// A single constructive diagnostic.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Diagnostic {
    /// The stable code (family + offset).
    pub code: DiagCode,
    /// Blocks a build (error) or advisory (warning).
    pub severity: Severity,
    /// The primary message, in the user's vocabulary.
    pub message: String,
    /// Source spans; the first is primary, the rest are secondary.
    pub spans: Vec<LabeledSpan>,
    /// The matched-entity table (origin + measures).
    pub matched: Vec<MatchedEntity>,
    /// 2-3 concrete fixes.
    pub fixes: Vec<Fix>,
    /// Cross-references to related diagnostics.
    pub related: Vec<RelatedRef>,
}

impl Diagnostic {
    /// Start an error diagnostic with a code and primary message.
    /// Builder methods add spans, matches, fixes, and relations.
    #[must_use]
    pub fn error(code: DiagCode, message: impl Into<String>) -> Diagnostic {
        Diagnostic {
            code,
            severity: Severity::Error,
            message: message.into(),
            spans: Vec::new(),
            matched: Vec::new(),
            fixes: Vec::new(),
            related: Vec::new(),
        }
    }

    /// Start a warning diagnostic.
    #[must_use]
    pub fn warning(code: DiagCode, message: impl Into<String>) -> Diagnostic {
        Diagnostic {
            severity: Severity::Warning,
            ..Diagnostic::error(code, message)
        }
    }

    /// Attach a labelled span (builder).
    #[must_use]
    pub fn with_span(mut self, span: LabeledSpan) -> Diagnostic {
        self.spans.push(span);
        self
    }

    /// Attach a matched entity row (builder).
    #[must_use]
    pub fn with_match(mut self, entity: MatchedEntity) -> Diagnostic {
        self.matched.push(entity);
        self
    }

    /// Attach a fix suggestion (builder).
    #[must_use]
    pub fn with_fix(mut self, fix: Fix) -> Diagnostic {
        self.fixes.push(fix);
        self
    }

    /// Attach a cross-reference to a related diagnostic (builder).
    #[must_use]
    pub fn with_related(mut self, related: RelatedRef) -> Diagnostic {
        self.related.push(related);
        self
    }

    /// The primary span (first attached), if any -- the anchor used for
    /// ordering in the sink.
    #[must_use]
    pub fn primary_span(&self) -> Option<&Span> {
        self.spans.first().map(|s| &s.span)
    }
}

#[cfg(test)]
mod tests {
    use super::{Diagnostic, Fix, MatchedEntity};
    use crate::code::codes;
    use crate::span::{LabeledSpan, Span};
    use crate::Severity;

    #[test]
    fn builder_assembles_a_full_diagnostic() {
        let d = Diagnostic::error(codes::AMBIGUOUS_SELECTION, "query matched 2 entities")
            .with_span(LabeledSpan::new(Span::new("eps.cupr", 5, 9), "here"))
            .with_match(MatchedEntity {
                origin: "eps.cupr:12".to_string(),
                measures: vec!["voltage = 3.3V".to_string()],
            })
            .with_fix(Fix {
                message: "disambiguate with `where`".to_string(),
                replacement: None,
            });
        assert_eq!(d.severity, Severity::Error);
        assert_eq!(d.matched.len(), 1);
        assert_eq!(d.fixes.len(), 1);
        assert_eq!(d.primary_span().unwrap().start, 5);
    }

    #[test]
    fn diagnostic_round_trips_json() {
        let d = Diagnostic::warning(codes::EQUALITY_ON_CONTINUOUS, "== on continuous");
        let json = serde_json::to_string(&d).unwrap();
        let back: Diagnostic = serde_json::from_str(&json).unwrap();
        assert_eq!(back, d);
    }
}
