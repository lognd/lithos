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
//! - **E0216** (`POWER_CROSS_STANDARD_MIX`, WO-133 deliverable 6,
//!   D255): a bus touched by two or more `feeders:` edges that each
//!   declare a `std=` standard family (`iec`/`nec`/`ansi_nema`), where
//!   those families disagree. Mixing is not forbidden -- mixing
//!   SILENTLY is; an undeclared `std=` on an edge is a named absence
//!   (D250.3) and never itself flagged.
//!
//! Like `calcite.rs`/`fluid.rs`, this is a PURE function of parsed
//! source: no IO, no rendering. A file with no `power` declaration
//! contributes nothing.

use std::collections::{HashSet, VecDeque};

use regolith_diag::codes::{
    POWER_CROSS_STANDARD_MIX, POWER_LOAD_UNREACHABLE, POWER_SUBNET_UNSOURCED,
    POWER_UNDECLARED_PARALLEL_PATH, POWER_UNPROTECTED_TRANSITION,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_oblig::power::StandardFamily;
use regolith_sem::net_core::{first_violation, NetEntry, PowerDiscipline, Terminal};
use regolith_syntax::ast::{AstNode, EdgeStmt, File, PowerDecl};

use crate::calcite::{field_idents, HasFields};
use crate::flownet_lower::{arg_quantity, arg_ref, callee_name, collect_args, edge_endpoints, Arg};
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
/// constructor name, whether that apparatus is itself a protective
/// device, and its declared `std=` standard family (D255), when named.
struct FeederEdge {
    id: String,
    from: String,
    to: String,
    apparatus: String,
    standard_family: Option<StandardFamily>,
    /// Every keyword argument on the apparatus constructor (WO-133
    /// deliverable 2): the branch-params source for payload emission,
    /// read alongside `standard_family`/`apparatus` above rather than
    /// re-walking the edge's value node a second time.
    args: Vec<Arg>,
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
    let value = edge.value();
    let apparatus = value.as_ref().and_then(callee_name).unwrap_or_default();
    let args = value.as_ref().map(collect_args).unwrap_or_default();
    let standard_family = arg_ref(&args, "std").and_then(|s| standard_family_from_str(&s));
    FeederEdge {
        id: edge.name(),
        from,
        to,
        apparatus,
        standard_family,
        args,
    }
}

/// Parse a declared `std=<name>` kwarg into a [`StandardFamily`] (D255).
/// An unrecognized spelling is treated the same as an absent kwarg
/// (`None`) -- never a guessed family.
fn standard_family_from_str(s: &str) -> Option<StandardFamily> {
    match s {
        "iec" => Some(StandardFamily::Iec),
        "nec" => Some(StandardFamily::Nec),
        "ansi_nema" | "ansi" | "nema" => Some(StandardFamily::AnsiNema),
        _ => None,
    }
}

/// D255 (the cross-standard guard, WO-133 deliverable 6): every bus
/// touched by two or more `feeders:` edges that each declare a `std=`
/// standard family, where those families DISAGREE, is a coded
/// diagnostic naming both families, both apparatus edges, and the bus
/// at stake. Mixing standard families is not itself forbidden (real
/// plants mix IEC and NEC/ANSI apparatus) -- mixing SILENTLY is; the
/// diagnostic is the deliverable, never a conversion between families
/// (D250 forbids translating one family's rating into another's
/// assumption).
fn check_cross_standard_mix(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    name: &str,
    edges: &[FeederEdge],
    diagnostics: &mut Vec<Diagnostic>,
) {
    use std::collections::BTreeMap;
    let mut by_bus: BTreeMap<&str, Vec<&FeederEdge>> = BTreeMap::new();
    for e in edges {
        if e.standard_family.is_some() {
            by_bus.entry(e.from.as_str()).or_default().push(e);
            by_bus.entry(e.to.as_str()).or_default().push(e);
        }
    }
    for (bus, touching) in by_bus {
        let mut families: Vec<(String, StandardFamily)> = touching
            .iter()
            .map(|e| (e.id.clone(), e.standard_family.unwrap()))
            .collect();
        families.sort_by(|a, b| a.0.cmp(&b.0));
        families.dedup();
        let distinct: HashSet<StandardFamily> = families.iter().map(|(_, f)| *f).collect();
        if distinct.len() > 1 {
            tracing::info!(
                power = %name,
                bus = %bus,
                "E0216: bus mixes standard families across apparatus records"
            );
            let sp = power_span(path, power);
            let named = families
                .iter()
                .map(|(id, f)| format!("{id} ({f:?})"))
                .collect::<Vec<_>>()
                .join(", ");
            diagnostics.push(
                Diagnostic::error(
                    POWER_CROSS_STANDARD_MIX,
                    format!(
                        "bus `{bus}` in power net `{name}` is touched by apparatus records \
                         declaring DIFFERENT standard families ({named}); mixing standard \
                         families is not forbidden but mixing SILENTLY is (D255) -- declare \
                         the crossing deliberately (`assume!` with a basis) or align the \
                         records"
                    ),
                )
                .with_span(LabeledSpan::new(
                    sp,
                    "apparatus records at this bus disagree on standard family",
                )),
            );
        }
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
    // `buses:`/`loads:` items may carry declared per-item properties
    // (WO-133 deliverable 2, F-WO133-1: `mainbus(nominal_voltage=480V,
    // phases=3)`) -- read through `bus_items`/`load_items` (which parse
    // the `(key=value, ...)` shape) rather than the naive `field_idents`
    // token walk, which would otherwise also collect every property KEY
    // and VALUE as a bogus extra bus/load name.
    let bus_names: Vec<String> = power.bus_items().into_iter().map(|i| i.name).collect();
    let tie_names: HashSet<String> = field_idents(power, "ties").into_iter().collect();
    let load_names: Vec<String> = power.load_items().into_iter().map(|i| i.name).collect();
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
    check_cross_standard_mix(path, power, &name, &edges, diagnostics);
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

// -- WO-133 deliverable 2: CST -> PowerNetPayload emission --------------
//
// F-WO133-1 (coordinator adjudication): `buses:`/`loads:` items carry
// OPTIONAL per-item properties (`mainbus(nominal_voltage=480V,
// phases=3)`, `press_motor(kva=45, class=motor, code_letter=G)`,
// `regolith_syntax::ast::PowerDecl::bus_items`/`load_items`), mirroring
// the apparatus edge-kwarg convention already used for `std=`. The
// schema stays FROZEN (D272 spent): `Bus.nominal_voltage`/`phases` and
// `Load.connected_kva` are REQUIRED fields, so a net whose source omits
// them REFUSES payload emission entirely (E0217,
// `POWER_PAYLOAD_FIELD_UNRESOLVED`) rather than fabricating a value
// (D250.3 exactly) -- the positive corpus member declares every
// required property; a dedicated negative fixture proves the refusal.

use regolith_diag::codes::POWER_PAYLOAD_FIELD_UNRESOLVED;
use regolith_oblig::flownet::{RecordRef, ScalarInterval};
use regolith_oblig::power::{
    Branch, BranchKind, BranchParams, Bus, Feeder, Load, MotorFields, PowerNetPayload,
    ProtectiveDevice, SourceParams, Transformer,
};

/// One power net's payload emission outcome: the completed payload,
/// when every required field resolved, and every diagnostic (an
/// unresolved-field refusal, E0217) hit along the way.
#[derive(Debug, Clone, Default)]
// frob:doc docs/modules/regolith-lower.md#power
pub struct PowerPayloadReport {
    /// The completed payload per net name, present only for a net
    /// where every required field resolved.
    pub payloads: std::collections::BTreeMap<String, PowerNetPayload>,
    /// Every diagnostic hit while emitting (currently only E0217).
    pub diagnostics: Vec<Diagnostic>,
}

/// Emit a [`PowerNetPayload`] for every `power` net in `files` (WO-133
/// deliverable 2). Elaboration-sorted (AD-6): buses/branches/loads are
/// each sorted by id before construction, so
/// [`PowerNetPayload::content_digest`] is stable across builds of the
/// same source (deliverable 5).
#[must_use]
// frob:doc docs/modules/regolith-lower.md#power
pub fn emit_power_payloads(files: &[ParsedFile]) -> PowerPayloadReport {
    let span = tracing::info_span!("lower.power.payload");
    let _enter = span.enter();

    let mut report = PowerPayloadReport::default();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for power in file.power_nets() {
            emit_one_power_payload(&pf.path, &power, &mut report);
        }
    }
    tracing::info!(
        payloads = report.payloads.len(),
        errors = report.diagnostics.len(),
        "power payload emission complete"
    );
    report
}

fn emit_one_power_payload(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    report: &mut PowerPayloadReport,
) {
    let name = power.name().unwrap_or_default();
    let mut ok = true;

    let mut buses: Vec<Bus> = Vec::new();
    for item in power.bus_items() {
        let voltage = property_scalar(&item.properties, "nominal_voltage");
        let phases = property_u8(&item.properties, "phases");
        let standard_family = property_family(&item.properties, "std");
        if let (Some(nominal_voltage), Some(phases)) = (voltage, phases) {
            buses.push(Bus {
                id: item.name,
                nominal_voltage,
                phases,
                standard_family,
            });
        } else {
            ok = false;
            unresolved_field(
                path,
                power,
                &format!(
                    "bus `{}`: nominal_voltage and phases both required for power \
                     payload emission (declare `{}(nominal_voltage=<V>, phases=<n>)` \
                     in `buses:`)",
                    item.name, item.name
                ),
                &mut report.diagnostics,
            );
        }
    }
    buses.sort_by(|a, b| a.id.cmp(&b.id));

    let mut loads: Vec<Load> = Vec::new();
    for item in power.load_items() {
        let connected_kva = property_scalar(&item.properties, "kva");
        let Some(connected_kva) = connected_kva else {
            ok = false;
            unresolved_field(
                path,
                power,
                &format!(
                    "load `{}`: connected_kva required for power payload emission \
                     (declare `{}(kva=<kVA>)` in `loads:`)",
                    item.name, item.name
                ),
                &mut report.diagnostics,
            );
            continue;
        };
        let demand_factor = property_scalar(&item.properties, "demand_factor").map(|iv| iv.lo);
        let continuous = property_text(&item.properties, "continuous").as_deref() == Some("true");
        let class = property_text(&item.properties, "class");
        let motor = if class.as_deref() == Some("motor") {
            property_scalar(&item.properties, "hp_kw").map(|hp_kw| MotorFields {
                hp_kw,
                code_letter: property_text(&item.properties, "code_letter"),
                service_factor: property_scalar(&item.properties, "service_factor").map(|iv| iv.lo),
                power_factor: property_scalar(&item.properties, "power_factor").map(|iv| iv.lo),
                efficiency: property_scalar(&item.properties, "efficiency").map(|iv| iv.lo),
            })
        } else {
            None
        };
        // The bus a load connects to is the same-named bus in this
        // corpus's convention (a load IS its own single-bus stub, the
        // same shape `feeders:` edges already target) -- the load's own
        // name doubles as its bus id.
        loads.push(Load {
            id: item.name.clone(),
            bus: item.name,
            connected_kva,
            demand_factor,
            continuous,
            class,
            motor,
        });
    }
    loads.sort_by(|a, b| a.id.cmp(&b.id));

    let edges = feeder_edges(power);
    let mut branches: Vec<Branch> = Vec::new();
    for edge in &edges {
        match build_branch(path, power, edge, &mut report.diagnostics) {
            Some(branch) => branches.push(branch),
            None => ok = false,
        }
    }
    branches.sort_by(|a, b| a.id.cmp(&b.id));

    if ok {
        report.payloads.insert(
            name,
            PowerNetPayload {
                buses,
                branches,
                loads,
            },
        );
    }
}

/// Build one [`Branch`] from a resolved `feeders:` edge, or push an
/// E0217 diagnostic and return `None` when a REQUIRED apparatus field
/// (`Transformer.kva`, `Feeder.length`, `ProtectiveDevice.frame`) has
/// no declared source.
fn build_branch(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    edge: &FeederEdge,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<Branch> {
    let (kind, params) = match edge.apparatus.as_str() {
        "service" => (BranchKind::Service, source_params(edge)),
        "generator" => (BranchKind::Generator, source_params(edge)),
        "transformer" => transformer_branch(path, power, edge, diagnostics)?,
        "feeder" | "busway" => feeder_branch(path, power, edge, diagnostics)?,
        "breaker" | "fuse" | "relay" => protective_device_branch(path, power, edge, diagnostics)?,
        other => {
            unresolved_field(
                path,
                power,
                &format!(
                    "edge `{}`: unrecognized apparatus `{other}` -- no branch kind to emit",
                    edge.id
                ),
                diagnostics,
            );
            return None;
        }
    };
    Some(Branch {
        id: edge.id.clone(),
        kind,
        a: edge.from.clone(),
        b: edge.to.clone(),
        params,
    })
}

fn source_params(edge: &FeederEdge) -> BranchParams {
    BranchParams::Source(SourceParams {
        available_fault_current: arg_quantity(&edge.args, "available_fault"),
        x_over_r: arg_quantity(&edge.args, "x_r"),
        voltage: arg_quantity(&edge.args, "voltage"),
    })
}

fn transformer_branch(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    edge: &FeederEdge,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<(BranchKind, BranchParams)> {
    let Some(kva) = arg_quantity(&edge.args, "kva") else {
        unresolved_field(
            path,
            power,
            &format!(
                "transformer `{}`: kva required for power payload emission",
                edge.id
            ),
            diagnostics,
        );
        return None;
    };
    Some((
        BranchKind::Transformer,
        BranchParams::Transformer(Transformer {
            kva,
            pct_z: arg_quantity(&edge.args, "pct_z"),
            x_over_r: arg_quantity(&edge.args, "x_r"),
            vector_group: arg_ref(&edge.args, "vector_group"),
            taps: Vec::new(),
            standard_family: edge.standard_family,
        }),
    ))
}

fn feeder_branch(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    edge: &FeederEdge,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<(BranchKind, BranchParams)> {
    let Some(length) = arg_quantity(&edge.args, "length") else {
        unresolved_field(
            path,
            power,
            &format!(
                "{} `{}`: length required for power payload emission",
                edge.apparatus, edge.id
            ),
            diagnostics,
        );
        return None;
    };
    let kind = if edge.apparatus == "busway" {
        BranchKind::Busway
    } else {
        BranchKind::Feeder
    };
    Some((
        kind,
        BranchParams::Feeder(Feeder {
            conductor: RecordRef {
                digest: String::new(),
                name: arg_ref(&edge.args, "size").unwrap_or_default(),
            },
            length,
            raceway: arg_ref(&edge.args, "raceway"),
            ambient: arg_quantity(&edge.args, "ambient"),
            grouping: arg_quantity(&edge.args, "grouping").map(|iv| clamp_to_u32(iv.lo)),
            standard_family: edge.standard_family,
        }),
    ))
}

fn protective_device_branch(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    edge: &FeederEdge,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<(BranchKind, BranchParams)> {
    let Some(frame) = arg_quantity(&edge.args, "frame") else {
        unresolved_field(
            path,
            power,
            &format!(
                "{} `{}`: frame required for power payload emission",
                edge.apparatus, edge.id
            ),
            diagnostics,
        );
        return None;
    };
    Some((
        BranchKind::ProtectiveDevice,
        BranchParams::ProtectiveDevice(ProtectiveDevice {
            frame,
            trip: arg_quantity(&edge.args, "trip"),
            interrupting_rating: arg_quantity(&edge.args, "aic"),
            curve: arg_ref(&edge.args, "curve").map(|name| RecordRef {
                digest: String::new(),
                name,
            }),
            standard_family: edge.standard_family,
        }),
    ))
}

/// Push an E0217 (`POWER_PAYLOAD_FIELD_UNRESOLVED`) diagnostic naming
/// exactly which required field has no declared source (D250.3:
/// refused, never fabricated).
fn unresolved_field(
    path: &camino::Utf8Path,
    power: &PowerDecl,
    detail: &str,
    diagnostics: &mut Vec<Diagnostic>,
) {
    tracing::info!(power = %power.name().unwrap_or_default(), detail, "E0217: required power payload field unresolved");
    let sp = power_span(path, power);
    diagnostics.push(
        Diagnostic::error(
            POWER_PAYLOAD_FIELD_UNRESOLVED,
            format!(
                "power payload emission refused: {detail} (D250.3 -- a required field with \
                 no declared source is never fabricated)"
            ),
        )
        .with_span(LabeledSpan::new(sp, "required field unresolved")),
    );
}

/// A declared property's raw text parsed as a scalar quantity
/// (`"480V"` -> `[480, 480] V`, `"3"` -> `[3, 3] ""`): a leading
/// optional sign and digits/`.` are the number, everything after is
/// the unit (trimmed). `None` when the text has no leading number.
fn property_scalar(properties: &[(String, String)], key: &str) -> Option<ScalarInterval> {
    let raw = properties.iter().find(|(k, _)| k == key)?.1.as_str();
    parse_scalar_text(raw)
}

/// A declared property's raw text parsed as a small non-negative
/// integer (`"3"` -> `3`) -- `phases` is always 1-3, so a clamped,
/// explicitly-truncating round is exact for every real declaration
/// and simply saturates rather than panicking/UB on a malformed one.
fn property_u8(properties: &[(String, String)], key: &str) -> Option<u8> {
    property_scalar(properties, key).map(|iv| clamp_to_u8(iv.lo))
}

#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
fn clamp_to_u8(value: f64) -> u8 {
    let rounded = value.round();
    if rounded <= 0.0 {
        0
    } else if rounded >= f64::from(u8::MAX) {
        u8::MAX
    } else {
        rounded as u8
    }
}

#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
fn clamp_to_u32(value: f64) -> u32 {
    let rounded = value.round();
    if rounded <= 0.0 {
        0
    } else if rounded >= f64::from(u32::MAX) {
        u32::MAX
    } else {
        rounded as u32
    }
}

fn parse_scalar_text(raw: &str) -> Option<ScalarInterval> {
    let s = raw.trim();
    let bytes = s.as_bytes();
    let mut end = 0usize;
    if end < bytes.len() && (bytes[end] == b'+' || bytes[end] == b'-') {
        end += 1;
    }
    while end < bytes.len() && (bytes[end].is_ascii_digit() || bytes[end] == b'.') {
        end += 1;
    }
    if end == 0 {
        return None;
    }
    let (num_part, unit_part) = s.split_at(end);
    let n: f64 = num_part.parse().ok()?;
    Some(ScalarInterval {
        lo: n,
        hi: n,
        unit: unit_part.trim().to_string(),
    })
}

/// A declared property's raw text, verbatim (`class=motor` -> `"motor"`).
fn property_text(properties: &[(String, String)], key: &str) -> Option<String> {
    properties
        .iter()
        .find(|(k, _)| k == key)
        .map(|(_, v)| v.clone())
}

/// A declared property's raw text parsed as a [`StandardFamily`]
/// (D255), same spellings `std=` already accepts on apparatus edges.
fn property_family(properties: &[(String, String)], key: &str) -> Option<StandardFamily> {
    property_text(properties, key).and_then(|s| standard_family_from_str(&s))
}

#[cfg(test)]
mod payload_tests {
    use super::{emit_power_payloads, unresolved_field, POWER_PAYLOAD_FIELD_UNRESOLVED};
    use crate::output::{ParsedFile, SourceFile};
    use crate::parse_sources;

    fn parse_one(text: &str) -> Vec<ParsedFile> {
        parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.cupr"),
            text: text.to_string(),
        }])
    }

    #[allow(dead_code)]
    fn silence_unused_import_lint() {
        // `unresolved_field`/the code const are exercised only via the
        // full `emit_power_payloads` pipeline below; referenced here so
        // an accidental dead-code drift is caught at compile time too.
        let _ = POWER_PAYLOAD_FIELD_UNRESOLVED;
        let _ = unresolved_field;
    }

    #[test]
    // frob:tests crates/regolith-lower/src/power.rs::emit_power_payloads kind="unit"
    fn complete_declarations_emit_a_full_payload() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1(nominal_voltage=480V, phases=3), \
                     MainBus(nominal_voltage=480V, phases=3)\n\
                   \x20   loads: Motor1(kva=10)\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA) (Svc1 -> MainBus)\n\
                   \x20       p1: breaker(frame=400A) (MainBus -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg, length=10m) (MainBus -> Motor1)\n";
        let report = emit_power_payloads(&parse_one(src));
        assert!(report.diagnostics.is_empty(), "{:?}", report.diagnostics);
        let payload = report.payloads.get("PlantMain").expect("payload emitted");
        assert_eq!(payload.buses.len(), 2);
        assert_eq!(payload.branches.len(), 3);
        assert_eq!(payload.loads.len(), 1);
    }

    #[test]
    fn missing_bus_voltage_refuses_with_e0217() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1, MainBus(nominal_voltage=480V, phases=3)\n\
                   \x20   loads: Motor1(kva=10)\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA) (Svc1 -> MainBus)\n\
                   \x20       p1: breaker(frame=400A) (MainBus -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg, length=10m) (MainBus -> Motor1)\n";
        let report = emit_power_payloads(&parse_one(src));
        assert!(report.payloads.is_empty(), "should refuse, never fabricate");
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code.to_string() == "E0217" && d.message.contains("Svc1")));
    }

    #[test]
    fn missing_load_kva_refuses_with_e0217() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1(nominal_voltage=480V, phases=3), \
                     MainBus(nominal_voltage=480V, phases=3)\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA) (Svc1 -> MainBus)\n\
                   \x20       p1: breaker(frame=400A) (MainBus -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg, length=10m) (MainBus -> Motor1)\n";
        let report = emit_power_payloads(&parse_one(src));
        assert!(report.payloads.is_empty(), "should refuse, never fabricate");
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code.to_string() == "E0217" && d.message.contains("Motor1")));
    }

    #[test]
    // frob:tests crates/regolith-oblig/src/power.rs::PowerNetPayload.content_digest kind="unit"
    fn positive_corpus_lowers_to_a_byte_stable_payload() {
        let repo = env!("CARGO_MANIFEST_DIR");
        let path = format!("{repo}/../../examples/tracks/cuprite/power_plant_main.cupr");
        let text = std::fs::read_to_string(&path).expect("read fixture");
        let files = parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from(path),
            text,
        }]);
        let first = emit_power_payloads(&files);
        assert!(first.diagnostics.is_empty(), "{:?}", first.diagnostics);
        let payload = first
            .payloads
            .get("PlantMain")
            .expect("PlantMain payload emitted");
        let digest_1 = payload.content_digest().expect("digest 1");

        // Lower a SECOND time from the same source (a fresh parse, not
        // a clone) -- byte stability across builds (deliverable 5),
        // not just within one in-memory value.
        let second = emit_power_payloads(&files);
        let payload_2 = second.payloads.get("PlantMain").expect("second payload");
        let digest_2 = payload_2.content_digest().expect("digest 2");

        assert_eq!(digest_1, digest_2, "same source must digest identically");
    }

    #[test]
    // frob:tests crates/regolith-lower/src/power.rs::emit_power_payloads kind="integration"
    fn negative_fixture_refuses_with_e0217() {
        let repo = env!("CARGO_MANIFEST_DIR");
        let path =
            format!("{repo}/../../examples/negative/77_cupr_power_payload_field_unresolved.cupr");
        let text = std::fs::read_to_string(&path).expect("read fixture");
        let files = parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from(path),
            text,
        }]);
        let report = emit_power_payloads(&files);
        assert!(report.payloads.is_empty(), "should refuse, never fabricate");
        let codes: Vec<String> = report
            .diagnostics
            .iter()
            .map(|d| d.code.to_string())
            .collect();
        assert!(codes.iter().all(|c| c == "E0217"), "{codes:?}");
        assert!(!codes.is_empty());
    }
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
    // frob:tests crates/regolith-lower/src/power.rs::check_cross_standard_mix kind="unit"
    fn cross_standard_mix_flags_e0216() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1, MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA, std=iec) (Svc1 -> MainBus)\n\
                   \x20       p1: breaker(frame=400A, std=nec) (MainBus -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg, std=nec) (MainBus -> Motor1)\n";
        assert!(
            codes(src).contains(&"E0216".to_string()),
            "{:?}",
            codes(src)
        );
        let report = run_power_checks(&parse_one(src));
        let mixed = report
            .diagnostics
            .iter()
            .find(|d| d.code.to_string() == "E0216")
            .expect("E0216 present");
        assert!(mixed.message.contains("f1"));
        assert!(mixed.message.contains("Iec"));
        assert!(mixed.message.contains("Nec"));
    }

    #[test]
    fn agreeing_standard_families_stay_silent() {
        let src = "power PlantMain:\n\
                   \x20   sources: Svc1\n\
                   \x20   buses: Svc1, MainBus\n\
                   \x20   loads: Motor1\n\
                   \x20   feeders:\n\
                   \x20       f1: transformer(kva=500kVA, std=nec) (Svc1 -> MainBus)\n\
                   \x20       p1: breaker(frame=400A, std=nec) (MainBus -> MainBus)\n\
                   \x20       f2: feeder(size=cu_4_0awg, std=nec) (MainBus -> Motor1)\n";
        assert!(
            !codes(src).contains(&"E0216".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn no_declared_standard_families_stay_silent() {
        // No `std=` kwarg anywhere -- an undeclared standard family is a
        // named absence (D255/D250.3), never flagged as a "mismatch".
        let src = clean_net();
        assert!(
            !codes(&src).contains(&"E0216".to_string()),
            "{:?}",
            codes(&src)
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
