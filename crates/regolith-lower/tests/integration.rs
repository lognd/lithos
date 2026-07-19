//! Integration test (TEST003): exercises `regolith-lower`'s public
//! pipeline entry points the same way `regolith-api::Session` does --
//! from outside the crate, against the published surface only.

// frob:tests crates/regolith-lower/src kind="integration"
#[test]
fn lower_produces_output_for_a_minimal_source_from_outside_the_crate() {
    use camino::Utf8PathBuf;
    use regolith_lower::{realized_input::RealizedInputs, SourceFile};

    let sources = vec![SourceFile {
        path: Utf8PathBuf::from("part.hema"),
        text: "part Bracket:\n".to_string(),
    }];
    let out = regolith_lower::lower(&sources, &RealizedInputs::new());

    // AD-17: `lower` is a pure function of source text and never
    // returns `Err` -- a build with no `require` blocks still
    // materializes a full LowerOutput, just with an empty obligation
    // set and no diagnostics for this well-formed minimal part.
    assert!(out.obligations.is_empty());
    assert!(
        out.diagnostics.is_empty(),
        "unexpected diagnostics: {:?}",
        out.diagnostics
    );
}
