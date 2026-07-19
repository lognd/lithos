//! Pass 3 (converter-graph half): build the continuous/discrete
//! converter graph (INV-16) from the now-typed elec behavioral bodies and
//! run the within-domain acyclicity check.
//!
//! Regolith reference: `docs/spec/cuprite/03-behavioral-layer.md` sec. 1/1a
//! (event-bounded hybrid semantics, the ZOH delta-by-type rule),
//! `docs/spec/regolith/13` INV-16 (converter non-instantaneity). WO-05 now
//! types the elec spec bodies: `ports:`/`spec:` blocks (as `Field`s with
//! bodies), converter/combinational assignments (`x = adc(...)` /
//! `x = expr` as `CtorStmt`), and clocked `on <event>:` bodies (`OnBlock`)
//! with non-blocking register updates (`RegAssign`). This is the caller
//! `regolith_sem::converter` never had: it feeds those typed nodes into a
//! per-declaration `ConverterGraph` and runs `check_acyclic()`.
//!
//! Domain assignment (a partition, cuprite/03 sec. 1a) is derived by type,
//! not causality analysis:
//!
//! - a `clock(...)` port declares a clock domain named by the port; every
//!   other port is a continuous signal;
//! - an `adc`/`comparator` output lives in its sample clock's domain; a
//!   `dac`/`pwm` output drives the continuous plant;
//! - any signal assigned inside `on <clk>.<edge>:` lives in `clk`'s domain;
//! - a remaining combinational assignment inherits the domain of a
//!   referenced signal (fixpoint), defaulting to continuous.
//!
//! Edge kind is likewise fixed by type: an `adc`/`dac`/`comparator`/`pwm`
//! assignment is a `Converter` edge (a ZOH delta), a `<=` register update
//! is a `Register` edge (a delta), and every other `=` relation is a
//! `Combinational` edge. The check is SOUND (under-approximate): only
//! same-domain combinational edges can form a flagged cycle, so a loop a
//! converter or register already breaks is never a false E0105, and a
//! continuous DAE derivative relation (`x ' = ...`, still an
//! `OpaqueIsland` -- a tracked cut) contributes no edge, never a false
//! positive.

use std::collections::{BTreeMap, BTreeSet};

use indexmap::IndexMap;
use regolith_diag::Diagnostic;
use regolith_sem::{ConverterGraph, Domain, EdgeKind};
use regolith_syntax::ast::{AstNode, CtorStmt, Decl, Field, File, OnBlock, RegAssign};
use regolith_syntax::cst::{SyntaxElement, SyntaxNode};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// The converter port words whose assignment is a ZOH delta crossing the
/// continuous/discrete boundary (cuprite/03 sec. 1). `adc`/`comparator`
/// sample the continuous plant into a clock domain; `dac`/`pwm` drive the
/// continuous plant from a clock domain.
const CONVERTER_WORDS: [&str; 4] = ["adc", "comparator", "dac", "pwm"];

/// The converter words whose output lives in the continuous domain (they
/// drive the plant); the others (`adc`/`comparator`) sample into a clock.
const CONTINUOUS_OUTPUT_WORDS: [&str; 2] = ["dac", "pwm"];

/// Build and check the INV-16 converter graph over every non-poisoned
/// declaration across `files`, returning the collected E0105 diagnostics
/// in file-then-source order (AD-6). Poisoned subjects are skipped
/// (INV-20 gating).
#[must_use]
// frob:doc docs/modules/regolith-lower.md#converter
pub fn run_converter_check(files: &[ParsedFile]) -> Vec<Diagnostic> {
    let span = tracing::info_span!("lower.converter");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            diagnostics.extend(check_decl(&decl, &name));
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "INV-16 converter-graph acyclicity check complete"
    );
    diagnostics
}

/// One behavioral assignment lowered from a typed CST node.
struct Assign {
    /// The target signal name.
    lhs: String,
    /// The value node (the right-hand side expression).
    value: Option<SyntaxNode>,
    /// The edge kind every incoming dependency of this assignment carries.
    kind: EdgeKind,
    /// The clock domain if the assignment is inside an `on <clk>:` body.
    on_clock: Option<String>,
    /// The converter word, if the value is a converter call (fixes the
    /// output domain: `adc`/`comparator` -> sample clock, `dac`/`pwm` ->
    /// continuous).
    converter: Option<String>,
}

