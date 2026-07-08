//! Pass 3d (WO-32 deliverable 3): fluorite flownet elaboration.
//!
//! Walks every parsed `.fluo` file's typed `flownet` AST into an
//! in-memory [`FlownetPayload`] (fluorite/03 sec. 1-2): nodes, the
//! reference datum, one [`FlowEdge`] per declared edge, and the
//! symbolic state domains. Hydraulic parameters for `from=` edges are
//! EXTRACTED through the ONE shared routed-geometry seam
//! ([`crate::extract::extract_path`]); `driven_by=` imposers thread
//! their promise-chain ref into a [`PromiseGiven`]; record-bound
//! parameters (`curve=`, `compliance=`) resolve hash-pinned records.
//!
//! PURITY (AD-17): this pass reads no IO. The orchestrator resolves
//! every ref -- medium property records, realized-geometry record
//! bytes, curve/compliance records -- through the WO-30 content store
//! and hands the resolved data in via [`FlownetInputs`]; this module
//! only decodes the AST and calls the pure extraction seam. The
//! caller-resolved [`MediumProps`] is passed into `extract_path` for
//! the Korteweg wave-speed field (the D1 medium-coupling boundary;
//! the extract module itself stays medium-IO-free).
//!
//! ERRORS ARE DATA: an unresolved ref or a failed extraction is a
//! typed [`FlownetLowerError`] value (thiserror), collected and
//! returned -- never a panic. A later dispatch (D4/D5) renders these
//! at the lowering boundary as `regolith_diag` diagnostics and wires
//! the payloads into `BuildPayload`; this module never renders and
//! never touches the obligation set.
//!
//! DETERMINISM (AD-6): flownets are elaborated in caller (sorted) file
//! order; within a payload, `nodes` and `edges` are sorted by id and
//! `states` are kept in source order, so an [`ElaboratedFlownet`]'s
//! payload digest is stable across builds of the same source.

use regolith_oblig::{
    Compliance, EdgeKind, EdgeParams, FlowEdge, FlownetPayload, MediumRef, NodeId, RecordRef,
    Reference, ScalarInterval, StateDomain,
};
use regolith_syntax::ast::{AstNode, EdgeStmt, Field, File, FlownetDecl};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_syntax::SyntaxNode;

use crate::extract::{extract_path, ExtractError, GeometryExtraction, MediumProps};
use crate::output::ParsedFile;

/// The medium data the caller resolved for a flownet's working fluid:
/// the property-record refs that pin the payload's [`MediumRef`] plus
/// the bulk-modulus/density [`MediumProps`] the wave-speed field needs.
#[derive(Debug, Clone)]
pub struct ResolvedMedium {
    /// The hash-pinned property records describing the medium.
    pub records: Vec<RecordRef>,
    /// Bulk modulus / density for the Korteweg wave-speed extraction.
    pub props: MediumProps,
}

/// A caller-resolved realized-geometry source for a `from=` edge: the
/// record ref (for provenance), the record bytes (resolved from the
/// WO-30 store -- the extraction input that keeps this module IO-free),
/// and the path/role selector into that record.
#[derive(Debug, Clone)]
pub struct ResolvedGeometry {
    /// The realized-geometry record ref (digest + name).
    pub record: RecordRef,
    /// The record's serialized bytes (the [`extract_path`] input).
    pub bytes: Vec<u8>,
    /// The path/role selector into the record.
    pub selector: String,
}

/// The orchestrator-side resolver every flownet ref goes through
/// (AD-17: this trait is the ONLY route to resolved content, and its
/// implementation -- not this pass -- does the IO). Unit tests supply
/// an in-memory implementation; the D4 wiring supplies one backed by
/// the WO-30 content store.
pub trait FlownetInputs {
    /// Resolve a flownet's `medium=<name>` to its property records and
    /// bulk-modulus/density props; `None` when the medium is unknown.
    fn medium(&self, name: &str) -> Option<ResolvedMedium>;

    /// Resolve a `from=<part.role>` ref to a realized-geometry source;
    /// `None` when no realized record backs the ref (the fluorite/03
    /// sec. 1 "no extractable wall" case -- a D5 diagnostic).
    fn geometry(&self, from_ref: &str) -> Option<ResolvedGeometry>;

    /// Resolve a `curve=`/`dp_curve=` registry ref to a record ref;
    /// `None` when the record is unknown.
    fn record(&self, reg_ref: &str) -> Option<RecordRef>;

    /// Resolve a record-bound `compliance=` ref to its wall compliance
    /// and wave speed; `None` when the record is unknown.
    fn compliance(&self, reg_ref: &str) -> Option<Compliance>;
}

