//! Pass 5: `RequireClaim` -> `Claim` -> `Obligation`, one per claim
//! line; one `SnapshotRecord` per committed entity scope.
//!
//! Regolith reference: `docs/spec/regolith/07-claims-and-evidence.md` sec.
//! 2, `docs/spec/regolith/13` INV-1 (obligation-key sensitivity). Each
//! `RequireClaim` group's `Field` lines (`subject: predicate`) become
//! one `Obligation` each; `subject_ref` is the enclosing declaration's
//! `EntityDb::snapshot_hash()` (AD-18). A `forall <var> in <domain>:`
//! claim-line prefix (WO-26 D105a) lowers into the obligation's
//! existing `sweep` slot (`SweepDomain`); every other claim line stays
//! a single-point obligation (`sweep: None`).

use std::collections::BTreeMap;

use regolith_diag::codes::{self, TRANSIENT_NO_COMPLIANCE};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_oblig::{
    Claim, ClaimForm, CoverageAxis, CoverageDomain, CoverageMethod, FieldDatum, FlownetPayload,
    Given, Obligation, PayloadRef, SnapshotRecord, SweepDomain, Window,
};
use regolith_qty::Unit;
use regolith_syntax::ast::{AstNode, Decl, Field, File};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::checks::CheckReport;
use crate::contracts::{impl_edge, ConformanceEdge, ContractGraph, RealizationEdge};
use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::flownet_lower::elaborate_flownets;
use crate::frame_lower::elaborate_frames;
use crate::output::ParsedFile;

/// Every obligation this pass produced, the snapshot records for every
/// committed scope, and any diagnostics.
#[derive(Debug, Clone, Default)]
pub struct ObligationSet {
    /// One obligation per structured claim line.
    pub obligations: Vec<Obligation>,
    /// One record per committed `EntityDb` scope.
    pub snapshots: Vec<SnapshotRecord>,
    /// Diagnostics from claim lowering: plain `require` claim lines are
    /// lowered structurally with no ambiguity to report, but WO-32
    /// deliverable 5's fluid transient/volume-budget compliance check
    /// (E0203) fires here, over the elaborated flownet payload, and
    /// WO-33 adds the two the compute-field pass can produce (an
    /// unresolved field reference, a compute-compute cycle).
    pub diagnostics: Vec<Diagnostic>,
    /// WO-32 deliverable 4b: every flownet elaborated while building
    /// fluid obligations (`push_fluid_obligations` is the sole
    /// `elaborate_flownets` call site in this pass, AD-22 -- no second
    /// elaboration happens for emission). Source order.
    pub flownets: Vec<crate::flownet_lower::ElaboratedFlownet>,
    /// WO-33 deliverable 3: one [`FieldDatum`] ledger entry per
    /// `compute` claim, in source order (the datum ledger, regolith/02
    /// sec. 5 precedent -- borrow-exempt, referenced by both tracks).
    pub field_datums: Vec<FieldDatum>,
    /// WO-48 deliverable 3/4: every frame elaborated while building
    /// calcite structural obligations (`push_calcite_frame_obligations`
    /// is the sole `elaborate_frames` call site in this pass, AD-22 --
    /// no second elaboration happens for emission). Source order.
    pub frames: Vec<crate::frame_lower::ElaboratedFrame>,
}

/// Lower every structured `require` group into obligations.
///
/// `realized_inputs` (WO-42 deliverable 3) is the caller-resolved set
/// of realized-domain IR bytes this build was supplied; it backs the
/// fluid-claim pass's `from=` geometry extraction (D128 -- extraction
/// runs in-pipeline when a realized-geometry record is available, and
/// stays the pre-realization `GeomExtract` placeholder otherwise).
#[must_use]
pub fn build_obligations(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
    checks: &CheckReport,
    graph: &ContractGraph,
    realized_inputs: &crate::realized_input::RealizedInputs,
) -> ObligationSet {
    let span = tracing::info_span!("lower.claims");
    let _enter = span.enter();

    let mut out = ObligationSet::default();

    for (scope, db) in &snapshots.scopes {
        out.snapshots.push(SnapshotRecord {
            scope: scope.clone(),
            hash: db.snapshot_hash(),
        });
    }

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let Some(decl_name) = decl.name() else {
                continue;
            };
            // Per-subject INV-20 gating: a poisoned subject produces no
            // obligations (parity with entities.rs, which already dropped
            // its snapshot).
            if decl_is_poisoned(&decl) {
                continue;
            }
            let subject_ref = snapshots
                .scopes
                .get(&decl_name)
                .map(regolith_sem::EntityDb::snapshot_hash)
                .unwrap_or_default();

            // BE-2/INV-1: the decl's structured materials/loads become
            // the obligation's `given:`, so two claims differing ONLY in
            // their governing materials/loads hash to DIFFERENT
            // obligations (and never share cached evidence).
            let given = given_for_decl(&decl);

            // WO-33 D98: collect every `compute` claim in this decl
            // FIRST (across all its `require` groups), so the ordinary
            // claims below can resolve a projection head (`max`/`min`/
            // `at`/`slope`) against the full set of names this decl
            // declares, in one pass -- and so a compute-compute
            // dependency cycle can be checked before any obligation is
            // pushed (cycle diagnostics never fire from a partial view).
            let (compute_producers, compute_over_text) = collect_compute_producers(
                &decl,
                &decl_name,
                &subject_ref,
                &given,
                &mut out.field_datums,
            );

            check_compute_field_cycles(
                &decl_name,
                &compute_over_text,
                &compute_producers,
                &mut out.diagnostics,
            );

            for obligation in compute_producers.values() {
                out.obligations.push(obligation.clone());
            }

            let ctx = ClaimLoweringCtx {
                path: &pf.path,
                decl_name: &decl_name,
                subject_ref: &subject_ref,
                compute_producers: &compute_producers,
                decl: &decl,
                files,
            };
            for group in decl.claims() {
                for line in group.claims() {
                    push_require_obligations(
                        &mut out.obligations,
                        &mut out.diagnostics,
                        &ctx,
                        &line,
                        &given,
                    );
                }
            }
        }
    }

    // WO-28 (design/21 sec. 2, the lower.claims touch point): lower
    // every attached rule's non-clean outcome to an obligation -- a
    // VIOLATED static rule so the release gate and waive ladder see it
    // (its E0601 diagnostic already fired in lower.checks), and a
    // DEFERRED rule (realized facts, unevaluable terms, unpopulated
    // domains) as an honestly indeterminate obligation whose given
    // names the blocking facts (INV-29: never a silent skip).
    push_rule_obligations(&mut out.obligations, &checks.rule_outcomes, snapshots);

    // BE-6/INV-13: one conformance obligation per impl/extern/import
    // binding the contract pass discovered, in its collected (file then
    // source) order, appended after the require-claim obligations.
    for edge in &graph.conformance {
        let obligation = conformance_obligation(edge, snapshots, files, &mut out.diagnostics);
        out.obligations.push(obligation);
    }

    // EOPEN-15 rules 2/3: one demand-implication obligation per workload/
    // compute-intent realization edge, declared or rule-3 DERIVED. The
    // actual rate/state/latency comparison (rule 2's arithmetic) is the
    // discharging model's job (AD-1, harness); the compiler's job here is
    // to emit a self-contained obligation the harness can discharge, with
    // the derived case tagged `cause: derived(intent <name>)` for the
    // lockfile (rule 3, INV-26 default).
    for edge in &graph.realization {
        out.obligations
            .push(realization_obligation(edge, snapshots));
    }

    // WO-32 deliverable 4a: fluorite `require` groups are NOT generic
    // `Decl`s (the front end gives them their own accessor,
    // `File::fluid_requires` -- a top-level require "is NOT a plain
    // Decl", regolith-syntax/ast.rs), so they never reach the
    // `file.decls()` loop above and need a dedicated pass. Every
    // `fluids.*`-form predicate (fluorite/03 sec. 3) lowers to an
    // obligation carrying a `kind: flownet` `PayloadRef` at the file's
    // (sole, per fluorite/02 sec. 1 v1) flownet.
    out.flownets = push_fluid_obligations(
        &mut out.obligations,
        &mut out.diagnostics,
        files,
        realized_inputs,
    );

    // WO-48 deliverable 4 (calcite/03 sec. 5): the same "not a plain
    // Decl" shape applies to calcite's top-level `require` groups (they
    // ride `File::fluid_requires`, the generic top-level-require
    // accessor -- the name is a WO-31 leftover, not fluorite-specific).
    out.frames = push_calcite_frame_obligations(&mut out.obligations, files);

    out
}

/// Elaborate every file's flownet(s) and lower each `fluids.*` require
/// line into an obligation carrying a `kind: flownet` [`PayloadRef`]
/// (fluorite/03 sec. 3). One flownet per file in v1 (fluorite/02 sec.
/// 1: "one medium per connected subnet"), so a file's require lines
/// resolve to its own flownet declaration. Returns every elaborated
/// flownet (WO-32 deliverable 4b: `LowerOutput.flownets`/
/// `BuildPayload.flownets` emission reads this instead of calling
/// `elaborate_flownets` a second time, AD-22's one-producer rule
/// applied within a single crate).
///
/// `realized_inputs` (WO-42 deliverable 3) layers realized-geometry
/// lookup on top of the pure AST-sourced refs (D128: `from=` edges
/// extract in-pipeline when a matching realized-geometry record was
/// supplied; otherwise they keep the deferred `GeomExtract` selector).
fn push_fluid_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    files: &[ParsedFile],
    realized_inputs: &crate::realized_input::RealizedInputs,
) -> Vec<crate::flownet_lower::ElaboratedFlownet> {
    let inputs = crate::flownet_lower::RealizedFlownetInputs::new(files, realized_inputs);
    let report = elaborate_flownets(files, &inputs);
    if !report.errors.is_empty() {
        tracing::debug!(
            errors = report.errors.len(),
            "flownet elaboration errors during fluid claim lowering (rendered elsewhere)"
        );
    }
    let mut flownets_by_name: std::collections::BTreeMap<&str, &FlownetPayload> =
        std::collections::BTreeMap::new();
    for fln in &report.flownets {
        flownets_by_name.insert(fln.name.as_str(), &fln.payload);
    }

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        // v1: at most one flownet per file (fluorite/02 sec. 1); a file
        // with none has no subject for its require lines to bind to.
        let Some(flownet_name) = file.flownets().into_iter().next().and_then(|f| f.name()) else {
            continue;
        };
        let Some(payload) = flownets_by_name.get(flownet_name.as_str()) else {
            continue;
        };
        for req in file.fluid_requires() {
            for line in req.claims() {
                push_fluid_obligation(out, diagnostics, &pf.path, &flownet_name, payload, &line);
            }
        }
    }

    report.flownets
}

/// Lower one fluorite `require` claim [`Field`] line into an obligation
/// carrying the flownet's content-addressed [`PayloadRef`]: every
/// `fluids.*`-form predicate (a bare comparison or a transient
/// `peak(fluids.*, ...)` wrapper, fluorite/03 sec. 3) names the file's
/// flownet as its subject. A non-fluid predicate in the same group
/// (none exist in v1's grammar, but the check stays honest rather than
/// assuming) is skipped, not misfiled as a flownet obligation.
fn push_fluid_obligation(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    path: &camino::Utf8Path,
    flownet_name: &str,
    payload: &FlownetPayload,
    line: &Field,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);
    if !predicate.contains("fluids.") {
        return;
    }

    // WO-32 deliverable 5 (fluorite/03 sec. 1): a transient/volume-budget
    // claim naming an edge with NEITHER a compliance record nor an
    // extractable wall is undischargeable -- reject it here, at compile
    // time, rather than let it fail honestly-indeterminate at solve time.
    // `payload.edges[..].compliance` already folds "record takes
    // precedence over extraction" (fluorite/03 sec. 1), so `None` means
    // neither source produced compliance.
    for edge_id in transient_compliance_edges(&predicate) {
        let Some(edge) = payload.edges.iter().find(|e| e.id == edge_id) else {
            // An edge name the claim references but the net does not
            // declare is a different problem (undeclared reference);
            // not this check's job to report.
            continue;
        };
        if edge.compliance.is_none() {
            tracing::info!(
                flownet = %flownet_name,
                edge = %edge_id,
                "E0203: transient/volume-budget claim over an edge with no compliance"
            );
            let sp = field_span(path, line);
            diagnostics.push(
                Diagnostic::error(
                    TRANSIENT_NO_COMPLIANCE,
                    format!(
                        "edge `{edge_id}` in flownet `{flownet_name}` is named by a \
                         transient/volume-budget claim (`{subject}`) but carries \
                         neither a compliance record nor an extractable wall; the \
                         claim would be undischargeable (fluorite/03 sec. 1)"
                    ),
                )
                .with_span(LabeledSpan::new(
                    sp,
                    "no compliance record or extractable wall for this edge",
                )),
            );
        }
    }

    let digest = match payload.content_digest() {
        Ok(digest) => digest,
        Err(source) => {
            // A non-finite payload float is an upstream compiler bug in
            // extraction/medium-props elsewhere (AD-6/AD-18 encoder
            // refuses to hash it silently); do not fabricate a digest.
            tracing::warn!(
                flownet = %flownet_name,
                error = ?source,
                "flownet payload digest failed, dropping fluid obligation"
            );
            return;
        }
    };

    let resolved_predicate = resolve_unit_suffix(&predicate);
    let claim = Claim {
        name: Some(subject.clone()),
        form: ClaimForm::Comparison {
            lhs: subject.clone(),
            op: "require".to_string(),
            rhs: resolved_predicate,
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };
    let payload_ref = PayloadRef {
        kind: "flownet".to_string(),
        digest: digest.clone(),
        origin: flownet_name.to_string(),
    };
    let obligation = Obligation {
        claim,
        // The flownet's own content-addressed digest is this
        // obligation's subject identity (INV-1: a mutated flownet
        // topology/params must hash to a different obligation) --
        // fluorite has no `EntityDb` snapshot to key on the way
        // hematite/cuprite decls do.
        subject_ref: digest,
        given: Given {
            materials: Vec::new(),
            loads: Vec::new(),
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads: vec![payload_ref],
    };
    tracing::debug!(
        flownet = %flownet_name,
        subject = %subject,
        hash = %obligation.content_hash(),
        "built fluid obligation with flownet payload ref"
    );
    out.push(obligation);
}

/// The 03-lowering sec. 5 claim forms that carry a `frame` [`PayloadRef`]
/// (WO-48 deliverable 4, exactly the table rows this slice covers --
/// `civil.travel_distance`/`exit_capacity`/`dead_end` are discharged
/// statically at L2 with no frame involved, and code-pack `rule`
/// demands are the WO-28 engine's own obligation shape; neither belongs
/// here).
const FRAME_CLAIM_FORMS: [&str; 5] = [
    "civil.utilization(",
    "mech.deflection(",
    "civil.story_drift(",
    "civil.bearing_pressure(",
    "mech.first_mode(",
];

/// Elaborate every file's structure(s) into a [`FramePayload`] and
/// lower each frame-referencing require claim (calcite/03 sec. 5) into
/// an obligation carrying a `kind: frame` [`PayloadRef`]. One structure
/// per file in v1 (mirrors `push_fluid_obligations`'s "one flownet per
/// file" simplification -- every calcite corpus design declares exactly
/// one `structure`), so a file's frame-referencing require lines
/// resolve to its own structure's frame. Returns every elaborated frame
/// (WO-48 deliverable 3: `LowerOutput.frames`/`BuildPayload.frames`
/// emission reads this instead of calling `elaborate_frames` a second
/// time, AD-22's one-producer rule applied within a single crate).
fn push_calcite_frame_obligations(
    out: &mut Vec<Obligation>,
    files: &[ParsedFile],
) -> Vec<crate::frame_lower::ElaboratedFrame> {
    let report = elaborate_frames(files);
    let mut frames_by_name: BTreeMap<&str, &regolith_oblig::FramePayload> = BTreeMap::new();
    for frame in &report.frames {
        frames_by_name.insert(frame.name.as_str(), &frame.payload);
    }

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        // v1: at most one structure per file (see the doc comment
        // above); a file with none has no subject for its frame claims.
        let Some(structure_name) = file.structures().into_iter().next().and_then(|s| s.name())
        else {
            continue;
        };
        let Some(payload) = frames_by_name.get(structure_name.as_str()) else {
            continue;
        };
        for req in file.fluid_requires() {
            for line in req.claims() {
                push_frame_obligation(out, &structure_name, payload, &line);
            }
        }
    }

    report.frames
}