/// Check one declaration's spec: build its converter graph and run the
/// within-domain acyclicity check (E0105 per combinational cycle).
fn check_decl(decl: &Decl, scope_name: &str) -> Vec<Diagnostic> {
    match build_decl_graph(decl, scope_name) {
        Some(graph) => graph.check_acyclic(),
        None => Vec::new(),
    }
}

/// Build one declaration's converter graph from its typed `spec:` body
/// (`None` when the declaration has no `spec:` -- nothing behavioral to
/// graph). The ONE graph-construction site (AD-22): both the INV-16
/// acyclicity check ([`check_decl`]) and the WO-88 payload collector
/// ([`collect_converter_graphs`]) read the result, so the domain
/// partition and edge-kind rules live in exactly one place.
#[must_use]
// frob:doc docs/modules/regolith-lower.md#converter
// frob:waive TEST001 reason="internal pass-pipeline helper exercised transitively through the crate's lower()/lower_and_discharge() pipeline tests; no isolated unit test calls it directly"
pub fn build_decl_graph(decl: &Decl, scope_name: &str) -> Option<ConverterGraph> {
    let spec = named_block(decl, "spec")?;

    // Ports: clock ports declare clock domains; other ports are
    // continuous signals. Both are graph nodes.
    let mut port_domains: BTreeMap<String, Domain> = BTreeMap::new();
    if let Some(ports) = named_block(decl, "ports") {
        for field in ports.syntax().children().filter_map(Field::cast) {
            let name = field.name();
            if name.is_empty() {
                continue;
            }
            let domain = if value_head_name(field.value().as_ref()).as_deref() == Some("clock") {
                Domain::Clock(name.clone())
            } else {
                Domain::Continuous
            };
            port_domains.insert(name, domain);
        }
    }

    // Collect the behavioral assignments in the spec (converter/
    // combinational `=` ctors and `<=` register assigns), tagging each
    // with its enclosing `on <clk>:` clock (if any).
    let assigns = collect_assigns(&spec);

    // The defined-signal set: every port plus every assignment target.
    // Only these become graph nodes and only references to these become
    // edges, so units/constants/parameter names contribute nothing.
    let mut defined: BTreeSet<String> = BTreeSet::new();
    for name in port_domains.keys() {
        defined.insert(name.clone());
    }
    for a in &assigns {
        if !a.lhs.is_empty() {
            defined.insert(a.lhs.clone());
        }
    }

    let domains = assign_domains(&port_domains, &assigns, &defined);

    // Build the graph: a node per defined signal (deterministic sorted
    // order), then an edge per (defined) reference of each assignment.
    let mut graph = ConverterGraph::new();
    let mut ids: BTreeMap<String, usize> = BTreeMap::new();
    for (name, domain) in &domains {
        let id = graph.add_node(name.clone(), domain.clone());
        ids.insert(name.clone(), id);
    }
    for a in &assigns {
        let Some(&to) = ids.get(&a.lhs) else {
            continue;
        };
        for r in refs_in(a.value.as_ref(), &defined) {
            let Some(&from) = ids.get(&r) else { continue };
            graph.add_edge(from, to, a.kind);
        }
    }

    tracing::debug!(
        scope = %scope_name,
        nodes = graph.nodes.len(),
        edges = graph.edges.len(),
        "converter graph built from spec"
    );
    Some(graph)
}

/// Collect the converter graph of every non-poisoned declaration that
/// has a behavioral `spec:` body, keyed by declaration name in file then
/// source order (AD-6), skipping empty graphs (a `spec:` with no
/// converter/combinational/register assignment and no ports contributes
/// nothing to evaluate). This is WO-88's FFI crossing: the graph WO-36
/// builds and checks Rust-side now also rides `BuildPayload.
/// converter_graphs` so a Python harness model (the buck family) can
/// resolve a behavioral body's topology instead of taking it hand-
/// supplied. Poisoned subjects are skipped (INV-20 gating), matching
/// [`run_converter_check`].
#[must_use]
// frob:doc docs/modules/regolith-lower.md#converter
pub fn collect_converter_graphs(files: &[ParsedFile]) -> IndexMap<String, ConverterGraph> {
    let span = tracing::info_span!("lower.converter.collect");
    let _enter = span.enter();

    let mut out: IndexMap<String, ConverterGraph> = IndexMap::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            let Some(graph) = build_decl_graph(&decl, &name) else {
                continue;
            };
            if graph.nodes.is_empty() {
                continue;
            }
            out.insert(name, graph);
        }
    }
    tracing::debug!(
        graphs = out.len(),
        "WO-88: converter graphs collected for the build payload"
    );
    out
}

