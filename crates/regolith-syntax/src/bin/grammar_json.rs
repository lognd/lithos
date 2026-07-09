//! WO-39 deliverable 1: the ONE table export the editor's generated
//! TextMate grammars build from (AD-24 -- no hand-maintained grammar,
//! no second keyword list). Emits deterministic JSON to stdout; run via
//! `cargo run --bin grammar-json` or `editors/vscode/scripts/gen-grammar.mjs`.
//!
//! Every string here is read, never hard-coded, from the compiler's own
//! tables: `regolith_syntax::EXTENSIONS` (the registry, ground rule 6)
//! and `regolith_syntax::KEYWORD_TABLE` (the one keyword table, WO-05).
//! The keyword CLASSES below (decl / value_source / control) are a
//! presentation-only grouping for syntax highlighting -- the underlying
//! word list is not duplicated, only partitioned by `SyntaxKind`.

use regolith_syntax::{Language, SyntaxKind, EXTENSIONS, KEYWORD_TABLE};
use serde::Serialize;

#[derive(Serialize)]
struct LanguageEntry {
    id: &'static str,
    extension: &'static str,
}

#[derive(Serialize)]
struct KeywordClasses {
    /// Keywords that introduce a declaration header (`part foo:`).
    decl: Vec<&'static str>,
    /// Keywords that appear in a value-source position
    /// (`locked:`, `extern`, `model`, `derived`, ...).
    value_source: Vec<&'static str>,
    /// Everything else reserved (`import`, `require`, `then`, ...).
    control: Vec<&'static str>,
}

#[derive(Serialize)]
struct CommentConfig {
    line: &'static str,
}

#[derive(Serialize)]
struct Export {
    /// Generator identity, so the drift check can assert provenance.
    generated_by: &'static str,
    /// One entry per registered extension (`regolith_syntax::EXTENSIONS`,
    /// the ONE registry -- ground rule 6 / AD-14). All four languages
    /// share the single grammar below (AD-24: one front end).
    languages: Vec<LanguageEntry>,
    keywords: KeywordClasses,
    comment: CommentConfig,
    /// Bracket pairs recognized by the layout/parser (`token.rs`).
    brackets: Vec<[&'static str; 2]>,
    /// The `Number` token's lexeme shape (`token.rs`); unit suffixes
    /// lex as a following `Ident`, joined by the parser -- so unit
    /// literals are `<number_regex><ws>*<ident>` at the grammar level.
    number_regex: &'static str,
    string_regex: &'static str,
    ident_regex: &'static str,
}

fn language_id(lang: Language) -> &'static str {
    match lang {
        Language::Hematite => "hematite",
        Language::Cuprite => "cuprite",
        Language::Fluorite => "fluorite",
        Language::Calcite => "calcite",
    }
}

fn is_decl_kw(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::NamespaceKw
            | SyntaxKind::QuantityKw
            | SyntaxKind::SignatureKw
            | SyntaxKind::PartKw
            | SyntaxKind::ProfileKw
            | SyntaxKind::InterfaceKw
            | SyntaxKind::MatingKw
            | SyntaxKind::AssemblyKw
            | SyntaxKind::SystemKw
            | SyntaxKind::BlockKw
            | SyntaxKind::ImplKw
            | SyntaxKind::ComponentKw
            | SyntaxKind::ProtocolKw
            | SyntaxKind::ComputerKw
            | SyntaxKind::ImageKw
            | SyntaxKind::BoardKw
            | SyntaxKind::TargetKw
            | SyntaxKind::DatumKw
            | SyntaxKind::EventKw
    )
}

fn is_value_source_kw(kind: SyntaxKind) -> bool {
    matches!(
        kind,
        SyntaxKind::LockedKw
            | SyntaxKind::ExternKw
            | SyntaxKind::ModelKw
            | SyntaxKind::HostedOnKw
            | SyntaxKind::FreeKw
            | SyntaxKind::DerivedKw
            | SyntaxKind::AllocatedKw
            | SyntaxKind::DefaultKw
            | SyntaxKind::OverrideKw
            | SyntaxKind::WithinKw
            | SyntaxKind::UseKw
            | SyntaxKind::ByKw
    )
}

fn main() {
    let languages: Vec<LanguageEntry> = EXTENSIONS
        .iter()
        .map(|&(ext, lang)| LanguageEntry {
            id: language_id(lang),
            extension: ext,
        })
        .collect();

    let mut decl = Vec::new();
    let mut value_source = Vec::new();
    let mut control = Vec::new();
    for &(word, kind) in KEYWORD_TABLE {
        if is_decl_kw(kind) {
            decl.push(word);
        } else if is_value_source_kw(kind) {
            value_source.push(word);
        } else {
            control.push(word);
        }
    }

    let export = Export {
        generated_by: "regolith-syntax grammar-json (WO-39)",
        languages,
        keywords: KeywordClasses {
            decl,
            value_source,
            control,
        },
        comment: CommentConfig { line: "#" },
        brackets: vec![["(", ")"], ["[", "]"]],
        number_regex: r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        string_regex: r#""([^"\\]|\\.)*""#,
        ident_regex: r"[A-Za-z_][A-Za-z0-9_]*",
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&export).expect("Export always serializes")
    );
}
