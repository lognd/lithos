//! The ONE registry of source-file extensions and their languages.
//!
//! Ground rule 6 / AD-14: extension strings live here and nowhere
//! else; every other layer (including Python, via the FFI) asks this
//! module. Extensions are chosen to not collide with established file
//! formats and follow the first-four-letters-of-the-mineral rule
//! (D108): `.hema` (hematite), `.cupr` (cuprite), `.fluo` (fluorite,
//! cycle 20 / D93; WO-31), `.calx` (calcite, civil/architectural,
//! cycle 26 / D133; WO-47) -- a deliberate D133 exception to the
//! four-letter rule: calcite's pre-cycle-26 draft used `.calc`, and
//! `.calc` stays permanently dead, so `.calx` avoids the retired
//! string.

/// A source language of the toolchain.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Language {
    /// Mechanical language: `hematite` (iron ore -> steel/structure),
    /// files end in `.hema`.
    Hematite,
    /// Electrical/computer language: `cuprite` (copper ore ->
    /// wire/current), files end in `.cupr`.
    Cuprite,
    /// Fluid-circuit language: `fluorite` (the calcium-fluoride ore ->
    /// flow networks), files end in `.fluo` (cycle 20 / D93; WO-31).
    Fluorite,
    /// Civil/architectural language: `calcite` (the carbonate mineral
    /// -> concrete/masonry/site work), files end in `.calx` (cycle 26
    /// / D133; WO-47).
    Calcite,
}

impl Language {
    /// The canonical file extension (without the dot) for this language.
    #[must_use]
    pub fn extension(self) -> &'static str {
        match self {
            Language::Hematite => "hema",
            Language::Cuprite => "cupr",
            Language::Fluorite => "fluo",
            Language::Calcite => "calx",
        }
    }
}

/// Every recognized `(extension, language)` pair. The single source of
/// truth iterated by the FFI so Python never hard-codes a string. If
/// you add a language track, also update the non-registry references:
/// `regolith-syntax/benches/parse.rs` and `regolith-ls/src/server.rs`
/// tests.
pub const EXTENSIONS: &[(&str, Language)] = &[
    ("hema", Language::Hematite),
    ("cupr", Language::Cuprite),
    ("fluo", Language::Fluorite),
    ("calx", Language::Calcite),
];

/// Resolve a bare extension (no leading dot, case-sensitive) to its
/// language, or `None` if it is not a regolith source file.
#[must_use]
pub fn language_for_extension(ext: &str) -> Option<Language> {
    EXTENSIONS
        .iter()
        .find_map(|&(e, lang)| (e == ext).then_some(lang))
}

/// The design-test file infix (WO-83; charter toolchain/37, D190): a
/// test file discovers by convention as `<name>.test.<track-ext>`,
/// sibling to the source it exercises, with NO manifest change. The
/// tripwire this constant exists to satisfy: the `.test.` infix is
/// spelled ONCE, here, beside the extension registry it composes with
/// -- nothing else (including tests) may hard-code the string `"test"`
/// for this purpose.
pub const TEST_FILE_INFIX: &str = "test";

/// Whether `file_name` (a bare file name, not a full path -- callers
/// strip any directory component first) is a design-test source file
/// under the `<name>.test.<ext>` convention, and if so, which track it
/// belongs to (the same [`Language`] its `<ext>` names via
/// [`language_for_extension`]).
///
/// A design-test file is an ordinary source file of its track PLUS the
/// `.test` infix immediately before the extension -- `spar.test.hema`
/// is a hematite test file for `spar.hema`; `spar.hema` itself is not.
/// `None` for any name that is not `<stem>.test.<recognized-ext>`
/// (including a bare `test.hema`, which has no `<stem>` before the
/// infix and is therefore an ordinary hematite source file named
/// `test`, not a test file -- the infix marks a SUFFIX on a name, not
/// the whole stem).
#[must_use]
pub fn test_file_language(file_name: &str) -> Option<Language> {
    let (base, ext) = file_name.rsplit_once('.')?;
    let lang = language_for_extension(ext)?;
    let stem = base.strip_suffix(&format!(".{TEST_FILE_INFIX}"))?;
    (!stem.is_empty()).then_some(lang)
}

#[cfg(test)]
mod tests {
    use super::{language_for_extension, test_file_language, Language};

    #[test]
    fn recognizes_settled_extensions() {
        assert_eq!(language_for_extension("hema"), Some(Language::Hematite));
        assert_eq!(language_for_extension("cupr"), Some(Language::Cuprite));
        assert_eq!(language_for_extension("fluo"), Some(Language::Fluorite));
        assert_eq!(language_for_extension("calx"), Some(Language::Calcite));
    }

    #[test]
    fn rejects_legacy_and_unknown() {
        assert_eq!(language_for_extension("mill"), None);
        assert_eq!(language_for_extension("loom"), None);
        assert_eq!(language_for_extension("hem"), None);
        assert_eq!(language_for_extension("calc"), None);
        assert_eq!(language_for_extension("txt"), None);
    }

    #[test]
    fn recognizes_test_files_per_track() {
        assert_eq!(
            test_file_language("spar.test.hema"),
            Some(Language::Hematite)
        );
        assert_eq!(
            test_file_language("mainboard.test.cupr"),
            Some(Language::Cuprite)
        );
        assert_eq!(
            test_file_language("hydraulics.test.fluo"),
            Some(Language::Fluorite)
        );
        assert_eq!(
            test_file_language("pavilion.test.calx"),
            Some(Language::Calcite)
        );
    }

    #[test]
    fn rejects_non_test_and_malformed_names() {
        // Ordinary source file, no `.test` infix.
        assert_eq!(test_file_language("spar.hema"), None);
        // The infix alone, with no name stem before it.
        assert_eq!(test_file_language("test.hema"), None);
        // Unrecognized extension.
        assert_eq!(test_file_language("spar.test.txt"), None);
        // No extension at all.
        assert_eq!(test_file_language("spar.test"), None);
    }
}