/// The real (non-test) [`FlownetInputs`] this pass resolves through
/// today (WO-32 deliverable 4a): resolves exactly what claims.rs's
/// PURE pipeline has on hand at this point -- the `.fluo` AST itself --
/// and nothing that needs IO. AD-17 purity: `regolith-lower` never
/// touches IO, so realized-geometry bytes and registry-record CONTENTS
/// (property tables, curves, wall records) are not resolvable here.
/// `geometry`/`compliance` honestly return `None`, so `from=` edges
/// fall back to their already-built deferred `GeomExtract` selector and
/// `compliance=` refs stay unresolved -- the fluorite/03 sec. 1
/// hydraulic-extraction promise is kept later, when D4b's
/// orchestrator-backed `FlownetInputs` (reading the WO-30 content
/// store) re-elaborates with real bytes. Medium/curve REFS (names) are
/// real, read straight off the AST, with an empty digest (a name-only
/// pin, mirroring the deferred-ref idiom already used above for an
/// unresolved `from=` edge) until that same store-backed impl lands.
pub struct AstFlownetInputs {
    /// `medium` name -> its `props: registry(<ref>)` ref name,
    /// harvested once from every parsed file's `medium` declarations
    /// (fluorite/02 sec. 1). Medium names are unique per file set, so a
    /// `BTreeMap` is both the right shape and keeps lookups
    /// deterministic (AD-6).
    media: std::collections::BTreeMap<String, String>,
}

impl AstFlownetInputs {
    /// Harvest the medium index from `files`. This is the WO-32
    /// deliverable-4a entry point callers construct once per build and
    /// pass to [`elaborate_flownets`] alongside `files`.
    #[must_use]
    pub fn new(files: &[ParsedFile]) -> Self {
        let mut media = std::collections::BTreeMap::new();
        for pf in files {
            let Some(file) = File::cast(pf.parse.syntax()) else {
                continue;
            };
            for medium in file.mediums() {
                let Some(name) = medium.name() else {
                    continue;
                };
                let Some(props_ref) = medium
                    .syntax()
                    .children()
                    .filter_map(Field::cast)
                    .find(|f| f.name() == "props")
                    .and_then(|f| f.value())
                    .and_then(|v| registry_ref_name(&v))
                else {
                    continue;
                };
                media.insert(name, props_ref);
            }
        }
        Self { media }
    }
}

impl FlownetInputs for AstFlownetInputs {
    fn medium(&self, name: &str) -> Option<ResolvedMedium> {
        let props_ref = self.media.get(name)?;
        Some(ResolvedMedium {
            records: vec![RecordRef {
                digest: String::new(),
                name: props_ref.clone(),
            }],
            // Bulk modulus/density are registry-record CONTENT (IO);
            // not resolvable in this pure pass. `geometry` below never
            // resolves bytes, so `extract_path` (the only consumer of
            // these props) is never invoked from this real
            // implementation -- these are unused placeholders until
            // D4b's store-backed impl supplies the real values.
            props: MediumProps {
                bulk_modulus: [0.0, 0.0],
                density: [0.0, 0.0],
            },
        })
    }

    fn geometry(&self, _from_ref: &str) -> Option<ResolvedGeometry> {
        // Realized-geometry bytes are IO-resolved content (AD-17); this
        // pure AST-sourced impl honestly defers every `from=` edge to
        // its GeomExtract selector rather than fabricating bytes.
        None
    }

    fn record(&self, reg_ref: &str) -> Option<RecordRef> {
        // Name-only pin (mirrors the medium-props precedent above): the
        // digest is IO-resolved content, not available here.
        Some(RecordRef {
            digest: String::new(),
            name: reg_ref.to_string(),
        })
    }

    fn compliance(&self, _reg_ref: &str) -> Option<Compliance> {
        // Wall compliance/wave-speed VALUES are registry-record content
        // (IO); honestly unresolved here rather than invented.
        None
    }
}

/// The first argument identifier of a `registry(<ref>)` call value
/// (`registry(rp1_mil_dtl_25576)` -> `"rp1_mil_dtl_25576"`); `None`
/// when the value carries no second identifier (a malformed/absent
/// `props:` field).
fn registry_ref_name(value: &SyntaxNode) -> Option<String> {
    value
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .nth(1)
}

/// A cross-track promise-chain given produced by a `driven_by=` imposer
/// (fluorite/03 sec. 1): the imposed edge's value carries the promise
/// ref, exactly like a dissipation promise. The D4 wiring attaches this
/// to the imposer obligation's givens; the payload itself is unchanged.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PromiseGiven {
    /// The imposer edge id the promise drives.
    pub edge_id: String,
    /// The imposed variable name (e.g. `"p"`).
    pub var: String,
    /// The promise-chain ref the given carries.
    pub promise_ref: String,
}

/// One elaborated flownet: its payload plus the promise-chain givens
/// its imposer edges contribute (kept beside the payload because givens
/// ride the obligation, not the payload -- fluorite/03 sec. 2).
#[derive(Debug, Clone)]
pub struct ElaboratedFlownet {
    /// The flownet's declared name.
    pub name: String,
    /// The elaborated, content-addressable payload.
    pub payload: FlownetPayload,
    /// The `driven_by=` promise-chain givens, in edge-id order.
    pub promise_givens: Vec<PromiseGiven>,
}

