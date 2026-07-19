// frob:waive TEST003 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
//! `regolith-ls`: the LSP server, one front end for humans and tools
//! over the compiler crates (AD-24, `design/24-developer-tooling.md`).
//!
//! Depends on `regolith-api` and below ONLY (AD-2 layering); never
//! `regolith-py`, never embeds or spawns Python (D111). Library form
//! exists so the protocol-level integration tests in `tests/` can drive
//! [`server::Server`] without a real stdio transport.

pub mod actions;
pub mod artifacts;
pub mod completion;
pub mod diagnostics;
pub mod folding;
pub mod formatting;
pub mod hover;
pub mod nav;
pub mod position;
pub mod semtok;
pub mod server;
pub mod symbols;
pub mod workspace;
