//! Fuzz the lexer (AD-3): it must never panic on any input, and its
//! token spans must cover every source byte contiguously (the raw
//! token stream is full-fidelity, retaining trivia and Error tokens).
#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // The lexer operates on `&str`; non-UTF-8 input is rejected upstream
    // (ASCII source is a spec guarantee) so only feed valid UTF-8.
    let Ok(source) = std::str::from_utf8(data) else {
        return;
    };

    let tokens = regolith_syntax::token::lex(source);

    // Coverage invariant (AD-3): the spans partition [0, len) exactly --
    // contiguous, non-overlapping, and reaching the end. This is the
    // lexer-level half of "the CST covers every input byte".
    let mut cursor = 0usize;
    for (_kind, span) in &tokens {
        assert_eq!(span.start, cursor, "gap or overlap in lexer spans");
        assert!(span.end >= span.start, "reversed lexer span");
        cursor = span.end;
    }
    assert_eq!(cursor, source.len(), "lexer spans do not cover all bytes");
});