/// A failure elaborating a flownet -- a value the lowering boundary
/// (D5) renders as a diagnostic. Never a panic; collected and returned.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum FlownetLowerError {
    /// The flownet's `medium=<name>` did not resolve to a medium.
    #[error("flownet `{flownet}` names unknown medium `{medium}`")]
    UnknownMedium {
        /// The flownet the reference appeared in.
        flownet: String,
        /// The unresolved medium name.
        medium: String,
    },
    /// A `from=` edge's realized-geometry extraction failed.
    #[error("flownet `{flownet}` edge `{edge}`: {source}")]
    Extract {
        /// The flownet the edge is in.
        flownet: String,
        /// The edge id.
        edge: String,
        /// The underlying extraction error.
        #[source]
        source: ExtractError,
    },
    /// An edge's constructor kind is not a known flownet edge kind.
    #[error("flownet `{flownet}` edge `{edge}` has unknown kind `{callee}`")]
    UnknownEdgeKind {
        /// The flownet the edge is in.
        flownet: String,
        /// The edge id.
        edge: String,
        /// The unrecognized constructor callee.
        callee: String,
    },
}

/// The result of elaborating every flownet in a set of parsed files.
#[derive(Debug, Clone, Default)]
pub struct FlownetLowerReport {
    /// The elaborated flownets, in file/source order.
    pub flownets: Vec<ElaboratedFlownet>,
    /// Typed elaboration errors, in discovery order (rendered as
    /// diagnostics by a later dispatch).
    pub errors: Vec<FlownetLowerError>,
}

/// Elaborate every `flownet` declaration across `files` into a
/// [`FlownetPayload`] plus promise-chain givens, resolving refs through
/// `inputs`. Pure and IO-free (AD-17); deterministic (AD-6). This is
/// the WO-32 deliverable-3 entry point.
#[must_use]
pub fn elaborate_flownets(files: &[ParsedFile], inputs: &dyn FlownetInputs) -> FlownetLowerReport {
    let span = tracing::info_span!("lower.flownet");
    let _enter = span.enter();

    let mut report = FlownetLowerReport::default();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for flownet in file.flownets() {
            elaborate_one(&flownet, inputs, &mut report);
        }
    }
    tracing::info!(
        flownets = report.flownets.len(),
        errors = report.errors.len(),
        "flownet elaboration complete"
    );
    report
}

/// Elaborate one flownet, appending its result (and any errors) to
/// `report`. A flownet whose medium is unresolved still elaborates its
/// topology (with empty medium records) so downstream shape checks see
/// a well-formed payload; the medium failure is recorded as data.
fn elaborate_one(
    flownet: &FlownetDecl,
    inputs: &dyn FlownetInputs,
    report: &mut FlownetLowerReport,
) {
    let name = flownet.name().unwrap_or_default();

    let medium_name = flownet_medium_name(flownet);
    let resolved_medium = inputs.medium(&medium_name);
    if resolved_medium.is_none() {
        tracing::info!(flownet = %name, medium = %medium_name, "unresolved medium");
        report.errors.push(FlownetLowerError::UnknownMedium {
            flownet: name.clone(),
            medium: medium_name.clone(),
        });
    }
    let medium_ref = MediumRef {
        records: resolved_medium
            .as_ref()
            .map(|m| m.records.clone())
            .unwrap_or_default(),
    };
    let medium_props = resolved_medium.as_ref().map(|m| m.props);

    let reference = flownet_reference(flownet);

    let mut nodes: Vec<NodeId> = flownet_nodes(flownet);
    nodes.sort();
    nodes.dedup();

    let mut edges: Vec<FlowEdge> = Vec::new();
    let mut promise_givens: Vec<PromiseGiven> = Vec::new();
    if let Some(edges_block) = flownet.edges() {
        for edge in edges_block.edges() {
            elaborate_edge(
                &name,
                &edge,
                inputs,
                medium_props.as_ref(),
                &mut edges,
                &mut promise_givens,
                report,
            );
        }
    }
    edges.sort_by(|a, b| a.id.cmp(&b.id));
    promise_givens.sort_by(|a, b| a.edge_id.cmp(&b.edge_id));

    let states = flownet_states(flownet, &name);

    let payload = FlownetPayload {
        medium: medium_ref,
        nodes,
        reference,
        edges,
        states,
    };
    report.flownets.push(ElaboratedFlownet {
        name,
        payload,
        promise_givens,
    });
}