/// Lower one calcite `require` claim [`Field`] line into an obligation
/// carrying the frame's content-addressed [`PayloadRef`], when its
/// predicate is one of the [`FRAME_CLAIM_FORMS`] (calcite/03 sec. 5).
/// Any other predicate in the same group (egress claims, code-pack
/// `rule` demands, ...) is skipped, not misfiled as a frame obligation.
fn push_frame_obligation(
    out: &mut Vec<Obligation>,
    structure_name: &str,
    payload: &regolith_oblig::FramePayload,
    line: &Field,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);
    if !FRAME_CLAIM_FORMS
        .iter()
        .any(|form| predicate.contains(form))
    {
        return;
    }

    let digest = match payload.content_digest() {
        Ok(digest) => digest,
        Err(source) => {
            tracing::warn!(
                structure = %structure_name,
                error = ?source,
                "frame payload digest failed, dropping structural obligation"
            );
            return;
        }
    };

    let claim = Claim {
        name: Some(subject.clone()),
        form: ClaimForm::Comparison {
            lhs: subject.clone(),
            op: "require".to_string(),
            rhs: resolve_unit_suffix(&predicate),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };
    let payload_ref = PayloadRef {
        kind: "frame".to_string(),
        digest: digest.clone(),
        origin: structure_name.to_string(),
    };
    let obligation = Obligation {
        claim,
        // The frame's own content-addressed digest is this
        // obligation's subject identity (INV-1: a mutated frame
        // topology/section/load must hash to a different obligation)
        // -- calcite has no single `EntityDb` snapshot to key on the
        // way hematite/cuprite decls do (the fluorite precedent, verbatim).
        subject_ref: digest,
        given: Given {
            materials: Vec::new(),
            loads: Vec::new(),
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads: vec![payload_ref],
    };
    tracing::debug!(
        structure = %structure_name,
        subject = %subject,
        hash = %obligation.content_hash(),
        "built calcite structural obligation with frame payload ref"
    );
    out.push(obligation);
}

/// The edge ids a transient/volume-budget predicate names (fluorite/03
/// sec. 1, sec. 3 table): `fluids.volume_consumed([<edges>], ...)`'s
/// bracketed edge-id list. Every other `fluids.*` predicate form names
/// no edge this check governs (E0203 scope: WO-32 deliverable 5 flips
/// exactly the `volume_consumed` fixture; a `peak(...)`-wrapped
/// transient claim over a fluid edge is a documented gap -- see the
/// WO-32 D5 close-out note -- left for a follow-up rather than guessed
/// at here).
fn transient_compliance_edges(predicate: &str) -> Vec<String> {
    let Some(call_start) = predicate.find("fluids.volume_consumed(") else {
        return Vec::new();
    };
    let after_call = &predicate[call_start..];
    let Some(lb) = after_call.find('[') else {
        return Vec::new();
    };
    let Some(rb) = after_call[lb..].find(']') else {
        return Vec::new();
    };
    after_call[lb + 1..lb + rb]
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

/// A primary span over a `Field` claim line's full text range.
pub(crate) fn field_span(path: &camino::Utf8Path, line: &Field) -> Span {
    let range = line.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

/// WO-33 D98: build one producer [`Obligation`] (`ClaimForm::Compute`)
/// and one [`FieldDatum`] ledger entry (appended to `field_datums`) per
/// `compute` claim in `decl`, across every `require` group. Returns the
/// declared name -> producer-obligation map plus the name -> `over`
/// text map ([`check_compute_field_cycles`]'s dependency scan), both
/// keyed for [`push_require_obligations`]'s projection-head resolution.
fn collect_compute_producers(
    decl: &Decl,
    decl_name: &str,
    subject_ref: &str,
    given: &Given,
    field_datums: &mut Vec<FieldDatum>,
) -> (BTreeMap<String, Obligation>, BTreeMap<String, String>) {
    let mut compute_producers: BTreeMap<String, Obligation> = BTreeMap::new();
    let mut compute_over_text: BTreeMap<String, String> = BTreeMap::new();
    for group in decl.claims() {
        for cfield in group.compute_claims() {
            let name = cfield.name();
            if name.is_empty() {
                continue;
            }
            let predicate = cfield.predicate_text();
            let (quantity_kind, over_text, axis) = parse_compute_domain(&predicate);
            let claim = Claim {
                name: Some(name.clone()),
                form: ClaimForm::Compute {
                    quantity_kind: quantity_kind.clone(),
                    over: over_text.clone(),
                },
                forall: Vec::new(),
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: Vec::new(),
                model_pin: None,
            };
            let obligation = Obligation {
                claim,
                subject_ref: subject_ref.to_string(),
                given: given.clone(),
                hints: Vec::new(),
                sweep: None,
                payloads: Vec::new(),
            };
            tracing::debug!(
                decl = %decl_name,
                field = %name,
                hash = %obligation.content_hash(),
                "built obligation from compute claim (WO-33 D98)"
            );
            field_datums.push(FieldDatum {
                name: name.clone(),
                quantity_kind,
                axis,
                payload: None,
            });
            compute_over_text.insert(name.clone(), over_text);
            compute_producers.insert(name, obligation);
        }
    }
    (compute_producers, compute_over_text)
}

/// Lower one `require` group's `Field` line (`subject: predicate`) into
/// one or more obligations, appending them to `out`. A `within [lo, hi]`
/// predicate (deliverable 2) splits into two one-sided obligations; every
/// other predicate's unit-suffixed bound resolves through `regolith-qty`
/// (deliverable 1) before becoming the obligation's `Comparison` claim.
///
/// WO-33 D98 deliverable 3: `compute_producers` is this decl's declared
/// field name -> producer-obligation map. When `predicate` names one of
/// those fields through a projection head (`max(name)`, `min(name)`,
/// `<name> at ...`, `slope(name, ...)`), the resulting obligation's
/// `given.refs` gains a `(name, "field:<producer content_hash>")` entry
/// -- the promise-chain reference the orchestrator resolves at
/// discharge time. A projection head naming a field NOT in
/// `compute_producers` pushes an [`codes::UNRESOLVED_FIELD_REFERENCE`]
/// diagnostic instead of silently passing the raw name through.
/// Every argument [`push_require_obligations`] needs but the claim
/// line/subject/predicate themselves -- bundled so the function stays
/// under clippy's argument-count lint.
struct ClaimLoweringCtx<'a> {
    path: &'a camino::Utf8Path,
    decl_name: &'a str,
    subject_ref: &'a str,
    compute_producers: &'a BTreeMap<String, Obligation>,
    /// The enclosing declaration (D103: its `parts:` entries map a
    /// reference head like `comms` to the declared part type).
    decl: &'a Decl,
    /// Every parsed file (D103: cross-file entity-field resolution).
    files: &'a [ParsedFile],
}

fn push_require_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    ctx: &ClaimLoweringCtx<'_>,
    line: &Field,
    given: &Given,
) {
    let subject = line.name();
    let raw_predicate = full_predicate_text(line);

    // WO-26 D105a: a `forall <var> in <domain>:` claim-line prefix
    // lowers into the obligation's EXISTING `sweep` slot (SweepDomain)
    // -- the grammar surface finally exposing what the schema already
    // carries. Both continuous `[lo, hi]` and discrete `{a, b}`
    // domains ride the same path (D93/D95 alignment); the remainder of
    // the line lowers through every path below unchanged.
    let (sweep, predicate) = match parse_forall_prefix(&raw_predicate) {
        Some((axis, domain, rest)) => {
            tracing::debug!(
                decl = %ctx.decl_name,
                subject = %subject,
                axis = %axis,
                domain = %domain,
                "claim line carries a forall sweep prefix (D105a)"
            );
            (Some(SweepDomain { axis, domain }), rest)
        }
        None => (None, raw_predicate),
    };
    let sweep = sweep.as_ref();

    let given = &with_field_refs(
        given,
        ctx.decl_name,
        &subject,
        &predicate,
        ctx.compute_producers,
        diagnostics,
    );

    // WO-26 D102: a recognized temporal claim form (`peak`/`rms`/
    // `overshoot`/`settles`/`stays_within` call syntax) lowers to its
    // typed `ClaimForm` variant instead of the opaque `Comparison`
    // blob. A predicate this parser does not recognize (an `at=`
    // location tag, an unsupported nested shape) falls through to the
    // existing paths below unchanged -- an honest, narrow cut, not a
    // silent guess.
    if push_temporal_obligation(
        out,
        diagnostics,
        ctx,
        line,
        &subject,
        &predicate,
        given,
        sweep,
    ) {
        return;
    }

    // WO-26 deliverable 2: a `within [lo, hi] ...` demanded window splits
    // into TWO one-sided obligations (`>= lo`, `<= hi`) over the SAME
    // subject, reusing the existing scalar-comparison path end to end
    // (the orchestrator never needs a two-sided request type). Each
    // half's bound goes through the same unit-suffix resolution as an
    // ordinary comparator bound.
    if let Some((lo, hi)) = within_window_bounds(&predicate) {
        push_within_window_obligations(out, ctx, &subject, given, sweep, (&lo, &hi));
        return;
    }

    // WO-26 D103: a general comparison claim (`lhs_expr <op> rhs_expr`
    // with the comparator mid-expression -- the Kestrel link budget)
    // splits at its exactly-one top-level comparator; each side stays
    // an ordinary quantity expression, and every entity-field
    // reference term either side names is resolved through the parsed
    // declarations into `given.refs` (reference path -> resolved value
    // source text). More than one top-level comparator is a compile
    // diagnostic (E0437); zero comparators falls through to the
    // pre-existing opaque path below (claims like
    // `manufacturable(milled)` are legitimately not comparisons).
    match split_general_comparison(&predicate) {
        GeneralComparison::Multiple(count) => {
            diagnostics.push(
                Diagnostic::error(
                    codes::GENERAL_COMPARISON_MULTIPLE_COMPARATORS,
                    format!(
                        "claim {subject:?} carries {count} top-level comparators \
                         (WO-26 D103: exactly ONE per claim line -- split the \
                         claim into one line per bound)"
                    ),
                )
                .with_span(LabeledSpan::new(
                    field_span(ctx.path, line),
                    "more than one top-level comparator here",
                )),
            );
            return;
        }
        GeneralComparison::One { lhs, op, rhs } => {
            push_general_comparison_obligation(out, ctx, &subject, given, sweep, (&lhs, &op, &rhs));
            return;
        }
        GeneralComparison::NotComparison => {}
    }

    // WO-26 deliverable 1: resolve any unit-suffixed bound magnitude in
    // the predicate through `regolith-qty` (e.g. `>= 6800 N`, `<=
    // 0.2mm`, `<= 85degC`) into its canonical SI-base numeral BEFORE the
    // text reaches the orchestrator, which parses only bare numerals
    // (regolith/02 sec. 1). A predicate whose bound is not a recognized
    // unit expression (`6dB`, a bare `%`, an entity reference) passes
    // through unchanged -- the orchestrator defers it exactly as before,
    // never a silently invented number.
    let resolved_predicate = resolve_unit_suffix(&predicate);

    let claim = Claim {
        name: Some(subject.clone()),
        form: ClaimForm::Comparison {
            lhs: subject.clone(),
            op: "require".to_string(),
            rhs: resolved_predicate,
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };

    let obligation = Obligation {
        claim,
        subject_ref: ctx.subject_ref.to_string(),
        given: given.clone(),
        hints: Vec::new(),
        sweep: sweep.cloned(),
        payloads: vec![],
    };

    tracing::debug!(
        decl = %ctx.decl_name,
        subject = %subject,
        hash = %obligation.content_hash(),
        "built obligation from require claim"
    );
    out.push(obligation);
}

/// WO-26 deliverable 2: build the two one-sided obligations a
/// `within [lo, hi]` demanded window splits into (`>= lo`, `<= hi`),
/// each bound unit-resolved like an ordinary comparator bound.
fn push_within_window_obligations(
    out: &mut Vec<Obligation>,
    ctx: &ClaimLoweringCtx<'_>,
    subject: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    (lo, hi): (&str, &str),
) {
    for (suffix, op, bound) in [("lo", ">=", lo), ("hi", "<=", hi)] {
        let bound_si = resolve_unit_suffix(bound.trim());
        let name = format!("{subject}.{suffix}");
        let claim = Claim {
            name: Some(name.clone()),
            form: ClaimForm::Comparison {
                lhs: subject.to_string(),
                op: op.to_string(),
                rhs: bound_si,
            },
            forall: Vec::new(),
            sf: None,
            scatter_factor: None,
            trust_floor: None,
            hints: Vec::new(),
            model_pin: None,
        };
        let obligation = Obligation {
            claim,
            subject_ref: ctx.subject_ref.to_string(),
            given: given.clone(),
            hints: Vec::new(),
            sweep: sweep.cloned(),
            payloads: vec![],
        };
        tracing::debug!(
            decl = %ctx.decl_name,
            subject = %name,
            hash = %obligation.content_hash(),
            "built obligation from within[lo,hi] window half"
        );
        out.push(obligation);
    }
}

/// D102: try to recognize `predicate` as a temporal claim-form call and
/// push its obligation/diagnostic. Returns `true` when it handled the
/// claim (obligation pushed or diagnostic pushed) so the caller's
/// untyped fallback paths are skipped; `false` (`NotTemporal`) leaves
/// `out`/`diagnostics` untouched.
#[allow(
    clippy::too_many_arguments,
    reason = "the per-line lowering context (subject/predicate/given/sweep) \
              is one call site's locals; bundling them into a struct would \
              only rename the same eight things"
)]
fn push_temporal_obligation(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    ctx: &ClaimLoweringCtx<'_>,
    line: &Field,
    subject: &str,
    predicate: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
) -> bool {
    match parse_temporal_form(subject, predicate, ctx.path, line) {
        TemporalOutcome::Form(form) => {
            let claim = Claim {
                name: Some(subject.to_string()),
                form,
                forall: Vec::new(),
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: Vec::new(),
                model_pin: None,
            };
            let obligation = Obligation {
                claim,
                subject_ref: ctx.subject_ref.to_string(),
                given: given.clone(),
                hints: Vec::new(),
                sweep: sweep.cloned(),
                payloads: vec![],
            };
            tracing::debug!(
                decl = %ctx.decl_name,
                subject = %subject,
                hash = %obligation.content_hash(),
                "built obligation from temporal claim form (D102)"
            );
            out.push(obligation);
            true
        }
        TemporalOutcome::Diagnosed(diag) => {
            diagnostics.push(diag);
            true
        }
        TemporalOutcome::NotTemporal => false,
    }
}

