//! Pass: v1 style/advisory lints (WO-40 deliverable 2), Warning severity
//! by default, over `regolith-diag`'s new `Lint` code family. Runs
//! inside the same pipeline every other pass runs in (AD-24: CLI and
//! LSP see identical results by construction) -- no second engine.
//!
//! Regolith reference: `docs/spec/toolchain/24-developer-tooling.md`
//! sec. 5. v1 covers three of the six named lints (`unused_import`,
//! `retired_vocabulary_usage`, `todo_assume_inventory`); the other
//! three (`unused_declaration`, `unreferenced_feature`, `shadowed_name`)
//! need a cross-file usage/scope graph this pass does not have yet --
//! cut and named in the WO-40 close-out, not stubbed to fire wrongly.

use regolith_diag::codes::{RETIRED_VOCABULARY_USAGE, TODO_ASSUME_INVENTORY, UNUSED_IMPORT};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_syntax::ast::{AstNode, File};
use regolith_syntax::{SyntaxKind, SyntaxNode};

use crate::output::ParsedFile;

/// Diagnostics from the v1 lint set.
// frob:doc docs/modules/regolith-lower.md#lints
#[derive(Debug, Clone, Default)]
pub struct LintReport {
    /// Lint-family diagnostics, in file-then-source order.
    pub diagnostics: Vec<Diagnostic>,
}

/// Retired project names (CLAUDE.md, `docs/workflow/README.md` sec. 6,
/// D132): DEAD names a source file should never spell as a bare
/// identifier. `mill` is deliberately EXCLUDED -- it is a live English
/// word for a real machining operation (lathe/mill) in mech content,
/// the documented carve-out; a mechanical lint cannot disambiguate it
/// from the retired language name, so it is left to human review.
const RETIRED_NAMES: &[&str] = &["dcad", "deda", "quarry", "lodestone"];

/// Run the v1 lint set over `files`, returning Warning-severity
/// diagnostics in the `Lint` family (`regolith-diag::apply_lint_config`
/// is the caller's job -- this pass never reads `[lints]` itself).
// frob:doc docs/modules/regolith-lower.md#lints
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
#[must_use]
pub fn run_lints(files: &[ParsedFile]) -> LintReport {
    let span = tracing::info_span!("lower.lints");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        lint_unused_imports(&file, pf, &mut diagnostics);
        lint_retired_vocabulary(pf, &mut diagnostics);
        lint_todo_assume_inventory(pf, &mut diagnostics);
    }
    tracing::info!(diagnostics = diagnostics.len(), "lower.lints: complete");
    LintReport { diagnostics }
}

/// L0801: an `import path (Name, ...)` binding whose bound `Name` never
/// appears as an `Ident` token anywhere else in the file (a dead
/// import). Names inside the import's own parens do not count as a
/// use of themselves.
fn lint_unused_imports(file: &File, pf: &ParsedFile, out: &mut Vec<Diagnostic>) {
    let root = pf.parse.syntax();
    let mut ident_counts: std::collections::BTreeMap<String, usize> =
        std::collections::BTreeMap::new();
    for tok in root
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
    {
        if tok.kind() == SyntaxKind::Ident {
            *ident_counts.entry(tok.text().to_string()).or_default() += 1;
        }
    }

    for import in file.imports() {
        for (range, name) in imported_names(import.syntax()) {
            // Bound exactly once (its own binding site) means it is
            // never referenced again.
            if ident_counts.get(&name).copied().unwrap_or(0) <= 1 {
                let sp = Span::new(pf.path.clone(), range.start().into(), range.end().into());
                out.push(
                    Diagnostic::warning(
                        UNUSED_IMPORT,
                        format!("`{name}` is imported but never referenced in this file"),
                    )
                    .with_span(LabeledSpan::new(sp, "unused import"))
                    .with_fix(regolith_diag::Fix {
                        message: format!("remove `{name}` from this import's name list"),
                        replacement: None,
                    }),
                );
            }
        }
    }
}

/// Every `Ident` token inside an `ImportStmt`'s `(...)` name list, with
/// its text range.
fn imported_names(node: &SyntaxNode) -> Vec<(rowan::TextRange, String)> {
    let mut names = Vec::new();
    let mut in_parens = false;
    for child in node.children_with_tokens() {
        let Some(tok) = child.as_token() else {
            continue;
        };
        match tok.kind() {
            SyntaxKind::LParen => in_parens = true,
            SyntaxKind::RParen => in_parens = false,
            SyntaxKind::Ident if in_parens => {
                names.push((tok.text_range(), tok.text().to_string()));
            }
            _ => {}
        }
    }
    names
}

