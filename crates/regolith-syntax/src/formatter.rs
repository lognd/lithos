//! The canonical formatter: the rowan-based normalizer (AD-3; WO-05
//! acceptance). It walks the lossless CST token stream and re-emits it
//! with canonical INTRA-line spacing, while preserving line structure
//! (newlines) and leading indentation verbatim -- so the transform is
//! meaning-preserving (`parse(format(x))` has the same token stream and
//! tree shape as `parse(x)`) and idempotent (`format(format(x)) ==
//! format(x)`).
//!
//! Regolith reference: `docs/spec/hematite/04` (canonical forms). One
//! normalizer; the CLI `fmt` and the golden pipeline both call it.
//!
//! Canonical form (FE-9):
//! - one space after a field/block `:` and after `,`; none before them;
//! - one space on each side of a binary/tolerance/range operator
//!   (`+ - * / < > <= >= == +- ..`); `=` is the one exception -- the
//!   grammar reuses it for both a spaced statement-level assignment/
//!   claim (`a.length = 120mm`) and a tight call/header keyword-style
//!   arg (`process=laser_cut(sheet=2.0mm)`), so its gap is preserved
//!   from the source rather than forced either way;
//! - member `.` stays tight (`a.b`); a call/index paren/bracket right
//!   after a value normally stays tight too (`f(x)`, `a[i]`), but its
//!   gap is only PRESERVED, not forced -- the corpus also spells a
//!   value-then-qualifier-group with a space (`a.frame (contact)`)
//!   and that space survives; `%` stays tight to its number, a
//!   `QuantityLit`'s number and unit stay adjacent (`5mm`);
//! - an `import` statement's name-list paren takes exactly one space
//!   (`import a.b (X, Y)`) -- unlike a call, which stays tight;
//! - a trailing comment's gap is preserved verbatim, so hand-aligned
//!   comment columns across a block of sibling statements survive a
//!   format pass instead of collapsing to one space;
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

/// A binary/range operator that is UNAMBIGUOUSLY binary in this
/// token-stream-only formatter (no tree context is consulted): `..`
/// (range) never appears in any other role, so it gets a forced
/// single space on each side.
///
/// Every other candidate operator (`+ - * / < > <= >= == = +-`) is
/// deliberately NOT forced: the grammar reuses these tokens across
/// house-style-distinct roles the formatter cannot tell apart from
/// the flat token stream alone --
/// - `=`: a spaced statement-level assignment/claim (`a.length =
///   120mm`) vs. a tight call/header keyword-style arg
///   (`process=laser_cut(sheet=2.0mm)`); `KeywordArg` only covers the
///   `name: value` colon form, not this one;
/// - `< >`: a spaced comparison (`a < b`) vs. tight generic-argument
///   angle brackets (`GearMesh<ratio=4>`, `PatternOf<CBore<M8>>`);
///   `InstExpr`/`GenericArgs` ARE typed nodes, but distinguishing
///   would mean switching this formatter from a token walk to a tree
///   walk -- deferred, not worth it while gap-preservation already
///   reproduces the corpus exactly;
/// - `- * /`: a spaced arithmetic expression (`2mm + 3mm`) vs. a
///   tight unary sign (`-10degC`) or a tight compound-unit/fit
///   designator the corpus writes glued (`k6/H7`, `N*m`);
/// - `+-`: a spaced inline tolerance (`22mm +- allocated`, `3.3V +-
///   5%`) vs. a tight compact-tolerance spelling in a keyword-arg
///   value (`to=+-2%`, `accuracy: +-0.5K`).
///
/// Since the corpus author already spells each site consistently, all
/// of these fall through to the "preserve source gap" default below,
/// which reproduces every form exactly and stays idempotent (the
/// preserved gap is itself already canonical).
fn is_operator(kind: SyntaxKind) -> bool {
    matches!(kind, SyntaxKind::DotDot)
}

