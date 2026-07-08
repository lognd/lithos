//! Pass 3c (WO-31 deliverable 3): the fluorite fluid net discipline.
//!
//! Runs the flownet compile checks (fluorite/02 sec. 4) over every
//! parsed `.fluo` file's typed `flownet` AST, riding the SAME AD-23 net
//! core (`regolith_sem::net_core`) the elec single-driver check uses --
//! the imposer-free-subnet check is `net_core::FluidDiscipline` wired
//! through to a real `regolith_diag` diagnostic (E0201). The unjoined
//! terminal check (E0202) reads the terminal ledger the same core doc
//! describes. Two subnet checks ship here (the front-end-decidable
//! ones); medium mixing (FOPEN-1) and the compliance/wall checks
//! (fluorite/03) need the WO-32 lowering data and are NOT decidable at
//! this front-end layer -- see the WO-31 handoff note.
//!
//! Like `checks.rs`, this is a PURE function of parsed source: it reads
//! the typed AST WO-31 deliverable 2 structures and never touches IO or
//! rendering. A file with no `flownet` declaration contributes nothing.

use regolith_diag::codes::{IMPOSER_FREE_SUBNET, UNJOINED_TERMINAL};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::net_core::{first_violation, FluidDiscipline, NetEntry, Terminal};
use regolith_syntax::ast::{AstNode, File, FlownetDecl};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::output::ParsedFile;

/// The diagnostics from the fluid net discipline over every file.
#[derive(Debug, Clone, Default)]
pub struct FluidReport {
    /// Diagnostics from the fluorite flownet checks (E02xx family).
    pub diagnostics: Vec<Diagnostic>,
}

/// Constructor callees (fluorite/02 sec. 3) that impose a pressure on
/// their subnet: an `Imposer`, a `Regulator`, or a `Pump` curve. The
/// `reference:` field is the fourth imposer, counted separately.
const IMPOSER_CTORS: &[&str] = &["Imposer", "Regulator", "Pump"];

/// Run the fluid net discipline over `files`, in caller (sorted) order.
#[must_use]
pub fn run_fluid_checks(files: &[ParsedFile]) -> FluidReport {
    let span = tracing::info_span!("lower.fluid");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for flownet in file.flownets() {
            check_flownet(&pf.path, &flownet, &mut diagnostics);
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "fluid discipline: flownet checks complete"
    );
    FluidReport { diagnostics }
}

/// Check one flownet: imposer presence (E0201) and terminal joining
/// (E0202). One flownet is treated as one subnet at this front-end
/// layer (the per-subnet partition needs the WO-32 connectivity graph).
fn check_flownet(
    path: &camino::Utf8Path,
    flownet: &FlownetDecl,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let name = flownet.name().unwrap_or_default();
    let reference_names = field_idents(flownet, "reference");
    let reference_present = flownet.fields().iter().any(|f| f.name() == "reference");
    let declared_nodes = field_idents(flownet, "nodes");

    // Every edge contributes its two positive-sense endpoints (joined
    // nodes) and one terminal to the imposer ledger.
    let mut joined: Vec<String> = reference_names.clone();
    let mut terminals: Vec<Terminal> = Vec::new();
    if reference_present {
        terminals.push(Terminal {
            component: name.clone(),
            terminal: "reference".to_string(),
            imposes: true,
        });
    }
    if let Some(edges) = flownet.edges() {
        for edge in edges.edges() {
            let edge_name = edge.name();
            joined.extend(edge_endpoints(&edge));
            let imposes = edge
                .value()
                .and_then(|v| callee_name(&v))
                .is_some_and(|c| IMPOSER_CTORS.contains(&c.as_str()));
            terminals.push(Terminal {
                component: edge_name,
                terminal: "edge".to_string(),
                imposes,
            });
        }
    }

    // E0201: imposer-free subnet, via the AD-23 fluid discipline core.
    let net = NetEntry {
        name: name.clone(),
        terminals,
    };
    if let Some(violation) = first_violation(&FluidDiscipline, &[net]) {
        tracing::info!(flownet = %name, "E0201: imposer-free flownet subnet");
        let sp = flownet_span(path, flownet);
        diagnostics.push(
            Diagnostic::error(
                IMPOSER_FREE_SUBNET,
                format!(
                    "flownet `{name}` has no pressure imposer (no `reference:`, \
                     `Regulator`, `Pump`, or `Imposer`); the network is singular \
                     by construction and is rejected at compile time (fluorite/02 \
                     sec. 4), never at solve time"
                ),
            )
            .with_span(LabeledSpan::new(sp, "add a reference or an imposing edge")),
        );
        let _ = violation;
    }

    // E0202: a declared node no edge (or the reference) joins.
    for node in &declared_nodes {
        if !joined.iter().any(|j| j == node) {
            tracing::info!(flownet = %name, node = %node, "E0202: unjoined terminal");
            let sp = flownet_span(path, flownet);
            diagnostics.push(
                Diagnostic::error(
                    UNJOINED_TERMINAL,
                    format!(
                        "node `{node}` in flownet `{name}` is declared but joined \
                         by no edge and is not the reference; every terminal must \
                         join exactly one node or be `sealed` (fluorite/02 sec. 4)"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "this node joins no edge")),
            );
        }
    }
}