/// Assign a domain to every defined signal (cuprite/03 sec. 1a). Ports
/// and converter/on-body outputs are seeded directly; remaining
/// combinational targets inherit a referenced signal's domain by fixpoint,
/// defaulting to continuous. Returns a deterministic (sorted) map.
fn assign_domains(
    port_domains: &BTreeMap<String, Domain>,
    assigns: &[Assign],
    defined: &BTreeSet<String>,
) -> BTreeMap<String, Domain> {
    let mut domains: BTreeMap<String, Domain> = port_domains.clone();

    // Seed the directly-typed domains.
    for a in assigns {
        if a.lhs.is_empty() {
            continue;
        }
        let seeded = match (&a.converter, &a.on_clock) {
            (Some(word), _) if CONTINUOUS_OUTPUT_WORDS.contains(&word.as_str()) => {
                Some(Domain::Continuous)
            }
            (Some(_word), _) => sample_clock(a.value.as_ref()).map(Domain::Clock),
            (None, Some(clk)) => Some(Domain::Clock(clk.clone())),
            (None, None) => None,
        };
        if let Some(domain) = seeded {
            domains.insert(a.lhs.clone(), domain);
        }
    }

    // Fixpoint: a still-unassigned combinational target inherits the
    // domain of a referenced signal that already has one.
    loop {
        let mut changed = false;
        for a in assigns {
            if a.lhs.is_empty() || domains.contains_key(&a.lhs) {
                continue;
            }
            for r in refs_in(a.value.as_ref(), defined) {
                if let Some(domain) = domains.get(&r).cloned() {
                    domains.insert(a.lhs.clone(), domain);
                    changed = true;
                    break;
                }
            }
        }
        if !changed {
            break;
        }
    }

    // Anything still unresolved is continuous by default.
    for name in defined {
        domains.entry(name.clone()).or_insert(Domain::Continuous);
    }
    domains
}

/// Collect every behavioral assignment inside `spec`, in source order.
/// A `CtorStmt` whose value is a converter call is a `Converter` edge; a
/// `RegAssign` (`<=`) is a `Register` edge; every other `CtorStmt` is a
/// `Combinational` edge. Each is tagged with its enclosing `on <clk>:`
/// clock, if any.
fn collect_assigns(spec: &Field) -> Vec<Assign> {
    let mut out = Vec::new();
    for node in spec.syntax().descendants() {
        if let Some(ctor) = CtorStmt::cast(node.clone()) {
            let value = ctor.value();
            let converter =
                value_head_name(value.as_ref()).filter(|h| CONVERTER_WORDS.contains(&h.as_str()));
            let kind = if converter.is_some() {
                EdgeKind::Converter
            } else {
                EdgeKind::Combinational
            };
            out.push(Assign {
                lhs: ctor.name(),
                value,
                kind,
                on_clock: enclosing_on_clock(&node),
                converter,
            });
        } else if let Some(reg) = RegAssign::cast(node.clone()) {
            out.push(Assign {
                lhs: reg.name(),
                value: reg.value(),
                kind: EdgeKind::Register,
                on_clock: enclosing_on_clock(&node),
                converter: None,
            });
        }
    }
    out
}

