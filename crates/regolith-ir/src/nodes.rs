//! The implementation-free contract graph: the IR nodes at L2, the
//! level where a system verifies with zero artifacts.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`, `docs/mech/03`,
//! `docs/elec/02` sec. 4a. Interfaces carry demands and promise slots
//! (value sources); impls bind roles as queries and may only NARROW
//! promises (widening is rejected, WO-12 / conformance); matings name
//! sides and remove/keep DOF; system/assembly nodes carry budgets,
//! reserves, targets, and config variables.

use regolith_qty::ValueSource;
use regolith_sem::Query;
use serde::{Deserialize, Serialize};

/// A reference frame an interface or mating is expressed in.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Frame {
    /// Frame name.
    pub name: String,
    /// The datum the frame anchors to.
    pub datum: String,
}

/// A named promise slot on an interface: a value the interface promises,
/// backed by a value source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromiseSlot {
    /// Slot name (`stiffness`, `i_max`).
    pub name: String,
    /// The value source deciding the promised value.
    pub value: ValueSource,
}

/// Distinguishes compile-time interface parameters (`<params>`,
/// monomorphizing) from runtime promise/demand fields (`params:`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParamKind {
    /// `<params>`: compile-time type parameters (monomorphized).
    Type,
    /// `params:`: runtime demand/promise fields.
    Field,
}

/// A contract parameter: a compile-time `<params>` type parameter or a
/// runtime `params:` field, with an optional declared type/shape. The
/// `ParamKind` distinguishes the two (substrate/04 sec. 1).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Param {
    /// Parameter name (`d`, `f_sw`, `screw`).
    pub name: String,
    /// Whether this is a `<params>` type parameter or a `params:` field.
    pub kind: ParamKind,
    /// The declared type or shape (`thread`, `int`, `voltage`, `20mm`),
    /// if the source declares one; `None` when untyped/free.
    pub ty: Option<String>,
}

/// A contract interface: roles (with their required entity kinds),
/// demands, promise slots, and parameters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Interface {
    /// Interface name.
    pub name: String,
    /// Role names the interface exposes.
    pub roles: Vec<String>,
    /// Per-role required entity KIND (`bore` -> `cylindrical`,
    /// `pad` -> `planar`): the role-kind demand an impl's binding must
    /// satisfy (substrate/04 sec. 1). A role absent here is kind-agnostic.
    pub role_kinds: Vec<(String, String)>,
    /// Demand field names (what the interface requires of its context).
    pub demands: Vec<String>,
    /// Promise slots (what it guarantees), each a value source.
    pub promises: Vec<PromiseSlot>,
    /// Interface parameters: `<params>` type parameters and `params:`
    /// fields (substrate/04 sec. 1's `<params>` vs `params:` distinction).
    pub params: Vec<Param>,
    /// The `spec:` body, kept as an opaque island reference (WO-05).
    pub spec_island: Option<String>,
}

/// An implementation of an interface: role bindings as queries plus
/// inline promise refinement (narrowing only).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Impl {
    /// The interface this implements.
    pub interface: String,
    /// Role name -> the query that binds it.
    pub role_bindings: Vec<(String, Query)>,
    /// Per-role KIND of the bound entity (`bore` -> `cylindrical`), when
    /// known. Checked against the interface's `role_kinds`. Populated from
    /// the entity DB (regolith-sem) once available; the CST extractor
    /// leaves this empty because a binding's entity kind is not carried in
    /// the impl's own syntax (documented WO-12 dependency).
    pub bound_kinds: Vec<(String, String)>,
    /// Impl-chosen parameters (the `params:` block and the impl header's
    /// `<...>` pins), matched against the interface's parameters.
    pub params: Vec<Param>,
    /// Inline promise refinements (must narrow, never widen; checked in
    /// `conformance`).
    pub refinements: Vec<PromiseSlot>,
}

/// CST extraction: build [`Interface`]/[`Impl`] contract nodes from the
/// typed syntax tree (WO-12). Role kinds come from the `roles:` block,
/// parameters from the header `<params>` and the `params:` block, and
/// impl role bindings from the impl body's ctor statements.
mod extract {
    use super::{Impl, Interface, Param, ParamKind};
    use regolith_sem::Query;
    use regolith_syntax::ast::{AstNode, Decl, Field};
    use regolith_syntax::cst::SyntaxNode;
    use regolith_syntax::syntax_kind::SyntaxKind;