/// Elaborate one edge into a [`FlowEdge`], resolving its parameters by
/// constructor kind (fluorite/02 sec. 3, fluorite/03 sec. 1).
fn elaborate_edge(
    flownet: &str,
    edge: &EdgeStmt,
    inputs: &dyn FlownetInputs,
    medium_props: Option<&MediumProps>,
    edges: &mut Vec<FlowEdge>,
    promise_givens: &mut Vec<PromiseGiven>,
    report: &mut FlownetLowerReport,
) {
    let id = edge.name();
    let (a, b) = edge_endpoints(edge);

    let value = edge.value();
    let callee = value.as_ref().and_then(callee_name).unwrap_or_default();
    let Some(kind) = edge_kind(&callee) else {
        report.errors.push(FlownetLowerError::UnknownEdgeKind {
            flownet: flownet.to_string(),
            edge: id,
            callee,
        });
        return;
    };

    let args = value.as_ref().map(collect_args).unwrap_or_default();

    let mut compliance: Option<Compliance> = None;
    let mut curves: Vec<RecordRef> = Vec::new();

    // `driven_by=` imposers thread the promise ref into a given.
    if let Some(promise_ref) = arg_ref(&args, "driven_by") {
        promise_givens.push(PromiseGiven {
            edge_id: id.clone(),
            var: "p".to_string(),
            promise_ref,
        });
    }

    // Record-bound curve/compliance refs (hash-pinned registry objects).
    for key in ["curve", "dp_curve"] {
        if let Some(reg_ref) = arg_ref(&args, key) {
            if let Some(rec) = inputs.record(&reg_ref) {
                curves.push(rec);
            }
        }
    }
    if let Some(reg_ref) = arg_ref(&args, "compliance") {
        compliance = inputs.compliance(&reg_ref);
    }

    // `from=` edges extract their hydraulic parameters through the ONE
    // shared routed-geometry seam; the params reduce to scalar givens
    // and (from a wall record) wall compliance + wave speed.
    let params = if let Some(from_ref) = arg_ref(&args, "from") {
        match inputs.geometry(&from_ref) {
            Some(geom) => match extract_path(&geom.bytes, &geom.selector, medium_props) {
                Ok(extraction) => {
                    if compliance.is_none() {
                        compliance = geometry_compliance(&extraction);
                    }
                    geometry_scalars(&extraction)
                }
                Err(source) => {
                    report.errors.push(FlownetLowerError::Extract {
                        flownet: flownet.to_string(),
                        edge: id.clone(),
                        source,
                    });
                    // Record the deferred selector so the payload stays
                    // well-formed; D5 renders the extraction failure.
                    EdgeParams::GeomExtract {
                        record: geom.record,
                        selector: geom.selector,
                    }
                }
            },
            // No realized record backs the ref: keep the selector as a
            // deferred extraction (D5 diagnoses transient/budget use).
            None => EdgeParams::GeomExtract {
                record: RecordRef {
                    digest: String::new(),
                    name: from_ref.clone(),
                },
                selector: from_ref,
            },
        }
    } else {
        EdgeParams::Scalars {
            values: scalar_args(&args),
        }
    };

    edges.push(FlowEdge {
        id,
        kind,
        a,
        b,
        params,
        compliance,
        curves,
    });
}

/// The [`EdgeKind`] a constructor callee names, or `None` for a callee
/// outside the fluorite/02 sec. 3 vocabulary.
fn edge_kind(callee: &str) -> Option<EdgeKind> {
    Some(match callee {
        "Pipe" => EdgeKind::Pipe,
        "Hose" => EdgeKind::Hose,
        "Orifice" => EdgeKind::Orifice,
        "Valve" => EdgeKind::Valve,
        "Pump" => EdgeKind::Pump,
        "Regulator" => EdgeKind::Regulator,
        "Filter" => EdgeKind::Filter,
        "Imposer" => EdgeKind::Imposer,
        "HxSegment" => EdgeKind::HxSegment,
        _ => return None,
    })
}

/// Collapse a single-segment fluid-edge extraction into scalar edge
/// params (fluorite/03 sec. 1): a fluid edge is a single routed run, so
/// its aggregate length/elevation and the segment's area/roughness (and
/// bend, when present) become the edge's scalar givens.
fn geometry_scalars(extraction: &GeometryExtraction) -> EdgeParams {
    use std::collections::BTreeMap;
    let mut values: BTreeMap<String, ScalarInterval> = BTreeMap::new();
    values.insert("length".to_string(), extraction.total_length.clone());
    values.insert(
        "elevation_change".to_string(),
        extraction.total_elevation_change.clone(),
    );
    if let Some(seg) = extraction.segments.first() {
        values.insert("area".to_string(), seg.flow_area.clone());
        values.insert("roughness".to_string(), seg.roughness.height.clone());
        if let Some(bend) = &seg.bend {
            values.insert("bend_angle".to_string(), bend.angle.clone());
            values.insert("bend_radius".to_string(), bend.radius.clone());
        }
    }
    EdgeParams::Scalars { values }
}

/// The wall compliance for a fluid edge, when its (single) segment
/// carries a wall record. The Korteweg wave speed is present because
/// elaboration passes the flownet's medium props into extraction.
fn geometry_compliance(extraction: &GeometryExtraction) -> Option<Compliance> {
    let seg = extraction.segments.first()?;
    let wall = seg.wall.as_ref()?;
    Some(Compliance {
        wall_compliance: wall.wall_compliance.clone(),
        wave_speed: wall.wave_speed.clone().unwrap_or_else(|| ScalarInterval {
            lo: 0.0,
            hi: f64::INFINITY,
            unit: "m/s".to_string(),
        }),
        snapshot_hash: extraction.snapshot_hash.clone(),
    })
}

/// The flownet header's `medium=<name>` value (`flownet L(medium=Water)`
/// -> `"Water"`), read from the header tokens before any field/block.
fn flownet_medium_name(flownet: &FlownetDecl) -> String {
    let mut toks = flownet
        .syntax()
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .skip_while(|t| !(t.kind() == SyntaxKind::Ident && t.text() == "medium"));
    toks.next(); // the `medium` ident itself
                 // The value is the next `Ident` after the `=`.
    toks.skip_while(|t| t.kind() != SyntaxKind::Eq)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .unwrap_or_default()
}

