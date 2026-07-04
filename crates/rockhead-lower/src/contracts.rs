//! Pass 4: structured contract IR (interfaces, budgets) + conformance
//! checks.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. Only the
//! structured surface WO-05 exposes is lowered: an `interface` decl's
//! own name (its `roles:`/`promises:`/`spec:` bodies are nested
//! `OpaqueIsland` blocks, not `Field`s at the decl's own level, so they
//! are recorded as skipped rather than hand-parsed); a decl's
//! structured `budget name: limit` statements become `rockhead_ir`
//! `Budget`s and are checked with `close_budget` when the limit is a
//! literal quantity (non-literal limits are not yet resolved at this
//! pass, matching `close_budget`'s own documented behavior). `impl...for`
//! and `connect` bodies are opaque islands and are skipped (see the
//! WO-19 partial-lowering note).

use rockhead_diag::Diagnostic;
use rockhead_ir::budget::close_budget;
use rockhead_ir::nodes::{Budget, Impl, Interface, Mating, SystemNode};
use rockhead_qty::{Literal, Qty, Unit, ValueSource};
use rockhead_syntax::ast::{AstNode, File};
use rockhead_syntax::cst::SyntaxNode;
use rockhead_syntax::syntax_kind::SyntaxKind;

use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;

/// A binding between an upper contract and a lower realization for which
/// INV-13 mandates a conformance obligation: an `impl` role binding, an
/// `impl ... by extern` foreign linkage, or an `import` edge. One
/// `Obligation` is emitted per edge in pass 5 (`claims.rs`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConformanceEdge {
    /// The binding kind: `impl`, `extern`, or `import`.
    pub kind: String,
    /// The upper contract / imported symbol (`interface`, module path).
    pub upper: String,
    /// The lower realization (`for <target>`, extern ref, import path).
    pub lower: String,
    /// The enclosing declaration name (subject for the obligation's
    /// `subject_ref`); empty for a file-level `import`.
    pub subject: String,
}

/// The (partial) contract IR this pass can build from structured
/// syntax, plus its diagnostics and resolutions.
#[derive(Debug, Clone, Default)]
pub struct ContractGraph {
    /// Interfaces named at the top level (bodies mostly opaque today).
    pub interfaces: Vec<Interface>,
    /// Matings -- none are structured yet (`connect` is opaque); always
    /// empty in this WO-19 increment.
    pub matings: Vec<Mating>,
    /// Budgets lowered from structured `budget ...:` statements.
    pub budgets: Vec<Budget>,
    /// System/assembly nodes -- none are structured yet; always empty.
    pub systems: Vec<SystemNode>,
    /// Impls -- `impl...for` bodies are opaque; always empty.
    pub impls: Vec<Impl>,
    /// Conformance/impl/extern/import bindings that require an INV-13
    /// obligation (emitted in pass 5), in file then source order.
    pub conformance: Vec<ConformanceEdge>,
    /// Diagnostics from budget-closure checks.
    pub diagnostics: Vec<Diagnostic>,
    /// Resolutions this pass produced (none yet -- budgets with a
    /// literal limit need no resolution; unresolved limits carry no
    /// value to resolve).
    pub resolutions: Vec<rockhead_qty::Resolution>,
}

/// Build the contract IR available from `files`' structured syntax.
#[must_use]
pub fn build_contract_ir(files: &[ParsedFile], _snapshots: &EntitySnapshots) -> ContractGraph {
    let span = tracing::info_span!("lower.contracts");
    let _enter = span.enter();

    let mut out = ContractGraph::default();

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };

        // INV-13/INV-22 import edges: every `import` binding gets a
        // conformance obligation (the upper is the imported module/path;
        // the lower realization is the pinned source it resolves to).
        for import in file.imports() {
            let path = header_path_text(import.syntax());
            if !path.is_empty() {
                out.conformance.push(ConformanceEdge {
                    kind: "import".to_string(),
                    upper: path.clone(),
                    lower: path,
                    subject: String::new(),
                });
            }
        }

        for decl in file.decls() {
            // Per-subject INV-20 gating: a poisoned subject contributes
            // no contract IR (parity with entities.rs).
            if decl_is_poisoned(&decl) {
                continue;
            }

            // A top-level `impl <Iface> for <target>` / `impl <Iface> by
            // extern(...)` declaration, plus any in-body `impl` block
            // (`ImplStmt`), each yield an INV-13 conformance/extern edge.
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw) {
                if let Some(edge) = impl_edge(decl.syntax(), &decl.name().unwrap_or_default()) {
                    out.conformance.push(edge);
                }
            }
            let decl_name = decl.name().unwrap_or_default();
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt {
                    if let Some(edge) = impl_edge(&node, &decl_name) {
                        out.conformance.push(edge);
                    }
                }
            }

            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw) {
                if let Some(name) = decl.name() {
                    out.interfaces.push(Interface {
                        name,
                        roles: Vec::new(),
                        role_kinds: Vec::new(),
                        demands: Vec::new(),
                        promises: Vec::new(),
                        params: Vec::new(),
                        spec_island: None,
                    });
                }
            }

            for stmt in decl.budgets() {
                let name = stmt.name();
                let limit = stmt
                    .value()
                    .and_then(|v| literal_qty_from_text(&v.text().to_string()))
                    .map_or(ValueSource::Free, |q| {
                        ValueSource::Literal(Literal::Value(q))
                    });
                let budget = Budget {
                    name: name.clone(),
                    limit,
                    reserve: None,
                };
                // No contributions are structured yet (they live in
                // opaque bodies); an empty ledger trivially closes, but
                // the call is real -- the moment contributions land,
                // `close_budget` starts reporting E0432 with no
                // pipeline change.
                if let Err(diags) = close_budget(&budget, &[]) {
                    out.diagnostics.extend(diags);
                }
                out.budgets.push(budget);
            }
        }
    }

    tracing::debug!(
        interfaces = out.interfaces.len(),
        budgets = out.budgets.len(),
        conformance = out.conformance.len(),
        "contract IR built (matings/systems skipped: opaque bodies)"
    );

    out
}

