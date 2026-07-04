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

    /// AD-3: `format` is idempotent over every corpus file under
    /// `examples/` (the concrete acceptance corpus, mirrored from
    /// `parser::tests::examples_parse`).
    #[test]
    fn format_is_idempotent_over_examples_corpus() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(std::path::Path::parent)
            .expect("crates/rockhead-syntax is two levels under the workspace root")
            .join("examples");
        let extensions: Vec<&'static str> = crate::extension::EXTENSIONS
            .iter()
            .map(|(e, _)| *e)
            .collect();
        let mut seen_any = false;
        for entry in walk_dir(&root) {
            let Some(ext) = entry.extension().and_then(|e| e.to_str()) else {
                continue;
            };
            if extensions.iter().all(|e| *e != ext) {
                continue;
            }
            seen_any = true;
            let src = std::fs::read_to_string(&entry)
                .unwrap_or_else(|e| panic!("reading {entry:?}: {e}"));
            let file = Utf8PathBuf::from_path_buf(entry.clone()).expect("utf8 path");
            let once = format(&src, &file);
            let twice = format(&once, &file);
            assert_eq!(once, twice, "format not idempotent for {entry:?}");
        }
        assert!(seen_any, "expected to find at least one example file");
    }

    fn walk_dir(dir: &std::path::Path) -> Vec<std::path::PathBuf> {
        let mut out = Vec::new();
        let Ok(entries) = std::fs::read_dir(dir) else {
            return out;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                out.extend(walk_dir(&path));
            } else {
                out.push(path);
            }
        }
        out
    }

    // AD-3/AD-11: idempotence over proptest-generated ASCII source text.
    // The formatter never fails (error-resilient parser + lossless CST),
    // so this holds for arbitrary ASCII input, not just accepted syntax.
    proptest::proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(256))]

        #[test]
        fn format_is_idempotent_over_arbitrary_ascii(src in "[ -~\\n\\t]{0,64}") {
            let file = Utf8PathBuf::from("prop.hem");
            let once = format(&src, &file);
            let twice = format(&once, &file);
            proptest::prop_assert_eq!(once, twice);
        }
    }
}