    impl Interface {
        /// Build an `Interface` from an `interface` [`Decl`] CST node,
        /// reading the typed structure: header generic `<params>`, and the
        /// `roles:` / `demands:` / `params:` sub-blocks. Returns `None`
        /// when the declaration is unnamed.
        #[must_use]
        pub fn from_decl(decl: &Decl) -> Option<Interface> {
            let name = decl.name()?;
            tracing::debug!(interface = %name, "extracting interface from CST");

            let mut roles = Vec::new();
            let mut role_kinds = Vec::new();
            for role in sub_block_fields(decl.syntax(), "roles") {
                let rn = role.name();
                if let Some(kind) = value_head(&role) {
                    role_kinds.push((rn.clone(), kind));
                }
                roles.push(rn);
            }

            let demands = sub_block_fields(decl.syntax(), "demands")
                .into_iter()
                .map(|f| f.name())
                .collect();

            let mut params = generic_params(decl.syntax());
            params.extend(
                sub_block_fields(decl.syntax(), "params")
                    .into_iter()
                    .map(|f| Param {
                        name: f.name(),
                        kind: ParamKind::Field,
                        ty: value_head(&f),
                    }),
            );

            Some(Interface {
                name,
                roles,
                role_kinds,
                demands,
                promises: Vec::new(),
                params,
                spec_island: None,
            })
        }
    }

    impl Impl {
        /// Build an `Impl` from an `ImplStmt` CST node: the implemented
        /// interface (the word after `impl`), role bindings (the body's
        /// ctor statements `role = query`), impl-header `<...>` pins, and
        /// the `params:` block. `bound_kinds` is left empty -- a binding's
        /// entity kind needs the entity DB (documented WO-12 dependency).
        #[must_use]
        pub fn from_impl_stmt(node: &SyntaxNode) -> Option<Impl> {
            if node.kind() != SyntaxKind::ImplStmt {
                return None;
            }
            // Interface = first Ident token after `impl`.
            let interface = node
                .children_with_tokens()
                .filter_map(rowan::NodeOrToken::into_token)
                .find(|t| t.kind() == SyntaxKind::Ident)
                .map(|t| t.text().to_string())?;
            tracing::debug!(interface = %interface, "extracting impl from CST");

            let role_bindings = node
                .children()
                .filter(|c| c.kind() == SyntaxKind::CtorStmt)
                .filter_map(|c| {
                    let stmt = regolith_syntax::ast::CtorStmt::cast(c)?;
                    let base = stmt.value().map(|v| v.text().to_string())?;
                    Some((
                        stmt.name(),
                        Query {
                            base: base.trim().to_string(),
                            ops: Vec::new(),
                        },
                    ))
                })
                .collect();

            let mut params = generic_params(node);
            params.extend(
                node.children()
                    .filter_map(Field::cast)
                    .filter(|f| f.name() == "params")
                    .flat_map(|f| f.syntax().children().filter_map(Field::cast))
                    .map(|f| Param {
                        name: f.name(),
                        kind: ParamKind::Field,
                        ty: value_head(&f),
                    }),
            );

            Some(Impl {
                interface,
                role_bindings,
                bound_kinds: Vec::new(),
                params,
                refinements: Vec::new(),
            })
        }
    }

    /// The inner [`Field`]s of a named sub-block (`roles:`, `demands:`,
    /// `params:`) in a declaration body, in source order.
    fn sub_block_fields(decl: &SyntaxNode, header: &str) -> Vec<Field> {
        decl.children()
            .filter_map(Field::cast)
            .find(|f| f.name() == header)
            .map(|block| block.syntax().children().filter_map(Field::cast).collect())
            .unwrap_or_default()
    }

    /// The leading word of a field's value (a role's required kind, a
    /// parameter's declared type): the value node's text up to the first
    /// separator, or `None` when the field has no value node.
    fn value_head(field: &Field) -> Option<String> {
        let text = field.value()?.text().to_string();
        let head = text
            .split([',', '(', ' ', '\n'])
            .find(|s| !s.is_empty())?
            .trim();
        (!head.is_empty()).then(|| head.to_string())
    }

    /// Parse a header generic-parameter list into `<params>` type
    /// parameters. Accepts either a typed [`SyntaxKind::GenericParams`]
    /// child node (declaration headers) or a raw `< ... >` token run
    /// (impl headers), splitting on commas into `name` / `name: ty` /
    /// `name=val` entries.
    fn generic_params(node: &SyntaxNode) -> Vec<Param> {
        let inner = generic_params_text(node);
        inner
            .split(',')
            .filter_map(|entry| {
                let entry = entry.trim();
                if entry.is_empty() {
                    return None;
                }
                let (name, ty) = match entry.split_once([':', '=']) {
                    Some((n, t)) => (n.trim().to_string(), Some(t.trim().to_string())),
                    None => (entry.to_string(), None),
                };
                Some(Param {
                    name,
                    kind: ParamKind::Type,
                    ty,
                })
            })
            .collect()
    }

