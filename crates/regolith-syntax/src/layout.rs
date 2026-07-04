//! The layout pass: converts leading-whitespace structure into
//! INDENT/DEDENT/NEWLINE tokens so the parser stays context-free
//! (AD-3, Python-style off-side rule).
//!
//! Substrate reference: `docs/substrate/08`. Indentation is spaces
//! only; a tab in indentation is an E01xx diagnostic (WO-06). Blank
//! lines and comment-only lines do not emit layout tokens.

use camino::Utf8PathBuf;
use regolith_diag::{DiagCode, Diagnostic, Family, LabeledSpan, Span};

use crate::syntax_kind::SyntaxKind;
use crate::token::RawToken;

/// `E01xx`: a tab character was used for indentation (spaces only).
const TAB_INDENTATION: DiagCode = DiagCode::new(Family::Parse, 90);
/// `E01xx`: a dedent landed on a column that does not match any
/// enclosing indent level; recovery resyncs to the new column.
const MISMATCHED_DEDENT: DiagCode = DiagCode::new(Family::Parse, 91);
/// `E0194`: a non-ASCII byte appears in source. regolith source is
/// ASCII-only (AD-3/AD-12; CLAUDE.md tripwire); this is enforced at the
/// lexical boundary, batch-emitted like the tab check. Kept a local
/// structural code alongside its siblings (`TAB_INDENTATION` and the
/// parser's `UNEXPECTED_TOKEN`/`MALFORMED_IN_BODY`), not a semantic
/// registry entry, since it is a raw-source lexical rejection.
const NON_ASCII_SOURCE: DiagCode = DiagCode::new(Family::Parse, 94);

/// Placeholder file used when constructing layout diagnostics: the
/// layout pass has no file identity of its own (it is a pure token
/// transform); the parser, which does know the file, rewrites this
/// before returning `Parse` to the caller.
fn placeholder_file() -> Utf8PathBuf {
    Utf8PathBuf::from("")
}

/// A token after the layout pass: a `SyntaxKind` (raw kinds plus the
/// synthesized Indent/Dedent/Newline) with its source span.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutToken {
    /// The post-layout kind.
    pub kind: SyntaxKind,
    /// Byte span in the original source (synthesized tokens are
    /// zero-width at the relevant offset).
    pub span: std::ops::Range<usize>,
}

/// Mutable state threaded through the off-side-rule scan; a struct so
/// `apply_layout` itself stays a short driver loop (clippy pedantic
/// `too_many_lines`).
struct Layout<'a> {
    raw: &'a [(RawToken, std::ops::Range<usize>)],
    source: &'a str,
    out: Vec<LayoutToken>,
    diags: Vec<Diagnostic>,
    stack: Vec<usize>,
    pos: usize,
}

/// Run the layout pass over raw tokens, emitting INDENT/DEDENT/NEWLINE
/// and mapping keyword idents. Tab-indentation errors are returned as
/// diagnostics alongside a best-effort token stream (batch discipline).
#[must_use]
pub fn apply_layout(
    raw: &[(RawToken, std::ops::Range<usize>)],
    source: &str,
) -> (Vec<LayoutToken>, Vec<Diagnostic>) {
    let mut l = Layout {
        raw,
        source,
        out: Vec::new(),
        diags: Vec::new(),
        stack: vec![0],
        pos: 0,
    };
    l.reject_non_ascii();
    while l.pos < l.raw.len() {
        let col = l.scan_leading_whitespace();
        if l.pos >= l.raw.len() {
            break;
        }
        if l.consume_blank_or_comment_only_line() {
            continue;
        }
        l.reconcile_indent(col);
        l.emit_rest_of_line();
    }
    l.close_remaining_indents();
    (l.out, l.diags)
}

