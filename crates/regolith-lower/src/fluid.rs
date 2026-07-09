//! Three subnet checks ship here: the two front-end-decidable ones
//! (imposer presence, terminal joining) plus, as of WO-49, the FOPEN-1
//! medium-mismatch check -- decidable at this layer after all, because
//! its binding surface (`impl FluidPort<medium=...>`, fluorite/02 sec.
//! 2) is itself pure AST: a flownet edge's `from=<part>.<role>` ref
//! names a component by its declaration name, and any `impl
//! FluidPort<medium=..., ...>` inside that declaration's body pins its
//! working medium -- no IO, no WO-32 realized-geometry resolution
//! needed (that resolves HYDRAULIC parameters, a separate concern from
//! which medium a component's port is bound to). The wall-compliance
//! checks (fluorite/03) still need the WO-32 lowering data and are not
//! decidable here -- see the WO-31 handoff note.
//!
//! Like `checks.rs`, this is a PURE function of parsed source: it reads
//! the typed AST WO-31 deliverable 2 structures and never touches IO or
//! rendering. A file with no `flownet` declaration contributes nothing.

use std::collections::BTreeMap;

use regolith_diag::codes::{IMPOSER_FREE_SUBNET, MEDIUM_MISMATCH, UNJOINED_TERMINAL};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::net_core::{first_violation, FluidDiscipline, NetEntry, Terminal};
use regolith_syntax::ast::{AstNode, File, FlownetDecl};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_syntax::SyntaxNode;

use crate::flownet_lower::{arg_ref, collect_args, flownet_medium_name};
use crate::output::ParsedFile;

/// A component's declared `impl FluidPort<medium=..., ...>` binding
/// (WO-49 deliverable 1): the medium name it pins, plus the impl
/// declaration's span (one of the two sites a mismatch diagnostic
/// names).
#[derive(Debug, Clone)]
struct FluidPortBinding {
    medium: String,
    span: Span,
}

/// Harvest every component's declared `impl FluidPort<medium=..., ...>`
/// binding across `files`, keyed by the ENCLOSING declaration's own
/// name (fluorite/02 sec. 2: "a hematite part exposes its wetted side
/// by implementing FluidPort") -- the same name a flownet edge's
/// `from=<part>.<role>` ref leads with. `BTreeMap` for deterministic
/// iteration (AD-6); a component with more than one `FluidPort` impl
/// keeps its FIRST (source order), matching the single-medium-per-
/// component precedent this WO enforces at the subnet level.
fn fluidport_bindings(files: &[ParsedFile]) -> BTreeMap<String, FluidPortBinding> {
    let mut table = BTreeMap::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let decl_name = decl.name().unwrap_or_default();
            if decl_name.is_empty() {
                continue;
            }
            for node in decl.syntax().descendants() {
                if node.kind() != SyntaxKind::ImplStmt {
                    continue;
                }
                let Some(medium) = fluidport_medium(&node) else {
                    continue;
                };
                let range = node.text_range();
                table.entry(decl_name.clone()).or_insert(FluidPortBinding {
                    medium,
                    span: Span::new(pf.path.clone(), range.start().into(), range.end().into()),
                });
            }
        }
    }
    table
}

