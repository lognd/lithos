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
use rockhead_syntax::syntax_kind::SyntaxKind;

use crate::entities::EntitySnapshots;
use crate::output::ParsedFile;

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
        for decl in file.decls() {
            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw) {
                if let Some(name) = decl.name() {
                    out.interfaces.push(Interface {
                        name,
                        roles: Vec::new(),
                        demands: Vec::new(),
                        promises: Vec::new(),
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
        "contract IR built (impls/matings/systems skipped: opaque bodies)"
    );

    out
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