/// D103: build the one obligation for a general comparison claim
/// (`lhs_expr <op> rhs_expr`, comparator mid-expression), resolving
/// each side's entity-field reference terms into `given.refs`.
fn push_general_comparison_obligation(
    out: &mut Vec<Obligation>,
    ctx: &ClaimLoweringCtx<'_>,
    subject: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    (lhs, op, rhs): (&str, &str, &str),
) {
    let mut given = given.clone();
    for side in [lhs, rhs] {
        for term in expression_ref_terms(side) {
            if let Some(resolved) = resolve_entity_ref(ctx, &term) {
                tracing::info!(
                    decl = %ctx.decl_name,
                    subject = %subject,
                    reference = %term,
                    value = %resolved,
                    "D103 expression given resolved (cause: obligation)"
                );
                given.refs.push((term, resolved));
            } else {
                tracing::info!(
                    decl = %ctx.decl_name,
                    subject = %subject,
                    reference = %term,
                    "D103 expression given did NOT resolve; the orchestrator \
                     defers naming it"
                );
            }
        }
    }
    let claim = Claim {
        name: Some(subject.to_string()),
        form: ClaimForm::Comparison {
            lhs: resolve_unit_suffix(lhs.trim()),
            op: op.to_string(),
            rhs: resolve_unit_suffix(rhs.trim()),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };
    let obligation = Obligation {
        claim,
        subject_ref: ctx.subject_ref.to_string(),
        given,
        hints: Vec::new(),
        sweep: sweep.cloned(),
        payloads: vec![],
    };
    tracing::debug!(
        decl = %ctx.decl_name,
        subject = %subject,
        hash = %obligation.content_hash(),
        "built obligation from general comparison claim (D103)"
    );
    out.push(obligation);
}

/// D105a: split a `forall <var> in <domain>: <rest>` claim-line prefix
/// into `(axis, domain, rest)`. The domain is a bracketed continuous
/// interval (`[lo, hi]`, unit suffixes resolved) or a braced discrete
/// set (`{a, b}`); anything else is not a sweep prefix (the trailing
/// `... forall <cfg>` SUFFIX form is a config-quantification axis, a
/// different surface, and never matches here because it does not LEAD
/// the predicate).
fn parse_forall_prefix(predicate: &str) -> Option<(String, String, String)> {
    let rest = predicate.trim_start().strip_prefix("forall ")?;
    // The axis may itself carry parens (`i(out)`), so find the ` in `
    // separator at paren depth 0.
    let bytes = rest.as_bytes();
    let mut depth = 0i32;
    let mut in_idx = None;
    for i in 0..bytes.len() {
        match bytes[i] {
            b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => depth -= 1,
            b' ' if depth == 0 && rest[i..].starts_with(" in ") => {
                in_idx = Some(i);
                break;
            }
            _ => {}
        }
    }
    let in_idx = in_idx?;
    let axis = rest[..in_idx].trim().to_string();
    let after = rest[in_idx + " in ".len()..].trim_start();
    let close = match after.as_bytes().first()? {
        b'[' => b']',
        b'{' => b'}',
        _ => return None,
    };
    let close_idx = after.bytes().position(|b| b == close)?;
    let domain = resolve_unit_suffix(&after[..=close_idx]);
    let tail = after[close_idx + 1..].trim_start().strip_prefix(':')?;
    Some((axis, domain, tail.trim().to_string()))
}

/// The outcome of scanning a claim predicate for top-level comparators
/// (WO-26 D103).
enum GeneralComparison {
    /// Exactly one top-level comparator with a non-empty left side.
    One {
        /// The left expression text.
        lhs: String,
        /// The comparator (`<`, `<=`, `>`, `>=`).
        op: String,
        /// The right expression text.
        rhs: String,
    },
    /// More than one top-level comparator: a compile diagnostic.
    Multiple(usize),
    /// Zero top-level comparators, or a LEADING comparator (the
    /// existing opaque `op="require"` path already handles a
    /// `subject: <comparator> <bound>` line).
    NotComparison,
}

/// Scan `predicate` for `<`/`<=`/`>`/`>=` at bracket depth 0. An `->`
/// arrow's `>` is not a comparator; neither is anything inside
/// `(...)`/`[...]`/`{...}`.
fn split_general_comparison(predicate: &str) -> GeneralComparison {
    let bytes = predicate.as_bytes();
    let mut depth = 0i32;
    let mut found: Vec<(usize, usize)> = Vec::new(); // (index, token length)
    let mut i = 0usize;
    while i < bytes.len() {
        match bytes[i] {
            b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => depth -= 1,
            b'<' | b'>' if depth == 0 => {
                let is_arrow_head = bytes[i] == b'>' && i > 0 && bytes[i - 1] == b'-';
                if !is_arrow_head {
                    let len = if bytes.get(i + 1) == Some(&b'=') {
                        2
                    } else {
                        1
                    };
                    found.push((i, len));
                    i += len;
                    continue;
                }
            }
            _ => {}
        }
        i += 1;
    }
    match found.as_slice() {
        [] => GeneralComparison::NotComparison,
        [(idx, len)] => {
            let lhs = predicate[..*idx].trim();
            if lhs.is_empty() {
                return GeneralComparison::NotComparison;
            }
            GeneralComparison::One {
                lhs: lhs.to_string(),
                op: predicate[*idx..idx + len].to_string(),
                rhs: predicate[idx + len..].trim().to_string(),
            }
        }
        many => GeneralComparison::Multiple(many.len()),
    }
}

/// D103: the dotted entity-field reference terms of one comparison
/// side (`comms.pa_out + antenna.gain - path_loss(...)` yields
/// `comms.pa_out` and `antenna.gain`; the `path_loss(...)` CALL term
/// and numeric-leading terms are not entity refs). The side's trailing
/// window/quantifier clause (` during ...`, ` until ...`) is ignored.
fn expression_ref_terms(side: &str) -> Vec<String> {
    // Cut the trailing window clause off at depth 0.
    let mut text = side;
    for marker in [" during ", " until ", " forall "] {
        if let Some(idx) = find_top_level(text, marker) {
            text = &text[..idx];
        }
    }
    let mut terms = Vec::new();
    let bytes = text.as_bytes();
    let mut depth = 0i32;
    let mut start = 0usize;
    let push_term = |term: &str, terms: &mut Vec<String>| {
        let term = term.trim();
        if is_dotted_ref(term) {
            terms.push(term.to_string());
        }
    };
    for (i, &b) in bytes.iter().enumerate() {
        match b {
            b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => depth -= 1,
            b'+' | b'-' if depth == 0 => {
                push_term(&text[start..i], &mut terms);
                start = i + 1;
            }
            _ => {}
        }
    }
    push_term(&text[start..], &mut terms);
    terms
}

/// The byte index of `needle` in `haystack` at bracket depth 0, if any.
fn find_top_level(haystack: &str, needle: &str) -> Option<usize> {
    let bytes = haystack.as_bytes();
    let mut depth = 0i32;
    for i in 0..bytes.len() {
        match bytes[i] {
            b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => depth -= 1,
            _ if depth == 0 && haystack[i..].starts_with(needle) => return Some(i),
            _ => {}
        }
    }
    None
}

/// True iff `term` is exactly `<ident>.<ident>` (a two-segment dotted
/// entity-field reference -- the D103 shape; deeper paths like
/// `boundary.orbit.slant_max` name nested boundary structure this
/// text-level resolver does not walk, an honest recorded narrowing).
fn is_dotted_ref(term: &str) -> bool {
    let Some((head, field)) = term.split_once('.') else {
        return false;
    };
    let is_ident = |s: &str| {
        !s.is_empty()
            && s.chars()
                .next()
                .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
            && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
    };
    is_ident(head) && is_ident(field)
}

/// D103: resolve the two-segment reference `a.b` -- `a` is a part/
/// field of the enclosing declaration whose value names a declared
/// type (or a top-level declaration itself), `b` is a field of that
/// declaration carrying either a comparator-bound promise
/// (`pa_out: ... >= 26dBm ...` resolves to its bound, `26dBm`) or a
/// plain value (`sensitivity: -110dBm`). Returns the resolved value
/// source text, or `None` (the orchestrator then defers naming the
/// reference -- never an invented number). Resolution provenance is
/// the reference path plus the resolving declaration/field, logged at
/// info level with its INV-21 cause class (`obligation`).
fn resolve_entity_ref(ctx: &ClaimLoweringCtx<'_>, reference: &str) -> Option<String> {
    let (head, field_name) = reference.split_once('.')?;
    let target = part_type_of(ctx.decl, head).unwrap_or_else(|| head.to_string());
    let decl = find_decl(ctx.files, &target)?;
    let text = find_field_value_text(&decl, field_name)?;
    Some(bound_or_value_text(&text))
}

/// The declared type name of the enclosing decl's part/field `name`
/// (`comms: CommsPcb(...)` -> `CommsPcb`), if any.
fn part_type_of(decl: &Decl, name: &str) -> Option<String> {
    for node in decl.syntax().descendants() {
        if let Some(field) = Field::cast(node) {
            if field.name() == name {
                let value = full_predicate_text(&field);
                let head: String = value
                    .chars()
                    .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
                    .collect();
                if !head.is_empty() && head.chars().next().is_some_and(char::is_alphabetic) {
                    return Some(head);
                }
            }
        }
    }
    None
}

/// The top-level declaration named `name` across every parsed file.
fn find_decl(files: &[ParsedFile], name: &str) -> Option<Decl> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.name().as_deref() == Some(name) {
                return Some(decl);
            }
        }
    }
    None
}

/// The full `: ...` value text of the FIRST field named `field_name`
/// anywhere under `decl` (source order), if any.
fn find_field_value_text(decl: &Decl, field_name: &str) -> Option<String> {
    for node in decl.syntax().descendants() {
        if let Some(field) = Field::cast(node) {
            if field.name() == field_name {
                let text = full_predicate_text(&field);
                if !text.is_empty() {
                    return Some(text);
                }
            }
        }
    }
    None
}

/// Reduce a resolved field's text to its VALUE: a leading-comparator
/// bound field (`>= 26dBm during ...`) or a mid-expression comparison
/// promise (`elec.power(x) >= 26dBm during ...`) resolves to the bound
/// side; a plain value field passes through whole. The trailing
/// window/quantifier clause is dropped either way.
fn bound_or_value_text(text: &str) -> String {
    let trimmed = text.trim();
    let after_comparator = ["<=", ">=", "<", ">"]
        .iter()
        .find_map(|comp| trimmed.strip_prefix(comp))
        .map(str::trim)
        .map(str::to_string);
    let value = match after_comparator {
        Some(bound) => bound,
        None => match split_general_comparison(trimmed) {
            GeneralComparison::One { rhs, .. } => rhs,
            _ => trimmed.to_string(),
        },
    };
    let mut value = value.as_str();
    for marker in [" during ", " until ", " forall "] {
        if let Some(idx) = find_top_level(value, marker) {
            value = &value[..idx];
        }
    }
    value.trim().to_string()
}

