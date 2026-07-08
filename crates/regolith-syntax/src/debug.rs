//! Pipeline inspection dumps backing `regolith debug tokens|cst|ast`
//! (AD-13 / DX contract 5: intermediate states are always inspectable).
//!
//! Plain-text, deterministic renderings of each stage for goldens and
//! human debugging. stdout is data (these strings); logs go to stderr.

use std::fmt::Write as _;

use camino::Utf8PathBuf;

/// The pipeline stage to dump.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stage {
    /// Raw + layout token stream.
    Tokens,
    /// The lossless CST (indented S-expression form).
    Cst,
    /// The typed AST view tree.
    Ast,
}

/// Render `stage` of parsing `source` (belonging to `file`) as a stable
/// plain-text dump.
#[must_use]
pub fn dump(stage: Stage, source: &str, file: &Utf8PathBuf) -> String {
    match stage {
        Stage::Tokens => dump_tokens(source),
        Stage::Cst => dump_cst(source, file),
        Stage::Ast => dump_ast(source, file),
    }
}

/// One line per post-layout token: `KIND@start..end "text"`.
fn dump_tokens(source: &str) -> String {
    let raw = crate::token::lex(source);
    let (tokens, _diags) = crate::layout::apply_layout(&raw, source);
    let mut out = String::new();
    for tok in &tokens {
        let text = &source[tok.span.clone()];
        let _ = writeln!(
            out,
            "{:?}@{}..{} {:?}",
            tok.kind, tok.span.start, tok.span.end, text
        );
    }
    out
}

/// The lossless CST as an indented tree (rowan's own `Debug` form).
fn dump_cst(source: &str, file: &Utf8PathBuf) -> String {
    let parse = crate::parser::parse(source, file);
    format!("{:#?}", parse.syntax())
}

/// The typed-AST view: top-level imports and declarations, in order.
fn dump_ast(source: &str, file: &Utf8PathBuf) -> String {
    use crate::ast::{AstNode, File};

    let parse = crate::parser::parse(source, file);
    let root = File::cast(parse.syntax()).expect("parser always emits a File root");
    let mut out = String::new();
    for import in root.imports() {
        let _ = writeln!(out, "Import {:?}", import.syntax().text().to_string());
    }
    for decl in root.decls() {
        let header: String = decl
            .syntax()
            .children_with_tokens()
            .take_while(|e| e.kind() != crate::syntax_kind::SyntaxKind::OpaqueIsland)
            .filter_map(rowan::NodeOrToken::into_token)
            .map(|t| t.text().to_string())
            .collect();
        let _ = writeln!(out, "Decl {:?}", header.trim());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::{dump, Stage};
    use camino::Utf8PathBuf;

    #[test]
    fn tokens_dump_is_deterministic() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part a:\n    x: 1\n";
        assert_eq!(
            dump(Stage::Tokens, src, &file),
            dump(Stage::Tokens, src, &file)
        );
        assert!(dump(Stage::Tokens, src, &file).contains("PartKw"));
    }

    #[test]
    fn cst_dump_contains_file_root() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "part a:\n    x: 1\n";
        assert!(dump(Stage::Cst, src, &file).contains("File"));
    }

    #[test]
    fn ast_dump_lists_decls() {
        let file = Utf8PathBuf::from("t.hema");
        let src = "import a.b\npart a:\n    x: 1\n";
        let out = dump(Stage::Ast, src, &file);
        assert!(out.contains("Import"));
        assert!(out.contains("Decl"));
    }
}
