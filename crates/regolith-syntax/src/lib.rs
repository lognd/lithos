//! Front-end: lexer, layout pass, rowan CST, parser, AST views,
//! formatter, and the language extension registry.
//!
//! Regolith reference: `docs/spec/hematite/02-language.md`,
//! `docs/spec/cuprite/01-overview.md`; parser technology is fixed by AD-3
//! (logos + layout pass + rowan + hand-written recursive descent). The
//! extension registry is normatively the one home for extension strings
//! (ground rule 6 / AD-14 risk register).
//!
//! Module map (WO-05): `token` (logos DFA), `layout` (off-side rule),
//! `syntax_kind` (CST tags + keywords), `cst` (rowan binding), `parser`
//! (event-based recursive descent), `ast` (typed views), `formatter`
//! (canonical normalizer), `debug` (pipeline dumps). Grammar EBNF is
//! authored under `docs/spec/toolchain/grammar.ebnf` in the same WO.

pub mod ast;
pub mod checks;
pub mod cst;
pub mod debug;
pub mod extension;
pub mod formatter;
pub mod layout;
pub mod parser;
pub mod syntax_kind;
pub mod token;
pub mod walk;

pub use ast::AstNode;
pub use cst::{RegolithLanguage, SyntaxElement, SyntaxNode, SyntaxToken};
pub use extension::{
    language_for_extension, test_file_language, Language, EXTENSIONS, TEST_FILE_INFIX,
};
pub use parser::{parse, Parse};
pub use syntax_kind::{keyword_kind, SyntaxKind, KEYWORD_TABLE};
pub use token::{lex, RawToken};