/// The tokens of a node's header LINE (everything before the body
/// `Indent`/`Newline`), as `(kind, text)` pairs, skipping only the
/// generic-parameter node (which is part of the header). Body statement
/// nodes end the header. Shared by the impl/import edge extractors so
/// they read structure, not a raw text scan.
fn header_tokens(node: &SyntaxNode) -> Vec<(SyntaxKind, String)> {
    let mut out = Vec::new();
    for child in node.children_with_tokens() {
        if let Some(t) = child.as_token() {
            match t.kind() {
                SyntaxKind::Newline | SyntaxKind::Indent | SyntaxKind::Dedent => break,
                SyntaxKind::Whitespace => {}
                k => out.push((k, t.text().to_string())),
            }
        } else if let Some(n) = child.as_node() {
            // The generic-parameter list is part of the header; any other
            // child node is a body statement, so the header is over.
            if n.kind() != SyntaxKind::GenericParams {
                break;
            }
        }
    }
    out
}

/// Join a statement's leading path tokens (`Ident`/`Dot`/`String`) into
/// one reference string (an `import` path, dotted or quoted).
fn header_path_text(node: &SyntaxNode) -> String {
    header_tokens(node)
        .into_iter()
        .skip_while(|(k, _)| *k == SyntaxKind::ImportKw)
        .take_while(|(k, _)| matches!(k, SyntaxKind::Ident | SyntaxKind::Dot | SyntaxKind::String))
        .map(|(_, t)| t.trim_matches('"').to_string())
        .collect::<String>()
}

/// Extract the INV-13 conformance edge from an `impl` header (top-level
/// `Decl` or in-body `ImplStmt`): the interface is the first `Ident`
/// after the `impl` keyword; a `by extern("ref", ...)` marks an
/// `extern` linkage (lower = the quoted ref); a `for <target>` marks an
/// ordinary `impl` binding (lower = the target). Returns `None` if no
/// interface name is present.
fn impl_edge(node: &SyntaxNode, subject: &str) -> Option<ConformanceEdge> {
    let toks = header_tokens(node);
    // First Ident after the `impl` keyword is the interface.
    let mut iter = toks.iter().skip_while(|(k, _)| *k != SyntaxKind::ImplKw);
    iter.next(); // the `impl` keyword itself
    let interface = iter
        .clone()
        .find(|(k, _)| *k == SyntaxKind::Ident)
        .map(|(_, t)| t.clone())?;

    // `by extern("ref", ...)`: the first String after `extern` is the
    // foreign reference.
    if let Some(pos) = toks.iter().position(|(k, _)| *k == SyntaxKind::ExternKw) {
        let reference = toks[pos + 1..]
            .iter()
            .find(|(k, _)| *k == SyntaxKind::String)
            .map_or_else(
                || "extern".to_string(),
                |(_, t)| t.trim_matches('"').to_string(),
            );
        return Some(ConformanceEdge {
            kind: "extern".to_string(),
            upper: interface,
            lower: reference,
            subject: subject.to_string(),
        });
    }

    // `for <target>`: the Ident after the bare `for` word.
    let target = toks
        .iter()
        .position(|(k, t)| *k == SyntaxKind::Ident && t == "for")
        .and_then(|pos| {
            toks[pos + 1..]
                .iter()
                .find(|(k, _)| *k == SyntaxKind::Ident)
                .map(|(_, t)| t.clone())
        })
        .unwrap_or_default();
    Some(ConformanceEdge {
        kind: "impl".to_string(),
        upper: interface,
        lower: target,
        subject: subject.to_string(),
    })
}

/// Parse a very small subset of quantity-literal text (`"4 mm"`,
/// `"100 g"`) into a dimensionless-unit `Qty`. A real unit lookup table
/// (mapping unit spellings to `rockhead_qty::Unit`s) is WO-05/WO-12
/// territory already recorded as deferred (unit-checking cut, cycle
/// 11 notes); this is a documented placeholder that recognizes a bare
/// leading number and otherwise reports no literal.
fn literal_qty_from_text(text: &str) -> Option<Qty> {
    let trimmed = text.trim();
    let number_part: String = trimmed
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();
    let magnitude: f64 = number_part.parse().ok()?;
    Some(Qty::new(magnitude, Unit::dimensionless()))
}

#[cfg(test)]
mod tests {
    use super::build_contract_ir;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hem");
        vec![ParsedFile {
            path: path.clone(),
            parse: rockhead_syntax::parse(src, &path),
        }]
    }

    #[test]
    fn import_and_impl_edges_are_collected() {
        let src =
            "import std.mech.cnc (saw_stock)\npart p:\n    impl Seat for self:\n        x: 1\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "import" && e.upper.contains("std")),
            "import edge collected: {:?}",
            graph.conformance
        );
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "impl" && e.upper == "Seat"),
            "impl edge collected: {:?}",
            graph.conformance
        );
    }

    #[test]
    fn extern_linkage_is_an_extern_edge() {
        let src = "impl Mux by extern(\"rtl/mux.v\", verilog2005) as Hand\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "extern" && e.upper == "Mux"),
            "extern edge collected: {:?}",
            graph.conformance
        );
    }
}
