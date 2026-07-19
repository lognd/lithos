//! Integration test (TEST003): exercises `regolith-syntax`'s public
//! lex/layout/parse/format surface the same way a caller outside the
//! crate (the CLI, the LSP) does -- against the published API only,
//! over a real source snippet.

// frob:tests crates/regolith-syntax/src kind="integration"
#[test]
fn parses_and_formats_a_minimal_source_from_outside_the_crate() {
    use camino::Utf8PathBuf;
    use regolith_syntax::formatter::format;
    use regolith_syntax::parser::parse;

    let file = Utf8PathBuf::from("part.hema");
    let text = "part Bracket:\n    require:\n        mech.mass(self) <= 2 kg\n";

    let parsed = parse(text, &file);
    assert!(
        parsed.diagnostics().is_empty(),
        "unexpected parse diagnostics: {:?}",
        parsed.diagnostics()
    );

    // AD-3: format is meaning-preserving and idempotent -- reformatting
    // already-canonical text is a no-op.
    let formatted = format(text, &file);
    let reparsed = parse(&formatted, &file);
    assert!(
        reparsed.diagnostics().is_empty(),
        "unexpected diagnostics after formatting: {:?}",
        reparsed.diagnostics()
    );
    assert_eq!(
        format(&formatted, &file),
        formatted,
        "format is not idempotent"
    );
}
