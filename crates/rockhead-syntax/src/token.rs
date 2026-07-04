//! The raw lexical tokens, defined as a `logos` DFA (AD-3). This is the
//! lexer *specification*: the patterns here define the terminal set.
//!
//! Substrate reference: `docs/substrate/08` (L0), `docs/mech/02`,
//! `docs/elec/07`. The lexer emits full-fidelity tokens including
//! whitespace and comments (rowan needs every byte); the layout pass
//! ([`crate::layout`]) turns leading whitespace into INDENT/DEDENT/
//! NEWLINE. Tabs in indentation are an E01xx error (spec: ASCII source,
//! spaces only). Keyword set grows with the grammar (WO-05).

use logos::Logos;

/// A raw token as produced directly by the lexer, before the layout
/// pass. Trivia (whitespace, comments) is retained for CST fidelity.
#[derive(Logos, Debug, Clone, Copy, PartialEq, Eq)]
pub enum RawToken {
    // -- trivia (kept for the lossless CST) --
    /// Runs of spaces and horizontal formatting (not newlines). Leading
    /// runs are consumed by the layout pass.
    #[regex(r"[ ]+")]
    Whitespace,
    /// A line comment `# ...` to end of line.
    #[regex(r"#[^\n]*")]
    Comment,
    /// One line terminator; significant to the layout pass.
    #[token("\n")]
    Newline,
    /// A tab character: illegal in rockhead source (E01xx at layout).
    #[token("\t")]
    Tab,

    // -- literals --
    /// An identifier or (context-resolved) keyword.
    #[regex(r"[A-Za-z_][A-Za-z0-9_]*")]
    Ident,
    /// A numeric literal (integer or decimal; unit suffix lexes as a
    /// following Ident and is bound in the parser).
    #[regex(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")]
    Number,
    /// A double-quoted string literal.
    #[regex(r#""([^"\\]|\\.)*""#)]
    String,

    // -- punctuation and operators --
    /// `:` field separator / block header.
    #[token(":")]
    Colon,
    /// `=` construction / discrete equality (never continuous equality).
    #[token("=")]
    Eq,
    /// `,` separator (and the interval bracket separator).
    #[token(",")]
    Comma,
    /// `..` half-open positional range separator.
    #[token("..")]
    DotDot,
    /// `.` member / path separator.
    #[token(".")]
    Dot,
    /// `(`.
    #[token("(")]
    LParen,
    /// `)`.
    #[token(")")]
    RParen,
    /// `[`.
    #[token("[")]
    LBracket,
    /// `]`.
    #[token("]")]
    RBracket,
    /// `+-` symmetric tolerance.
    #[token("+-")]
    PlusMinus,
    /// `%` percent (tolerance).
    #[token("%")]
    Percent,
    /// `<=` at-most comparator literal.
    #[token("<=")]
    LtEq,
    /// `>=` at-least comparator literal.
    #[token(">=")]
    GtEq,
    /// `<` strict less-than (claims).
    #[token("<")]
    Lt,
    /// `>` strict greater-than (claims).
    #[token(">")]
    Gt,
    /// `+` addition.
    #[token("+")]
    Plus,
    /// `-` subtraction / negation.
    #[token("-")]
    Minus,
    /// `*` multiplication (and `[k1,k2] * x` interval scaling).
    #[token("*")]
    Star,
    /// `/` division (and unit expressions `N/m`).
    #[token("/")]
    Slash,

    /// Any byte the lexer could not classify (error recovery anchor).
    Error,
}

/// Lex `source` into raw tokens with their byte spans, retaining trivia.
///
/// Never fails: unclassified bytes become [`RawToken::Error`] tokens so
/// the CST still covers every byte (the fuzz invariant, AD-3).
#[must_use]
pub fn lex(_source: &str) -> Vec<(RawToken, std::ops::Range<usize>)> {
    todo!("STUB WO-05: drive logos over source, mapping lex errors to RawToken::Error spans")
}

#[cfg(test)]
mod tests {
    use super::RawToken;
    use logos::Logos;

    #[test]
    fn lexes_core_punctuation_and_literals() {
        // Exercises the DFA directly (the `lex` wrapper is a STUB).
        let mut lx = RawToken::lexer("wall = 4mm +- 5%");
        assert_eq!(lx.next(), Some(Ok(RawToken::Ident)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Whitespace)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Eq)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Whitespace)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Number)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Ident))); // mm
    }

    #[test]
    fn distinguishes_dotdot_from_dot() {
        let mut lx = RawToken::lexer("a..b.c");
        assert_eq!(lx.next(), Some(Ok(RawToken::Ident)));
        assert_eq!(lx.next(), Some(Ok(RawToken::DotDot)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Ident)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Dot)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Ident)));
    }

    #[test]
    fn lexes_comparators_and_tolerance() {
        let mut lx = RawToken::lexer("<= >= +-");
        assert_eq!(lx.next(), Some(Ok(RawToken::LtEq)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Whitespace)));
        assert_eq!(lx.next(), Some(Ok(RawToken::GtEq)));
        assert_eq!(lx.next(), Some(Ok(RawToken::Whitespace)));
        assert_eq!(lx.next(), Some(Ok(RawToken::PlusMinus)));
    }
}
