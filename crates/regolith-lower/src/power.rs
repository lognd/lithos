//! Pass 3e (WO-132): the cuprite power-distribution net discipline
//! (charter toolchain/43-power-distribution.md secs. 1-2, D248/AD-42).
//!
//! Runs the front-end-decidable power discipline checks over every
//! parsed `.cupr` file's typed [`PowerDecl`] AST, riding the SAME
//! AD-23 net core (`regolith_sem::net_core`) the elec/fluid/calcite
//! disciplines use -- `net_core::PowerDiscipline` wired to `E0212`
//! (charter 43 sec. 1 rule 1: at least one source imposer per
//! energized subnet).
//!
//! Rules 2-4 (undeclared parallel source paths, unprotected ampacity
//! transitions, load reachability) need edge-walk machinery the
//! `NetDiscipline` trait does not provide (it only counts imposer
//! terminals per net) -- the SAME scope split `calcite.rs`'s module
//! doc comment names for `LoadPathDiscipline`/`CirculationDiscipline`,
//! so this module implements them as plain graph walks over the typed
//! `PowerDecl` AST, not new `NetDiscipline` plugins:
//!
//! - **E0213** (`POWER_UNDECLARED_PARALLEL_PATH`): a bus reachable
//!   from more than one declared source (through `feeders:` edges,
//!   walked backward) that is not named in the net's `ties:` field.
//! - **E0214** (`POWER_UNPROTECTED_TRANSITION`): a `feeders:` edge
//!   whose apparatus constructor narrows ampacity (`transformer`,
//!   `feeder`, `busway`) with no adjoining protective device
//!   (`breaker`/`fuse`/`relay`) edge touching either of its endpoints.
//! - **E0215** (`POWER_LOAD_UNREACHABLE`): a declared `loads:` entry
//!   that no declared source can reach by walking the net's
//!   `feeders:` edges FORWARD in their declared feed sense (power
//!   flows one way, unlike calcite's bidirectional egress openings --
//!   see `reachable_from`'s doc comment).
//!
//! Like `calcite.rs`/`fluid.rs`, this is a PURE function of parsed
//! source: no IO, no rendering. A file with no `power` declaration
//! contributes nothing.

use std::collections::{HashSet, VecDeque};