/// L0802: a retired project name used as a bare `Ident` token (comments
/// are lexed as `Comment` trivia, never `Ident`, so this never fires on
/// natural-language prose -- only on identifiers/keywords in real
/// source positions).
fn lint_retired_vocabulary(pf: &ParsedFile, out: &mut Vec<Diagnostic>) {
    let root = pf.parse.syntax();
    for tok in root
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
    {
        if tok.kind() != SyntaxKind::Ident {
            continue;
        }
        let text = tok.text();
        if RETIRED_NAMES.iter().any(|n| n.eq_ignore_ascii_case(text)) {
            let range = tok.text_range();
            let sp = Span::new(pf.path.clone(), range.start().into(), range.end().into());
            out.push(
                Diagnostic::warning(
                    RETIRED_VOCABULARY_USAGE,
                    format!("`{text}` is a retired project name (CLAUDE.md); it names nothing in this toolchain"),
                )
                .with_span(LabeledSpan::new(sp, "retired name")),
            );
        }
    }
}

/// L0803: one advisory per file summarizing its `todo!`/`assume!`
/// occurrences (count + locations) -- the honest-deferral surface, not
/// a nag per line. `!` has no dedicated punctuation token (WO-05's
/// lexer, `token.rs`): it lexes as a `SyntaxKind::Error` byte, so this
/// scans `Ident` tokens spelling `todo`/`assume` immediately followed
/// by such an `Error` token whose text is exactly `"!"`, matching the
/// `impl ... = todo!` / `assume!(expr, basis=...)` source shapes
/// (regolith/07 sec. "todo!/assume!").
fn lint_todo_assume_inventory(pf: &ParsedFile, out: &mut Vec<Diagnostic>) {
    let root = pf.parse.syntax();
    let tokens: Vec<_> = root
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .collect();
    let mut locations = Vec::new();
    for i in 0..tokens.len() {
        let tok = &tokens[i];
        if tok.kind() != SyntaxKind::Ident {
            continue;
        }
        let text = tok.text();
        if text != "todo" && text != "assume" {
            continue;
        }
        let Some(next) = tokens.get(i + 1) else {
            continue;
        };
        if next.kind() != SyntaxKind::Error || next.text() != "!" {
            continue;
        }
        let range = tok.text_range();
        locations.push(format!("{text}! at byte {}", u32::from(range.start())));
    }
    if locations.is_empty() {
        return;
    }
    let count = locations.len();
    out.push(Diagnostic::warning(
        TODO_ASSUME_INVENTORY,
        format!(
            "{} honestly-deferred site(s) in {}: {}",
            count,
            pf.path,
            locations.join("; ")
        ),
    ));
}

#[cfg(test)]
mod tests {
    use super::run_lints;
    use crate::output::{ParsedFile, SourceFile};
    use crate::parse_sources;

    fn parsed(text: &str) -> Vec<ParsedFile> {
        parse_sources(&[SourceFile {
            path: "t.cupr".into(),
            text: text.to_string(),
        }])
    }

    // frob:tests crates/regolith-lower/src/lints.rs::run_lints kind="unit"
    #[test]
    fn unused_import_fires_when_name_never_referenced_again() {
        let src = "import std.elec.power (Inductor)\nblock Amp:\n    ports:\n        vdd: supply(in, 3.3V +- 5%, i <= 1mA)\n";
        let files = parsed(src);
        let report = run_lints(&files);
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::UNUSED_IMPORT));
    }

    #[test]
    fn used_import_is_silent() {
        let src = "import std.elec.power (Inductor)\nblock Amp:\n    ports:\n        l: Inductor\n";
        let files = parsed(src);
        let report = run_lints(&files);
        assert!(!report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::UNUSED_IMPORT));
    }

    #[test]
    fn retired_vocabulary_fires_on_bare_identifier() {
        let src = "block quarry:\n    ports:\n        vdd: supply(in, 3.3V +- 5%, i <= 1mA)\n";
        let files = parsed(src);
        let report = run_lints(&files);
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::RETIRED_VOCABULARY_USAGE));
    }

    #[test]
    fn retired_vocabulary_silent_in_comments() {
        let src = "# see the old quarry design\nblock Amp:\n    ports:\n        vdd: supply(in, 3.3V +- 5%, i <= 1mA)\n";
        let files = parsed(src);
        let report = run_lints(&files);
        assert!(!report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::RETIRED_VOCABULARY_USAGE));
    }

    #[test]
    fn mill_is_never_flagged() {
        let src = "block mill:\n    ports:\n        vdd: supply(in, 3.3V +- 5%, i <= 1mA)\n";
        let files = parsed(src);
        let report = run_lints(&files);
        assert!(!report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::RETIRED_VOCABULARY_USAGE));
    }
}