/// The medium an `impl FluidPort<...>` binding pins: the keyword
/// spelling `medium=<name>` (the WO-49 form) or, failing that, the
/// positional first-argument spelling from fluorite/02 sec. 2's own
/// example (`impl FluidPort<RP1, dia 12mm> for self as fuel_in` ->
/// `Some("RP1")` -- `m: medium` is the interface's FIRST declared
/// generic param, so a bare leading identifier binds it). `None` when
/// the impl's interface is not `FluidPort` or no spelling matches.
fn fluidport_medium(node: &SyntaxNode) -> Option<String> {
    let mut toks = node
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .skip_while(|t| t.kind() != SyntaxKind::ImplKw);
    toks.next(); // the `impl` keyword itself
    let interface = toks.find(|t| t.kind() == SyntaxKind::Ident)?;
    if interface.text() != "FluidPort" {
        return None;
    }
    // Scan the header's `<...>` generic-argument run (impl headers keep
    // generics as raw tokens, mirroring `regolith_ir::nodes`'s reader).
    let mut depth = 0i32;
    let mut inner = String::new();
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
            inner.push_str(tok.text());
        }
    }
    let keyword = inner.split(',').find_map(|entry| {
        let (key, val) = entry.trim().split_once('=')?;
        (key.trim() == "medium").then(|| val.trim().to_string())
    });
    keyword.or_else(|| {
        // Positional: a bare leading identifier (no `=`/`:`/space)
        // binds the interface's first declared param, `m: medium`.
        let first = inner.split(',').next()?.trim();
        (!first.is_empty()
            && first.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
            && !first.chars().next().is_some_and(|c| c.is_ascii_digit()))
        .then(|| first.to_string())
    })
}

/// The leading (component-name) segment of a dotted `from=<ref>` value
/// (`"feed_tube.run"` -> `"feed_tube"`; a bare name with no dot returns
/// itself unchanged).
fn leading_segment(dotted: &str) -> &str {
    dotted.split('.').next().unwrap_or(dotted)
}

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

    let bindings = fluidport_bindings(files);

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for flownet in file.flownets() {
            check_flownet(&pf.path, &flownet, &bindings, &mut diagnostics);
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "fluid discipline: flownet checks complete"
    );
    FluidReport { diagnostics }
}