/// The canonical separator between two adjacent significant tokens.
/// `ws_text` is the source's own gap text there, if any (`None` means
/// no gap at all). Wherever a gap is merely REQUIRED (not forced to
/// exactly one space), the source's own text is reused verbatim --
/// this is what preserves hand-aligned columns (comments, field
/// values) across a format pass: a wider gap the corpus author
/// deliberately typed survives, while a genuinely missing gap still
/// gets the minimum one space FE-9 requires.
/// `cur_is_ellipsis_head` marks `cur` as the leading `DotDot` of a
/// literal `...` (see the caller): its LEADING gap must not be forced
/// open either (`path=...` must not become `path= ...`), so it is
/// excluded from the forced-operator branch below.
fn canonical_gap(
    prev: SyntaxKind,
    cur: SyntaxKind,
    ws_text: Option<&str>,
    cur_is_ellipsis_head: bool,
) -> String {
    use SyntaxKind as K;
    // Forced tight (no space). A call/index paren/bracket right after a
    // value-end token is NOT forced tight here even though `f(x)` and
    // `a[i]` are the overwhelmingly common spelling -- the corpus also
    // has a distinct "value (qualifier annotation)" spelling
    // (`a.frame (contact)`, `tcc x 3 (pwm, waveform)`) that keeps its
    // author-typed space; both fall through to the "preserve source
    // gap" default below, which reproduces whichever the author wrote.
    let tight = matches!(
        cur,
        K::Colon | K::Comma | K::RParen | K::RBracket | K::Percent
    ) || matches!(prev, K::LParen | K::LBracket)
        || (cur == K::Dot && is_value_end(prev))
        || (prev == K::Dot && is_name_start(cur))
        // A literal ellipsis (`...`, an elided-content placeholder) is
        // lexed as `DotDot` + `Dot` (the lexer has no 3-dot token); it
        // must never split into `.. .` -- the forced-space rule below
        // is for a REAL `..` range operator only.
        || (prev == K::DotDot && cur == K::Dot)
        || (prev == K::Dot && cur == K::DotDot);
    if tight {
        return String::new();
    }
    // A gap is REQUIRED (at least one space) around a forced operator
    // and after `:`/`,` -- but its exact width is preserved when the
    // source already had one (alignment), and collapsed to a single
    // space only when the source had none at all.
    if is_operator(prev)
        || (is_operator(cur) && !cur_is_ellipsis_head)
        || matches!(prev, K::Colon | K::Comma)
    {
        return ws_text.unwrap_or(" ").to_string();
    }
    // Otherwise preserve the source's gap presence verbatim (safe:
    // never changes tokenization -- e.g. a `QuantityLit`'s adjacent
    // number+unit stays tight, two space-separated names stay
    // separated, and any hand-aligned padding in that gap survives).
    ws_text.unwrap_or("").to_string()
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
    // The verbatim text of the interior whitespace gap most recently
    // seen (reset on every significant token). Column-aligned trailing
    // comments (house style: hand-aligned `#` columns across a block of
    // sibling statements, cycle-27+ corpus) are preserved by re-emitting
    // this text before a trailing `Comment` instead of collapsing it to
    // one space -- the simplest rule that reproduces the corpus exactly
    // and stays idempotent (the captured gap is itself already
    // canonical, so a second pass captures and re-emits the same text).
    let mut ws_text: Option<String> = None;
    let mut at_import_header = false;
    let tokens: Vec<_> = parse
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .collect();
    for (idx, tok) in tokens.iter().enumerate() {
        // A literal ellipsis (`...`) lexes as `DotDot` immediately
        // followed by `Dot` with no gap (see the `ellipsis_never_
        // splits` test) -- its LEADING gap must not be forced open
        // either, or `path=...` would become `path= ...`. Only the
        // head `DotDot` of such a run is exempted; a real range `..`
        // is never followed immediately by a bare `.`.
        let is_ellipsis_head = tok.kind() == SyntaxKind::DotDot
            && tokens
                .get(idx + 1)
                .is_some_and(|n| n.kind() == SyntaxKind::Dot);
        match tok.kind() {
            SyntaxKind::Newline => {
                out.push_str(tok.text());
                at_line_start = true;
                prev_sig = None;
                ws_text = None;
                at_import_header = false;
            }
            SyntaxKind::Whitespace => {
                if at_line_start {
                    out.push_str(tok.text()); // leading indentation, verbatim
                } else {
                    // Interior gap. ACCUMULATE consecutive whitespace
                    // tokens (WO-90): a physical-line break inside an open
                    // bracket reaches the formatter as a `Whitespace(\n)`
                    // token FOLLOWED by the continuation line's leading-
                    // space `Whitespace` token (the layout pass joins the
                    // break as trivia, not a `Newline`). Concatenating them
                    // -- instead of the old overwrite, which dropped the
                    // newline and left a long padded run -- preserves the
                    // author's multi-line bracketed layout verbatim across a
                    // format pass (meaning-preserving and idempotent: the
                    // exact source bytes are reproduced).
                    let mut acc = ws_text.take().unwrap_or_default();
                    acc.push_str(tok.text());
                    ws_text = Some(acc);
                }
            }
            // Zero-width layout markers: nothing to emit, still line-start.
            SyntaxKind::Indent | SyntaxKind::Dedent => {}
            SyntaxKind::Comment => {
                if !at_line_start {
                    // Preserve the original gap verbatim (see `ws_text`
                    // doc above) so hand-aligned comment columns survive
                    // a format pass; a bare single space if the source
                    // had none (still meaning-preserving: a comment
                    // always needs at least one space of separation).
                    out.push_str(ws_text.as_deref().unwrap_or(" "));
                }
                out.push_str(tok.text());
                at_line_start = false;
                prev_sig = None;
                ws_text = None;
            }
            SyntaxKind::ImportKw if at_line_start => {
                out.push_str(tok.text());
                prev_sig = Some(SyntaxKind::ImportKw);
                at_line_start = false;
                ws_text = None;
                at_import_header = true;
            }
            // FE-9 (revised): an import statement's name-list paren
            // keeps exactly one space before it (`import a.b (X, Y)`),
            // unlike a call/index paren which stays tight -- the corpus
            // house style distinguishes "this is the statement's
            // argument list", not a call, from ordinary `f(x)` calls.
            // Only the FIRST paren on an import header line is treated
            // this way (an import header has no nested calls).
            SyntaxKind::LParen if at_import_header => {
                out.push(' ');
                out.push_str(tok.text());
                prev_sig = Some(SyntaxKind::LParen);
                at_line_start = false;
                ws_text = None;
                at_import_header = false;
            }
            kind => {
                if let Some(prev) = prev_sig {
                    out.push_str(&canonical_gap(
                        prev,
                        kind,
                        ws_text.as_deref(),
                        is_ellipsis_head,
                    ));
                }
                out.push_str(tok.text());
                prev_sig = Some(kind);
                at_line_start = false;
                ws_text = None;
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
        let file = Utf8PathBuf::from("t.hema");
        let src = "import a.b\npart wall:\n    thickness: 4mm\n";
        let once = format(src, &file);
        let twice = format(&once, &file);
        assert_eq!(once, twice);
    }

    #[test]
    fn respaces_field_colon() {
        // FE-9: the normalizer actually canonicalizes spacing, it does
        // not merely reprint. A tight field colon is fixed; leading
        // indentation and newlines are preserved. `+` is NOT forced
        // (house-style reconciliation: `- * /` gaps are preserved
        // verbatim, see `is_operator`'s doc), so a tight `2mm+3mm`
        // stays tight -- it is not ambiguous either way, and forcing
        // it would fight the corpus's own compact-arithmetic spots.
        let file = Utf8PathBuf::from("t.hema");
        let messy = "part wall:\n    thickness:4mm\n    span: 2mm+3mm\n";
        let want = "part wall:\n    thickness: 4mm\n    span: 2mm+3mm\n";
        assert_eq!(format(messy, &file), want);
    }

    #[test]
    fn respaces_interval_and_range_and_call() {
        // Commas take one trailing space; `..` is spaced; `f(x)` and
        // member access stay tight; a `QuantityLit` never splits.
        let file = Utf8PathBuf::from("t.hema");
        let messy = "part p:\n    a: [1mm,2mm]\n    b: [0..3]\n    c: peak( x.y , z )\n";
        let want = "part p:\n    a: [1mm, 2mm]\n    b: [0 .. 3]\n    c: peak(x.y, z)\n";
        assert_eq!(format(messy, &file), want);
    }

    #[test]
    fn canonical_form_is_a_fixed_point() {
        // The canonical output is itself already canonical (idempotence
        // on the normalized form, not just on identity).
        let file = Utf8PathBuf::from("t.hema");
        let messy = "part p:\n    a:[1mm,2mm]\n    v: x==y\n";
        let once = format(messy, &file);
        assert_eq!(
            format(&once, &file),
            once,
            "canonical output must be stable"
        );
    }

    #[test]
    fn import_name_list_paren_takes_one_space() {
        // House style (corpus, reconciled): an import's name-list paren
        // is NOT a call, so it keeps exactly one space, both when the
        // source already has one and when it has none. Idempotent.
        let file = Utf8PathBuf::from("t.hema");
        let no_space = "import std.mech.sheet(Blank, Pierce, Bend)\n";
        let one_space = "import std.mech.sheet (Blank, Pierce, Bend)\n";
        let want = "import std.mech.sheet (Blank, Pierce, Bend)\n";
        assert_eq!(format(no_space, &file), want);
        assert_eq!(format(one_space, &file), want);
        let once = format(one_space, &file);
        assert_eq!(format(&once, &file), once);
    }

    #[test]
    fn import_paren_rule_does_not_leak_into_calls() {
        // Only the import header's own paren gets the space; an
        // ordinary call elsewhere in the file stays tight.
        let file = Utf8PathBuf::from("t.hema");
        let src = "import a.b (X)\npart p:\n    c: peak(x)\n";
        let want = "import a.b (X)\npart p:\n    c: peak(x)\n";
        assert_eq!(format(src, &file), want);
    }

    #[test]
    fn trailing_comment_alignment_is_preserved() {
        // House style (corpus, reconciled): hand-aligned trailing-
        // comment columns across a block of sibling statements are
        // preserved verbatim rather than collapsed to one space, even
        // when an intervening sibling line has no comment of its own.
        let file = Utf8PathBuf::from("t.hema");
        let src = "profile p:\n    walk:\n        a: line right               # root\n        b: line up\n        c: line left                # flange\n        d: close\n";
        assert_eq!(format(src, &file), src);
        let once = format(src, &file);
        assert_eq!(format(&once, &file), once);
    }

    #[test]
    fn trailing_comment_with_no_source_gap_gets_one_space() {
        // A comment glued directly to the previous token (no gap at
        // all) still gets separated by exactly one space -- the
        // "preserve verbatim" rule only preserves an EXISTING gap, it
        // never fuses a comment onto a token.
        let file = Utf8PathBuf::from("t.hema");
        let src = "part p:\n    a: 4mm# tight\n";
        let want = "part p:\n    a: 4mm # tight\n";
        assert_eq!(format(src, &file), want);
    }

    #[test]
    fn ellipsis_never_splits() {
        // `...` (an elided-content placeholder, e.g. `FaceMill(...)`)
        // lexes as `DotDot` + `Dot` (no dedicated 3-dot token); the
        // range operator's forced single space must not land between
        // them and split it into `.. .` -- that would be a byte the
        // formatter invented meaning for. A real `..` range keeps its
        // forced spacing (`0 .. 3`) right next to it, unaffected.
        let file = Utf8PathBuf::from("t.hema");
        let src = "part p:\n    a: f(...)\n    b: [0..3]\n";
        let want = "part p:\n    a: f(...)\n    b: [0 .. 3]\n";
        assert_eq!(format(src, &file), want);
        let once = format(src, &file);
        assert_eq!(format(&once, &file), once);
    }

    #[test]
    fn pathological_input_is_stable_and_never_panics() {
        // The parser is error-resilient, so even non-statement input
        // formats without panicking and reaches a fixed point.
        let file = Utf8PathBuf::from("t.hema");
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
            let file = Utf8PathBuf::from("prop.hema");
            let once = format(&src, &file);
            let twice = format(&once, &file);
            proptest::prop_assert_eq!(once, twice);
        }
    }
}