impl Layout<'_> {
    fn push(&mut self, kind: SyntaxKind, span: std::ops::Range<usize>) {
        self.out.push(LayoutToken { kind, span });
    }

    /// Emit one `E0194` diagnostic per non-ASCII character in source.
    /// regolith source is ASCII-only (AD-3/AD-12); a non-ASCII byte is
    /// otherwise swept into an `Error` token / opaque island with no
    /// error, so it is rejected here at the lexical boundary. Runs once,
    /// up front, so the check is batch-emitted like the tab check (a
    /// whole file's violations surface in one pass).
    fn reject_non_ascii(&mut self) {
        for (offset, ch) in self.source.char_indices() {
            if !ch.is_ascii() {
                let span = offset..offset + ch.len_utf8();
                self.diags.push(
                    Diagnostic::error(
                        NON_ASCII_SOURCE,
                        "non-ASCII character in source; regolith source is ASCII-only",
                    )
                    .with_span(LabeledSpan::new(
                        Span::new(placeholder_file(), span.start, span.end),
                        "non-ASCII character here",
                    )),
                );
            }
        }
    }

    fn tab_diagnostic(&mut self, span: std::ops::Range<usize>) {
        self.diags.push(
            Diagnostic::error(
                TAB_INDENTATION,
                "tab character in source; regolith source is space-indented",
            )
            .with_span(LabeledSpan::new(
                Span::new(placeholder_file(), span.start, span.end),
                "tab here",
            )),
        );
    }

    /// Consume leading `Whitespace`/`Tab` at the current position,
    /// returning the indentation column reached (space count).
    fn scan_leading_whitespace(&mut self) -> usize {
        let mut col = 0usize;
        let mut saw_tab = false;
        while let Some((tok, span)) = self.raw.get(self.pos) {
            match tok {
                RawToken::Whitespace => {
                    col += span.len();
                    self.push(SyntaxKind::Whitespace, span.clone());
                    self.pos += 1;
                }
                RawToken::Tab => {
                    if !saw_tab {
                        saw_tab = true;
                        self.tab_diagnostic(span.clone());
                    }
                    self.push(SyntaxKind::Error, span.clone());
                    self.pos += 1;
                }
                _ => break,
            }
        }
        col
    }

    /// If the current line is blank or comment-only, pass it through
    /// (no indent-stack change) and report `true`.
    fn consume_blank_or_comment_only_line(&mut self) -> bool {
        match self.raw[self.pos].0 {
            RawToken::Newline => {
                let span = self.raw[self.pos].1.clone();
                self.push(SyntaxKind::Newline, span);
                self.pos += 1;
                true
            }
            RawToken::Comment => {
                let span = self.raw[self.pos].1.clone();
                self.push(SyntaxKind::Comment, span);
                self.pos += 1;
                if let Some((RawToken::Newline, nl)) = self.raw.get(self.pos).cloned() {
                    self.push(SyntaxKind::Newline, nl);
                    self.pos += 1;
                }
                true
            }
            _ => false,
        }
    }

    /// Reconcile `col` (this line's indentation) against the indent
    /// stack, emitting `Indent`/`Dedent` tokens and, on a mismatched
    /// dedent, a diagnostic (recovery resyncs rather than panicking).
    fn reconcile_indent(&mut self, col: usize) {
        let at = self.raw[self.pos].1.start;
        let top = self.stack.last().copied().unwrap_or(0);
        if col > top {
            self.stack.push(col);
            self.push(SyntaxKind::Indent, at..at);
            return;
        }
        while self.stack.len() > 1 && col < self.stack.last().copied().unwrap_or(0) {
            self.stack.pop();
            self.push(SyntaxKind::Dedent, at..at);
        }
        if self.stack.last().copied().unwrap_or(0) != col {
            let span = self.raw[self.pos].1.clone();
            self.diags.push(
                Diagnostic::error(
                    MISMATCHED_DEDENT,
                    "dedent does not match any enclosing indentation level",
                )
                .with_span(LabeledSpan::new(
                    Span::new(placeholder_file(), span.start, span.end),
                    "indentation resets here",
                )),
            );
            self.stack.push(col);
        }
    }

    /// Emit the rest of this LOGICAL line's tokens (mapping idents to
    /// keywords) through and including its terminating `Newline`.
    ///
    /// Bracket-aware, Python-style implicit line joining: while inside
    /// an open `(`/`[` (tracked by `depth`), a physical-line `Newline`
    /// is emitted as ordinary trivia and the following physical line's
    /// leading whitespace/comments pass through WITHOUT an
    /// indent/dedent reconcile -- the logical line continues. Only a
    /// `Newline` at bracket depth zero terminates the logical line.
    /// This lets a multi-line call/interval/import argument list (as in
    /// the mech corpus) span physical lines without the deeper
    /// continuation indent desyncing the off-side rule (substrate/08:
    /// bracketed continuations are one logical line).
    fn emit_rest_of_line(&mut self) {
        let mut depth: i32 = 0;
        while let Some((tok, span)) = self.raw.get(self.pos).cloned() {
            match tok {
                RawToken::Newline => {
                    self.push(SyntaxKind::Newline, span);
                    self.pos += 1;
                    if depth <= 0 {
                        break;
                    }
                }
                RawToken::Tab => {
                    self.tab_diagnostic(span.clone());
                    self.push(SyntaxKind::Error, span);
                    self.pos += 1;
                }
                RawToken::LParen | RawToken::LBracket => {
                    depth += 1;
                    self.push(map_raw_kind(tok), span);
                    self.pos += 1;
                }
                RawToken::RParen | RawToken::RBracket => {
                    depth -= 1;
                    self.push(map_raw_kind(tok), span);
                    self.pos += 1;
                }
                RawToken::Ident => {
                    let text = &self.source[span.clone()];
                    let kind = crate::syntax_kind::keyword_kind(text).unwrap_or(SyntaxKind::Ident);
                    self.push(kind, span);
                    self.pos += 1;
                }
                other => {
                    self.push(map_raw_kind(other), span);
                    self.pos += 1;
                }
            }
        }
    }

    /// EOF: close every indentation level still open.
    fn close_remaining_indents(&mut self) {
        let eof = self.source.len();
        while self.stack.len() > 1 {
            self.stack.pop();
            self.push(SyntaxKind::Dedent, eof..eof);
        }
    }
}