/// The flownet's reference datum and imposed reference state, read from
/// the `reference:` field. The datum is a virtual node (the elec `gnd`
/// analog, fluorite/02 sec. 4): its id is the reference callee
/// (`ambient`, `reservoir`, ...) and its imposed `p`/`T` are the two
/// quantity literals. A missing/degenerate reference yields an empty
/// datum with unbounded state (a topology-only payload).
fn flownet_reference(flownet: &FlownetDecl) -> Reference {
    let Some(field) = flownet
        .fields()
        .into_iter()
        .find(|f| f.name() == "reference")
    else {
        return degenerate_reference();
    };
    let Some(value) = field.value() else {
        return degenerate_reference();
    };
    // A bare node name (`reference: tank_in`) names an existing node as
    // the datum with unbounded imposed state; a `datum(p, T)` call fixes
    // both bounds.
    let node = callee_name(&value)
        .or_else(|| Some(name_text(&value)))
        .unwrap_or_default();
    let quantities = quantity_literals(&value);
    let p = quantities
        .first()
        .cloned()
        .unwrap_or_else(|| unbounded("Pa"));
    let t = quantities.get(1).cloned().unwrap_or_else(|| unbounded("K"));
    Reference { node, p, t }
}

fn degenerate_reference() -> Reference {
    Reference {
        node: String::new(),
        p: unbounded("Pa"),
        t: unbounded("K"),
    }
}

fn unbounded(unit: &str) -> ScalarInterval {
    ScalarInterval {
        lo: f64::NEG_INFINITY,
        hi: f64::INFINITY,
        unit: unit.to_string(),
    }
}

/// The declared node ids of the flownet's `nodes:` field.
fn flownet_nodes(flownet: &FlownetDecl) -> Vec<NodeId> {
    let Some(field) = flownet.fields().into_iter().find(|f| f.name() == "nodes") else {
        return Vec::new();
    };
    let mut idents: Vec<String> = field
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    if !idents.is_empty() {
        idents.remove(0); // drop the leading `nodes` field-name ident
    }
    idents
}

/// The symbolic state domains of the flownet's `states:` block
/// (fluorite/03 sec. 1: state expansion). Each `<edge>.<param> in {..}`
/// or `state <name> in {..}` line yields EXACTLY ONE [`StateDomain`] --
/// the domain stays symbolic (the ONE-swept-obligation rule), never
/// enumerated into one entry per value. `event` lines (the actuation
/// coupling, fluorite/03 sec. 4) are not swept states and are skipped.
fn flownet_states(flownet: &FlownetDecl, net_name: &str) -> Vec<StateDomain> {
    let Some(block) = flownet.states() else {
        return Vec::new();
    };
    let mut out: Vec<StateDomain> = Vec::new();
    for stmt in block.states() {
        // `event ...` lines lead with the `event` keyword; skip them.
        let leads_with_event = stmt
            .syntax()
            .children_with_tokens()
            .filter_map(rowan::NodeOrToken::into_token)
            .find(|t| !matches!(t.kind(), SyntaxKind::Whitespace | SyntaxKind::Newline))
            .is_some_and(|t| t.kind() == SyntaxKind::EventKw);
        if leads_with_event {
            continue;
        }
        let Some(domain_set) = stmt.domain() else {
            continue;
        };
        let domain = domain_set_text(domain_set.syntax());
        let (target, var) = state_target_var(stmt.syntax(), net_name);
        out.push(StateDomain {
            target,
            var,
            domain,
        });
    }
    out
}

/// Split a `states:` line's leading path into `(target, var)`. A
/// `<edge>.<param>` line targets the edge with the trailing param name;
/// a `state <name>` line targets the net with the declared variable.
fn state_target_var(stmt: &SyntaxNode, net_name: &str) -> (String, String) {
    let idents: Vec<String> = stmt
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .take_while(|t| {
            matches!(
                t.kind(),
                SyntaxKind::Ident | SyntaxKind::Dot | SyntaxKind::Whitespace
            )
        })
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    match idents.split_first() {
        // `state <name> in {..}`: net-level config variable.
        Some((first, rest)) if first == "state" && !rest.is_empty() => {
            (net_name.to_string(), rest.join("."))
        }
        // `<edge>.<param> in {..}`: edge-parameter domain.
        Some((edge, params)) if !params.is_empty() => (edge.clone(), params.join(".")),
        // A lone name: target the net.
        Some((only, _)) => (net_name.to_string(), only.clone()),
        None => (net_name.to_string(), String::new()),
    }
}

/// The canonical `{a, b, c}` text of a domain set (idents/keywords
/// only; the brace `Error` tokens and whitespace are normalized out).
fn domain_set_text(node: &SyntaxNode) -> String {
    let members: Vec<String> = node
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| {
            !matches!(
                t.kind(),
                SyntaxKind::Whitespace
                    | SyntaxKind::Newline
                    | SyntaxKind::Comma
                    | SyntaxKind::Error
            )
        })
        .map(|t| t.text().to_string())
        .collect();
    format!("{{{}}}", members.join(", "))
}

