//! The canonical formatter: the rowan-based normalizer. Because the CST
//! is lossless, `parse -> print -> parse` is a fixed point on accepted
//! input by construction (AD-3; WO-05 acceptance).
//!
//! Substrate reference: `docs/mech/04` (canonical forms). One
//! normalizer; the CLI `fmt` and the golden pipeline both call it.

use camino::Utf8PathBuf;

/// Format `source` into its canonical spelling. On unparseable input the
/// original text is returned unchanged (never destroys source).
#[must_use]
pub fn format(_source: &str, _file: &Utf8PathBuf) -> String {
    todo!("STUB WO-05: parse then pretty-print the CST canonically; idempotent on accepted input")
}

#[cfg(test)]
mod tests {
    // Idempotence over examples/ (parse->print->parse fixed point) is
    // the acceptance test; lands with the formatter body.
    #[test]
    #[ignore = "WO-05 impl: format body + idempotence goldens pending"]
    fn format_is_idempotent() {}
}
