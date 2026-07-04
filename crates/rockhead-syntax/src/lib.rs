//! Front-end: lexer, layout pass, rowan CST, parser, AST views,
//! formatter, and the language extension registry.
//!
//! Substrate reference: `docs/mech/02-language.md`,
//! `docs/elec/01-overview.md`; parser technology is fixed by AD-3
//! (logos + layout pass + rowan + hand-written recursive descent).
//! WO-05 fills in the pipeline; WO-01 ships only the extension
//! registry, which is normatively the one home for extension strings
//! (ground rule 6 / AD-14 risk register).

pub mod extension;
