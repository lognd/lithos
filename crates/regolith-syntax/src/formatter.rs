//! The canonical formatter: the rowan-based normalizer (AD-3; WO-05
//! acceptance). It walks the lossless CST token stream and re-emits it
//! with canonical INTRA-line spacing, while preserving line structure
//! (newlines) and leading indentation verbatim -- so the transform is
//! meaning-preserving (`parse(format(x))` has the same token stream and
//! tree shape as `parse(x)`) and idempotent (`format(format(x)) ==
//! format(x)`).
//!
//! Substrate reference: `docs/hematite/04` (canonical forms). One
//! normalizer; the CLI `fmt` and the golden pipeline both call it.
//!
//! Canonical form (FE-9):
//! - one space after a field/block `:` and after `,`; none before them;
//! - one space on each side of a binary/tolerance/range operator
//!   (`+ - * / < > <= >= == = +- ..`);
//! - member `.` and call/index brackets stay tight (`a.b`, `f(x)`,
//!   `[..]`), `%` stays tight to its number, a `QuantityLit`'s number
//!   and unit stay adjacent (`5mm`);
//! - any other gap is preserved exactly (a space stays a space, no gap
//!   stays no gap) so two names never merge and a quantity never splits.

use camino::Utf8PathBuf;

use crate::syntax_kind::SyntaxKind;

/// Tokens that END a value, so a following `(`/`[`/`.` is a call/index/
/// member access (tight) rather than a grouping/collection (spaced).
fn is_value_end(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::Ident
            | SyntaxKind::Number
            | SyntaxKind::String
            | SyntaxKind::RParen
            | SyntaxKind::RBracket
            | SyntaxKind::Percent
    )
}

/// Tokens that can begin a member-access target after a `.` (`a.b`,
/// `a.5`); a `.` next to anything else is left as-is (never merged into
/// `..`).
fn is_name_start(kind: SyntaxKind) -> bool {
    matches!(kind, SyntaxKind::Ident | SyntaxKind::Number)
}

/// A binary/tolerance/range operator: canonically surrounded by single
/// spaces.
fn is_operator(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::Plus
            | SyntaxKind::Minus
            | SyntaxKind::Star
            | SyntaxKind::Slash
            | SyntaxKind::Lt
            | SyntaxKind::Gt
            | SyntaxKind::LtEq
            | SyntaxKind::GtEq
            | SyntaxKind::EqEqTok
            | SyntaxKind::Eq
            | SyntaxKind::DotDot
            | SyntaxKind::PlusMinus
    )
}

/// The canonical separator between two adjacent significant tokens.
/// `had_ws` is whether the source had a gap there; it is only consulted
/// for the "preserve" default, which never merges or splits a token.
fn canonical_gap(prev: SyntaxKind, cur: SyntaxKind, had_ws: bool) -> &'static str {
    use SyntaxKind as K;
    // Forced tight (no space).
    let tight = matches!(
        cur,
        K::Colon | K::Comma | K::RParen | K::RBracket | K::Percent
    ) || matches!(prev, K::LParen | K::LBracket)
        || (cur == K::Dot && is_value_end(prev))
        || (prev == K::Dot && is_name_start(cur))
        || (matches!(cur, K::LParen | K::LBracket) && is_value_end(prev));
    if tight {
        return "";
    }
    // Forced single space: around operators, and after `:`/`,`.
    if is_operator(prev) || is_operator(cur) || matches!(prev, K::Colon | K::Comma) {
        return " ";
    }
    // Otherwise preserve the source's gap presence (safe: never changes
    // tokenization -- e.g. a `QuantityLit`'s adjacent number+unit stays
    // tight, two space-separated names stay separated).
    if had_ws {
        " "
    } else {
        ""
    }
}

/// Format `source` into its canonical spelling. On unparseable input the
/// error-resilient CST still yields a best-effort canonical reprint
/// (never panics, never drops bytes of meaning).
#[must_use]
pub fn format(source: &str, file: &Utf8PathBuf) -> String {
    let parse = crate::parser::parse(source, file);
    let mut out = String::with_capacity(source.len());
    let mut prev_sig: Option<SyntaxKind> = None;
    let mut at_line_start = true;
    let mut had_ws = false;
    for tok in parse
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
    {
        match tok.kind() {
            SyntaxKind::Newline => {
                out.push_str(tok.text());
                at_line_start = true;
                prev_sig = None;
                had_ws = false;
            }
            SyntaxKind::Whitespace => {
                if at_line_start {
                    out.push_str(tok.text()); // leading indentation, verbatim
                } else {
                    had_ws = true; // interior gap; regenerated canonically
                }
            }
            // Zero-width layout markers: nothing to emit, still line-start.
            SyntaxKind::Indent | SyntaxKind::Dedent => {}
            SyntaxKind::Comment => {
                if !at_line_start {
                    out.push(' '); // one space before a trailing comment
                }
                out.push_str(tok.text());
                at_line_start = false;
                prev_sig = None;
                had_ws = false;
            }
            kind => {
                if let Some(prev) = prev_sig {
                    out.push_str(canonical_gap(prev, kind, had_ws));
                }
                out.push_str(tok.text());
                prev_sig = Some(kind);
                at_line_start = false;
                had_ws = false;
            }
        }
    }
    out
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
    fn respaces_field_colon_and_operators() {
        // FE-9: the normalizer actually canonicalizes spacing, it does
        // not merely reprint. Tight colon + missing operator spaces are
        // fixed; leading indentation and newlines are preserved.
        let file = Utf8PathBuf::from("t.hem");
        let messy = "part wall:\n    thickness:4mm\n    span: 2mm+3mm\n";
        let want = "part wall:\n    thickness: 4mm\n    span: 2mm + 3mm\n";
        assert_eq!(format(messy, &file), want);
    }

    #[test]
    fn respaces_interval_and_range_and_call() {
        // Commas take one trailing space; `..` is spaced; `f(x)` and
        // member access stay tight; a `QuantityLit` never splits.
        let file = Utf8PathBuf::from("t.hem");
        let messy = "part p:\n    a: [1mm,2mm]\n    b: [0..3]\n    c: peak( x.y , z )\n";
        let want = "part p:\n    a: [1mm, 2mm]\n    b: [0 .. 3]\n    c: peak(x.y, z)\n";
        assert_eq!(format(messy, &file), want);
    }

    #[test]
    fn canonical_form_is_a_fixed_point() {
        // The canonical output is itself already canonical (idempotence
        // on the normalized form, not just on identity).
        let file = Utf8PathBuf::from("t.hem");
        let messy = "part p:\n    a:[1mm,2mm]\n    v: x==y\n";
        let once = format(messy, &file);
        assert_eq!(
            format(&once, &file),
            once,
            "canonical output must be stable"
        );
    }

    #[test]
    fn pathological_input_is_stable_and_never_panics() {
        // The parser is error-resilient, so even non-statement input
        // formats without panicking and reaches a fixed point.
        let file = Utf8PathBuf::from("t.hem");
        let src = ")))###\n";
        let once = format(src, &file);
        assert_eq!(format(&once, &file), once);
    }

    /// AD-3: `format` is idempotent over every corpus file under
    /// `examples/` (the concrete acceptance corpus, mirrored from
    /// `parser::tests::examples_parse`).
    #[test]
    fn format_is_idempotent_over_examples_corpus() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(std::path::Path::parent)
            .expect("crates/regolith-syntax is two levels under the workspace root")
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