    /// The text between the header's `<` and matching `>` (inclusive of
    /// nested angle brackets), or empty when the node carries no generics.
    fn generic_params_text(node: &SyntaxNode) -> String {
        // Prefer the typed node (declaration headers wrap generics).
        if let Some(gp) = node
            .children()
            .find(|c| c.kind() == SyntaxKind::GenericParams)
        {
            let t = gp.text().to_string();
            return t.trim_start_matches('<').trim_end_matches('>').to_string();
        }
        // Impl headers keep generics as raw tokens: scan for the `<..>`
        // run, tracking depth, and stop at the header's own `>`.
        let mut out = String::new();
        let mut depth = 0i32;
        for tok in node
            .children_with_tokens()
            .filter_map(rowan::NodeOrToken::into_token)
        {
            match tok.kind() {
                SyntaxKind::Lt => {
                    depth += 1;
                    if depth == 1 {
                        continue;
                    }
                }
                SyntaxKind::Gt => {
                    depth -= 1;
                    if depth == 0 {
                        break;
                    }
                }
                _ => {}
            }
            if depth >= 1 {
                out.push_str(tok.text());
            }
        }
        out
    }
}

/// A mating between two artifacts: named sides, alignment, and the DOF it
/// removes and keeps.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mating {
    /// Mating name.
    pub name: String,
    /// The two (or more) named sides.
    pub sides: Vec<String>,
    /// Alignment record (reuses the WO-05 align AST, kept as text here).
    pub align: Option<String>,
    /// Degrees of freedom removed by the mating.
    pub dof_removed: Vec<String>,
    /// Degrees of freedom deliberately kept.
    pub dof_kept: Vec<String>,
    /// Coupled quantities across the mating.
    pub couples: Vec<String>,
    /// Preload value source, if any.
    pub preload: Option<ValueSource>,
    /// Physical effects, as signature references (harness contracts).
    pub effects: Vec<String>,
}

/// A budget declared at a system/assembly node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Budget {
    /// Budget name (`mass`, `energy`, `noise`).
    pub name: String,
    /// The limit value source.
    pub limit: ValueSource,
    /// Reserve held back for targets.
    pub reserve: Option<ValueSource>,
}

/// A system or assembly node: parts, boundary datums, connections,
/// budgets, reserves, targets, and config variables.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemNode {
    /// Node name.
    pub name: String,
    /// Whether this is a system (true) or an assembly (false).
    pub is_system: bool,
    /// Contained part/child names.
    pub parts: Vec<String>,
    /// Boundary datums (`at=` anchors).
    pub boundary_datums: Vec<String>,
    /// Connections between parts (display/reference names).
    pub connects: Vec<String>,
    /// The matings participating in this node's ledgers: every ledger
    /// (mech DOF/Gruebler, elec driver/load + domain-crossing + flow)
    /// sums over exactly this list, in source order (INV-15:
    /// participation is syntactic -- there is no way to remove a
    /// freedom or feed a net outside a declared mating).
    pub matings: Vec<Mating>,
    /// Declared budgets.
    pub budgets: Vec<Budget>,
    /// Named targets (build variants).
    pub targets: Vec<String>,
    /// Config variables, namespaced by their exposer.
    pub config_vars: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::{Interface, ParamKind, PromiseSlot};
    use regolith_qty::ValueSource;

    #[test]
    fn interface_round_trips_json() {
        let iface = Interface {
            name: "seat".to_string(),
            roles: vec!["bore".to_string()],
            role_kinds: vec![("bore".to_string(), "cylindrical".to_string())],
            demands: vec!["stiffness".to_string()],
            promises: vec![PromiseSlot {
                name: "runout".to_string(),
                value: ValueSource::Free,
            }],
            params: Vec::new(),
            spec_island: None,
        };
        let json = serde_json::to_string(&iface).unwrap();
        let back: Interface = serde_json::from_str(&json).unwrap();
        assert_eq!(back.name, "seat");
        assert_eq!(back.promises.len(), 1);
    }

    #[test]
    fn param_kind_distinguishes_type_and_field() {
        assert_ne!(ParamKind::Type, ParamKind::Field);
    }
}