/// The positive-sense endpoint node names of an edge (`(a -> b)` ->
/// `["a", "b"]`). A single-line edge carries a typed [`SensePair`]; when
/// the constructor call wraps to a continuation line the trailing
/// `(a -> b)` degrades to an `OpaqueIsland` (a WO-05/D2 grammar edge --
/// the arrow is not re-lexed across the wrap), so this reads the
/// endpoints from either form. The `->` marker plus the parentheses
/// distinguish an endpoint island from any other opaque tail.
fn edge_endpoints(edge: &regolith_syntax::ast::EdgeStmt) -> Vec<String> {
    if let Some(sense) = edge.sense() {
        return sense.names();
    }
    for node in edge.syntax().children() {
        if node.kind() == SyntaxKind::OpaqueIsland && node.text().to_string().contains("->") {
            return node
                .descendants_with_tokens()
                .filter_map(rowan::NodeOrToken::into_token)
                .filter(|t| t.kind() == SyntaxKind::Ident)
                .map(|t| t.text().to_string())
                .collect();
        }
    }
    Vec::new()
}

/// The identifier tokens of a flownet header field's value (`nodes:`,
/// `reference:`), i.e. every `Ident` after the field's name/colon. The
/// leading field-name ident is dropped; a `reference: ambient(...)`
/// spec yields `["ambient"]`, a `reference: tank_in` yields
/// `["tank_in"]`, and `nodes: a, b, c` yields `["a", "b", "c"]`.
fn field_idents(flownet: &FlownetDecl, field_name: &str) -> Vec<String> {
    let Some(field) = flownet
        .fields()
        .into_iter()
        .find(|f| f.name() == field_name)
    else {
        return Vec::new();
    };
    let mut idents: Vec<String> = field
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    // Drop the leading field-name ident (`nodes`/`reference`).
    if !idents.is_empty() {
        idents.remove(0);
    }
    idents
}

/// The leading `Ident` token of an edge's constructor value node (the
/// callee: `Pipe(...)` -> `"Pipe"`, `vendor(x)` -> `"vendor"`), or
/// `None` for a value with no leading identifier.
fn callee_name(value: &regolith_syntax::SyntaxNode) -> Option<String> {
    value
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

/// A primary span over a flownet declaration's full text range.
fn flownet_span(path: &camino::Utf8Path, flownet: &FlownetDecl) -> Span {
    let range = flownet.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

#[cfg(test)]
mod tests {
    use super::run_fluid_checks;
    use crate::output::{ParsedFile, SourceFile};
    use crate::parse_sources;

    fn parse_one(text: &str) -> Vec<ParsedFile> {
        parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.fluo"),
            text: text.to_string(),
        }])
    }

    fn codes(text: &str) -> Vec<String> {
        run_fluid_checks(&parse_one(text))
            .diagnostics
            .iter()
            .map(|d| d.code.to_string())
            .collect()
    }

    #[test]
    fn clean_flownet_with_reference_passes() {
        let src = "flownet Loop(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       pipe: Pipe(from=line.run) (a -> b)\n";
        assert!(codes(src).is_empty(), "expected clean: {:?}", codes(src));
    }

    #[test]
    fn imposer_free_flownet_flags_e0201() {
        let src = "flownet NoRef(medium=Water):\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       pipe: Pipe(from=line.run) (a -> b)\n";
        assert!(
            codes(src).contains(&"E0201".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn imposer_edge_satisfies_the_discipline() {
        // No `reference:` field, but a `Pump` edge imposes pressure.
        let src = "flownet Pumped(medium=Water):\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       p: Pump(curve=registry(x)) (a -> b)\n";
        assert!(
            !codes(src).contains(&"E0201".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn unjoined_node_flags_e0202() {
        let src = "flownet Dangling(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b, c\n\
                   \x20   edges:\n\
                   \x20       pipe: Pipe(from=line.run) (a -> b)\n";
        assert!(
            codes(src).contains(&"E0202".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn wrapped_edge_sense_pair_still_joins_nodes() {
        // A long constructor wraps and its trailing `(a -> b)` degrades
        // to an OpaqueIsland; the endpoints must still count as joined
        // (no false E0202 on a valid multi-line edge, as in aquarium_loop).
        let src = "flownet Wrapped(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       p: Pump(curve=registry(some_long_curve_name_here))\n\
                   \x20              (a -> b)\n";
        assert!(
            !codes(src).contains(&"E0202".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn reference_named_node_counts_as_joined() {
        // `reference: tank_in` joins tank_in even though no edge names it.
        let src = "flownet Ref(medium=Water):\n\
                   \x20   reference: tank_in\n\
                   \x20   nodes: tank_in, a, b\n\
                   \x20   edges:\n\
                   \x20       pipe: Pipe(from=line.run) (a -> b)\n";
        assert!(
            !codes(src).contains(&"E0202".to_string()),
            "{:?}",
            codes(src)
        );
    }
}