// -- argument reading -------------------------------------------------

/// A resolved constructor argument: a keyword arg's name and its value
/// node (a ref path, a bare name, or a quantity literal).
struct Arg {
    key: String,
    value: SyntaxNode,
}

/// Collect the keyword arguments of a constructor `CallExpr` value node
/// (`Pipe(from=line.run)` -> `[from = line.run]`). Positional
/// quantity-literal args are gathered separately by [`scalar_args`].
fn collect_args(value: &SyntaxNode) -> Vec<Arg> {
    let Some(arglist) = value.children().find(|c| c.kind() == SyntaxKind::ArgList) else {
        return Vec::new();
    };
    let mut args = Vec::new();
    for bin in arglist
        .children()
        .filter(|c| c.kind() == SyntaxKind::BinExpr)
    {
        let key = bin
            .children()
            .find(|c| matches!(c.kind(), SyntaxKind::NameRef | SyntaxKind::Path))
            .map(|n| name_text(&n))
            .unwrap_or_default();
        if let Some(rhs) = bin
            .children()
            .filter(|c| matches!(c.kind(), SyntaxKind::NameRef | SyntaxKind::Path))
            .nth(1)
            .or_else(|| bin.children().find(|c| c.kind() == SyntaxKind::QuantityLit))
        {
            args.push(Arg { key, value: rhs });
        }
    }
    args
}

/// The dotted-path value of a named argument (`from` -> `"line.run"`),
/// if present.
fn arg_ref(args: &[Arg], key: &str) -> Option<String> {
    args.iter()
        .find(|a| a.key == key)
        .map(|a| name_text(&a.value))
}

/// The scalar-interval params of a constructor's keyword quantity args
/// (e.g. `Orifice(cd=0.6, dia=2mm)`): each quantity-literal arg becomes
/// a point interval keyed by its arg name.
fn scalar_args(args: &[Arg]) -> std::collections::BTreeMap<String, ScalarInterval> {
    let mut values = std::collections::BTreeMap::new();
    for arg in args {
        if arg.value.kind() == SyntaxKind::QuantityLit {
            if let Some(iv) = quantity_scalar(&arg.value) {
                values.insert(arg.key.clone(), iv);
            }
        }
    }
    values
}

/// Every quantity literal inside a call's argument list, in order
/// (`ambient(101kPa, 293K)` -> `[101 kPa, 293 K]`).
fn quantity_literals(value: &SyntaxNode) -> Vec<ScalarInterval> {
    value
        .descendants()
        .filter(|n| n.kind() == SyntaxKind::QuantityLit)
        .filter_map(|n| quantity_scalar(&n))
        .collect()
}

/// A quantity literal (`101kPa`) as a point [`ScalarInterval`] in its
/// own unit (`[101, 101] kPa`); `None` when the number does not parse.
fn quantity_scalar(node: &SyntaxNode) -> Option<ScalarInterval> {
    let mut number: Option<f64> = None;
    let mut unit = String::new();
    for tok in node
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
    {
        match tok.kind() {
            SyntaxKind::Number => number = tok.text().parse::<f64>().ok(),
            SyntaxKind::Ident if unit.is_empty() => unit = tok.text().to_string(),
            _ => {}
        }
    }
    number.map(|n| ScalarInterval { lo: n, hi: n, unit })
}

// -- shared AST helpers -----------------------------------------------

