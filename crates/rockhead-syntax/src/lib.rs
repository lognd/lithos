//! Front-end: lexer, layout pass, rowan CST, parser, AST views,
//! formatter, and the language extension registry.
//!
//! Substrate reference: `docs/mech/02-language.md`,
//! `docs/elec/01-overview.md`; parser technology is fixed by AD-3
//! (logos + layout pass + rowan + hand-written recursive descent). The
//! extension registry is normatively the one home for extension strings
//! (ground rule 6 / AD-14 risk register).
//!
//! Module map (WO-05): `token` (logos DFA), `layout` (off-side rule),
//! `syntax_kind` (CST tags + keywords), `cst` (rowan binding), `parser`
//! (event-based recursive descent), `ast` (typed views), `formatter`
//! (canonical normalizer), `debug` (pipeline dumps). Grammar EBNF is
//! authored under `docs/implementation/grammar.ebnf` in the same WO.

pub mod ast;
pub mod cst;
pub mod debug;
pub mod extension;
pub mod formatter;
pub mod layout;
pub mod parser;
pub mod syntax_kind;
pub mod token;

pub use ast::AstNode;
pub use cst::{RockheadLanguage, SyntaxElement, SyntaxNode, SyntaxToken};
pub use extension::{language_for_extension, Language, EXTENSIONS};
pub use parser::{parse, Parse};
pub use syntax_kind::{keyword_kind, SyntaxKind};
pub use token::{lex, RawToken};