/// The result of attempting to recognize `predicate` as one of the
/// D102 temporal claim-form calls.
enum TemporalOutcome {
    /// Recognized and lowered to a typed `ClaimForm`.
    Form(ClaimForm),
    /// Recognized but shape-invalid (missing/unexpected comparator);
    /// the diagnostic to emit instead of an obligation.
    Diagnosed(Diagnostic),
    /// Not a recognized temporal call at all -- fall through to the
    /// existing untyped paths.
    NotTemporal,
}

/// Find `name(` at the head of `predicate` (after trimming) and return
/// the balanced-paren argument text plus whatever trails the closing
/// paren, or `None` if `predicate` does not start with that exact call.
fn match_call<'a>(predicate: &'a str, name: &str) -> Option<(&'a str, &'a str)> {
    let trimmed = predicate.trim_start();
    let rest = trimmed.strip_prefix(name)?;
    let rest = rest.strip_prefix('(')?;
    let mut depth = 1i32;
    for (idx, ch) in rest.char_indices() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => {
                depth -= 1;
                if depth == 0 {
                    // `ch` here is always `)` (the only way depth can
                    // reach zero starting from a `(`-opened call).
                    let args = &rest[..idx];
                    let after = &rest[idx + 1..];
                    return Some((args, after));
                }
            }
            _ => {}
        }
    }
    None
}

/// Split `args` on top-level commas (depth-0 only -- nested `(...)`/
/// `[...]` commas, e.g. `band=[10Hz, 1kHz]`, stay inside their piece).
fn split_top_level_args(args: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut depth = 0i32;
    let mut start = 0usize;
    for (idx, ch) in args.char_indices() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => depth -= 1,
            ',' if depth == 0 => {
                out.push(args[start..idx].trim().to_string());
                start = idx + 1;
            }
            _ => {}
        }
    }
    let tail = args[start..].trim();
    if !tail.is_empty() {
        out.push(tail.to_string());
    }
    out
}

/// Parse a positional `during <event>` or `within <dur> after <event>`
/// argument into a [`Window`]. Returns `None` for any other shape
/// (e.g. an `at=<location>` tag, which is not a temporal window).
fn parse_window_arg(arg: &str) -> Option<Window> {
    let arg = arg.trim();
    if let Some(event) = arg.strip_prefix("during ") {
        return Some(Window::During(event.trim().to_string()));
    }
    if let Some(rest) = arg.strip_prefix("within ") {
        let (duration, rest) = rest.split_once(" after ")?;
        // The bounding duration resolves through `regolith-qty` like
        // every other bound (`500us` -> `0.0005`), so the orchestrator
        // can read a containment window's limit as a bare numeral.
        return Some(Window::WithinAfter {
            duration: resolve_unit_suffix(duration.trim()),
            event: rest.trim().to_string(),
        });
    }
    if let Some(event) = arg.strip_prefix("until ") {
        return Some(Window::Until(event.trim().to_string()));
    }
    None
}

/// Split a `key=value` argument, or `None` if `arg` carries no `=`.
fn split_kwarg(arg: &str) -> Option<(&str, &str)> {
    let (key, value) = arg.split_once('=')?;
    Some((key.trim(), value.trim()))
}

/// The comparator tokens a REDUCTION form's trailing text may lead
/// with, longest first (`<=`/`>=` before `<`/`>`).
const TEMPORAL_COMPARATORS: [&str; 4] = ["<=", ">=", "<", ">"];

/// Split `after` (the text following a recognized call's closing
/// paren) into `(op, rhs)` if it leads with a comparator, else `None`.
fn split_trailing_comparator(after: &str) -> Option<(String, String)> {
    let trimmed = after.trim();
    for comp in TEMPORAL_COMPARATORS {
        if let Some(rhs) = trimmed.strip_prefix(comp) {
            return Some((comp.to_string(), resolve_unit_suffix(rhs.trim())));
        }
    }
    None
}

/// WO-26 D102: recognize `predicate` as a temporal claim-form call
/// (`peak`/`rms`/`overshoot`/`settles`/`stays_within`) and lower it to
/// its typed `ClaimForm`, or report why it could not be recognized.
///
/// Scope, deliberately narrow (this dispatch, not a design decision):
/// REDUCTIONS (`peak`/`rms`/`overshoot`) are only recognized when
/// their window argument (if any) is a `during`/`within .. after`/
/// `until` clause this pass understands -- a `peak(x, at=<location>)`
/// spatial tag is not a temporal window at all (D102 only speaks to
/// the temporal family) and is left as `NotTemporal`, falling through
/// to the pre-existing untyped `Comparison` lowering exactly as
/// before. `stays_within` types both the un-windowed and windowed
/// forms (WO-54 rider: the schema's `ClaimForm::StaysWithin` now
/// carries an optional `window` field).
fn parse_temporal_form(
    subject: &str,
    predicate: &str,
    path: &camino::Utf8Path,
    line: &Field,
) -> TemporalOutcome {
    for name in ["peak", "rms", "overshoot"] {
        if let Some((args, after)) = match_call(predicate, name) {
            let outcome = parse_reduction_form(subject, name, args, after, path, line);
            if !matches!(outcome, TemporalOutcome::NotTemporal) {
                return outcome;
            }
        }
    }
    if let Some((args, after)) = match_call(predicate, "settles") {
        let outcome = parse_settles_form(subject, args, after, path, line);
        if !matches!(outcome, TemporalOutcome::NotTemporal) {
            return outcome;
        }
    }
    if let Some((args, after)) = match_call(predicate, "stays_within") {
        let outcome = parse_stays_within_form(subject, args, after, path, line);
        if !matches!(outcome, TemporalOutcome::NotTemporal) {
            return outcome;
        }
    }
    TemporalOutcome::NotTemporal
}

/// D102 REDUCTION forms (`peak`/`rms`/`overshoot`): `signal[, window]
/// <op> <rhs>`, external comparator REQUIRED. See
/// [`parse_temporal_form`]'s doc comment for the scope this narrows to
/// (a `peak(x, at=<location>)` spatial tag, or `rms` with no `band=`,
/// falls through as `NotTemporal`).
fn parse_reduction_form(
    subject: &str,
    name: &str,
    args: &str,
    after: &str,
    path: &camino::Utf8Path,
    line: &Field,
) -> TemporalOutcome {
    let parts = split_top_level_args(args);
    if parts.is_empty() {
        return TemporalOutcome::NotTemporal;
    }
    let signal = parts[0].clone();

    // Every non-first positional/kwarg argument must resolve to
    // something this pass understands, or the call is left untouched
    // (NotTemporal) rather than half-built.
    let mut window: Option<Window> = None;
    let mut band: Option<String> = None;
    let mut event: Option<String> = None;
    for extra in &parts[1..] {
        if name == "rms" {
            if let Some(("band", value)) = split_kwarg(extra) {
                band = Some(value.to_string());
                continue;
            }
        }
        if let Some(w) = parse_window_arg(extra) {
            window = Some(w);
            continue;
        }
        if name == "overshoot" {
            if let Some(after_event) = extra.strip_prefix("after ") {
                event = Some(after_event.trim().to_string());
                continue;
            }
        }
        return TemporalOutcome::NotTemporal;
    }
    if name == "rms" && band.is_none() {
        return TemporalOutcome::NotTemporal;
    }
    // `peak` with no window argument at all has no temporal anchor to
    // type (every corpus use carries one); leave it untouched rather
    // than invent a placeholder window.
    if name == "peak" && window.is_none() {
        return TemporalOutcome::NotTemporal;
    }

    let Some((op, rhs)) = split_trailing_comparator(after) else {
        return TemporalOutcome::Diagnosed(
            Diagnostic::error(
                codes::TEMPORAL_REDUCTION_MISSING_COMPARATOR,
                format!(
                    "claim {subject:?} calls `{name}(...)` (a REDUCTION form) \
                     with no trailing comparator (WO-26 D102 requires one: \
                     `{name}(...) <op> <rhs>`)"
                ),
            )
            .with_span(LabeledSpan::new(
                field_span(path, line),
                "no trailing comparator here",
            )),
        );
    };

    let form = match name {
        "peak" => ClaimForm::Peak {
            signal,
            window: window.unwrap_or(Window::During(String::new())),
            op,
            rhs,
        },
        "rms" => ClaimForm::Rms {
            signal,
            band: band.unwrap_or_default(),
            op,
            rhs,
        },
        "overshoot" => ClaimForm::Overshoot {
            signal,
            event: event.unwrap_or_default(),
            op,
            rhs,
        },
        _ => unreachable!("caller iterates only peak/rms/overshoot"),
    };
    TemporalOutcome::Form(form)
}

/// D102 CONTAINMENT form `settles(x, to=tol, within d after e)`: self-
/// contained, NO trailing comparator allowed.
fn parse_settles_form(
    subject: &str,
    args: &str,
    after: &str,
    path: &camino::Utf8Path,
    line: &Field,
) -> TemporalOutcome {
    let parts = split_top_level_args(args);
    if parts.len() < 2 {
        return TemporalOutcome::NotTemporal;
    }
    let signal = parts[0].clone();
    let mut tol: Option<String> = None;
    let mut window: Option<Window> = None;
    for extra in &parts[1..] {
        if let Some(("to", value)) = split_kwarg(extra) {
            tol = Some(value.to_string());
            continue;
        }
        if let Some(w) = parse_window_arg(extra) {
            window = Some(w);
            continue;
        }
        return TemporalOutcome::NotTemporal;
    }
    let (Some(tol), Some(window)) = (tol, window) else {
        return TemporalOutcome::NotTemporal;
    };
    if split_trailing_comparator(after).is_some() {
        return TemporalOutcome::Diagnosed(
            Diagnostic::error(
                codes::TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR,
                format!(
                    "claim {subject:?} calls `settles(...)` (a CONTAINMENT \
                     form) with a trailing comparator (WO-26 D102: its `to=` \
                     tolerance IS the acceptance -- no external comparator)"
                ),
            )
            .with_span(LabeledSpan::new(
                field_span(path, line),
                "unexpected trailing comparator here",
            )),
        );
    }
    TemporalOutcome::Form(ClaimForm::Settles {
        signal,
        tol,
        window,
    })
}

/// D102 CONTAINMENT form `stays_within(x, mask=<ref>)`: self-
/// contained, NO trailing comparator allowed. WO-54 rider: a windowed
/// use (`, during ...`/`, within .. after ..`/`, until ...`) now types
/// through the schema's `window` field (the dune_buggy/buck_converter
/// corpus shape); the WO-26 D102 residual recording it as untyped is
/// closed.
fn parse_stays_within_form(
    subject: &str,
    args: &str,
    after: &str,
    path: &camino::Utf8Path,
    line: &Field,
) -> TemporalOutcome {
    let parts = split_top_level_args(args);
    if parts.len() < 2 {
        return TemporalOutcome::NotTemporal;
    }
    let signal = parts[0].clone();
    let mut mask: Option<String> = None;
    let mut window: Option<Window> = None;
    for extra in &parts[1..] {
        if let Some(("mask", value)) = split_kwarg(extra) {
            mask = Some(value.to_string());
            continue;
        }
        if let Some(w) = parse_window_arg(extra) {
            window = Some(w);
            continue;
        }
        return TemporalOutcome::NotTemporal;
    }
    let Some(mask) = mask else {
        return TemporalOutcome::NotTemporal;
    };
    if split_trailing_comparator(after).is_some() {
        return TemporalOutcome::Diagnosed(
            Diagnostic::error(
                codes::TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR,
                format!(
                    "claim {subject:?} calls `stays_within(...)` (a \
                     CONTAINMENT form) with a trailing comparator (WO-26 \
                     D102: its `mask=` IS the acceptance -- no external \
                     comparator)"
                ),
            )
            .with_span(LabeledSpan::new(
                field_span(path, line),
                "unexpected trailing comparator here",
            )),
        );
    }
    TemporalOutcome::Form(ClaimForm::StaysWithin {
        signal,
        mask,
        window,
    })
}

/// WO-33 D98: split a `compute` claim's predicate text
/// (`<quantity kind> over <index domain>`) into `(quantity_kind,
/// over_text, axis)`. `over_text` is kept verbatim (the harness half
/// interprets it); `axis` is the DECLARED `CoverageAxis` for the
/// `FieldDatum` ledger entry, with `method: Undischarged` -- no model
/// has resolved it yet (this WO's honest interim, see the module doc's
/// non-goals). A `<var> in [lo, hi]` domain is a continuous interval
/// axis named `<var>`; anything else (a zone-set reference, e.g.
/// `liner.zones`) is an enumerated axis with the reference itself as
/// its one (unexpanded) value -- the actual zone membership is a
/// semantic fact this text-only pass does not resolve.
fn parse_compute_domain(predicate: &str) -> (String, String, CoverageAxis) {
    let (quantity_kind, over_text) = match predicate.split_once(" over ") {
        Some((q, o)) => (q.trim().to_string(), o.trim().to_string()),
        None => (predicate.trim().to_string(), String::new()),
    };

    let axis = if let Some((var, rest)) = over_text.split_once(" in ") {
        CoverageAxis {
            axis: var.trim().to_string(),
            domain: CoverageDomain::Interval(rest.trim().to_string()),
            method: CoverageMethod::Undischarged,
        }
    } else {
        CoverageAxis {
            axis: over_text.clone(),
            domain: CoverageDomain::Values {
                values: vec![over_text.clone()],
            },
            method: CoverageMethod::Undischarged,
        }
    };

    (quantity_kind, over_text, axis)
}

