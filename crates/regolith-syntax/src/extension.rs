//! The ONE registry of source-file extensions and their languages.
//!
//! Ground rule 6 / AD-14: extension strings live here and nowhere
//! else; every other layer (including Python, via the FFI) asks this
//! module. Extensions are chosen to not collide with established file
//! formats and follow the first-four-letters-of-the-mineral rule
//! (D108): `.hema` (hematite), `.cupr` (cuprite), `.fluo` (fluorite,
//! cycle 20 / D93; WO-31).

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
}

impl Language {
    /// The canonical file extension (without the dot) for this language.
    #[must_use]
    pub fn extension(self) -> &'static str {
        match self {
            Language::Hematite => "hema",
            Language::Cuprite => "cupr",
            Language::Fluorite => "fluo",
        }
    }
}

/// Every recognized `(extension, language)` pair. The single source of
/// truth iterated by the FFI so Python never hard-codes a string.
pub const EXTENSIONS: &[(&str, Language)] = &[
    ("hema", Language::Hematite),
    ("cupr", Language::Cuprite),
    ("fluo", Language::Fluorite),
];

/// Resolve a bare extension (no leading dot, case-sensitive) to its
/// language, or `None` if it is not a regolith source file.
#[must_use]
pub fn language_for_extension(ext: &str) -> Option<Language> {
    EXTENSIONS
        .iter()
        .find_map(|&(e, lang)| (e == ext).then_some(lang))
}

#[cfg(test)]
mod tests {
    use super::{language_for_extension, Language};

    #[test]
    fn recognizes_settled_extensions() {
        assert_eq!(language_for_extension("hema"), Some(Language::Hematite));
        assert_eq!(language_for_extension("cupr"), Some(Language::Cuprite));
        assert_eq!(language_for_extension("fluo"), Some(Language::Fluorite));
    }

    #[test]
    fn rejects_legacy_and_unknown() {
        assert_eq!(language_for_extension("mill"), None);
        assert_eq!(language_for_extension("loom"), None);
        assert_eq!(language_for_extension("hem"), None);
        assert_eq!(language_for_extension("calc"), None);
        assert_eq!(language_for_extension("txt"), None);
    }
}
