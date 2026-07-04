//! The canonical formatter: the rowan-based normalizer. Because the CST
//! is lossless, `parse -> print -> parse` is a fixed point on accepted
//! input by construction (AD-3; WO-05 acceptance).
//!
//! Substrate reference: `docs/mech/04` (canonical forms). One
//! normalizer; the CLI `fmt` and the golden pipeline both call it.

use camino::Utf8PathBuf;

/// Format `source` into its canonical spelling. On unparseable input the
/// original text is returned unchanged (never destroys source).
///
/// The parser is error-resilient and always produces a lossless CST, so
/// reprinting it (`parse.syntax().text()`) reproduces `source` exactly
/// and is therefore idempotent by construction. This bootstrap pass
/// does not yet implement true canonicalization (re-spacing, quote
/// normalization, ...) -- that lands once the statement-level grammar
/// (fields, ctor statements, expressions) is filled in beyond this
/// WO-05 pass's opaque-island simplification; see the report note.
#[must_use]
pub fn format(source: &str, file: &Utf8PathBuf) -> String {
    let parse = crate::parser::parse(source, file);
    parse.syntax().text().to_string()
}

#[cfg(test)]
mod tests {
    use super::format;
    use camino::Utf8PathBuf;

    #[test]
    fn format_is_idempotent() {
        let file = Utf8PathBuf::from("t.hem");
        let src = "import a.b\npart wall:\n    thickness: 4mm\n";
        let once = format(src, &file);
        let twice = format(&once, &file);
        assert_eq!(once, twice);
    }

    #[test]
    fn unparseable_input_returned_unchanged() {
        // The parser never fails outright (error-resilient), so even
        // pathological input round-trips through format unchanged.
        let file = Utf8PathBuf::from("t.hem");
        let src = ")))###\n";
        assert_eq!(format(src, &file), src);
    }
}