/// True iff `word` occurs in `haystack` as a whole identifier (not a
/// substring of a longer one): neither the character before nor after
/// the match is alphanumeric, `_`, or `.` (so `wall_T` does not match
/// inside `wall_Total`, and a dotted path is never partially matched).
/// Shared by the projection-head extraction and the compute-cycle scan.
fn contains_word(haystack: &str, word: &str) -> bool {
    if word.is_empty() {
        return false;
    }
    let mut search_from = 0usize;
    while let Some(rel) = haystack[search_from..].find(word) {
        let idx = search_from + rel;
        let before_ok = haystack[..idx]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_' && c != '.');
        let after = &haystack[idx + word.len()..];
        let after_ok = after
            .chars()
            .next()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_' && c != '.');
        if before_ok && after_ok {
            return true;
        }
        search_from = idx + word.len();
    }
    false
}

/// WO-33 D98: extract every projection-head field reference from a
/// predicate (`max(name)`, `min(name)`, `slope(name, ...)`, or a
/// leading `<name> at ...` form), in source order. This is a
/// deliberately narrow, text-only recognizer -- it does not parse a
/// general call expression -- matching the same "kept as text" stance
/// as the rest of this pass (`full_predicate_text`, `resolve_unit_suffix`).
fn extract_projection_heads(predicate: &str) -> Vec<String> {
    let mut refs = Vec::new();
    for head in ["max(", "min(", "slope("] {
        let mut search_from = 0usize;
        while let Some(rel) = predicate[search_from..].find(head) {
            let match_start = search_from + rel;
            let start = match_start + head.len();
            let arg_end = predicate[start..]
                .find([',', ')'])
                .map_or(predicate.len(), |i| start + i);
            let name = predicate[start..arg_end].trim();
            if !name.is_empty() {
                refs.push(name.to_string());
            }
            search_from = arg_end.max(start);
        }
    }
    // `<name> at zone(...)` / `<name> at <var>(...)`: the leading
    // dotted identifier before a top-level " at " qualifier.
    if let Some(at_idx) = predicate.find(" at ") {
        let lead = predicate[..at_idx].trim();
        if !lead.is_empty()
            && lead
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
        {
            refs.push(lead.to_string());
        }
    }
    refs
}

/// WO-33 D98 deliverable 3: fold `predicate`'s projection-head field
/// references into `given.refs` (as `(name, "field:<content_hash>")`
/// pairs, the promise-chain reference), diagnosing any reference to a
/// field NOT in `compute_producers` as [`codes::UNRESOLVED_FIELD_REFERENCE`]
/// rather than passing the raw name through silently.
fn with_field_refs(
    given: &Given,
    decl_name: &str,
    subject: &str,
    predicate: &str,
    compute_producers: &BTreeMap<String, Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
) -> Given {
    let mut out = given.clone();
    for name in extract_projection_heads(predicate) {
        if let Some(producer) = compute_producers.get(&name) {
            out.refs
                .push((name, format!("field:{}", producer.content_hash())));
        } else {
            tracing::debug!(
                decl = %decl_name,
                subject = %subject,
                field = %name,
                "compute-field projection names an undeclared field"
            );
            diagnostics.push(Diagnostic::error(
                codes::UNRESOLVED_FIELD_REFERENCE,
                format!(
                    "`{subject}` projects field `{name}`, but `{decl_name}` \
                     declares no `compute {name}: ...` claim"
                ),
            ));
        }
    }
    out
}

/// WO-33 D98: detect a cycle in the compute-field promise DAG within
/// one decl -- a `compute` claim whose `over` text (directly or
/// transitively) references another compute field that, in turn,
/// depends back on it. Standard white/gray/black DFS; on the first
/// back-edge found, names the full chain in one diagnostic (never a
/// panic/infinite loop, and never more than one diagnostic per decl --
/// fixing the first reported cycle is enough to re-run the check).
fn check_compute_field_cycles(
    decl_name: &str,
    over_text: &BTreeMap<String, String>,
    compute_producers: &BTreeMap<String, Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let names: Vec<&String> = compute_producers.keys().collect();
    let neighbors = |n: &str| -> Vec<String> {
        let Some(text) = over_text.get(n) else {
            return Vec::new();
        };
        names
            .iter()
            .filter(|other| other.as_str() != n && contains_word(text, other))
            .map(|s| (*s).clone())
            .collect()
    };

    let mut state: BTreeMap<String, u8> = BTreeMap::new(); // 0=white,1=gray,2=black
    for start in &names {
        if state.get(start.as_str()).copied().unwrap_or(0) != 0 {
            continue;
        }
        let mut stack: Vec<(String, usize)> = vec![((*start).clone(), 0)];
        let mut path: Vec<String> = vec![(*start).clone()];
        state.insert((*start).clone(), 1);
        while let Some((node, idx)) = stack.pop() {
            let succ = neighbors(&node);
            if idx < succ.len() {
                let next = succ[idx].clone();
                stack.push((node.clone(), idx + 1));
                match state.get(&next).copied().unwrap_or(0) {
                    0 => {
                        state.insert(next.clone(), 1);
                        path.push(next.clone());
                        stack.push((next, 0));
                    }
                    1 => {
                        // Back edge: a cycle from `next` to `next` through `path`.
                        let cycle_start = path.iter().position(|p| p == &next).unwrap_or(0);
                        let mut chain: Vec<String> = path[cycle_start..].to_vec();
                        chain.push(next.clone());
                        diagnostics.push(Diagnostic::error(
                            codes::COMPUTE_FIELD_CYCLE,
                            format!(
                                "compute-field cycle in `{decl_name}`: {}",
                                chain.join(" -> ")
                            ),
                        ));
                        return;
                    }
                    _ => {}
                }
            } else {
                state.insert(node.clone(), 2);
                if path.last() == Some(&node) {
                    path.pop();
                }
            }
        }
    }
}

/// Build the EOPEN-15 demand-implication obligation for one
/// [`RealizationEdge`]: a `<workload> implies <intent>` claim keyed on
/// the enclosing system's snapshot. A rule-3 DERIVED edge additionally
/// carries `cause: derived(intent <name>)` in `given.loads` and its
/// hints, so the orchestrator/lockfile can surface the allocation
/// (cuprite/05 sec. 1; the intent's demands themselves are not
/// structurally available here -- `intents:` bodies are opaque islands,
/// WO-05 -- so no numeric copy happens in the core; the harness/lockfile
/// side threads the demand values, tracked in `docs/audit/TRIAGE.md`).
fn realization_obligation(edge: &RealizationEdge, snapshots: &EntitySnapshots) -> Obligation {
    let subject_ref = snapshots
        .scopes
        .get(&edge.system)
        .map(regolith_sem::EntityDb::snapshot_hash)
        .unwrap_or_default();
    let claim = Claim {
        name: Some(format!("realizes:{}:{}", edge.workload, edge.intent)),
        form: ClaimForm::Comparison {
            lhs: edge.workload.clone(),
            op: "implies".to_string(),
            rhs: edge.intent.clone(),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: if edge.derived {
            vec![format!("derived(intent {})", edge.intent)]
        } else {
            Vec::new()
        },
        model_pin: None,
    };
    let loads = if edge.derived {
        vec![format!("cause: derived(intent {})", edge.intent)]
    } else {
        Vec::new()
    };
    let obligation = Obligation {
        claim,
        subject_ref,
        given: Given {
            materials: Vec::new(),
            loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: if edge.derived {
            vec![format!("derived(intent {})", edge.intent)]
        } else {
            Vec::new()
        },
        sweep: None,
        payloads: vec![],
    };
    tracing::debug!(
        system = %edge.system,
        workload = %edge.workload,
        intent = %edge.intent,
        derived = edge.derived,
        hash = %obligation.content_hash(),
        "built realization demand-implication obligation (EOPEN-15 rules 2/3)"
    );
    obligation
}

/// Build the INV-13 conformance obligation for one impl/extern/import
/// [`ConformanceEdge`]: a `<upper> conforms <lower>` claim keyed on the
/// enclosing subject's snapshot (empty for a file-level `import`).
fn conformance_obligation(
    edge: &ConformanceEdge,
    snapshots: &EntitySnapshots,
    files: &[ParsedFile],
    diagnostics: &mut Vec<Diagnostic>,
) -> Obligation {
    let subject_ref = snapshots
        .scopes
        .get(&edge.subject)
        .map(regolith_sem::EntityDb::snapshot_hash)
        .unwrap_or_default();
    let claim = Claim {
        name: Some(format!("{}:{}", edge.kind, edge.upper)),
        form: ClaimForm::Comparison {
            lhs: edge.upper.clone(),
            op: "conforms".to_string(),
            rhs: edge.lower.clone(),
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin: None,
    };
    // BE-6/INV-13: when BOTH the upper contract and the lower realization
    // carry a resolved leading comparator bound (`q: <= 20` vs `q: <= 14`),
    // thread the two refinement windows into `given.loads` so the
    // orchestrator can lower the conformance obligation into a real
    // `DischargeRequest` (the harness conformance model, AD-1). Absent a
    // literal bound on either side the windows are simply not carried and
    // the orchestrator defers the obligation honestly -- no invented window.
    let loads = conformance_windows(edge, files, diagnostics).map_or_else(
        Vec::new,
        |(sense, spec, imp)| {
            vec![
                format!("conformance_sense: {sense}"),
                format!("spec_bound: {spec}"),
                format!("impl_bound: {imp}"),
            ]
        },
    );
    let obligation = Obligation {
        claim,
        subject_ref,
        given: Given {
            materials: Vec::new(),
            loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads: vec![],
    };
    tracing::debug!(
        kind = %edge.kind,
        upper = %edge.upper,
        lower = %edge.lower,
        hash = %obligation.content_hash(),
        "built conformance obligation (INV-13)"
    );
    obligation
}

/// Extract the `(sense, spec_bound, impl_bound)` refinement window for
/// an `impl` conformance edge, matching the upper contract's promised
/// comparator-bound fields (the interface named by `edge.upper`) against
/// the lower realization's (the impl body's) same-named fields (WO-26
/// D104: field NAME is the identity, per the WO-12 contract IR's
/// existing source-level keying -- names are already unique per
/// interface, L1-checked). Returns `None` for import/extern edges, or
/// when the interface declares no comparator-bound field at all. For
/// each promised name with a same-named impl field whose sense agrees
/// (`q: <= 20` refined by `q: <= 14`), the FIRST such match (source
/// order) is returned.
///
/// A promised name with NO same-named impl field pushes a constructive
/// [`codes::PROMISED_BOUND_UNMATCHED`] diagnostic naming both sides --
/// but ONLY when the impl body realizes at least one OTHER comparator-
/// bound field, i.e. it looks like an attempted refinement whose name
/// drifted from the promise. An impl that carries NO comparator-bound
/// fields at all is not diagnosed: the corpus's `FittingPort.leak`
/// promise (espresso_machine/fittings.hema) is never locally refined by
/// any implementing part -- it is consumed by the flownet leak-budget
/// chain instead (fluorite/02 sec. 6), a legitimate promise-without-
/// local-refinement shape D104's text did not anticipate. A sense
/// DISagreement between two same-named fields is likewise not an error
/// -- that pair is simply not a refinement window, and the obligation
/// still defers honestly rather than the compiler inventing one
/// (INV-13/26).
fn conformance_windows(
    edge: &ConformanceEdge,
    files: &[ParsedFile],
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<(String, f64, f64)> {
    if edge.kind != "impl" {
        return None;
    }
    let spec_fields = interface_bound_fields(&edge.upper, files);
    if spec_fields.is_empty() {
        return None;
    }
    let impl_fields = impl_bound_fields(edge, files);
    let mut result = None;
    let any_impl_bound_field = !impl_fields.is_empty();
    for (name, (spec_sense, spec_bound)) in &spec_fields {
        match impl_fields.get(name) {
            Some((impl_sense, impl_bound)) => {
                if result.is_none() && spec_sense == impl_sense {
                    result = Some((spec_sense.clone(), *spec_bound, *impl_bound));
                }
            }
            None => {
                // WO-26 D104 nuance the corpus surfaced (espresso_machine's
                // `FittingPort.leak` promise, realized nowhere in the impl
                // body -- it is consumed by the flownet budget chain
                // instead, fluorite/02 sec. 6): a promised name is only a
                // constructive diagnostic when the impl body realizes NO
                // comparator-bound fields at all yet still binds this
                // edge, i.e. it looks like an attempted refinement that
                // typo'd the name. An impl that legitimately carries
                // OTHER bound fields (or none, because its promises are
                // consumed elsewhere in the promise chain) is not an
                // error -- the obligation simply has no window for THIS
                // name and defers honestly, same as before D104.
                if any_impl_bound_field {
                    diagnostics.push(Diagnostic::error(
                        codes::PROMISED_BOUND_UNMATCHED,
                        format!(
                            "interface `{}` promises bound field `{name}`, but the \
                             impl for `{}` declares no matching `{name}:` field \
                             (it declares other bound fields, so this looks like \
                             a name mismatch rather than a promise consumed \
                             elsewhere)",
                            edge.upper, edge.lower
                        ),
                    ));
                }
            }
        }
    }
    result
}

/// Parse a leading one-sided comparator bound (`<= 20`, `>= 6`, `< 3`)
/// off a field's value text into `(sense, magnitude)`; `sense` is
/// `"upper"` for `<`/`<=` and `"lower"` for `>`/`>=`. `None` when the
/// text is not a leading comparator over a bare number.
fn bound_from_value_text(text: &str) -> Option<(String, f64)> {
    let trimmed = text.trim();
    let (sense, rest) = if let Some(rest) = trimmed.strip_prefix("<=") {
        ("upper", rest)
    } else if let Some(rest) = trimmed.strip_prefix(">=") {
        ("lower", rest)
    } else if let Some(rest) = trimmed.strip_prefix('<') {
        ("upper", rest)
    } else if let Some(rest) = trimmed.strip_prefix('>') {
        ("lower", rest)
    } else {
        return None;
    };
    let number: String = rest
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+')
        .collect();
    let magnitude: f64 = number.parse().ok()?;
    Some((sense.to_string(), magnitude))
}

/// Every comparator-bound field anywhere under `node` (interface decl
/// body or impl body), keyed by its field NAME (WO-26 D104 -- name is
/// the promised-bound identity; source order, first bound per name
/// wins if a name somehow repeats).
fn collect_bound_fields(node: &SyntaxNode) -> Vec<(String, (String, f64))> {
    let mut out = Vec::new();
    for descendant in node.descendants() {
        if let Some(field) = Field::cast(descendant) {
            if let Some(value) = field.value() {
                if let Some(bound) = bound_from_value_text(&value.text().to_string()) {
                    out.push((field.name(), bound));
                }
            }
        }
    }
    out
}

/// The upper contract's promised bounds: every comparator-bound field
/// of the `interface <name>` declaration, by name, in source order.
fn interface_bound_fields(name: &str, files: &[ParsedFile]) -> Vec<(String, (String, f64))> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw)
                && decl.name().as_deref() == Some(name)
            {
                let fields = collect_bound_fields(decl.syntax());
                if !fields.is_empty() {
                    return fields;
                }
            }
        }
    }
    Vec::new()
}

/// The lower realization's declared bounds: every comparator-bound
/// field of the impl body (`impl <upper> for <lower>`) matching `edge`,
/// whether the impl is a top-level decl or an in-body `ImplStmt`, keyed
/// by name.
fn impl_bound_fields(
    edge: &ConformanceEdge,
    files: &[ParsedFile],
) -> BTreeMap<String, (String, f64)> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let decl_name = decl.name().unwrap_or_default();
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw) {
                if let Some(candidate) = impl_edge(decl.syntax(), &decl_name) {
                    if &candidate == edge {
                        let fields = collect_bound_fields(decl.syntax());
                        if !fields.is_empty() {
                            return fields.into_iter().collect();
                        }
                    }
                }
            }
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt {
                    if let Some(candidate) = impl_edge(&node, &decl_name) {
                        if &candidate == edge {
                            let fields = collect_bound_fields(&node);
                            if !fields.is_empty() {
                                return fields.into_iter().collect();
                            }
                        }
                    }
                }
            }
        }
    }
    BTreeMap::new()
}