/// Check one flownet: imposer presence (E0201), terminal joining
/// (E0202), and FOPEN-1 medium mismatch (E0210, WO-49). One flownet is
/// treated as one subnet at this front-end layer (the per-subnet
/// partition needs the WO-32 connectivity graph).
fn check_flownet(
    path: &camino::Utf8Path,
    flownet: &FlownetDecl,
    bindings: &BTreeMap<String, FluidPortBinding>,
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
    let net_medium = flownet_medium_name(flownet);
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

            check_edge_medium(
                path,
                flownet,
                &name,
                &net_medium,
                &edge,
                bindings,
                diagnostics,
            );
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

/// FOPEN-1 (E0210, WO-49): one edge's medium-consistency check. The
/// edge's `from=<part>.<role>` ref names a component; if that component
/// declared an `impl FluidPort<medium=...>` binding whose medium
/// disagrees with the subnet's own `medium=` header, the subnet is
/// mixed-medium -- rejected here, BEFORE the WO-32 payload is ever
/// constructed (fluorite/02 sec. 1), with both media and both
/// declaration sites named. An edge with no `from=` ref or an unbound
/// component contributes nothing (the whole pre-WO-49 corpus).
fn check_edge_medium(
    path: &camino::Utf8Path,
    flownet: &FlownetDecl,
    name: &str,
    net_medium: &str,
    edge: &regolith_syntax::ast::EdgeStmt,
    bindings: &BTreeMap<String, FluidPortBinding>,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let Some(from_ref) = edge
        .value()
        .map(|v| collect_args(&v))
        .and_then(|args| arg_ref(&args, "from"))
    else {
        return;
    };
    let component = leading_segment(&from_ref);
    let Some(binding) = bindings.get(component) else {
        return;
    };
    if net_medium.is_empty() || binding.medium == net_medium {
        return;
    }
    let edge_name = edge.name();
    tracing::info!(
        flownet = %name,
        edge = %edge_name,
        component = %component,
        net_medium = %net_medium,
        port_medium = %binding.medium,
        "E0210: mixed-medium subnet"
    );
    let net_sp = flownet_span(path, flownet);
    diagnostics.push(
        Diagnostic::error(
            MEDIUM_MISMATCH,
            format!(
                "flownet `{name}` declares medium `{net_medium}`, but \
                 edge `{edge_name}` (`from={from_ref}`) resolves to \
                 component `{component}`, whose `impl FluidPort` binds \
                 medium `{port}`; one medium per connected subnet in v1 \
                 (fluorite/02 sec. 1, FOPEN-1) -- mismatched media are a \
                 compile error, not a solve-time surprise",
                port = binding.medium,
            ),
        )
        .with_span(LabeledSpan::new(
            net_sp,
            format!("subnet declared medium `{net_medium}` here"),
        ))
        .with_span(LabeledSpan::new(
            binding.span.clone(),
            format!(
                "component `{component}` binds medium `{}` here",
                binding.medium
            ),
        )),
    );
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

    /// FOPEN-1 (WO-49): `AirLine`'s `impl FluidPort<medium=ShopAir>`
    /// binding disagrees with `Mixed`'s own `medium=Water` header -- a
    /// mixed-medium subnet, flagged before any WO-32 payload exists.
    /// Mirrors `examples/negative/40_fluo_medium_mismatch.fluo`.
    #[test]
    fn mismatched_fluidport_binding_flags_e0204() {
        let src = "medium Water: liquid\n\
                   \x20   props: registry(potable_water_nist)\n\
                   medium ShopAir: gas\n\
                   \x20   props: registry(air_nist)\n\
                   part AirLine:\n\
                   \x20   impl FluidPort<medium=ShopAir, dia=12mm> for self as vent:\n\
                   \x20       bore = turned.inlet\n\
                   flownet Mixed(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       bad: Pipe(from=AirLine.vent) (a -> b)\n";
        let diags = codes(src);
        assert!(
            diags.contains(&"E0210".to_string()),
            "expected E0210: {diags:?}"
        );
    }

    /// The honest-pass sibling: `SupplyLine`'s `FluidPort` binding
    /// agrees with `Loop`'s own header medium, so E0210 stays silent.
    /// Mirrors `examples/tracks/fluorite/medium_binding_ok.fluo`.
    #[test]
    fn matching_fluidport_binding_is_clean() {
        let src = "medium Water: liquid\n\
                   \x20   props: registry(potable_water_nist)\n\
                   part SupplyLine:\n\
                   \x20   impl FluidPort<medium=Water, dia=12mm> for self as feed:\n\
                   \x20       bore = turned.inlet\n\
                   flownet Loop(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       supply: Pipe(from=SupplyLine.feed) (a -> b)\n";
        let diags = codes(src);
        assert!(
            !diags.contains(&"E0210".to_string()),
            "expected no E0210: {diags:?}"
        );
    }

    /// fluorite/02 sec. 2's own POSITIONAL spelling (`impl
    /// FluidPort<RP1, dia 12mm>` -- the first generic arg binds the
    /// interface's first declared param, `m: medium`) resolves the
    /// medium exactly like the keyword form.
    #[test]
    fn positional_fluidport_binding_flags_e0204() {
        let src = "part FuelTube:\n\
                   \x20   impl FluidPort<RP1, dia 12mm> for self as fuel_in:\n\
                   \x20       bore = turned.inlet\n\
                   flownet Feed(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       feed: Pipe(from=FuelTube.fuel_in) (a -> b)\n";
        let diags = codes(src);
        assert!(
            diags.contains(&"E0210".to_string()),
            "expected E0210: {diags:?}"
        );
    }

    /// A `from=` ref naming a component with NO `FluidPort` binding at
    /// all (the whole existing fluorite corpus, single-medium
    /// throughout): the check has nothing to compare against and stays
    /// silent -- no false positive on ordinary geometry-only edges.
    #[test]
    fn unbound_component_is_not_flagged() {
        let src = "flownet Loop(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       pipe: Pipe(from=line.run) (a -> b)\n";
        let diags = codes(src);
        assert!(
            !diags.contains(&"E0210".to_string()),
            "expected no E0210: {diags:?}"
        );
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
