//! Fuzz the parser (AD-3): it must never panic on any input, and the
//! resulting lossless CST must cover every input byte (rowan red/green
//! trees are full-fidelity; the concatenated tree text is byte-identical
//! to the source). Diagnostics are data, never failure (AD-7), so a
//! broken file still yields a usable tree here.
#![no_main]

use camino::Utf8PathBuf;
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(source) = std::str::from_utf8(data) else {
        return;
    };

    let file = Utf8PathBuf::from("fuzz.cupr");
    let parse = regolith_syntax::parser::parse(source, &file);

    // Coverage invariant (AD-3): the CST text is byte-identical to the
    // source -- every input byte lives in exactly one token in the tree.
    let tree_text = parse.syntax().text().to_string();
    assert_eq!(
        tree_text, source,
        "CST does not cover every input byte losslessly"
    );

    // Touching diagnostics must not panic either (they are constructed
    // during the parse and read on the error path).
    let _ = parse.diagnostics().len();
});
