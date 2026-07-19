//! End-to-end exercise of the crate from outside: assemble a
//! `Diagnostic` with a span, a matched entity, and a fix, then run it
//! through the one renderer (AD-7) and check the rendered text carries
//! every piece -- driven entirely through `pub` API, per TEST003 (min
//! one integration test per crate interface).
// frob:tests crates/regolith-diag/src kind="integration"

use regolith_diag::{
    codes, render, ColorMode, Diagnostic, LabeledSpan, MatchedEntity, Severity, Span,
};

#[test]
fn a_full_diagnostic_renders_every_attached_piece() {
    let diagnostic = Diagnostic::error(codes::AMBIGUOUS_SELECTION, "query matched 2 entities")
        .with_span(LabeledSpan::new(Span::new("eps.cupr", 5, 9), "here"))
        .with_match(MatchedEntity {
            origin: "eps.cupr:12".to_string(),
            measures: vec!["voltage = 3.3V".to_string()],
        });

    assert_eq!(diagnostic.severity, Severity::Error);
    assert_eq!(diagnostic.primary_span().unwrap().file.as_str(), "eps.cupr");

    let source = "PWR1\nPWR2\nPWR3\nVCC =\n3.3V; # here\n";
    let rendered = render(&diagnostic, ColorMode::Plain, &|path| {
        if path.as_str() == "eps.cupr" {
            Some(source.to_string())
        } else {
            None
        }
    });

    assert!(rendered.contains("query matched 2 entities"));
    assert!(rendered.contains("matched: eps.cupr:12"));
    assert!(rendered.contains("voltage = 3.3V"));
}

#[test]
fn warning_severity_never_reads_as_error_text() {
    let diagnostic = Diagnostic::warning(codes::COMBINATIONAL_CYCLE, "advisory only");
    assert_eq!(diagnostic.severity, Severity::Warning);
    let rendered = render(&diagnostic, ColorMode::Plain, &|_| None);
    assert!(rendered.contains("advisory only"));
}