/// The field's FULL predicate text after its `name:` separator, spanning
/// every value-ish child -- not just the first, as `Field::value()` does.
/// A continuation predicate (`expr\n    within [lo, hi] forall op`) parses
/// as more than one sibling node under the field (the quantity expression,
/// then the `within` window), and `Field::value()`'s "first value child"
/// contract silently drops everything after the first -- exactly the
/// bracket this pass needs to see for deliverable 2. Reading the field's
/// raw source text and splitting on its first `:` sidesteps that CST
/// shape entirely and is robust to it; the field's dotted name (the only
/// thing before that colon) never itself contains a `:`, so the split
/// point is unambiguous even when the predicate has its own later colon
/// (`within 5s after anomaly: op = safe`).
pub(crate) fn full_predicate_text(field: &Field) -> String {
    let full = field.syntax().text().to_string();
    match full.split_once(':') {
        Some((_, rest)) => rest.trim().to_string(),
        None => String::new(),
    }
}

/// Split a `<quantity expr> within [lo, hi] ...` predicate's two literal
/// endpoints out of its bracket, ignoring the leading quantity expression
/// (`thermo.temperature(eps.store.cells)`, dropped the same way the rest
/// of this pass drops non-literal LHS text) and whatever quantifier/window
/// text follows the bracket (`forall op`, `during ...`). The `within`
/// keyword is matched as a whole word (not a substring of a longer
/// identifier) so it can appear anywhere in the predicate, not just at its
/// head. Returns `None` when no such bracketed two-endpoint window is
/// present (a bare `within` used as a tolerance form elsewhere, or any
/// other comparator, is left untouched).
fn within_window_bounds(predicate: &str) -> Option<(String, String)> {
    let mut search_from = 0usize;
    loop {
        let rel = predicate[search_from..].find("within")?;
        let idx = search_from + rel;
        let before_ok = predicate[..idx]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_');
        let after = &predicate[idx + "within".len()..];
        let after_ok = after
            .chars()
            .next()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_');
        if before_ok && after_ok {
            let rest = after.trim_start();
            if let Some(rest) = rest.strip_prefix('[') {
                let close = rest.find(']')?;
                let inside = &rest[..close];
                let (lo, hi) = inside.split_once(',')?;
                return Some((lo.trim().to_string(), hi.trim().to_string()));
            }
        }
        search_from = idx + "within".len();
        if search_from >= predicate.len() {
            return None;
        }
    }
}

/// Resolve every unit-suffixed numeral in `text` to its bare SI-base
/// magnitude via `regolith-qty` (regolith/02 sec. 1), leaving every other
/// token (comparators, keywords, entity references, unrecognized suffixes
/// such as `dB` or `%`) exactly as written. This is a textual pass, not a
/// full expression parse (WO-05's typed AST is not yet wired to claim
/// predicates): it finds each `<number><unit-like-suffix>` run and
/// replaces it in place when the suffix is a unit `regolith-qty` accepts.
fn resolve_unit_suffix(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = String::with_capacity(text.len());
    let mut i = 0usize;
    while i < bytes.len() {
        let start = i;
        let mut j = i;
        if j < bytes.len() && (bytes[j] == b'+' || bytes[j] == b'-') {
            j += 1;
        }
        let digits_start = j;
        while j < bytes.len() && bytes[j].is_ascii_digit() {
            j += 1;
        }
        if j < bytes.len() && bytes[j] == b'.' {
            let k = j + 1;
            if k < bytes.len() && bytes[k].is_ascii_digit() {
                j = k;
                while j < bytes.len() && bytes[j].is_ascii_digit() {
                    j += 1;
                }
            }
        }
        if j == digits_start {
            // No digits here: copy one char through and keep scanning.
            let ch_len = text[start..].chars().next().map_or(1, char::len_utf8);
            out.push_str(&text[start..start + ch_len]);
            i = start + ch_len;
            continue;
        }
        let number_end = j;
        // A single space is allowed between the magnitude and its unit
        // (`6800 N`), matching the corpus's spelling of both spaced and
        // unspaced forms (`20mV`).
        let unit_start = if number_end < bytes.len() && bytes[number_end] == b' ' {
            number_end + 1
        } else {
            number_end
        };
        // A unit-like suffix: letters, `/`, `.` (compound units), and
        // digits (unit exponents `m2`), but a digit only continues the
        // run once at least one letter has appeared -- otherwise it is
        // the START of the NEXT number, not part of this unit.
        let mut k = unit_start;
        let mut saw_letter = false;
        loop {
            if k < bytes.len() && (bytes[k].is_ascii_alphabetic()) {
                saw_letter = true;
                k += 1;
            } else if k < bytes.len() && saw_letter && (bytes[k] == b'/' || bytes[k] == b'.') {
                k += 1;
                saw_letter = false; // require a letter again before another digit
            } else if k < bytes.len() && saw_letter && bytes[k].is_ascii_digit() {
                k += 1;
            } else {
                break;
            }
        }
        let suffix = &text[unit_start..k];
        let number_text = &text[start..number_end];
        if !suffix.is_empty() {
            if let (Ok(magnitude), Ok(unit)) =
                (number_text.parse::<f64>(), Unit::parse_expr(suffix))
            {
                let si = magnitude * ratio_f64(unit.scale) + ratio_f64(unit.offset);
                out.push_str(&format_si(si));
                i = k;
                continue;
            }
        }
        out.push_str(number_text);
        i = number_end;
    }
    out
}

/// `regolith-qty`'s exact-rational scale/offset as `f64`; the unit table's
/// factors are small SI-prefix ratios, well within `f64`'s exact range.
#[allow(
    clippy::cast_precision_loss,
    reason = "unit scale/offset rationals are small SI-prefix factors, exactly \
              representable in f64 (mirrors regolith_qty::quantity::ratio_to_f64)"
)]
fn ratio_f64(r: regolith_qty::Scale) -> f64 {
    *r.numer() as f64 / *r.denom() as f64
}

/// Render a resolved SI magnitude as a compact ASCII numeral (no trailing
/// zeros/point), keeping the lowered obligation text byte-stable and
/// diffable (INV-10 note: the orchestrator hashes this as parsed text, not
/// this string, so a shorter render never perturbs determinism).
fn format_si(value: f64) -> String {
    let mut s = format!("{value:.10}");
    if s.contains('.') {
        while s.ends_with('0') {
            s.pop();
        }
        if s.ends_with('.') {
            s.pop();
        }
    }
    s
}

/// WO-28: one obligation per attached rule per consuming declaration
/// whose evaluation was not a clean pass. Violated matches make the
/// obligation's given name each failing entity with its evaluated
/// detail; deferred matches name the blocking fact (D-E: "givens name
/// the required facts"). The claim name is the rule's waive-target
/// spelling (`dfm(pack.rule)`), so `waive dfm(pack.rule)` matches it
/// through the EXISTING ladder (D-D: zero new override surface).
/// `advise:` rules never lower (droppable guidance is never
/// load-bearing, INV-3).
fn push_rule_obligations(
    obligations: &mut Vec<Obligation>,
    outcomes: &[crate::rule_engine::RuleEvaluation],
    snapshots: &EntitySnapshots,
) {
    for eval in outcomes {
        let rule = &eval.rule;
        if rule.demand.is_none() {
            continue;
        }
        if eval.is_clean_pass() {
            continue;
        }
        let subject_ref = snapshots
            .scopes
            .get(&eval.decl_name)
            .map(regolith_sem::EntityDb::snapshot_hash)
            .unwrap_or_default();

        let demand_text = rule.demand.clone().unwrap_or_default();
        let form = match crate::rule_engine::split_comparison(&demand_text) {
            Some((lhs, op, rhs)) => ClaimForm::Comparison {
                lhs: lhs.trim().to_string(),
                op: op.to_string(),
                rhs: rhs.trim().to_string(),
            },
            None => ClaimForm::Comparison {
                lhs: demand_text.clone(),
                op: "holds".to_string(),
                rhs: String::new(),
            },
        };

        let mut refs: Vec<(String, String)> = Vec::new();
        for (origin, detail, _margin) in &eval.violations {
            refs.push((origin.clone(), format!("violated: {detail}")));
        }
        for (origin, fact) in &eval.deferrals {
            refs.push((origin.clone(), format!("requires fact: {fact}")));
        }

        let mut hints = Vec::new();
        if let Some(why) = &rule.why {
            hints.push(format!("why: {why}"));
        }
        if let Some(per) = &rule.per {
            hints.push(format!("per: {per}"));
        }

        let forall = match (&rule.forall_var, rule.query_text.is_empty()) {
            (Some(var), false) => vec![format!("{var} in {}", rule.query_text)],
            _ => Vec::new(),
        };
        let sweep = rule.forall_var.as_ref().map(|var| SweepDomain {
            axis: var.clone(),
            domain: rule.query_text.clone(),
        });

        tracing::info!(
            rule = %rule.qualified(),
            subject = %eval.decl_name,
            violations = eval.violations.len(),
            deferrals = eval.deferrals.len(),
            "lowering rule outcome to an obligation"
        );
        obligations.push(Obligation {
            claim: Claim {
                name: Some(rule.claim_name()),
                form,
                forall,
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: hints.clone(),
                model_pin: None,
            },
            subject_ref,
            given: Given {
                materials: Vec::new(),
                loads: Vec::new(),
                backing: Vec::new(),
                refs,
            },
            hints,
            sweep,
            payloads: Vec::new(),
        });
    }
}