/// Every `on <event>:` trigger name declared per subject, across
/// `files` (WO-37 close-out follow-up, `TODO.md`: promotes
/// `regolith.realizer.firmware.contract.EventDecl` off its
/// forward-authored placeholder per AD-22 -- the firmware realizer's
/// event surface now reads this typed `OnBlock` data instead of a
/// private contract). Returns deduplicated `(declaration name, event
/// name)` pairs in sorted order (AD-6 determinism); the event name is
/// the trigger's root identifier (`OnBlock::clock`), e.g. `on
/// button.press:` -> `"button"`. Poisoned subjects are skipped
/// (INV-20 gating), matching `run_converter_check`.
#[must_use]
// frob:doc docs/modules/regolith-lower.md#converter
pub fn collect_on_events(files: &[ParsedFile]) -> Vec<(String, String)> {
    let span = tracing::info_span!("lower.converter.on_events");
    let _enter = span.enter();

    let mut out: BTreeSet<(String, String)> = BTreeSet::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            let Some(spec) = named_block(&decl, "spec") else {
                continue;
            };
            for node in spec.syntax().descendants() {
                let Some(on) = OnBlock::cast(node) else {
                    continue;
                };
                if let Some(event) = on.clock() {
                    out.insert((name.clone(), event));
                }
            }
        }
    }
    tracing::debug!(events = out.len(), "typed on-event names collected");
    out.into_iter().collect()
}

/// A block declared as a `Field` whose name is `name` (`ports:`/`spec:`
/// are typed as `Field`s with indented bodies).
fn named_block(decl: &Decl, name: &str) -> Option<Field> {
    decl.syntax()
        .descendants()
        .filter_map(Field::cast)
        .find(|f| f.name() == name)
}