/// The two positive-sense endpoint node names of an edge (`(a -> b)` ->
/// `("a", "b")`), reading a typed [`SensePair`] or its wrapped
/// `OpaqueIsland` degradation (the WO-31 grammar edge).
fn edge_endpoints(edge: &EdgeStmt) -> (NodeId, NodeId) {
    let names = if let Some(sense) = edge.sense() {
        sense.names()
    } else {
        edge.syntax()
            .children()
            .find(|n| n.kind() == SyntaxKind::OpaqueIsland && n.text().to_string().contains("->"))
            .map(|node| {
                node.descendants_with_tokens()
                    .filter_map(rowan::NodeOrToken::into_token)
                    .filter(|t| t.kind() == SyntaxKind::Ident)
                    .map(|t| t.text().to_string())
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default()
    };
    let a = names.first().cloned().unwrap_or_default();
    let b = names.get(1).cloned().unwrap_or_default();
    (a, b)
}

/// The leading callee `Ident` of a constructor value node (`Pipe(..)`
/// -> `"Pipe"`), or `None` for a value with no leading identifier.
fn callee_name(value: &SyntaxNode) -> Option<String> {
    value
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
}

/// The dotted-name text of a `NameRef`/`Path` node (`line.run`), or the
/// node's leading ident chain otherwise.
fn name_text(node: &SyntaxNode) -> String {
    node.children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .take_while(|t| matches!(t.kind(), SyntaxKind::Ident | SyntaxKind::Dot))
        .map(|t| t.text().to_string())
        .collect()
}

#[cfg(test)]
// Point-valued fixtures pass exact bounds through elaboration, so
// `assert_eq!` on a bound against its literal is the correct comparison
// (not an epsilon) -- mirrors `extract`'s test discipline.
#[allow(clippy::float_cmp)]
mod tests {
    use super::*;
    use crate::output::SourceFile;
    use crate::parse_sources;
    use std::collections::BTreeMap;

    /// A point-valued realized tube record: one straight run with a wall
    /// (so extraction yields compliance + a wave speed), keyed by the
    /// `line.run` selector the fixtures name.
    fn tube_bytes() -> Vec<u8> {
        serde_json::json!({
            "snapshot_hash": "blake3:snap-tube",
            "paths": {
                "line.run": {
                    "segments": [{
                        "role": "run",
                        "flow_area": [1.0e-4, 1.0e-4],
                        "length": [2.0, 2.0],
                        "roughness_class": "drawn_tube",
                        "elevation_change": [0.3, 0.3],
                        "wall": {"youngs_modulus": [2.0e11, 2.0e11],
                                 "thickness": [1.0e-3, 1.0e-3],
                                 "diameter": [0.02, 0.02]}
                    }]
                }
            }
        })
        .to_string()
        .into_bytes()
    }

    /// An in-memory [`FlownetInputs`] resolving one medium and the tube
    /// geometry (AD-17: the pass never does IO -- the test supplies the
    /// resolved content the orchestrator would supply in production).
    struct FakeInputs {
        with_geometry: bool,
    }

    impl FlownetInputs for FakeInputs {
        fn medium(&self, name: &str) -> Option<ResolvedMedium> {
            if name == "Water" {
                Some(ResolvedMedium {
                    records: vec![RecordRef {
                        digest: "blake3:water".to_string(),
                        name: "potable_water_nist".to_string(),
                    }],
                    props: MediumProps {
                        bulk_modulus: [2.2e9, 2.2e9],
                        density: [998.0, 998.0],
                    },
                })
            } else {
                None
            }
        }

        fn geometry(&self, from_ref: &str) -> Option<ResolvedGeometry> {
            if self.with_geometry && from_ref == "line.run" {
                Some(ResolvedGeometry {
                    record: RecordRef {
                        digest: "blake3:tube".to_string(),
                        name: "line".to_string(),
                    },
                    bytes: tube_bytes(),
                    selector: "line.run".to_string(),
                })
            } else {
                None
            }
        }

        fn record(&self, reg_ref: &str) -> Option<RecordRef> {
            Some(RecordRef {
                digest: "blake3:curve".to_string(),
                name: reg_ref.to_string(),
            })
        }

        fn compliance(&self, _reg_ref: &str) -> Option<Compliance> {
            Some(Compliance {
                wall_compliance: ScalarInterval {
                    lo: 1.0e-12,
                    hi: 1.0e-12,
                    unit: "m^3/Pa".to_string(),
                },
                wave_speed: ScalarInterval {
                    lo: 1400.0,
                    hi: 1400.0,
                    unit: "m/s".to_string(),
                },
                snapshot_hash: String::new(),
            })
        }
    }

    fn elaborate(src: &str, inputs: &dyn FlownetInputs) -> FlownetLowerReport {
        let files = parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.fluo"),
            text: src.to_string(),
        }]);
        elaborate_flownets(&files, inputs)
    }

    const LOOP_SRC: &str = "flownet Loop(medium=Water):\n\
        \x20   reference: ambient(101kPa, 293K)\n\
        \x20   nodes: a, b\n\
        \x20   edges:\n\
        \x20       supply: Pipe(from=line.run) (a -> b)\n";

    #[test]
    fn elaborates_topology_and_reference() {
        let report = elaborate(
            LOOP_SRC,
            &FakeInputs {
                with_geometry: true,
            },
        );
        assert!(report.errors.is_empty(), "errors: {:?}", report.errors);
        assert_eq!(report.flownets.len(), 1);
        let fln = &report.flownets[0];
        assert_eq!(fln.name, "Loop");
        assert_eq!(fln.payload.nodes, vec!["a".to_string(), "b".to_string()]);
        // The reference datum is the `ambient` virtual node with its
        // imposed p/T bounds parsed from the two quantity literals.
        assert_eq!(fln.payload.reference.node, "ambient");
        assert_eq!(fln.payload.reference.p.lo, 101.0);
        assert_eq!(fln.payload.reference.p.unit, "kPa");
        assert_eq!(fln.payload.reference.t.lo, 293.0);
        // One medium record resolved through the caller.
        assert_eq!(fln.payload.medium.records.len(), 1);
    }

    #[test]
    fn from_edge_extracts_scalars_and_compliance() {
        let report = elaborate(
            LOOP_SRC,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let edge = &report.flownets[0].payload.edges[0];
        assert_eq!(edge.kind, EdgeKind::Pipe);
        assert_eq!(edge.a, "a");
        assert_eq!(edge.b, "b");
        // Extraction reduced the run to scalar givens.
        let EdgeParams::Scalars { values } = &edge.params else {
            panic!("expected extracted scalars, got {:?}", edge.params);
        };
        assert!(values.contains_key("area"));
        assert!(values.contains_key("length"));
        assert!(values.contains_key("roughness"));
        // The wall record produced compliance + a wave speed cited to the
        // geometry snapshot hash (the D1 medium-coupling boundary).
        let compliance = edge.compliance.as_ref().expect("wall compliance");
        assert_eq!(compliance.snapshot_hash, "blake3:snap-tube");
        assert!(compliance.wave_speed.lo > 0.0);
    }

    #[test]
    fn unresolved_geometry_defers_to_geom_extract() {
        // No realized record backs `line.run`: the edge keeps a deferred
        // GeomExtract selector (the D5 "no extractable wall" case) and no
        // extraction error is raised here.
        let report = elaborate(
            LOOP_SRC,
            &FakeInputs {
                with_geometry: false,
            },
        );
        assert!(
            report.errors.is_empty(),
            "no extraction attempted: {:?}",
            report.errors
        );
        let edge = &report.flownets[0].payload.edges[0];
        assert!(matches!(edge.params, EdgeParams::GeomExtract { .. }));
        assert!(edge.compliance.is_none());
    }

    #[test]
    fn driven_by_imposer_threads_a_promise_given() {
        let src = "flownet Jack(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       mc: Imposer(p=x, driven_by=Handle.force) (a -> b)\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let givens = &report.flownets[0].promise_givens;
        assert_eq!(givens.len(), 1);
        assert_eq!(givens[0].edge_id, "mc");
        assert_eq!(givens[0].var, "p");
        assert_eq!(givens[0].promise_ref, "Handle.force");
    }

    #[test]
    fn record_bound_curve_edge_resolves_curves() {
        let src = "flownet P(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       pmp: Pump(curve=eheim_1250) (a -> b)\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let edge = &report.flownets[0].payload.edges[0];
        assert_eq!(edge.kind, EdgeKind::Pump);
        assert_eq!(edge.curves.len(), 1);
    }

    /// The correctness-sensitive dedup rule (fluorite/03 sec. 1): a state
    /// domain of N discrete values lowers to EXACTLY ONE [`StateDomain`]
    /// (symbolic sweep), never N entries; the domain is carried as one
    /// symbolic set and the payload count stays one regardless of state
    /// cardinality (the ONE-swept-obligation rule, regolith/07 sec. 2).
    #[test]
    fn state_domain_stays_one_swept_entry_not_per_value() {
        let src = "flownet Sw(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n\
            \x20   states:\n\
            \x20       state line_up in {tool_only, gun_only, both}\n\
            \x20       supply.position in {closed, open}\n\
            \x20       event supply.start: commanded by op.sw\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let states = &report.flownets[0].payload.states;
        // Two domain lines -> two StateDomains (the event line is not a
        // swept state); NOT 3 + 2 = 5 per-value entries.
        assert_eq!(states.len(), 2, "states: {states:?}");
        let net_var = states.iter().find(|s| s.var == "line_up").expect("line_up");
        // The three values ride ONE symbolic domain, not three entries.
        assert_eq!(net_var.target, "Sw");
        assert_eq!(net_var.domain, "{tool_only, gun_only, both}");
        let edge_var = states
            .iter()
            .find(|s| s.target == "supply")
            .expect("edge state");
        assert_eq!(edge_var.var, "position");
        assert_eq!(edge_var.domain, "{closed, open}");
    }

    #[test]
    fn elaboration_is_deterministic() {
        let a = elaborate(
            LOOP_SRC,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let b = elaborate(
            LOOP_SRC,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let da = a.flownets[0].payload.content_digest().unwrap();
        let db = b.flownets[0].payload.content_digest().unwrap();
        assert_eq!(da, db, "same source -> identical payload digest (AD-6)");
    }

    #[test]
    fn unknown_medium_records_error_but_still_elaborates_topology() {
        let src = "flownet X(medium=Unknownium):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        assert!(report
            .errors
            .iter()
            .any(|e| matches!(e, FlownetLowerError::UnknownMedium { .. })));
        // Topology still elaborated (empty medium records).
        assert_eq!(report.flownets.len(), 1);
        assert!(report.flownets[0].payload.medium.records.is_empty());
    }

    #[test]
    fn unknown_edge_kind_is_reported_not_panicked() {
        let src = "flownet X(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       cv: CheckValve(crack_dp=5kPa) (a -> b)\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        assert!(report
            .errors
            .iter()
            .any(|e| matches!(e, FlownetLowerError::UnknownEdgeKind { .. })));
    }

    #[test]
    fn scalar_arg_edge_reads_literal_params() {
        let src = "flownet O(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       orf: Orifice(dia=2mm) (a -> b)\n";
        let report = elaborate(
            src,
            &FakeInputs {
                with_geometry: true,
            },
        );
        let edge = &report.flownets[0].payload.edges[0];
        assert_eq!(edge.kind, EdgeKind::Orifice);
        let EdgeParams::Scalars { values } = &edge.params else {
            panic!("expected scalars");
        };
        let dia = values.get("dia").expect("dia param");
        assert_eq!(dia.lo, 2.0);
        assert_eq!(dia.unit, "mm");
        let _ = BTreeMap::<String, ScalarInterval>::new();
    }
}