/// Map a raw (non-Ident, non-layout) token kind to its `SyntaxKind`.
/// The variant names are identical by construction (AD-3 token set).
fn map_raw_kind(raw: RawToken) -> SyntaxKind {
    match raw {
        RawToken::Whitespace => SyntaxKind::Whitespace,
        RawToken::Comment => SyntaxKind::Comment,
        RawToken::Newline => SyntaxKind::Newline,
        RawToken::Tab | RawToken::Error => SyntaxKind::Error,
        RawToken::Ident => SyntaxKind::Ident,
        RawToken::Number => SyntaxKind::Number,
        RawToken::String => SyntaxKind::String,
        RawToken::Colon => SyntaxKind::Colon,
        RawToken::Eq => SyntaxKind::Eq,
        RawToken::EqEq => SyntaxKind::EqEqTok,
        RawToken::Comma => SyntaxKind::Comma,
        RawToken::DotDot => SyntaxKind::DotDot,
        RawToken::Dot => SyntaxKind::Dot,
        RawToken::LParen => SyntaxKind::LParen,
        RawToken::RParen => SyntaxKind::RParen,
        RawToken::LBracket => SyntaxKind::LBracket,
        RawToken::RBracket => SyntaxKind::RBracket,
        RawToken::PlusMinus => SyntaxKind::PlusMinus,
        RawToken::Percent => SyntaxKind::Percent,
        RawToken::LtEq => SyntaxKind::LtEq,
        RawToken::GtEq => SyntaxKind::GtEq,
        RawToken::Lt => SyntaxKind::Lt,
        RawToken::Gt => SyntaxKind::Gt,
        RawToken::Plus => SyntaxKind::Plus,
        RawToken::Minus => SyntaxKind::Minus,
        RawToken::Star => SyntaxKind::Star,
        RawToken::Slash => SyntaxKind::Slash,
    }
}

#[cfg(test)]
mod tests {
    use super::apply_layout;
    use crate::syntax_kind::SyntaxKind;
    use crate::token::lex;

    fn kinds(source: &str) -> Vec<SyntaxKind> {
        let raw = lex(source);
        let (toks, diags) = apply_layout(&raw, source);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
        toks.into_iter().map(|t| t.kind).collect()
    }

    #[test]
    fn indent_then_dedent() {
        let ks = kinds("part a:\n    field: 1\nnext\n");
        assert_eq!(
            ks,
            vec![
                SyntaxKind::PartKw,
                SyntaxKind::Whitespace,
                SyntaxKind::Ident,
                SyntaxKind::Colon,
                SyntaxKind::Newline,
                SyntaxKind::Whitespace,
                SyntaxKind::Indent,
                SyntaxKind::Ident,
                SyntaxKind::Colon,
                SyntaxKind::Whitespace,
                SyntaxKind::Number,
                SyntaxKind::Newline,
                SyntaxKind::Dedent,
                SyntaxKind::Ident,
                SyntaxKind::Newline,
            ]
        );
    }

    #[test]
    fn blank_and_comment_only_lines_do_not_shift_indent() {
        let ks = kinds("part a:\n\n    # a comment\n    x: 1\n");
        assert!(ks.contains(&SyntaxKind::Indent));
        assert_eq!(ks.iter().filter(|k| **k == SyntaxKind::Indent).count(), 1);
    }

    #[test]
    fn tab_indentation_is_an_error() {
        let raw = lex("part a:\n\tx: 1\n");
        let (_toks, diags) = apply_layout(&raw, "part a:\n\tx: 1\n");
        assert!(!diags.is_empty());
    }

    #[test]
    fn non_ascii_byte_is_rejected() {
        // FE-3: a non-ASCII character (here a micro sign, written as an
        // ASCII escape so this file stays ASCII-only) in a value position
        // is otherwise swept into an opaque island with no error. It must
        // surface an E0194 non-ASCII diagnostic at the lexical boundary.
        let src = "part p:\n    dia: 5\u{00b5}m\n";
        let raw = lex(src);
        let (_toks, diags) = apply_layout(&raw, src);
        assert!(
            diags.iter().any(|d| d.code.to_string() == "E0194"),
            "expected a non-ASCII diagnostic: {diags:?}"
        );
    }

    #[test]
    fn pure_ascii_source_has_no_non_ascii_diagnostic() {
        let src = "part p:\n    dia: 5mm\n";
        let raw = lex(src);
        let (_toks, diags) = apply_layout(&raw, src);
        assert!(
            diags.is_empty(),
            "clean ASCII source must not diagnose: {diags:?}"
        );
    }

    #[test]
    fn eof_closes_every_open_indent() {
        let raw = lex("part a:\n    x: 1\n");
        let (toks, _) = apply_layout(&raw, "part a:\n    x: 1\n");
        assert_eq!(toks.last().unwrap().kind, SyntaxKind::Dedent);
    }
}