/// The head identifier of a value node when it is a call (`adc(...)` ->
/// `adc`, `clock(...)` -> `clock`): the first `Ident` token of a
/// `CallExpr`, or the node's own leading `Ident` for a bare name.
fn value_head_name(value: Option<&SyntaxNode>) -> Option<String> {
    let node = value?;
    let target = if node.kind() == SyntaxKind::CallExpr {
        node.clone()
    } else {
        node.descendants()
            .find(|d| d.kind() == SyntaxKind::CallExpr)
            .unwrap_or_else(|| node.clone())
    };
    target
        .descendants_with_tokens()
        .filter_map(SyntaxElement::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

/// The sample/update clock of a converter call: the root identifier of a
/// `sample=<path>` / `update=<path>` / `clk=<path>` argument
/// (`sample=ctrl_clk.rise` -> `ctrl_clk`). `None` if the call declares no
/// sampling clock.
fn sample_clock(value: Option<&SyntaxNode>) -> Option<String> {
    let node = value?;
    for bin in node
        .descendants()
        .filter(|d| d.kind() == SyntaxKind::BinExpr)
    {
        let mut idents = bin
            .descendants_with_tokens()
            .filter_map(SyntaxElement::into_token)
            .filter(|t| t.kind() == SyntaxKind::Ident)
            .map(|t| t.text().to_string());
        let key = idents.next();
        if matches!(key.as_deref(), Some("sample" | "update" | "clk")) {
            if let Some(clock) = idents.next() {
                return Some(clock);
            }
        }
    }
    None
}

/// The clock of the nearest enclosing `on <clk>.<edge>:` body, if `node`
/// is inside one.
fn enclosing_on_clock(node: &SyntaxNode) -> Option<String> {
    node.ancestors()
        .find_map(OnBlock::cast)
        .and_then(|b| b.clock())
}

/// The defined-signal references inside a value node, in source order
/// without duplicates: every `Ident` token that names a defined signal.
/// Ignores the converter head word and argument keywords (they are not
/// defined signals), so only real dependencies become edges.
fn refs_in(value: Option<&SyntaxNode>, defined: &BTreeSet<String>) -> Vec<String> {
    let Some(node) = value else {
        return Vec::new();
    };
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut out = Vec::new();
    for tok in node
        .descendants_with_tokens()
        .filter_map(SyntaxElement::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
    {
        let text = tok.text().to_string();
        if defined.contains(&text) && seen.insert(text.clone()) {
            out.push(text);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::run_converter_check;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::COMBINATIONAL_CYCLE;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.cupr");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn codes(diags: &[regolith_diag::Diagnostic]) -> Vec<regolith_diag::DiagCode> {
        diags.iter().map(|d| d.code).collect()
    }

    #[test]
    // frob:tests crates/regolith-lower/src/converter.rs::run_converter_check kind="unit"
    fn comparator_feeds_own_threshold_is_legal() {
        // INV-16 legal fixture: the feedback loop
        // vout -> cmp -> threshold -> drive -> vout passes through two
        // converters (comparator sampling the plant, dac driving it), so
        // the combinational subgraph is acyclic.
        let src = "block Regulator:\n    ports:\n        ctrl_clk: clock(200kHz)\n    spec:\n        cmp = comparator(vout, sample=ctrl_clk.rise)\n        on ctrl_clk.rise:\n            threshold = cmp\n        drive = dac(threshold, update=ctrl_clk.rise)\n        vout = drive\n";
        let diags = run_converter_check(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }

    #[test]
    fn same_domain_combinational_cycle_is_flagged() {
        // INV-16 violation: a genuine algebraic loop within one
        // (continuous) domain, no delta to break it -> E0105.
        let src = "block BadLoop:\n    spec:\n        a = b\n        b = a\n";
        let diags = run_converter_check(&parsed(src));
        assert!(codes(&diags).contains(&COMBINATIONAL_CYCLE), "{diags:?}");
    }

    #[test]
    // frob:tests crates/regolith-lower/src/converter.rs::collect_on_events kind="unit"
    fn on_event_names_collected_deduplicated_and_sorted() {
        // WO-37 close-out follow-up: `on <event>:` trigger names come
        // back per-declaration, deduplicated, in sorted order -- not
        // emission/insert order, so a caller (`regolith.compiler.
        // on_events`) never sees accidental variation (INV-10 shape).
        let src = "block Regulator:\n    ports:\n        ctrl_clk: clock(200kHz)\n    spec:\n        on ctrl_clk.rise:\n            a = b\n        on ctrl_clk.rise:\n            c = d\n";
        let events = super::collect_on_events(&parsed(src));
        assert_eq!(
            events,
            vec![("Regulator".to_string(), "ctrl_clk".to_string())]
        );
    }

    #[test]
    fn on_event_names_span_multiple_declarations() {
        let src = "block A:\n    ports:\n        clk: clock(1MHz)\n    spec:\n        on clk.rise:\n            a = b\nblock B:\n    ports:\n        btn: clock(1Hz)\n    spec:\n        on btn.rise:\n            c = d\n";
        let events = super::collect_on_events(&parsed(src));
        assert_eq!(
            events,
            vec![
                ("A".to_string(), "clk".to_string()),
                ("B".to_string(), "btn".to_string()),
            ]
        );
    }

    #[test]
    fn register_broken_loop_is_legal() {
        // A loop broken by a clocked `<=` register (a delta) is legal:
        // `a = b` is combinational, `b <= a` is a register commit.
        let src = "block RegLoop:\n    ports:\n        clk: clock(1MHz)\n    spec:\n        on clk.rise:\n            a = b\n            b <= a\n";
        let diags = run_converter_check(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }

    #[test]
    // frob:tests crates/regolith-lower/src/converter.rs::collect_converter_graphs kind="unit"
    fn collect_exposes_the_buck_topology_graph() {
        // WO-88 deliverable 2: a sampled-buck behavioral body's graph
        // rides `collect_converter_graphs`, keyed by declaration name,
        // carrying the adc sense edge (continuous -> clock) and the pwm
        // drive edge (clock -> continuous) a Python model reads for the
        // buck topology.
        let src = "block DigitalBuck:\n    ports:\n        out: supply(out)\n        ctrl_clk: clock(200kHz)\n    spec:\n        vs = adc(out, sample=ctrl_clk.rise)\n        sw = pwm(duty, update=ctrl_clk.rise)\n        on ctrl_clk.rise:\n            duty <= vs\n";
        let graphs = super::collect_converter_graphs(&parsed(src));
        let graph = graphs.get("DigitalBuck").expect("graph for DigitalBuck");
        assert!(!graph.nodes.is_empty(), "graph has nodes");
        // The graph carries at least one converter (ZOH) edge -- the
        // adc/pwm boundary crossing the buck model classifies as topology.
        assert!(
            graph
                .edges
                .iter()
                .any(|e| e.kind == regolith_sem::EdgeKind::Converter),
            "expected a converter edge in {graph:?}"
        );
    }

    #[test]
    fn collect_skips_declarations_without_a_spec_body() {
        // A structural-only block (no `spec:`) contributes no graph:
        // the payload map stays empty rather than carrying empty graphs.
        let src = "block Bracket:\n    ports:\n        a: supply(in)\n";
        assert!(super::collect_converter_graphs(&parsed(src)).is_empty());
    }
}