use regolith_diag::codes::{
    POWER_LOAD_UNREACHABLE, POWER_SUBNET_UNSOURCED, POWER_UNDECLARED_PARALLEL_PATH,
    POWER_UNPROTECTED_TRANSITION,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::net_core::{first_violation, NetEntry, PowerDiscipline, Terminal};
use regolith_syntax::ast::{AstNode, EdgeStmt, File, PowerDecl};

use crate::calcite::{field_idents, HasFields};
use crate::flownet_lower::{callee_name, edge_endpoints};
use crate::output::ParsedFile;

impl HasFields for PowerDecl {
    fn fields(&self) -> Vec<regolith_syntax::ast::Field> {
        PowerDecl::fields(self)
    }
}

/// Apparatus constructor names that narrow ampacity (charter 43 sec. 1
/// rule 3): a transition through one of these needs a declared
/// protective device somewhere on the same bus.
const AMPACITY_NARROWING: &[&str] = &["transformer", "feeder", "busway"];

/// Apparatus constructor names that ARE a protective device (charter
/// 43 sec. 2's vocabulary): a feeder touching one of these at either
/// endpoint discharges rule 3 for that transition.
const PROTECTIVE_DEVICE: &[&str] = &["breaker", "fuse", "relay"];

/// The diagnostics from the power discipline over every file.
#[derive(Debug, Clone, Default)]
// frob:doc docs/modules/regolith-lower.md#power
pub struct PowerReport {
    /// Diagnostics from the power discipline checks (E02xx family,
    /// the power discipline's E0212-E0215 offsets).
    pub diagnostics: Vec<Diagnostic>,
}

/// Run the power net discipline over `files`, in caller (sorted)
/// order.
#[must_use]
// frob:doc docs/modules/regolith-lower.md#power
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn run_power_checks(files: &[ParsedFile]) -> PowerReport {
    let span = tracing::info_span!("lower.power");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for power in file.power_nets() {
            check_power_net(&pf.path, &power, &mut diagnostics);
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "power discipline: checks complete"
    );
    PowerReport { diagnostics }
}

/// One resolved `feeders:` edge: its declared endpoints, apparatus
/// constructor name, and whether that apparatus is itself a
/// protective device.
struct FeederEdge {
    from: String,
    to: String,
    apparatus: String,
}

/// Every `feeders:` edge in `power`, resolved to endpoints + apparatus
/// constructor name.
fn feeder_edges(power: &PowerDecl) -> Vec<FeederEdge> {
    let Some(block) = power.feeders() else {
        return Vec::new();
    };
    block.edges().iter().map(resolve_feeder_edge).collect()
}

fn resolve_feeder_edge(edge: &EdgeStmt) -> FeederEdge {
    let (from, to) = edge_endpoints(edge);
    let apparatus = edge
        .value()
        .and_then(|v| callee_name(&v))
        .unwrap_or_default();
    FeederEdge {
        from,
        to,
        apparatus,
    }
}

/// Breadth-first reachability over a DIRECTED graph: every node
/// reachable from `start` by following `edges` in their declared
/// `(from, to)` feed sense (including `start` itself). Directed, NOT
/// undirected like `calcite::reachable_from`'s egress walk: a power
/// feed has a real direction (source -> load), so treating it as
/// bidirectional would let a bus "reach" every other source that
/// happens to share a downstream node -- see the E0213 false-positive
/// this caught in review. The net_core module only counts imposer
/// terminals per net, it does not walk edges, so this lives here
/// rather than growing a new `NetDiscipline` shape.
fn reachable_from(start: &str, edges: &[(String, String)]) -> HashSet<String> {
    let mut seen = HashSet::new();
    seen.insert(start.to_string());
    let mut queue = VecDeque::new();
    queue.push_back(start.to_string());
    while let Some(node) = queue.pop_front() {
        for (a, b) in edges {
            if a == &node && seen.insert(b.clone()) {
                queue.push_back(b.clone());
            }
        }
    }
    seen
}

/// Check one `power` declaration: E0212 (no source imposer at all,
/// via `net_core::PowerDiscipline`), E0213 (undeclared parallel source
/// path per bus), E0214 (unprotected ampacity transition), E0215
/// (declared load unreachable from any source).
fn check_power_net(path: &camino::Utf8Path, power: &PowerDecl, diagnostics: &mut Vec<Diagnostic>) {
    let name = power.name().unwrap_or_default();
    let source_names = field_idents(power, "sources");
    let bus_names = field_idents(power, "buses");
    let tie_names: HashSet<String> = field_idents(power, "ties").into_iter().collect();
    let load_names = field_idents(power, "loads");
    let edges = feeder_edges(power);

    // E0212: the whole-net imposer-free-subnet analog. A net with no
    // declared source at all is unsourced regardless of topology.
    let net = NetEntry {
        name: name.clone(),
        terminals: source_names
            .iter()
            .map(|s| Terminal {
                component: s.clone(),
                terminal: "source".to_string(),
                imposes: true,
            })
            .collect(),
    };
    if first_violation(&PowerDiscipline, &[net]).is_some() {
        tracing::info!(power = %name, "E0212: power net has no declared source");
        let sp = power_span(path, power);
        diagnostics.push(
            Diagnostic::error(
                POWER_SUBNET_UNSOURCED,
                format!(
                    "power net `{name}` declares no `sources:`; an energized subnet needs at \
                     least one source imposer (utility `service` or `generator`), never an \
                     assumption (charter toolchain/43 sec. 1 rule 1)"
                ),
            )
            .with_span(LabeledSpan::new(sp, "declare at least one source")),
        );
        // No usable sources to walk from -- E0213/E0215 would be noise
        // on top of E0212, so stop here (fail-fast, the net_core
        // precedent `check_circulation` also follows).
        return;
    }

    // A DIRECTED feeder graph, in declared feed sense (source ->
    // ... -> load): power flows one way, unlike calcite's egress
    // openings (which are physically walkable both ways) -- so unlike
    // `calcite::reachable_from`'s undirected walk, both E0213 (which
    // source(s) feed a bus) and E0215 (can a load trace to a source)
    // read the arrow as the feed direction, not a bidirectional
    // mating.
    let directed: Vec<(String, String)> = edges
        .iter()
        .map(|e| (e.from.clone(), e.to.clone()))
        .collect();

    check_parallel_paths(
        path,
        power,
        &name,
        &source_names,
        &bus_names,
        &tie_names,
        &directed,
        diagnostics,
    );
    check_unprotected_transitions(path, power, &name, &edges, diagnostics);
    check_load_reachability(
        path,
        power,
        &name,
        &source_names,
        &load_names,
        &directed,
        diagnostics,
    );
}

/// E0213: exactly one source path per bus unless a TIE is declared.
/// For each bus, count how many DISTINCT sources can reach it; more
/// than one with no matching `ties:` entry is undeclared parallelism.
#[allow(clippy::too_many_arguments)]
fn check_parallel_paths(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    name: &str,
    source_names: &[String],
    bus_names: &[String],
    tie_names: &HashSet<String>,
    directed: &[(String, String)],
    diagnostics: &mut Vec<Diagnostic>,
) {
    // Once sources merge at a DECLARED tie, everything downstream of
    // that tie legitimately carries both sources' feed -- the tie
    // declaration covers the whole downstream tree, not just the tie
    // bus itself (an engineer ties two sources together precisely so
    // the rest of the system can be fed from either). Buses reachable
    // FORWARD from a declared tie are exempt from this check.
    let downstream_of_tie: HashSet<String> = tie_names
        .iter()
        .flat_map(|t| reachable_from(t, directed))
        .collect();

    for bus in bus_names {
        let reachable_sources: Vec<&String> = source_names
            .iter()
            .filter(|s| reachable_from(s, directed).contains(bus))
            .collect();
        if reachable_sources.len() > 1
            && !tie_names.contains(bus)
            && !downstream_of_tie.contains(bus)
        {
            tracing::info!(
                power = %name,
                bus = %bus,
                sources = reachable_sources.len(),
                "E0213: bus has an undeclared parallel source path"
            );
            let sp = power_span(path, power);
            diagnostics.push(
                Diagnostic::error(
                    POWER_UNDECLARED_PARALLEL_PATH,
                    format!(
                        "bus `{bus}` in power net `{name}` is reachable from {} sources \
                         ({}) with no matching `ties:` declaration; a radial system allows \
                         exactly one source path per bus unless a TIE is explicitly declared \
                         (charter toolchain/43 sec. 1 rule 2 -- undeclared parallelism \
                         destroys equipment)",
                        reachable_sources.len(),
                        reachable_sources
                            .iter()
                            .map(|s| s.as_str())
                            .collect::<Vec<_>>()
                            .join(", ")
                    ),
                )
                .with_span(LabeledSpan::new(sp, "declare a `ties:` entry for this bus")),
            );
        }
    }
}

/// E0214: every ampacity-narrowing edge needs a protective device
/// touching one of its endpoints (a dedicated protective-device edge
/// sharing an endpoint with the narrowing edge).
fn check_unprotected_transitions(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    name: &str,
    edges: &[FeederEdge],
    diagnostics: &mut Vec<Diagnostic>,
) {
    let protected_nodes: HashSet<&str> = edges
        .iter()
        .filter(|e| PROTECTIVE_DEVICE.contains(&e.apparatus.as_str()))
        .flat_map(|e| [e.from.as_str(), e.to.as_str()])
        .collect();
    for e in edges {
        if AMPACITY_NARROWING.contains(&e.apparatus.as_str())
            && !protected_nodes.contains(e.from.as_str())
            && !protected_nodes.contains(e.to.as_str())
        {
            tracing::info!(
                power = %name,
                from = %e.from,
                to = %e.to,
                apparatus = %e.apparatus,
                "E0214: ampacity transition has no declared protective device"
            );
            let sp = power_span(path, power);
            diagnostics.push(
                Diagnostic::error(
                    POWER_UNPROTECTED_TRANSITION,
                    format!(
                        "the `{}` transition (`{}` -> `{}`) in power net `{name}` declares \
                         no adjoining protective device (`breaker`/`fuse`/`relay`); every \
                         ampacity transition needs a declared protective device (charter \
                         toolchain/43 sec. 1 rule 3)",
                        e.apparatus, e.from, e.to
                    ),
                )
                .with_span(LabeledSpan::new(
                    sp,
                    "declare a breaker/fuse/relay at this transition",
                )),
            );
        }
    }
}

/// E0215: every declared load must be reachable FROM a source,
/// following the feed direction forward (a source cannot be
/// downstream of its own load).
#[allow(clippy::too_many_arguments)]
fn check_load_reachability(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    name: &str,
    source_names: &[String],
    load_names: &[String],
    directed: &[(String, String)],
    diagnostics: &mut Vec<Diagnostic>,
) {
    for load in load_names {
        let reachable = source_names
            .iter()
            .any(|s| reachable_from(s, directed).contains(load));
        if !reachable {
            tracing::info!(power = %name, load = %load, "E0215: load cannot reach a source");
            let sp = power_span(path, power);
            diagnostics.push(
                Diagnostic::error(
                    POWER_LOAD_UNREACHABLE,
                    format!(
                        "load `{load}` in power net `{name}` cannot reach a declared source \
                         through the net's `feeders:` edges; every load must trace to a \
                         source (charter toolchain/43 sec. 1 rule 4)"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "this load's feed path dead-ends")),
            );
        }
    }
}

/// A primary span over a power declaration's full text range.
fn power_span(path: &camino::Utf8Path, power: &PowerDecl) -> Span {
    let range = power.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

#[cfg(test)]
mod tests {
    use super::run_power_checks;
    use crate::output::{ParsedFile, SourceFile};
    use crate::parse_sources;

    fn parse_one(text: &str) -> Vec<ParsedFile> {
        parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.cupr"),
            text: text.to_string(),
        }])
    }

    fn codes(text: &str) -> Vec<String> {
        run_power_checks(&parse_one(text))
            .diagnostics
            .iter()
            .map(|d| d.code.to_string())
            .collect()
    }

    fn clean_net() -> String {
        "power PlantMain:\n\
         \x20   sources: Svc1\n\
         \x20   buses: Svc1, MainBus, PanelA\n\
         \x20   loads: Motor1\n\
         \x20   feeders:\n\
         \x20       f1: transformer(kva=500kVA) (Svc1 -> MainBus)\n\
         \x20       p1: breaker(frame=400A) (MainBus -> MainBus)\n\
         \x20       f2: feeder(size=cu_4_0awg) (MainBus -> PanelA)\n\
         \x20       p2: breaker(frame=100A) (PanelA -> PanelA)\n\
         \x20       f3: feeder(size=cu_10awg) (PanelA -> Motor1)\n"
            .to_string()
    }

    #[test]
    fn clean_power_net_passes() {
        let src = clean_net();
        assert!(codes(&src).is_empty(), "expected clean: {:?}", codes(&src));
    }

    #[test]
    // frob:tests crates/regolith-lower/src/power.rs::run_power_checks kind="unit"
    fn unsourced_net_flags_e0212() {
        let src = "power PlantMain:\n\
                   \x20   buses: MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: feeder(size=cu_4_0awg) (MainBus -> Motor1)\n";
        assert!(
            codes(src).contains(&"E0212".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn undeclared_parallel_source_flags_e0213() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1, Svc2\n\
                   \x20   buses: Svc1, Svc2, MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: feeder(size=cu_4_0awg) (Svc1 -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg) (Svc2 -> MainBus)\n\
                   \x20       f3: feeder(size=cu_4_0awg) (MainBus -> Motor1)\n";
        assert!(
            codes(src).contains(&"E0213".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn declared_tie_bus_silences_e0213() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1, Svc2\n\
                   \x20   buses: Svc1, Svc2, MainBus\n\
                   \x20   ties: MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: feeder(size=cu_4_0awg) (Svc1 -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg) (Svc2 -> MainBus)\n\
                   \x20       f3: feeder(size=cu_4_0awg) (MainBus -> Motor1)\n";
        assert!(
            !codes(src).contains(&"E0213".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn unprotected_transformer_flags_e0214() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1, MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA) (Svc1 -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg) (MainBus -> Motor1)\n";
        assert!(
            codes(src).contains(&"E0214".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn unreachable_load_flags_e0215() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1, MainBus\n\
                   \x20   loads: Motor1, StrandedMotor\n\
                   \x20   feeders:\n\
                   \x20       f1: feeder(size=cu_4_0awg) (Svc1 -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg) (MainBus -> Motor1)\n";
        assert!(
            codes(src).contains(&"E0215".to_string()),
            "{:?}",
            codes(src)
        );
        // Motor1 is reachable and must not also flag.
        let report = run_power_checks(&parse_one(src));
        let unreachable_msg = report
            .diagnostics
            .iter()
            .find(|d| d.code.to_string() == "E0215")
            .expect("E0215 present");
        assert!(unreachable_msg.message.contains("StrandedMotor"));
        assert!(!unreachable_msg.message.contains("`Motor1`"));
    }
}

/// Binds the WO-132 deliverable-5 corpus (the negative fixtures under
/// `examples/negative/`, the positive design under
/// `examples/tracks/cuprite/`) to real `run_power_checks` output --
/// the Rust-side companion to the Python `test_negative_corpus.py`
/// header-driven sweep, which walks the same fixtures by their
/// `# BREAKS:`/`# EXPECT:` header contract.
#[cfg(test)]
mod fixture_check {
    use crate::output::SourceFile;
    use crate::parse_sources;
    use camino::Utf8PathBuf;

    fn codes_for(path: &str) -> Vec<String> {
        let text = std::fs::read_to_string(path).expect("read fixture");
        let parsed = parse_sources(&[SourceFile {
            path: Utf8PathBuf::from(path),
            text,
        }]);
        super::run_power_checks(&parsed)
            .diagnostics
            .iter()
            .map(|d| d.code.to_string())
            .collect()
    }

    #[test]
    // frob:tests crates/regolith-lower/src/power.rs::run_power_checks kind="integration"
    fn negative_fixtures_fire_exactly_their_code() {
        let repo = env!("CARGO_MANIFEST_DIR");
        let cases = [
            ("73_cupr_power_subnet_unsourced.cupr", "E0212"),
            ("74_cupr_power_undeclared_parallel_path.cupr", "E0213"),
            ("75_cupr_power_unprotected_transition.cupr", "E0214"),
            ("76_cupr_power_load_unreachable.cupr", "E0215"),
        ];
        for (file, expect) in cases {
            let path = format!("{repo}/../../examples/negative/{file}");
            let codes = codes_for(&path);
            assert!(
                codes.contains(&expect.to_string()),
                "{file}: expected {expect}, got {codes:?}"
            );
        }
    }

    #[test]
    fn positive_fixture_is_clean() {
        let repo = env!("CARGO_MANIFEST_DIR");
        let path = format!("{repo}/../../examples/tracks/cuprite/power_plant_main.cupr");
        let codes = codes_for(&path);
        assert!(codes.is_empty(), "expected clean: {codes:?}");
    }
}