/// Collect a declaration's structured materials and loads into a
/// [`Given`] (BE-2). `material`/`materials` fields become
/// `given.materials`; the child lines of a `loads:` block become
/// `given.loads` (as `name: value` text). Reading the typed `Field`
/// tree (not a raw text scan) keeps the obligation key sensitive to the
/// exact declared values while staying deterministic (source order).
fn given_for_decl(decl: &Decl) -> Given {
    let mut materials = Vec::new();
    let mut loads = Vec::new();

    for node in decl.syntax().descendants() {
        let Some(field) = Field::cast(node.clone()) else {
            continue;
        };
        let name = field.name();
        let leaf = name.rsplit('.').next().unwrap_or(&name);
        if matches!(leaf, "material" | "materials") {
            if let Some(value) = field.value() {
                materials.push((name.clone(), value.text().to_string().trim().to_string()));
            }
        }
        if leaf == "loads" {
            for inner in node.descendants() {
                if inner == node {
                    continue;
                }
                let Some(load) = Field::cast(inner) else {
                    continue;
                };
                if let Some(value) = load.value() {
                    loads.push(format!(
                        "{}: {}",
                        load.name(),
                        value.text().to_string().trim()
                    ));
                }
            }
        }
    }

    Given {
        materials,
        loads,
        backing: Vec::new(),
        refs: Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::build_obligations;
    use crate::checks::run_checks;
    use crate::contracts::build_contract_ir;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn obligations(src: &str) -> Vec<super::Obligation> {
        let files = parsed(src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
    }

    /// A fluid claim over a self-contained flownet (WO-32 deliverable
    /// 4a): the `require` group is NOT a plain `Decl` (fluorite's
    /// `File::fluid_requires`), so this exercises the dedicated
    /// `push_fluid_obligations` pass end to end.
    fn fluid_obligations(src: &str) -> Vec<super::Obligation> {
        let path = Utf8PathBuf::from("t.fluo");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }];
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations
    }

    /// Same as [`fluid_obligations`] but returns the full [`ObligationSet`]
    /// (WO-32 deliverable 5: E0203 assertions need the diagnostics too).
    fn fluid_obligation_set(src: &str) -> super::ObligationSet {
        let path = Utf8PathBuf::from("t.fluo");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }];
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        build_obligations(&files, &snaps, &checks, &graph, &realized_inputs)
    }

    const FLUID_SRC: &str = "medium Water: liquid\n\
        \x20   props: registry(potable_water_nist)\n\
        flownet Loop(medium=Water):\n\
        \x20   reference: ambient(101kPa, 293K)\n\
        \x20   nodes: a, b\n\
        \x20   edges:\n\
        \x20       supply: Pipe(from=line.run) (a -> b)\n\
        require Margin:\n\
        \x20   dp: fluids.dp(a -> b) <= 40kPa\n";

    #[test]
    fn fluid_claim_lowers_to_an_obligation_with_a_flownet_payload_ref() {
        let obls = fluid_obligations(FLUID_SRC);
        assert_eq!(obls.len(), 1, "one fluid claim -> one obligation");
        let obl = &obls[0];
        assert_eq!(obl.payloads.len(), 1, "carries exactly one payload ref");
        let payload_ref = &obl.payloads[0];
        assert_eq!(payload_ref.kind, "flownet");
        assert!(!payload_ref.digest.is_empty(), "resolvable digest");
        assert_eq!(payload_ref.origin, "Loop");
        assert_eq!(obl.subject_ref, payload_ref.digest);
    }

    #[test]
    fn dp_claim_over_a_bare_pipe_does_not_trigger_e0203() {
        // WO-32 deliverable 5: E0203 governs transient/volume-budget
        // claims only (`fluids.volume_consumed`); an ordinary `dp` claim
        // over the same compliance-less edge is untouched.
        let set = fluid_obligation_set(FLUID_SRC);
        assert!(
            set.diagnostics
                .iter()
                .all(|d| d.code.to_string() != "E0203"),
            "{:?}",
            set.diagnostics
        );
    }

    const FLUID_VOLUME_BUDGET_NO_COMPLIANCE_SRC: &str = "medium HydOil: liquid\n\
        \x20   props: registry(iso_vg32_hydraulic)\n\
        flownet Rigid(medium=HydOil):\n\
        \x20   reference: ambient(101kPa, 293K)\n\
        \x20   nodes: a, b\n\
        \x20   edges:\n\
        \x20       pipe: Pipe(from=nowhere.run) (a -> b)\n\
        require Budget:\n\
        \x20   bad: fluids.volume_consumed([pipe], at=10MPa) < 1L\n";

    #[test]
    fn volume_consumed_over_an_edge_with_no_compliance_flags_e0203() {
        // WO-32 deliverable 5 (fluorite/03 sec. 1): `pipe` has neither a
        // `compliance=` record nor (this session's `AstFlownetInputs`,
        // WO-42's realized-geometry channel not yet wired to a real
        // wall record either) an extractable wall -- the claim is
        // undischargeable and must reject at compile time.
        let set = fluid_obligation_set(FLUID_VOLUME_BUDGET_NO_COMPLIANCE_SRC);
        let codes: Vec<String> = set.diagnostics.iter().map(|d| d.code.to_string()).collect();
        assert!(codes.contains(&"E0203".to_string()), "{codes:?}");
    }

    #[test]
    fn volume_consumed_over_an_unknown_edge_id_is_not_this_checks_job() {
        // A claim naming an edge id absent from the flownet's edge list
        // is a different (undeclared-reference) problem; E0203 stays
        // silent rather than misreport it.
        let src = "medium Water: liquid\n\
            \x20   props: registry(potable_water_nist)\n\
            flownet Loop(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n\
            require Budget:\n\
            \x20   bad: fluids.volume_consumed([nope], at=10MPa) < 1L\n";
        let set = fluid_obligation_set(src);
        assert!(
            set.diagnostics
                .iter()
                .all(|d| d.code.to_string() != "E0203"),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn fluid_obligation_is_deterministic() {
        // AD-6: same source, same obligation content hash, twice.
        let a = &fluid_obligations(FLUID_SRC)[0];
        let b = &fluid_obligations(FLUID_SRC)[0];
        assert_eq!(a.content_hash(), b.content_hash());
    }

    #[test]
    fn fluid_source_populates_the_flownets_emission_set() {
        // WO-32 deliverable 4b: `ObligationSet.flownets` is the seam
        // `LowerOutput.flownets`/`BuildPayload.flownets` reads -- it
        // must carry the same elaborated payload the obligation's
        // `PayloadRef.digest` names, without a second elaboration.
        let path = Utf8PathBuf::from("t.fluo");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(FLUID_SRC, &path),
        }];
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let set = build_obligations(
            &files,
            &snaps,
            &checks,
            &graph,
            &crate::realized_input::RealizedInputs::new(),
        );
        assert_eq!(set.flownets.len(), 1, "one flownet elaborated");
        assert_eq!(set.flownets[0].name, "Loop");
        let obl = &set.obligations[0];
        let payload_ref = &obl.payloads[0];
        assert_eq!(
            set.flownets[0].payload.content_digest().unwrap(),
            payload_ref.digest,
            "the emitted flownet's digest matches the obligation's payload ref"
        );
    }

    #[test]
    fn non_fluid_source_produces_no_fluid_obligation_noise() {
        // A plain hematite source has no `flownet`/`require fluids.*`
        // surface: `push_fluid_obligations` must contribute nothing.
        let src = "part p:\n    require R:\n        strength: >= 1\n";
        let obls = obligations(src);
        assert!(obls.iter().all(|o| o.payloads.is_empty()));
    }

    fn obligation_set(src: &str) -> super::ObligationSet {
        let files = parsed(src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        build_obligations(
            &files,
            &snaps,
            &checks,
            &graph,
            &crate::realized_input::RealizedInputs::new(),
        )
    }

    #[test]
    fn compute_claim_produces_one_obligation_and_one_field_datum() {
        // WO-33 D98 deliverable 3: a zone-indexed `compute` claim lowers
        // to exactly one obligation (`ClaimForm::Compute`) plus one
        // `FieldDatum` ledger entry with a null (pre-discharge) payload.
        let src = "part liner:\n    require Thermal:\n        compute wall_T: thermo.wall_temperature over liner.zones\n";
        let set = obligation_set(src);
        assert_eq!(set.field_datums.len(), 1);
        let datum = &set.field_datums[0];
        assert_eq!(datum.name, "wall_T");
        assert_eq!(datum.quantity_kind, "thermo.wall_temperature");
        assert!(datum.payload.is_none(), "pre-discharge payload is null");
        assert_eq!(
            datum.axis.method,
            regolith_oblig::CoverageMethod::Undischarged
        );

        let compute_obls: Vec<_> = set
            .obligations
            .iter()
            .filter(|o| matches!(o.claim.form, super::ClaimForm::Compute { .. }))
            .collect();
        assert_eq!(compute_obls.len(), 1, "exactly one producer obligation");
        if let super::ClaimForm::Compute {
            quantity_kind,
            over,
        } = &compute_obls[0].claim.form
        {
            assert_eq!(quantity_kind, "thermo.wall_temperature");
            assert_eq!(over, "liner.zones");
        } else {
            unreachable!();
        }
    }

    #[test]
    fn config_indexed_compute_claim_declares_an_interval_axis() {
        let src = "part susp:\n    require Kinematics:\n        compute camber: vehicle.camber over travel in [-80mm, 120mm]\n";
        let set = obligation_set(src);
        let datum = &set.field_datums[0];
        assert_eq!(datum.axis.axis, "travel");
        assert_eq!(
            datum.axis.domain,
            regolith_oblig::CoverageDomain::Interval("[-80mm, 120mm]".to_string())
        );
    }

    #[test]
    fn projection_references_the_producing_field_by_digest_slot() {
        // Deliverable 3: a `max(wall_T) < 800K` claim's obligation gains
        // a `given.refs` entry pointing at the compute obligation's
        // content hash -- the promise-chain reference.
        let src = "part liner:\n    require Thermal:\n        compute wall_T: thermo.wall_temperature over liner.zones\n        tip_temp: max(wall_T) < 800K\n";
        let set = obligation_set(src);
        let producer = set
            .obligations
            .iter()
            .find(|o| matches!(o.claim.form, super::ClaimForm::Compute { .. }))
            .expect("producer obligation");
        let consumer = set
            .obligations
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("tip_temp"))
            .expect("consumer obligation");
        assert!(
            consumer.given.refs.contains(&(
                "wall_T".to_string(),
                format!("field:{}", producer.content_hash())
            )),
            "consumer given.refs: {:?}",
            consumer.given.refs
        );
        assert!(set.diagnostics.is_empty());
    }

    #[test]
    fn projection_naming_an_undeclared_field_is_an_unresolved_reference() {
        let src = "part liner:\n    require Thermal:\n        tip_temp: max(wall_T) < 800K\n";
        let set = obligation_set(src);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::UNRESOLVED_FIELD_REFERENCE),
            "expected an unresolved-field-reference diagnostic: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn a_compute_compute_cycle_is_a_diagnostic_naming_the_chain() {
        // A sibling `compute` consuming another as a given, in a cycle,
        // must be a compile diagnostic naming the cycle -- never a panic
        // or an infinite loop.
        let src = "part susp:\n    require Kinematics:\n        compute mr: vehicle.motion_ratio over roll_stiffness\n        compute roll_stiffness: vehicle.roll_stiffness over mr\n";
        let set = obligation_set(src);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::COMPUTE_FIELD_CYCLE),
            "expected a compute-field cycle diagnostic: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn given_captures_material_so_the_key_is_mutation_sensitive() {
        // BE-2/INV-1: two decls differing ONLY in material must hash to
        // different obligations (no shared cached evidence).
        let a = "part p:\n    material: AL7075_T6\n    require R:\n        strength: >= 1\n";
        let b = "part p:\n    material: TI64\n    require R:\n        strength: >= 1\n";
        let oa = &obligations(a)[0];
        let ob = &obligations(b)[0];
        assert!(
            !oa.given.materials.is_empty(),
            "material populated into given"
        );
        assert_ne!(
            oa.content_hash(),
            ob.content_hash(),
            "changing material must change the obligation key"
        );
    }

    #[test]
    fn loads_block_is_threaded_into_given() {
        let src = "part p:\n    loads:\n        radial: derived\n    require R:\n        s: >= 1\n";
        let obl = &obligations(src)[0];
        assert!(
            obl.given.loads.iter().any(|l| l.contains("radial")),
            "loads block threaded into given: {:?}",
            obl.given.loads
        );
    }

    #[test]
    fn an_impl_binding_emits_a_conformance_obligation() {
        // BE-6/INV-13: an in-body `impl X for Y:` yields a conformance
        // obligation.
        let src = "part p:\n    impl Seat for self:\n        x: 1\n";
        let obl = obligations(src);
        assert!(
            obl.iter().any(|o| matches!(
                &o.claim.form,
                super::ClaimForm::Comparison { op, .. } if op == "conforms"
            )),
            "expected a conformance obligation"
        );
    }

    #[test]
    fn conformance_windows_match_promised_bounds_by_name_not_position() {
        // WO-26 D104: the impl's SECOND field, `y`, must be matched
        // against the interface's promised `y` bound -- not its FIRST
        // field `x` -- because matching is now by field NAME.
        let src = "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self:\n        x: <= 5\n        y: <= 14\n";
        let set = obligation_set(src);
        let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
        assert!(
            conforms.given.loads.iter().any(|l| l == "spec_bound: 20"),
            "expected the name-matched `y` promise (20), got {:?}",
            conforms.given.loads
        );
        assert!(
            conforms.given.loads.iter().any(|l| l == "impl_bound: 14"),
            "expected the name-matched `y` realization (14), got {:?}",
            conforms.given.loads
        );
        assert!(
            set.diagnostics.is_empty(),
            "every promised name matched; no diagnostic expected: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn a_promised_bound_with_no_matching_impl_field_is_diagnosed() {
        // WO-26 D104: the interface promises `y`, but the impl only
        // realizes `x` -- a constructive diagnostic naming both sides,
        // not a silent defer.
        let src =
            "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self:\n        x: <= 5\n";
        let set = obligation_set(src);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::PROMISED_BOUND_UNMATCHED),
            "expected a PROMISED_BOUND_UNMATCHED diagnostic: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn a_poisoned_subject_emits_no_obligation() {
        let src = "part bad:\n    )\n    require R:\n        s: >= 1\npart good:\n    require R:\n        s: >= 1\n";
        let obl = obligations(src);
        // Exactly one require obligation (from `good`); `bad` is gated.
        let require_count = obl
            .iter()
            .filter(|o| {
                matches!(
                    &o.claim.form,
                    super::ClaimForm::Comparison { op, .. } if op == "require"
                )
            })
            .count();
        assert_eq!(require_count, 1, "poisoned subject `bad` must not obligate");
    }

    #[test]
    fn realization_obligation_is_emitted_per_declared_edge() {
        let src = "system Sys:\n    intents:\n        decide: compute(law)\n    workloads:\n        att: loop(rate=4Hz) realizes decide\n";
        let obl = obligations(src);
        let realizes_obl = obl
            .iter()
            .find(|o| matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "implies"))
            .expect("a realization obligation is emitted");
        match &realizes_obl.claim.form {
            super::ClaimForm::Comparison { lhs, rhs, .. } => {
                assert_eq!(lhs, "att");
                assert_eq!(rhs, "decide");
            }
            _ => unreachable!(),
        }
        assert!(
            realizes_obl.given.loads.is_empty(),
            "a declared edge carries no derived cause"
        );
        assert!(realizes_obl.hints.is_empty());
    }

    #[test]
    fn derived_edge_tags_its_obligation_with_the_derived_cause() {
        let src = "system Sys:\n    intents:\n        decide: compute(law)\n";
        let obl = obligations(src);
        let derived_obl = obl
            .iter()
            .find(|o| matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "implies"))
            .expect("a derived realization obligation is emitted");
        assert!(
            derived_obl
                .given
                .loads
                .iter()
                .any(|l| l == "cause: derived(intent decide)"),
            "derived cause tagged in given.loads: {:?}",
            derived_obl.given.loads
        );
        assert!(derived_obl
            .hints
            .iter()
            .any(|h| h == "derived(intent decide)"));
    }

    #[test]
    fn unit_suffixed_bound_resolves_through_regolith_qty() {
        // WO-26 deliverable 1: `<= 0.2mm` and `>= 6800 N` resolve to SI
        // base numerals (meters, newtons) instead of the naive leading
        // digits, so the orchestrator's numeric parse sees the RIGHT
        // magnitude, not a unit-blind literal.
        let src = "part p:\n    require R:\n        sag: <= 0.2mm\n        preload: >= 6800 N\n";
        let obl = obligations(src);
        let bounds: Vec<String> = obl
            .iter()
            .map(|o| match &o.claim.form {
                super::ClaimForm::Comparison { rhs, .. } => rhs.clone(),
                _ => String::new(),
            })
            .collect();
        assert!(
            bounds.iter().any(|b| b == "<= 0.0002"),
            "0.2mm resolved to meters: {bounds:?}"
        );
        assert!(
            bounds.iter().any(|b| b == ">= 6800"),
            "6800 N resolved (N is already SI base): {bounds:?}"
        );
    }

    #[test]
    fn unresolvable_suffix_passes_through_unchanged() {
        // A non-unit suffix (`dB`) is left exactly as written -- never an
        // invented conversion (INV-24/26 honesty).
        let src = "part p:\n    require R:\n        margin: >= 6dB\n";
        let obl = &obligations(src)[0];
        match &obl.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert_eq!(rhs, ">= 6dB", "unrecognized unit left untouched");
            }
            _ => unreachable!(),
        }
    }

    #[test]
    fn temperature_offset_unit_resolves_through_its_additive_offset() {
        // `degC` is an offset unit (regolith/02 sec. 1): 85 degC resolves
        // to its Kelvin SI-base value (358.15), not a bare 85.
        let src = "part p:\n    require R:\n        junction: <= 85degC\n";
        let obl = &obligations(src)[0];
        match &obl.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert_eq!(rhs, "<= 358.15", "degC resolved via its additive offset");
            }
            _ => unreachable!(),
        }
    }

    #[test]
    fn within_lo_hi_window_splits_into_two_bound_obligations() {
        // WO-26 deliverable 2: a `within [lo, hi]` demanded window becomes
        // two one-sided obligations over the same subject, each carrying
        // its own resolved bound -- the orchestrator's existing scalar
        // path then lowers each to a real DischargeRequest (no more
        // `unsupported_op` deferral for a within-windowed claim).
        let src = "part p:\n    require Thermal:\n        batt_window: thermo.temperature(eps.store.cells)\n                         within [0degC, 45degC] forall op\n";
        let obl = obligations(src);
        let named: Vec<(String, String, String)> = obl
            .iter()
            .filter_map(|o| match &o.claim.form {
                super::ClaimForm::Comparison { op, rhs, .. } => Some((
                    o.claim.name.clone().unwrap_or_default(),
                    op.clone(),
                    rhs.clone(),
                )),
                _ => None,
            })
            .collect();
        assert_eq!(named.len(), 2, "exactly two halves emitted: {named:?}");
        let lo = named
            .iter()
            .find(|(name, ..)| name == "batt_window.lo")
            .expect("lo half present");
        assert_eq!(lo.1, ">=");
        assert_eq!(lo.2, "273.15", "0degC resolved to Kelvin");
        let hi = named
            .iter()
            .find(|(name, ..)| name == "batt_window.hi")
            .expect("hi half present");
        assert_eq!(hi.1, "<=");
        assert_eq!(hi.2, "318.15", "45degC resolved to Kelvin");
    }

    #[test]
    fn peak_with_during_window_lowers_to_a_typed_reduction() {
        // D102: a REDUCTION form with a `during` window and a trailing
        // comparator constructs `ClaimForm::Peak` (op/rhs typed, not an
        // opaque Comparison blob).
        let src = "part p:\n    require Structural:\n        grms_ok: peak(mech.stress.von_mises, during boundary.load_spectrum) < 200MPa\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Peak {
                signal,
                window,
                op,
                rhs,
            } => {
                assert_eq!(signal, "mech.stress.von_mises");
                assert_eq!(
                    *window,
                    super::Window::During("boundary.load_spectrum".to_string())
                );
                assert_eq!(op, "<");
                assert_eq!(rhs, "200000000", "MPa resolved to Pa");
            }
            other => panic!("expected ClaimForm::Peak, got {other:?}"),
        }
    }

    #[test]
    fn peak_with_within_after_window_lowers_to_a_typed_reduction() {
        let src = "part p:\n    require Drive:\n        coil_ok: peak(v(mv_f), within 5ms after mv_f.close) < 45V\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Peak { window, op, .. } => {
                assert_eq!(
                    *window,
                    super::Window::WithinAfter {
                        duration: "0.005".to_string(),
                        event: "mv_f.close".to_string(),
                    },
                    "5ms duration resolved to seconds"
                );
                assert_eq!(op, "<");
            }
            other => panic!("expected ClaimForm::Peak, got {other:?}"),
        }
    }

    #[test]
    fn peak_with_at_location_tag_is_left_untyped() {
        // A spatial `at=` tag is not a D102 temporal window; the claim
        // stays the pre-existing untyped `Comparison` (an honest,
        // recorded scope narrowing, not a silent guess).
        let src = "part p:\n    require Structural:\n        shell: peak(mech.stress.von_mises, at=welded.tank.shell) < material.sigma_y\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        assert!(matches!(
            obl[0].claim.form,
            super::ClaimForm::Comparison { .. }
        ));
    }

    #[test]
    fn rms_with_band_lowers_to_a_typed_reduction() {
        let src = "part p:\n    require Noise:\n        floor: rms(v(out), band=[100kHz, 10MHz]) < 20mV\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Rms {
                signal,
                band,
                op,
                rhs,
            } => {
                assert_eq!(signal, "v(out)");
                assert_eq!(band, "[100kHz, 10MHz]");
                assert_eq!(op, "<");
                assert_eq!(rhs, "0.02", "20mV resolved to volts");
            }
            other => panic!("expected ClaimForm::Rms, got {other:?}"),
        }
    }

    #[test]
    fn peak_reduction_with_no_trailing_comparator_is_a_compile_diagnostic() {
        let src = "part p:\n    require Structural:\n        bad: peak(mech.stress.von_mises, during boundary.load_spectrum)\n";
        let set = obligation_set(src);
        assert!(
            set.obligations.is_empty(),
            "no obligation for a diagnosed claim"
        );
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::TEMPORAL_REDUCTION_MISSING_COMPARATOR),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn settles_lowers_to_a_typed_containment() {
        let src = "part p:\n    require Regulation:\n        transient: settles(v(out), to=+-2%, within 500us after load_step)\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Settles {
                signal,
                tol,
                window,
            } => {
                assert_eq!(signal, "v(out)");
                assert_eq!(tol, "+-2%");
                assert_eq!(
                    *window,
                    super::Window::WithinAfter {
                        duration: "0.0005".to_string(),
                        event: "load_step".to_string(),
                    },
                    "500us duration resolved to seconds"
                );
            }
            other => panic!("expected ClaimForm::Settles, got {other:?}"),
        }
    }

    #[test]
    fn settles_with_trailing_comparator_is_a_compile_diagnostic() {
        let src = "part p:\n    require Regulation:\n        bad: settles(v(out), to=+-2%, within 500us after load_step) < 1\n";
        let set = obligation_set(src);
        assert!(set.obligations.is_empty());
        assert!(
            set.diagnostics.iter().any(|d| d.code
                == regolith_diag::codes::TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn stays_within_with_no_window_lowers_to_a_typed_containment() {
        let src = "part p:\n    require Survival:\n        mask_ok: stays_within(emissions, mask=fcc_part90_mask(25kHz))\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::StaysWithin {
                signal,
                mask,
                window,
            } => {
                assert_eq!(signal, "emissions");
                assert_eq!(mask, "fcc_part90_mask(25kHz)");
                assert_eq!(*window, None);
            }
            other => panic!("expected ClaimForm::StaysWithin, got {other:?}"),
        }
    }

    #[test]
    fn stays_within_with_a_window_lowers_to_a_typed_containment() {
        // WO-54 rider: `ClaimForm::StaysWithin` now carries a `window`
        // field, so the dune-buggy/buck-converter windowed corpus
        // shape types through instead of falling back to Comparison.
        let src = "part p:\n    require Survival:\n        landing: stays_within(mech.load(frame.pickups.all), mask=dune_jump_srs, during event(jump_landing))\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::StaysWithin {
                signal,
                mask,
                window,
            } => {
                assert_eq!(signal, "mech.load(frame.pickups.all)");
                assert_eq!(mask, "dune_jump_srs");
                assert_eq!(
                    *window,
                    Some(super::Window::During("event(jump_landing)".to_string()))
                );
            }
            other => panic!("expected ClaimForm::StaysWithin, got {other:?}"),
        }
    }

    #[test]
    fn overshoot_lowers_to_a_typed_reduction() {
        let src = "part p:\n    require Transient:\n        os: overshoot(v(out), after load_step) < 5%\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Overshoot {
                signal,
                event,
                op,
                rhs,
            } => {
                assert_eq!(signal, "v(out)");
                assert_eq!(event, "load_step");
                assert_eq!(op, "<");
                assert_eq!(rhs, "5%", "a bare % suffix is not a regolith-qty unit");
            }
            other => panic!("expected ClaimForm::Overshoot, got {other:?}"),
        }
    }

    #[test]
    fn forall_interval_prefix_lowers_into_the_sweep_slot() {
        // D105a: the buck-efficiency shape -- an interval sweep prefix
        // becomes the obligation's SweepDomain; the remainder lowers as
        // an ordinary (here general-comparison) claim.
        let src = "part p:\n    require Efficiency:\n        eta: forall i(out) in [0.2A, i_max]: elec.power(out) / elec.power(vin) >= 85%\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        let sweep = obl[0].sweep.as_ref().expect("sweep populated");
        assert_eq!(sweep.axis, "i(out)");
        assert_eq!(sweep.domain, "[0.2, i_max]", "0.2A resolved to amperes");
        match &obl[0].claim.form {
            super::ClaimForm::Comparison { lhs, op, rhs } => {
                assert_eq!(lhs, "elec.power(out) / elec.power(vin)");
                assert_eq!(op, ">=");
                assert_eq!(rhs, "85%");
            }
            other => panic!("expected general Comparison, got {other:?}"),
        }
    }

    #[test]
    fn forall_discrete_prefix_lowers_into_the_sweep_slot() {
        let src = "part p:\n    require Modes:\n        ok: forall m in {run, idle}: thermo.temperature(core) <= 85degC\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        let sweep = obl[0].sweep.as_ref().expect("sweep populated");
        assert_eq!(sweep.axis, "m");
        assert_eq!(sweep.domain, "{run, idle}");
    }

    #[test]
    fn mid_expression_comparator_splits_into_a_general_comparison() {
        // D103: `expr <op> bound` with the comparator mid-expression
        // becomes a real Comparison (lhs kept, bound unit-resolved),
        // not the opaque op="require" blob.
        let src = "part p:\n    require Thermal:\n        fet_t: thermo.temperature(sw.fet.junction) < 110degC\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Comparison { lhs, op, rhs } => {
                assert_eq!(lhs, "thermo.temperature(sw.fet.junction)");
                assert_eq!(op, "<");
                assert_eq!(rhs, "383.15", "110degC resolved to Kelvin");
            }
            other => panic!("expected general Comparison, got {other:?}"),
        }
    }

    #[test]
    fn leading_comparator_claims_keep_the_existing_opaque_path() {
        // A `subject: >= 200` line has no lhs expression; the existing
        // op="require" path (whose comparator the orchestrator
        // recovers) must stay byte-identical.
        let src = "part p:\n    require Strength:\n        yield: >= 200\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        match &obl[0].claim.form {
            super::ClaimForm::Comparison { op, rhs, .. } => {
                assert_eq!(op, "require");
                assert_eq!(rhs, ">= 200");
            }
            other => panic!("expected opaque Comparison, got {other:?}"),
        }
    }

    #[test]
    fn two_top_level_comparators_are_a_compile_diagnostic() {
        let src = "part p:\n    require Bad:\n        chained: a.x < b.y < 10\n";
        let set = obligation_set(src);
        assert!(set.obligations.is_empty());
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::GENERAL_COMPARISON_MULTIPLE_COMPARATORS),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn link_budget_refs_resolve_through_the_parsed_declarations() {
        // D103 end-to-end (Rust half): a Kestrel-shaped general
        // comparison resolves every two-segment entity-field reference
        // into given.refs -- a promise bound (`pa_out`), plain values
        // (`path_loss`/`sensitivity`), and a bound field (`gain`).
        let src = "part Radio:\n    require Rf:\n        pa_out: elec.power(rf_conn) >= 30dBm during op = downlink\n\
                   part Dish:\n    gain: >= 12dBi\n\
                   part Station:\n    sensitivity: -110dBm\n    path_loss: 140dB\n\
                   system Sat:\n    parts:\n        comms: Radio\n        ant: Dish\n        gs: Station\n    require Link:\n        margin: comms.pa_out + ant.gain - gs.path_loss >= gs.sensitivity + 6dB during op = downlink\n";
        let obls = obligations(src);
        let margin = obls
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("margin"))
            .expect("margin obligation");
        let refs: std::collections::BTreeMap<_, _> = margin.given.refs.iter().cloned().collect();
        assert_eq!(refs.get("comms.pa_out").map(String::as_str), Some("30dBm"));
        assert_eq!(refs.get("ant.gain").map(String::as_str), Some("12dBi"));
        assert_eq!(refs.get("gs.path_loss").map(String::as_str), Some("140dB"));
        assert_eq!(
            refs.get("gs.sensitivity").map(String::as_str),
            Some("-110dBm")
        );
        match &margin.claim.form {
            super::ClaimForm::Comparison { op, .. } => assert_eq!(op, ">="),
            other => panic!("expected general Comparison, got {other:?}"),
        }
    }

    #[test]
    fn an_unresolvable_ref_is_skipped_never_invented() {
        // The REAL Kestrel posture: `antenna.gain` names nothing the
        // source declares; the ref simply does not enter given.refs
        // (the orchestrator defers naming it).
        let src =
            "system Sat:\n    require Link:\n        margin: comms.pa_out + antenna.gain >= 6dB\n";
        let obls = obligations(src);
        let margin = &obls[0];
        assert!(
            margin.given.refs.is_empty(),
            "nothing resolvable -> no refs: {:?}",
            margin.given.refs
        );
    }
}
