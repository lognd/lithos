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
use crate::contracts::{
    impl_edge, plan_clause, ConformanceEdge, ContractGraph, PlanClause, RealizationEdge,
    KNOWN_PLAN_DIALECTS,
};
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
                // WO-68: `all_claims()` walks direct Field claims AND
                // every claim nested inside a `forall <var> in
                // <domain>:` BLOCK claim (previously invisible to this
                // pass -- swallowed whole into an `OpaqueIsland` by the
                // parser, the silent-no-obligation bug this WO fixes).
                for (line, block_sweep) in group.all_claims() {
                    push_require_obligations(
                        &mut out.obligations,
                        &mut out.diagnostics,
                        &ctx,
                        &line,
                        block_sweep
                            .as_ref()
                            .and_then(sweep_domain_from_ast)
                            .as_ref(),
                        &given,
                    );
                }
                // WO-90 deliverable 2: a `forall <var> in <domain>:`
                // sweep whose domain is a BARE PLURAL naming no declared
                // domain (`boards`, `assemblies`) covers zero points --
                // a vacuous pass. Emit E0450 ONCE per such block (not per
                // nested claim), constructively naming the declared forms.
                for sweep in group.sweeps() {
                    check_forall_domain(&mut out.diagnostics, &pf.path, &sweep);
                }
            }

            // WO-69 (regolith/08 sec. 4 L6 row, WO-67's follow-up ledger):
            // a `plan:` field on this decl lowers to the five `cam.*`
            // obligations, keyed on this decl's own subject/geometry --
            // runs once per decl, after its ordinary require claims.
            push_plan_obligations(
                &mut out.obligations,
                &mut out.diagnostics,
                &pf.path,
                &decl,
                &decl_name,
                &subject_ref,
                realized_inputs,
            );
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

    // WO-54 deliverable 1: `mfg.cost(...)` claims in TOP-LEVEL require
    // groups (the calcite/fluorite file shape -- small_office's
    // program.calx whole-project estimate). The frame pass above only
    // lowers FRAME_CLAIM_FORMS and the fluid pass only `fluids.*`
    // forms, so a cost claim there would otherwise be silently
    // dropped; this pass gives it the same validation + given
    // threading as the decl path (minus a decl's `parts:` BOM -- a
    // top-level group has no enclosing decl; the orchestrator's
    // subject matching supplies the frame/flownet quantity bases).
    push_top_level_cost_obligations(&mut out.obligations, &mut out.diagnostics, files);

    out
}

/// The five `cam.*` claim kinds a `plan:` clause discharges through
/// (33-cam-verification.md, WO-67's landed `std.cam` pack; WO-69
/// wires the source-level linkage the pack's models already expect).
/// ONE list, source order fixed, so "exactly five obligations, keyed
/// distinctly" (this WO's acceptance criterion) is provable by
/// construction rather than by convention.
const CAM_CLAIM_KINDS: [&str; 5] = [
    "cam.parse",
    "cam.envelope",
    "cam.collision_coarse",
    "cam.removal",
    "cam.coverage",
];

/// WO-69 (regolith/08 sec. 4's L6 row, WO-67's close-out ledger
/// follow-up): a `plan: extern(<ref>, <dialect>) machine=.., tooling=..,
/// resolution=..` field on `decl` lowers to one obligation per
/// [`CAM_CLAIM_KINDS`] entry, each carrying a `kind: plan` [`PayloadRef`]
/// (digest resolved orchestrator-side, D96/D154 -- the compiler has no
/// IO to hash foreign bytes, AD-17) plus, when this decl's own realized
/// geometry was supplied to this build, a `kind: geometry.realized`
/// ref citing it (the "target RealizedGeometry digest" the WO's
/// deliverable 2 names -- the plan machines ITS OWN enclosing subject,
/// so no second declared reference is needed, unlike a flownet edge's
/// `from=`). A malformed clause (empty ref, or a dialect outside
/// [`KNOWN_PLAN_DIALECTS`]) emits E0449 and NO obligations -- honest
/// silence, never a guess (removing the `plan:` field removes exactly
/// these five, satisfying the WO's other acceptance line by the same
/// construction).
fn push_plan_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    path: &camino::Utf8Path,
    decl: &Decl,
    decl_name: &str,
    subject_ref: &str,
    realized_inputs: &crate::realized_input::RealizedInputs,
) {
    for field in decl.fields() {
        let Some(clause) = plan_clause(&field) else {
            continue;
        };
        let sp = field_span(path, &field);
        if clause.plan_ref.is_empty() {
            diagnostics.push(
                Diagnostic::error(
                    codes::PLAN_CLAUSE_MALFORMED,
                    "`plan: extern(...)` names no ref string",
                )
                .with_span(LabeledSpan::new(sp, "missing the extern ref")),
            );
            continue;
        }
        let Some(dialect) = clause.dialect.as_deref() else {
            diagnostics.push(
                Diagnostic::error(
                    codes::PLAN_CLAUSE_MALFORMED,
                    "`plan: extern(...)` names no dialect",
                )
                .with_span(LabeledSpan::new(sp, "missing the dialect argument")),
            );
            continue;
        };
        if !KNOWN_PLAN_DIALECTS.contains(&dialect) {
            diagnostics.push(
                Diagnostic::error(
                    codes::PLAN_CLAUSE_MALFORMED,
                    format!(
                        "unknown plan dialect {dialect:?} (known: {})",
                        KNOWN_PLAN_DIALECTS.join(", ")
                    ),
                )
                .with_span(LabeledSpan::new(sp, "not a registered fmt.gcode_* dialect")),
            );
            continue;
        }

        // The plan's own subject is its target: this decl's realized
        // geometry, if this build was supplied one (D128's honest
        // placeholder path otherwise -- removal/coverage then defer at
        // discharge naming the missing target, never a fabricated one).
        let target_geometry = realized_inputs
            .iter()
            .find(|(_, input)| input.subject == decl_name);

        for kind in CAM_CLAIM_KINDS {
            out.push(plan_obligation(
                kind,
                &clause,
                dialect,
                decl_name,
                subject_ref,
                target_geometry,
            ));
        }
        tracing::debug!(
            decl = %decl_name,
            plan_ref = %clause.plan_ref,
            dialect = %dialect,
            "built 5 cam.* obligations from a plan: clause"
        );
    }
}

/// One `cam.*` obligation (see [`push_plan_obligations`]): the claim
/// name/kind IS the exact `cam.*` string the `std.cam` pack's
/// `ModelSignature.claim_kind` registers (WO-67's landed model ids),
/// keyed distinctly per kind (INV-1) by that name alone -- no two of
/// the five obligations from the same clause ever collide.
fn plan_obligation(
    kind: &str,
    clause: &PlanClause,
    dialect: &str,
    decl_name: &str,
    subject_ref: &str,
    target_geometry: Option<(&String, &crate::realized_input::RealizedInput)>,
) -> Obligation {
    let mut loads = vec![
        format!("plan_ref: {}", clause.plan_ref),
        format!("plan_dialect: {dialect}"),
    ];
    let mut payloads = vec![PayloadRef {
        kind: "plan".to_string(),
        digest: String::new(),
        origin: clause.plan_ref.clone(),
    }];
    if let Some(machine_ref) = &clause.machine_ref {
        loads.push(format!("cam_machine_ref: {machine_ref}"));
    }
    if let Some(tooling_ref) = &clause.tooling_ref {
        loads.push(format!("cam_tooling_ref: {tooling_ref}"));
    }
    if let Some(resolution) = &clause.resolution_text {
        loads.push(format!("resolution_mm: {resolution}"));
    }
    if let Some((digest, input)) = target_geometry {
        payloads.push(PayloadRef {
            kind: "geometry.realized".to_string(),
            digest: digest.clone(),
            origin: input.subject.clone(),
        });
    }
    let obligation = Obligation {
        claim: Claim {
            name: Some(kind.to_string()),
            form: ClaimForm::Comparison {
                lhs: kind.to_string(),
                op: "<=".to_string(),
                rhs: "0".to_string(),
            },
            forall: Vec::new(),
            sf: None,
            scatter_factor: None,
            trust_floor: None,
            hints: Vec::new(),
            model_pin: None,
        },
        subject_ref: subject_ref.to_string(),
        given: Given {
            materials: Vec::new(),
            loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads,
    };
    tracing::debug!(
        decl = %decl_name,
        kind = %kind,
        hash = %obligation.content_hash(),
        "built cam.* obligation"
    );
    obligation
}

/// WO-54 deliverable 1 (see the call site above): lower every
/// `mfg.cost(...)` comparison claim in a top-level `require` group,
/// with the D105a `forall` sweep prefix honored and E0438 argument
/// validation. `subject_ref` stays empty (the fluorite/calcite passes
/// key their obligations on payload digests; a top-level cost claim's
/// priced content is resolved orchestrator-side, where the staged
/// inputs doc's digest folds it into the evidence hash).
fn push_top_level_cost_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    files: &[ParsedFile],
) {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for req in file.fluid_requires() {
            // WO-68: reach cost claims nested inside a `forall <var>
            // in <domain>:` block, same shape as every other require
            // group form this WO fixes.
            for (line, block_sweep) in req.all_claims() {
                let subject = line.name();
                let raw_predicate = full_predicate_text(&line);
                let (sweep, predicate) = match parse_forall_prefix(&raw_predicate) {
                    Some((axis, domain, rest)) => (Some(SweepDomain { axis, domain }), rest),
                    None => (
                        block_sweep.as_ref().and_then(sweep_domain_from_ast),
                        raw_predicate,
                    ),
                };
                let GeneralComparison::One { lhs, op, rhs } = split_general_comparison(&predicate)
                else {
                    continue;
                };
                let Some((args, after)) = match_call(&lhs, "mfg.cost") else {
                    continue;
                };
                if !after.trim().is_empty() {
                    continue;
                }
                match parse_cost_claim_args(args) {
                    Ok((cost_subject, profile)) => {
                        let mut loads = vec![format!("cost_subject: {cost_subject}")];
                        if let Some(profile) = profile {
                            loads.push(format!("cost_profile: {profile}"));
                        }
                        let obligation = Obligation {
                            claim: Claim {
                                name: Some(subject.clone()),
                                form: ClaimForm::Comparison {
                                    lhs: resolve_unit_suffix(lhs.trim()),
                                    op: op.clone(),
                                    rhs: resolve_unit_suffix(rhs.trim()),
                                },
                                forall: Vec::new(),
                                sf: None,
                                scatter_factor: None,
                                trust_floor: None,
                                hints: Vec::new(),
                                model_pin: None,
                            },
                            subject_ref: String::new(),
                            given: Given {
                                materials: Vec::new(),
                                loads,
                                backing: Vec::new(),
                                refs: Vec::new(),
                            },
                            hints: Vec::new(),
                            sweep,
                            payloads: vec![],
                        };
                        tracing::debug!(
                            subject = %subject,
                            cost_subject = %cost_subject,
                            hash = %obligation.content_hash(),
                            "built top-level cost obligation (WO-54)"
                        );
                        out.push(obligation);
                    }
                    Err(detail) => {
                        tracing::debug!(
                            subject = %subject,
                            detail = %detail,
                            "malformed top-level mfg.cost claim arguments (E0438)"
                        );
                        diagnostics.push(
                            Diagnostic::error(
                                codes::COST_CLAIM_MALFORMED,
                                format!(
                                    "claim {subject:?}: malformed mfg.cost argument \
                                     list: {detail} (accepted shape: \
                                     `mfg.cost(<subject>[, profile=<name>])`, \
                                     toolchain/27 sec. 1.1)"
                                ),
                            )
                            .with_span(LabeledSpan::new(
                                field_span(&pf.path, &line),
                                "malformed mfg.cost argument list here",
                            )),
                        );
                    }
                }
            }
        }
    }
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
            // WO-68: reach claims nested inside a `forall <var> in
            // <domain>:` block (fluorite/03's `states:`-indexed
            // require sweeps use exactly this shape).
            for (line, sweep) in req.all_claims() {
                push_fluid_obligation(
                    out,
                    diagnostics,
                    &pf.path,
                    &flownet_name,
                    payload,
                    &line,
                    sweep.as_ref().and_then(sweep_domain_from_ast),
                );
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
    sweep: Option<SweepDomain>,
) {
    let subject = line.name();
    let raw_predicate = full_predicate_text(line);
    if !raw_predicate.contains("fluids.") {
        return;
    }
    // WO-94 escalation 1: the corpus-wide `given <ident> = <expr>` claim
    // suffix (`given T_group = 90degC`, `given v3 = brew`) rides inside
    // the fluid predicate text; split it off BEFORE the comparison scan
    // (so it never pollutes the comparator RHS) and thread every binding
    // into `given.loads` -- the `_translate_call_kwargs_claim` fallback
    // channel (npsh/supply_dp/dp read these when the call carries no
    // inline kwarg; inline still wins). Non-fluid givens (regime
    // selectors like `v3 = brew`) ride along harmlessly: `resolve_givens`
    // simply skips a non-numeric value.
    let (predicate, given_loads) = split_claim_suffix_givens(&raw_predicate);

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
    // WO-92 deliverable 2: a fluid predicate whose comparator sits AFTER the
    // `fluids.*(...)` call expression (`fluids.mdot(duct) >= 0.0003`) is
    // opaque to the translate-side head-only `_split_comparator` (it defers
    // `unsupported_op`). Lower it STRUCTURALLY here: the CST-derived
    // predicate text carries exactly one top-level comparator, unambiguous
    // to `split_general_comparison`'s depth-0 scan, so the obligation can
    // carry a real comparator (`op=">="`, LHS = the call expression) and
    // translate lowers it to a scalar `DischargeRequest` keyed on the
    // claim's own name (`flow`). A head comparator (`<= 5kPa`, whose empty
    // LHS makes `split_general_comparison` return `NotComparison`) or any
    // multi-comparator predicate stays the opaque `require` form the
    // translate-side head split already handles -- no behavior change there.
    let (claim_lhs, claim_op, claim_rhs) = match split_general_comparison(&resolved_predicate) {
        GeneralComparison::One { lhs, op, rhs } => (lhs, op, rhs),
        _ => (subject.clone(), "require".to_string(), resolved_predicate),
    };
    let claim = Claim {
        name: Some(subject.clone()),
        form: ClaimForm::Comparison {
            lhs: claim_lhs,
            op: claim_op,
            rhs: claim_rhs,
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
            // WO-94 escalation 1: the claim-suffix givens, threaded so
            // the fluid translate paths can read them (INV-1: a claim
            // with different givens now hashes to a different
            // obligation, which is correct -- the given is part of the
            // evaluation context, not incidental text).
            loads: given_loads,
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        // WO-68: a claim nested inside a `forall <var> in <domain>:`
        // block (e.g. a fluid `states:`-indexed require sweep) keys
        // its obligation with the declared domain, per INV-1.
        sweep,
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
const FRAME_CLAIM_FORMS: [&str; 6] = [
    "civil.utilization(",
    "mech.deflection(",
    "civil.story_drift(",
    "civil.bearing_pressure(",
    "mech.first_mode(",
    // WO-85/D194: declared embedment depth vs required (the
    // `civil.bearing_pressure` reaction-based closed-form pattern).
    "civil.embedment(",
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

    // WO-85/D194: the `civil.embedment` bound resolver's site-datum
    // index, built once across the WHOLE project's files (`site` decls
    // typically live in `site.calx`, the claims in `frame.calx` -- the
    // same cross-file relationship `frame_lower`'s grid/level
    // aggregation already honors).
    let all_files: Vec<File> = files
        .iter()
        .filter_map(|pf| File::cast(pf.parse.syntax()))
        .collect();
    let site_index = site_quantities(&all_files);
    // WO-96 bearing close-out: the parallel interval-datum index (the
    // `civil.bearing_pressure` bound resolver's `site.soil.bearing`
    // capacity ranges), built over the same whole-project file set.
    let site_interval_index = site_interval_quantities(&all_files);

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
        // Site-datum resolution scope: the claim's OWN file wins (a
        // multi-design directory -- examples/tracks/calcite -- carries
        // one site per design file, and pole_barn's `frost_depth` must
        // never collide with bus_shelter's); the project-wide index is
        // the fallback for the ordinary `site.calx` + `frame.calx`
        // split, where the claim's file declares no site of its own.
        let local_index = site_quantities(std::slice::from_ref(&file));
        let mut effective_index = site_index.clone();
        effective_index.extend(local_index);
        let local_intervals = site_interval_quantities(std::slice::from_ref(&file));
        let mut effective_intervals = site_interval_index.clone();
        effective_intervals.extend(local_intervals);

        for req in file.fluid_requires() {
            // WO-68: `all_claims()` reaches claims nested inside a
            // `forall combo in ...:` block (calcite/02 sec. 9's
            // `strength:` sweep is exactly this shape) -- previously
            // invisible here, the live footbridge repro (4 obligations,
            // zero `strength`).
            for (line, sweep) in req.all_claims() {
                let sweep_domain = sweep.as_ref().and_then(sweep_domain_from_ast);
                push_frame_obligation(
                    out,
                    &structure_name,
                    payload,
                    &line,
                    sweep_domain.as_ref(),
                    &effective_index,
                    &effective_intervals,
                );
            }
        }
    }

    report.frames
}

/// Every `site` declaration's point-quantity fields across the
/// project, keyed by LEAF field name (`frost_depth` -> `"1.2m"`) --
/// the `civil.embedment` bound resolver's lookup table (WO-85/D194).
/// A leaf name declared twice with DIFFERENT value text maps to `None`
/// (ambiguous: never guessed, the claim's bound stays symbolic and
/// defers downstream by name); interval-valued fields (`bearing:
/// [120kPa, 170kPa]`) are not point quantities and are simply absent.
fn site_quantities(files: &[File]) -> BTreeMap<String, Option<String>> {
    let mut index: BTreeMap<String, Option<String>> = BTreeMap::new();
    for file in files {
        for site in file.sites() {
            for field in site.syntax().descendants().filter_map(Field::cast) {
                let Some(value) = field.value() else {
                    continue;
                };
                if value.kind() != SyntaxKind::QuantityLit {
                    continue;
                }
                let text = value.text().to_string().trim().to_string();
                match index.entry(field.name()) {
                    std::collections::btree_map::Entry::Vacant(v) => {
                        v.insert(Some(text));
                    }
                    std::collections::btree_map::Entry::Occupied(mut o) => {
                        if o.get().as_deref() != Some(text.as_str()) {
                            tracing::info!(
                                field = %field.name(),
                                "site datum declared twice with different values; \
                                 embedment bound resolution marks it ambiguous"
                            );
                            o.insert(None);
                        }
                    }
                }
            }
        }
    }
    index
}

/// Every `site` declaration's INTERVAL-valued fields across the project,
/// keyed by LEAF field name (`bearing` -> `("120kPa", "170kPa")`) -- the
/// `civil.bearing_pressure` bound resolver's lookup table (WO-96 bearing
/// close-out). A `by test`/`by catalog` provenance clause after the
/// bracket is dropped (only the two endpoints matter). A leaf declared
/// twice with DIFFERENT endpoints maps to `None` (ambiguous: never
/// guessed, the claim's bound stays symbolic and defers downstream by
/// name); point-quantity fields are handled by [`site_quantities`].
fn site_interval_quantities(files: &[File]) -> BTreeMap<String, Option<(String, String)>> {
    let mut index: BTreeMap<String, Option<(String, String)>> = BTreeMap::new();
    for file in files {
        for site in file.sites() {
            for field in site.syntax().descendants().filter_map(Field::cast) {
                let Some(value) = field.value() else {
                    continue;
                };
                if value.kind() != SyntaxKind::IntervalExpr {
                    continue;
                }
                let text = value.text().to_string();
                let Some(endpoints) = interval_endpoints(&text) else {
                    continue;
                };
                match index.entry(field.name()) {
                    std::collections::btree_map::Entry::Vacant(v) => {
                        v.insert(Some(endpoints));
                    }
                    std::collections::btree_map::Entry::Occupied(mut o) => {
                        if o.get().as_ref() != Some(&endpoints) {
                            tracing::info!(
                                field = %field.name(),
                                "site interval datum declared twice with different \
                                 endpoints; bearing bound resolution marks it ambiguous"
                            );
                            o.insert(None);
                        }
                    }
                }
            }
        }
    }
    index
}

/// The two endpoint texts of a `[lo, hi]` interval literal (`"[120kPa,
/// 170kPa]"` -> `("120kPa", "170kPa")`), trimmed. `None` when the text
/// is not a two-endpoint bracket (a `{a, b}` discrete set or a malformed
/// literal is not a numeric interval this resolver substitutes).
fn interval_endpoints(text: &str) -> Option<(String, String)> {
    let inner = text.trim().strip_prefix('[')?;
    let close = inner.find(']')?;
    let (lo, hi) = inner[..close].split_once(',')?;
    Some((lo.trim().to_string(), hi.trim().to_string()))
}

/// Resolve a civil predicate's trailing dotted site-datum bound to its
/// declared quantity text, matching by the path's LEAF segment against
/// the project's `site` decls. Two datum shapes:
///
/// - POINT (WO-85/D194, `civil.embedment`): `>= site.frost_depth` ->
///   `>= 1.2m` from [`site_quantities`].
/// - INTERVAL (WO-96 bearing close-out, `civil.bearing_pressure`): `<=
///   site.soil.bearing`/`<= ShopFloor.soil.bearing` -> the CONSERVATIVE
///   endpoint of the tested-capacity interval (`[150kPa, 210kPa]` ->
///   `150kPa` for a `<=` allowable, `210kPa` for a `>=` demand) from
///   [`site_interval_quantities`]. Picking the tightest endpoint by
///   comparator sense keeps the discharged verdict on the safe side of
///   the measured range (never the optimistic end).
///
/// The bound's dotted path may be prefixed either by the literal `site.`
/// (the ordinary `site.calx` split) or by the site's declared NAME
/// (`ShopFloor.soil.bearing`, hydro_press's in-file site) -- the leaf is
/// the stable key either way. Returns the predicate unchanged when the
/// bound is not a dotted reference or the leaf is unknown/ambiguous --
/// the claim then defers downstream with its symbolic bound intact
/// (honest, never guessed).
fn resolve_embedment_site_bound(
    predicate: &str,
    site_index: &BTreeMap<String, Option<String>>,
    site_intervals: &BTreeMap<String, Option<(String, String)>>,
) -> String {
    let Some(cmp_idx) = predicate.find(">=").or_else(|| predicate.find("<=")) else {
        return predicate.to_string();
    };
    let op = &predicate[cmp_idx..cmp_idx + 2];
    let head = &predicate[..cmp_idx + 2];
    let bound = predicate[cmp_idx + 2..].trim();
    let path: String = bound
        .chars()
        .take_while(|c| c.is_alphanumeric() || *c == '.' || *c == '_')
        .collect();
    // A bare quantity bound (`<= 150kPa`) or non-reference is left alone.
    if path.is_empty() || !path.contains('.') {
        return predicate.to_string();
    }
    let Some(leaf) = path.rsplit('.').next().filter(|l| !l.is_empty()) else {
        return predicate.to_string();
    };
    let tail = &bound[path.len()..];
    // Point datum (embedment) takes precedence; then the interval datum
    // (bearing). A leaf in neither index leaves the bound symbolic.
    if let Some(entry) = site_index.get(leaf) {
        return if let Some(quantity) = entry {
            tracing::debug!(
                leaf = %leaf,
                quantity = %quantity,
                "civil bound resolved from point site datum"
            );
            format!("{head} {quantity}{tail}")
        } else {
            tracing::info!(leaf = %leaf, "point site datum ambiguous; left symbolic");
            predicate.to_string()
        };
    }
    match site_intervals.get(leaf) {
        Some(Some((lo, hi))) => {
            let endpoint = if op == ">=" { hi } else { lo };
            tracing::debug!(
                leaf = %leaf,
                endpoint = %endpoint,
                op = %op,
                "civil bound resolved to conservative endpoint of site interval datum"
            );
            format!("{head} {endpoint}{tail}")
        }
        Some(None) => {
            tracing::info!(leaf = %leaf, "interval site datum ambiguous; left symbolic");
            predicate.to_string()
        }
        None => {
            tracing::info!(leaf = %leaf, "site datum not found; left symbolic");
            predicate.to_string()
        }
    }
}

/// Lower one calcite `require` claim [`Field`] line into obligation(s)
/// carrying the frame's content-addressed [`PayloadRef`], when its
/// predicate is one of the [`FRAME_CLAIM_FORMS`] (calcite/03 sec. 5).
/// Any other predicate in the same group (egress claims, code-pack
/// `rule` demands, ...) is skipped, not misfiled as a frame obligation.
///
/// WO-85/D194 ruling 3: a `<X>.members.all` group subject is SUGAR for
/// a per-member sweep -- it EXPANDS here into one obligation per
/// payload member, the member pinned in both the claim name
/// (`strength[G1]`) and the rewritten predicate subject
/// (`<X>.members.G1`), exactly the WO-68 forall-combo precedent. A
/// group with one indeterminate member thereby yields N-1 real
/// verdicts plus one honest per-member deferral downstream, never a
/// wholesale defer and never a fabricated aggregate pass. A
/// `civil.embedment` bound naming a `site.<datum>` path resolves to
/// its declared quantity ([`resolve_embedment_site_bound`]).
fn push_frame_obligation(
    out: &mut Vec<Obligation>,
    structure_name: &str,
    payload: &regolith_oblig::FramePayload,
    line: &Field,
    sweep: Option<&SweepDomain>,
    site_index: &BTreeMap<String, Option<String>>,
    site_intervals: &BTreeMap<String, Option<(String, String)>>,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);
    if !FRAME_CLAIM_FORMS
        .iter()
        .any(|form| predicate.contains(form))
    {
        return;
    }
    // Both the embedment (point-datum) and bearing-pressure (interval-
    // datum) claim forms carry a site-datum comparator bound the
    // resolver literalizes; every other frame claim keeps its predicate.
    let predicate = if predicate.contains("civil.embedment(")
        || predicate.contains("civil.bearing_pressure(")
    {
        resolve_embedment_site_bound(&predicate, site_index, site_intervals)
    } else {
        predicate
    };

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

    // The (name, predicate) instances this claim line lowers to: the
    // line itself, or its per-member expansion (D194 ruling 3). An
    // aggregate over an empty member list degrades to the unexpanded
    // single obligation (it defers downstream naming the empty frame
    // -- honest, and E0208's territory at check time).
    let group_marker = ".members.all";
    let instances: Vec<(String, String)> =
        if predicate.contains(group_marker) && !payload.members.is_empty() {
            payload
                .members
                .iter()
                .map(|member| {
                    (
                        format!("{subject}[{id}]", id = member.id),
                        predicate.replacen(group_marker, &format!(".members.{}", member.id), 1),
                    )
                })
                .collect()
        } else {
            vec![(subject.clone(), predicate.clone())]
        };
    let expanded = instances.len() > 1;

    for (instance_name, instance_predicate) in instances {
        let claim = Claim {
            name: Some(instance_name.clone()),
            form: ClaimForm::Comparison {
                lhs: instance_name.clone(),
                op: "require".to_string(),
                rhs: resolve_unit_suffix(&instance_predicate),
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
            // way hematite/cuprite decls do (the fluorite precedent,
            // verbatim). Per-member expansion instances stay distinct
            // through their claim name + rewritten predicate.
            subject_ref: digest.clone(),
            given: Given {
                materials: Vec::new(),
                loads: Vec::new(),
                backing: Vec::new(),
                refs: Vec::new(),
            },
            hints: Vec::new(),
            // WO-68: a claim nested inside a `forall combo in ...:` block
            // (calcite/02 sec. 9's strength sweep) keys its obligation with
            // the declared combination-set domain, per INV-1.
            sweep: sweep.cloned(),
            payloads: vec![payload_ref],
        };
        tracing::debug!(
            structure = %structure_name,
            subject = %instance_name,
            expanded,
            hash = %obligation.content_hash(),
            "built calcite structural obligation with frame payload ref"
        );
        out.push(obligation);
    }
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
    block_sweep: Option<&SweepDomain>,
    given: &Given,
) {
    let subject = line.name();
    let raw_predicate = full_predicate_text(line);
    // WO-80 deliverable 2: the claim line's rung-5 `model=<ident>` pin
    // (WO-80 deliverable 1's typed `ModelPin` node), read once and
    // threaded into every obligation this line produces -- a pin
    // changes the obligation's content, so re-keying evidence built
    // under a different (or absent) pin is CORRECT per INV-2, not a
    // bug (WO-80 deliverable 2's note).
    let model_pin = line.model_pin();

    // WO-26 D105a: a `forall <var> in <domain>:` claim-line prefix
    // lowers into the obligation's EXISTING `sweep` slot (SweepDomain)
    // -- the grammar surface finally exposing what the schema already
    // carries. Both continuous `[lo, hi]` and discrete `{a, b}`
    // domains ride the same path (D93/D95 alignment); the remainder of
    // the line lowers through every path below unchanged. WO-68: a
    // claim nested inside a `forall <var> in <domain>:` BLOCK carries
    // its sweep via `block_sweep` instead (the two forms are mutually
    // exclusive in source, but the inline prefix wins if somehow both
    // are present -- it is the more specific, line-local source).
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
        None => (block_sweep.cloned(), raw_predicate),
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

    // WO-78 deliverable 2 (charter 35 sec. 1.2): an
    // `elec.impedance(<net>, ...) within [lo, hi]` claim splits into
    // the same two one-sided obligations the generic `within` path
    // below builds, but PRESERVES the resolved call expression as each
    // half's `lhs` -- the generic path's `lhs = subject` would drop the
    // net and the geometry kwargs (`stackup=`, `layer=`, `w=`) the
    // orchestrator's SI translation routes to the feldspar WO-25
    // models. Checked before the generic split so it wins on exactly
    // this call shape and nothing else; an `elec.impedance(...)` with
    // a plain comparator falls through to the D103 general-comparison
    // path, which already preserves call text.
    if push_impedance_window_obligations(
        out,
        diagnostics,
        ctx,
        line,
        &subject,
        &predicate,
        given,
        sweep,
        model_pin.as_deref(),
    ) {
        return;
    }

    // WO-26 deliverable 2: a `within [lo, hi] ...` demanded window splits
    // into TWO one-sided obligations (`>= lo`, `<= hi`) over the SAME
    // subject, reusing the existing scalar-comparison path end to end
    // (the orchestrator never needs a two-sided request type). Each
    // half's bound goes through the same unit-suffix resolution as an
    // ordinary comparator bound.
    if let Some((window_lhs, lo, hi)) = within_window_bounds(&predicate) {
        // The windowed call EXPRESSION (`thermo.temperature(...)`) is
        // carried as each half's LHS so translate's `_match_call_lhs`
        // routes it to the model; an empty leading expression falls back
        // to the claim label inside the helper.
        push_within_window_obligations(
            out,
            ctx,
            &subject,
            &window_lhs,
            given,
            sweep,
            (&lo, &hi),
            model_pin.as_deref(),
        );
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
            // WO-54 deliverable 1: an `mfg.cost(...)` claim gets its
            // own validation + given-threading path (E0438 on a
            // malformed argument list); everything else lowers through
            // the generic D103 comparison unchanged.
            let sides = (lhs.as_str(), op.as_str(), rhs.as_str());
            if !push_cost_claim_obligation(
                out,
                diagnostics,
                ctx,
                line,
                &subject,
                given,
                sweep,
                sides,
                model_pin.clone(),
            ) {
                push_general_comparison_obligation(
                    out,
                    ctx,
                    &subject,
                    given,
                    sweep,
                    sides,
                    model_pin.clone(),
                );
            }
            return;
        }
        GeneralComparison::NotComparison => {}
    }

    push_opaque_require_obligation(out, ctx, &subject, given, sweep, &predicate, model_pin);
}

/// The pre-existing opaque `require` path: the predicate stays a text
/// blob (`op="require"`) after WO-26 deliverable 1's unit-suffix bound
/// resolution through `regolith-qty` (`>= 6800 N` -> its canonical
/// SI-base numeral) -- a predicate whose bound is not a recognized unit
/// expression passes through unchanged and the orchestrator defers it
/// exactly as before, never a silently invented number.
fn push_opaque_require_obligation(
    out: &mut Vec<Obligation>,
    ctx: &ClaimLoweringCtx<'_>,
    subject: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    predicate: &str,
    model_pin: Option<String>,
) {
    let resolved_predicate = resolve_unit_suffix(predicate);

    let claim = Claim {
        name: Some(subject.to_string()),
        form: ClaimForm::Comparison {
            lhs: subject.to_string(),
            op: "require".to_string(),
            rhs: resolved_predicate,
        },
        forall: Vec::new(),
        sf: None,
        scatter_factor: None,
        trust_floor: None,
        hints: Vec::new(),
        model_pin,
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

/// WO-78 deliverable 2: lower an `elec.impedance(<net>, ...) within
/// [lo, hi]` claim to its two one-sided obligations (`<subject>.lo`
/// with `>=`, `<subject>.hi` with `<=`), each half's `lhs` carrying
/// the unit-resolved call expression so the orchestrator's SI
/// translation (`translate._translate_si_impedance`) reads the net and
/// geometry kwargs without a second grammar. Returns `true` when the
/// claim was handled here (obligations pushed OR the E0452
/// malformed-argument diagnostic fired); `false` when the predicate is
/// not an impedance-window claim at all.
#[allow(
    clippy::too_many_arguments,
    reason = "the per-line lowering context (subject/predicate/given/sweep) \
              is one call site's locals; bundling them into a struct would \
              only rename the same nine things"
)]
fn push_impedance_window_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    ctx: &ClaimLoweringCtx<'_>,
    line: &Field,
    subject: &str,
    predicate: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    model_pin: Option<&str>,
) -> bool {
    let Some((args, after)) = match_call(predicate, "elec.impedance") else {
        return false;
    };
    if !after.trim_start().starts_with("within") {
        // A comparator-shaped impedance claim (`elec.impedance(x) <= 60`)
        // is the D103 general-comparison path's job; only the window
        // form is handled here.
        return false;
    }
    let Some((lo, hi)) = within_window_bounds(after) else {
        return false;
    };
    let named_net = split_top_level_args(args)
        .into_iter()
        .next()
        .filter(|first| !first.is_empty() && !first.contains('='));
    let Some(net) = named_net else {
        tracing::debug!(
            decl = %ctx.decl_name,
            subject = %subject,
            "elec.impedance claim names no net (E0452)"
        );
        diagnostics.push(
            Diagnostic::error(
                codes::SI_IMPEDANCE_MALFORMED,
                format!(
                    "claim {subject:?}: `elec.impedance(...)` names no net: the \
                     first argument must be the net or net-class reference \
                     (accepted shape: `elec.impedance(<net>[, role=..., \
                     stackup=..., layer=..., w=...]) within [lo, hi]`)"
                ),
            )
            .with_span(LabeledSpan::new(
                field_span(ctx.path, line),
                "impedance claim names no net",
            )),
        );
        return true;
    };
    let call = format!("elec.impedance({})", resolve_unit_suffix(args));
    for (suffix, op, bound) in [("lo", ">=", lo.as_str()), ("hi", "<=", hi.as_str())] {
        let bound_si = resolve_unit_suffix(bound.trim());
        let name = format!("{subject}.{suffix}");
        let claim = Claim {
            name: Some(name.clone()),
            form: ClaimForm::Comparison {
                lhs: call.clone(),
                op: op.to_string(),
                rhs: bound_si,
            },
            forall: Vec::new(),
            sf: None,
            scatter_factor: None,
            trust_floor: None,
            hints: Vec::new(),
            model_pin: model_pin.map(str::to_string),
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
            net = %net,
            hash = %obligation.content_hash(),
            "built obligation from elec.impedance window half (WO-78)"
        );
        out.push(obligation);
    }
    true
}

/// WO-26 deliverable 2: build the two one-sided obligations a
/// `within [lo, hi]` demanded window splits into (`>= lo`, `<= hi`),
/// each bound unit-resolved like an ordinary comparator bound.
#[allow(
    clippy::too_many_arguments,
    reason = "the per-line lowering context (subject/window_lhs/given/sweep/\
              bounds/pin) is one call site's locals; a struct would only \
              rename the same eight things"
)]
fn push_within_window_obligations(
    out: &mut Vec<Obligation>,
    ctx: &ClaimLoweringCtx<'_>,
    subject: &str,
    window_lhs: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    (lo, hi): (&str, &str),
    model_pin: Option<&str>,
) {
    // An empty leading expression (a bare scalar window) keeps the claim
    // label as its LHS, exactly as before this call form was carried.
    let window_lhs = if window_lhs.is_empty() {
        subject
    } else {
        window_lhs
    };
    for (suffix, op, bound) in [("lo", ">=", lo), ("hi", "<=", hi)] {
        let bound_si = resolve_unit_suffix(bound.trim());
        let name = format!("{subject}.{suffix}");
        let claim = Claim {
            name: Some(name.clone()),
            form: ClaimForm::Comparison {
                // The full windowed expression (a call form when present,
                // else the claim label): translate's `_match_call_lhs`
                // routes a `thermo.temperature(...)` LHS to its model, so
                // a windowed claim reaches the same model a bare one does.
                lhs: window_lhs.to_string(),
                op: op.to_string(),
                rhs: bound_si,
            },
            forall: Vec::new(),
            sf: None,
            scatter_factor: None,
            trust_floor: None,
            hints: Vec::new(),
            model_pin: model_pin.map(str::to_string),
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
                model_pin: line.model_pin(),
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
    model_pin: Option<String>,
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
        model_pin,
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

/// WO-68: the [`SweepDomain`] a `forall <var> in <domain>:` BLOCK
/// claim's header carries, for a claim nested inside it (the
/// `RequireClaim::all_claims` companion). `None` when the node was
/// itself the AD-3 opaque-degrade case (no bound variable found -- a
/// malformed header the parser recorded structure for but could not
/// fully type).
fn sweep_domain_from_ast(sweep: &regolith_syntax::ast::ForallSweepClaim) -> Option<SweepDomain> {
    let axis = sweep.var()?;
    let domain = resolve_unit_suffix(&sweep.domain_text());
    Some(SweepDomain { axis, domain })
}

/// WO-90 deliverable 2: is `domain` (a `forall <var> in <domain>:` sweep
/// header's domain text) a BARE PLURAL that names no declared domain?
/// The declared domain forms are a `[lo, hi]` interval, a `{a, b}`
/// discrete set, a `registry(<family>)` record family, an
/// `<Entity>.members.all` collection, or any dotted pack/entity ref
/// (`std.pack.family`) -- all of which carry a bracket, a `registry(`
/// prefix, or a `.`. Anything left is a single bare identifier
/// (`boards`, `assemblies`) that resolves to no declared domain, so the
/// sweep silently covers zero points. An explicitly EMPTY declared
/// domain (`{}`, `[]`) stays legal (it starts with a bracket) -- an
/// honest empty sweep, not this trap.
fn is_undeclared_bare_plural_domain(domain: &str) -> bool {
    let d = domain.trim();
    if d.is_empty() {
        // A missing domain is a malformed header the parser already
        // degraded (AD-3 opaque), not this diagnostic's concern.
        return false;
    }
    let declared = d.starts_with('[')
        || d.starts_with('{')
        || d.starts_with("registry(")
        || d.contains('.')
        || d.contains('(');
    !declared
}

/// WO-90 deliverable 2: emit `E0450` when a `forall` sweep's domain is
/// an undeclared bare plural (see [`is_undeclared_bare_plural_domain`]),
/// constructively naming the declared domain forms. A well-formed
/// declared domain (or a malformed header with no domain text) is left
/// untouched.
fn check_forall_domain(
    diagnostics: &mut Vec<Diagnostic>,
    path: &camino::Utf8Path,
    sweep: &regolith_syntax::ast::ForallSweepClaim,
) {
    let domain = sweep.domain_text();
    if !is_undeclared_bare_plural_domain(&domain) {
        return;
    }
    let domain = domain.trim();
    let range = sweep.syntax().text_range();
    let sp = Span::new(path.to_owned(), range.start().into(), range.end().into());
    tracing::info!(
        domain = %domain,
        "E0450: forall sweep names an undeclared bare-plural domain"
    );
    diagnostics.push(
        Diagnostic::error(
            codes::FORALL_DOMAIN_UNDECLARED,
            format!(
                "`forall ... in {domain}:` names no declared domain, so the sweep \
                 covers zero points (a vacuous pass); declare a domain -- a \
                 `registry(<family>)` record family, an `<Entity>.members.all` \
                 collection, a `[lo, hi]` interval, or a `{{a, b}}` discrete set"
            ),
        )
        .with_span(LabeledSpan::new(
            sp,
            format!("no declared domain named `{domain}`"),
        )),
    );
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

/// Split a fluid claim predicate's trailing `given <ident> = <expr>[,
/// <ident> = <expr>]*` suffix (fluorite/03, the corpus-wide claim-suffix
/// given form) off the comparison text. Returns the predicate with the
/// suffix removed plus one `"<ident>: <expr>"` load line per binding, in
/// source order -- exactly the `given.loads` shape the Python translate
/// paths already consume (`resolve_givens`/`_load_fields`), with inline
/// call kwargs still winning over these (`_translate_call_kwargs_claim`).
/// Returns the predicate unchanged and an empty vec when no whole-word
/// `given` keyword is present. The keyword is matched as a whole word so
/// it never fires on a longer identifier (`givenness`), and only the
/// FIRST occurrence is treated as the suffix start (a given expression
/// naming `given` again would be pathological and is left to the value).
fn split_claim_suffix_givens(predicate: &str) -> (String, Vec<String>) {
    let mut search_from = 0usize;
    let mut idx = None;
    while let Some(rel) = predicate[search_from..].find("given") {
        let i = search_from + rel;
        let before_ok = predicate[..i]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_');
        let after = &predicate[i + "given".len()..];
        let after_ok = after
            .chars()
            .next()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_');
        if before_ok && after_ok {
            idx = Some(i);
            break;
        }
        search_from = i + "given".len();
    }
    let Some(i) = idx else {
        return (predicate.to_string(), Vec::new());
    };
    let head = predicate[..i].trim_end().to_string();
    let suffix = predicate[i + "given".len()..].trim();
    let mut loads = Vec::new();
    for segment in split_top_level_args(suffix) {
        let seg = segment.trim();
        if seg.is_empty() {
            continue;
        }
        // Only `ident = expr` bindings thread into loads; a bare token
        // (a malformed suffix) is skipped rather than misfiled.
        if let Some((name, value)) = seg.split_once('=') {
            let name = name.trim();
            let value = value.trim();
            // Thread ONLY quantity-valued givens (`T_group = 90degC`,
            // `dia = [8mm, 10mm]`): those are the model inputs the fluid
            // translate paths consume. A regime-selector given naming a
            // bare state (`v3 = brew`, `wand.position = closed`) is NOT a
            // numeric input and stays dropped exactly as before -- else
            // the generic scalar translate path's D97 `resolve_givens`
            // would read it as an unresolved given and hard-defer a claim
            // that used to lower (the WO's "zero lowered->deferred" bar).
            if !name.is_empty() && value_is_quantity(value) {
                loads.push(format!("{name}: {value}"));
            }
        }
    }
    (head, loads)
}

/// True iff `value` reads as a numeric quantity or `[lo, hi]` interval
/// (the shapes `resolve_givens`/`_parse_interval` accept on the Python
/// side) rather than a bare regime-selector identifier. Matches a
/// leading sign/digit/decimal point or an opening interval bracket.
fn value_is_quantity(value: &str) -> bool {
    let trimmed = value.trim_start_matches(['+', '-']).trim_start();
    trimmed
        .chars()
        .next()
        .is_some_and(|c| c.is_ascii_digit() || c == '.' || c == '[')
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

/// WO-54 deliverable 1 (toolchain/27 sec. 1.1, AD-29): lower an
/// `mfg.cost(<subject>[, profile=<name>])` comparison claim, validating
/// its argument shape at compile time (E0438, constructive) and
/// threading `cost_subject:`/`cost_profile:` plus the enclosing decl's
/// `parts:` BOM lines into `given.loads` (the conformance-windows
/// precedent) so the orchestrator's profile resolution (deliverable 4)
/// reads structured fields instead of re-parsing claim text.
///
/// Returns `true` when the claim was handled here (an obligation was
/// pushed OR a malformed-argument diagnostic fired); `false` when the
/// lhs is not the v1 cost-claim surface (including an lhs that only
/// EMBEDS a cost call in a larger expression, `mfg.cost(x) + shipping`)
/// -- the caller's generic comparison path then applies unchanged.
#[allow(clippy::too_many_arguments)]
#[allow(
    clippy::too_many_arguments,
    reason = "the per-line lowering context (subject/predicate/given/sweep) \
              is one call site's locals; bundling them into a struct would \
              only rename the same nine things"
)]
fn push_cost_claim_obligation(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    ctx: &ClaimLoweringCtx<'_>,
    line: &Field,
    subject: &str,
    given: &Given,
    sweep: Option<&SweepDomain>,
    (lhs, op, rhs): (&str, &str, &str),
    model_pin: Option<String>,
) -> bool {
    let Some((args, after)) = match_call(lhs, "mfg.cost") else {
        return false;
    };
    if !after.trim().is_empty() {
        return false;
    }
    match parse_cost_claim_args(args) {
        Ok((cost_subject, profile)) => {
            let mut cost_given = given.clone();
            cost_given
                .loads
                .push(format!("cost_subject: {cost_subject}"));
            if let Some(profile) = profile {
                cost_given.loads.push(format!("cost_profile: {profile}"));
            }
            for (part, value) in cost_bom_lines(ctx.decl) {
                cost_given.loads.push(format!("cost_bom.{part}: {value}"));
            }
            tracing::debug!(
                decl = %ctx.decl_name,
                subject = %subject,
                cost_subject = %cost_subject,
                "mfg.cost claim threads cost fields into given (WO-54)"
            );
            push_general_comparison_obligation(
                out,
                ctx,
                subject,
                &cost_given,
                sweep,
                (lhs, op, rhs),
                model_pin,
            );
        }
        Err(detail) => {
            tracing::debug!(
                decl = %ctx.decl_name,
                subject = %subject,
                detail = %detail,
                "malformed mfg.cost claim arguments (E0438)"
            );
            diagnostics.push(
                Diagnostic::error(
                    codes::COST_CLAIM_MALFORMED,
                    format!(
                        "claim {subject:?}: malformed mfg.cost argument list: {detail} \
                         (accepted shape: `mfg.cost(<subject>[, profile=<name>])`, \
                         toolchain/27 sec. 1.1)"
                    ),
                )
                .with_span(LabeledSpan::new(
                    field_span(ctx.path, line),
                    "malformed mfg.cost argument list here",
                )),
            );
        }
    }
    true
}

/// WO-54 deliverable 1: parse an `mfg.cost(...)` argument list into
/// `(subject, profile)`. The accepted shape (toolchain/27 sec. 1.1) is
/// exactly `<subject>[, profile=<name>]`; anything else is an `Err`
/// naming the offending argument (lowered to E0438 by the caller).
fn parse_cost_claim_args(args: &str) -> Result<(String, Option<String>), String> {
    let pieces = split_top_level_args(args);
    let Some(first) = pieces.first() else {
        return Err("missing <subject> (empty argument list)".to_string());
    };
    if split_kwarg(first).is_some() {
        return Err(format!(
            "first argument {first:?} must be the positional <subject>"
        ));
    }
    let subject = first.trim().to_string();
    if subject.is_empty() {
        return Err("missing <subject> (empty argument list)".to_string());
    }
    let mut profile: Option<String> = None;
    for extra in &pieces[1..] {
        match split_kwarg(extra) {
            Some(("profile", value)) => {
                if value.is_empty() || value.contains(char::is_whitespace) {
                    return Err(format!("profile= value {value:?} is not a bare name"));
                }
                if profile.is_some() {
                    return Err("duplicate profile= argument".to_string());
                }
                profile = Some(value.to_string());
            }
            Some((key, _)) => {
                return Err(format!("unknown keyword argument {key:?}"));
            }
            None => {
                return Err(format!(
                    "stray positional argument {extra:?} (only <subject> is positional)"
                ));
            }
        }
    }
    Ok((subject, profile))
}

/// WO-54 deliverable 1: the enclosing decl's `parts:` entries as
/// `(part name, raw value text)` BOM lines, in source order (AD-6) --
/// threaded into an `mfg.cost` obligation's `given.loads` as
/// `cost_bom.<part>: <value>` so the elec BOM estimator has a
/// subject-scoped quantity basis (`vendor(<key>)` values resolve to
/// pricing records orchestrator-side). Mirrors `given_for_decl`'s
/// `loads:` descent for the `parts:` block.
fn cost_bom_lines(decl: &Decl) -> Vec<(String, String)> {
    // A `parts:` block is its own node kind, not a `Field` (the
    // `contracts.rs::part_type_refs` precedent), so find it by kind
    // and cast only its entry children.
    let mut lines = Vec::new();
    for block in decl
        .syntax()
        .descendants()
        .filter(|n| n.kind() == SyntaxKind::PartsBlock)
    {
        for part in block.children().filter_map(Field::cast) {
            if let Some(value) = part.value() {
                lines.push((part.name(), value.text().to_string().trim().to_string()));
            }
        }
    }
    lines
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
    // `DischargeRequest` (the harness conformance model, AD-1). D195
    // (WO-92): when only the SPEC side resolves -- a literal promise, or
    // a parametric promise (`power: <= watts`) closed by the impl
    // header's generic pin (`<watts=50W>`) -- the sense + spec bound +
    // field name are still threaded so the orchestrator can defer with
    // the TEACHING `conformance_impl_bound_missing` reason; an
    // `impl_bound` is NEVER fabricated from the pin (a `50 <= 50`
    // discharge would be vacuous and mask real indeterminacy). Absent a
    // scalar bound on either side the windows are simply not carried and
    // the orchestrator defers the obligation honestly -- no invented window.
    let loads = match conformance_windows(edge, files, diagnostics) {
        Some(ConformanceWindow::Both {
            sense,
            spec,
            imp,
            field,
        }) => vec![
            format!("conformance_sense: {sense}"),
            format!("spec_bound: {spec}"),
            format!("impl_bound: {imp}"),
            format!("conformance_field: {field}"),
        ],
        Some(ConformanceWindow::SpecOnly { sense, spec, field }) => vec![
            format!("conformance_sense: {sense}"),
            format!("spec_bound: {spec}"),
            format!("conformance_field: {field}"),
        ],
        None => Vec::new(),
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

/// The refinement window an `impl` conformance edge carries (D195):
/// both sides resolved (dischargeable), or the spec side only (the
/// teaching-deferral shape -- the impl owes a bound).
enum ConformanceWindow {
    /// Both the promised and the realized bound resolved, same sense --
    /// the harness conformance model can discharge this (WO-26 D104).
    Both {
        sense: String,
        spec: f64,
        imp: f64,
        field: String,
    },
    /// Only the spec side resolved (a literal promise, or a parametric
    /// promise closed by the impl header's generic pin); the impl body
    /// declares no same-named bound. NEVER discharged -- carried so the
    /// orchestrator's deferral can teach the two honest paths (D195).
    SpecOnly {
        sense: String,
        spec: f64,
        field: String,
    },
}

/// Extract the refinement window for an `impl` conformance edge,
/// matching the upper contract's promised comparator-bound fields (the
/// interface named by `edge.upper`) against the lower realization's
/// (the impl body's) same-named fields (WO-26 D104: field NAME is the
/// identity, per the WO-12 contract IR's existing source-level keying
/// -- names are already unique per interface, L1-checked). Returns
/// `None` for import/extern/select edges, or when the interface
/// declares no comparator-bound field at all.
///
/// The spec side of a promise resolves two ways (D195): a literal bound
/// (`q: <= 20`), or a parametric bound (`power: <= watts`) closed by the
/// matching impl header's generic pin (`impl HeaterDrive<watts=50W>`)
/// -- the pin resolves the SPEC side only, never the impl side (a
/// fabricated `impl_bound = 50W` would discharge `50 <= 50` vacuously,
/// masking real indeterminacy -- the INV-13/26 violation D195 forbids).
/// For each resolved promise with a same-named impl field whose sense
/// agrees (`q: <= 20` refined by `q: <= 14`), the FIRST such match
/// (source order) is returned as [`ConformanceWindow::Both`]; failing
/// any Both match, the first resolved promise with NO same-named impl
/// field is returned as [`ConformanceWindow::SpecOnly`] so the
/// orchestrator can defer teaching what the impl owes.
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
/// AND not a SpecOnly window -- the impl DID declare a bound (teaching
/// it to declare one would be wrong); that pair is simply not a
/// refinement window, and the obligation still defers honestly with the
/// blanket reason rather than the compiler inventing a verdict
/// (INV-13/26).
fn conformance_windows(
    edge: &ConformanceEdge,
    files: &[ParsedFile],
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<ConformanceWindow> {
    if edge.kind != "impl" {
        return None;
    }
    let spec_fields = interface_promised_bounds(&edge.upper, files);
    if spec_fields.is_empty() {
        return None;
    }
    let impl_nodes = matching_impl_nodes(edge, files);
    let impl_fields = impl_bound_fields(&impl_nodes);
    let pins = impl_generic_pins(&impl_nodes);
    let mut both = None;
    let mut spec_only = None;
    let mut sense_disagreement = false;
    let any_impl_bound_field = !impl_fields.is_empty();
    for (name, (spec_sense, promised)) in &spec_fields {
        // Resolve the spec side: literal, or parametric via the impl
        // header's generic pin. An unresolvable spec side (no pin, or a
        // pin whose value is not a leading quantity) contributes nothing
        // -- never a guessed bound.
        let spec_bound = match promised {
            PromisedBound::Literal(value) => Some(*value),
            PromisedBound::Param(ident) => pins.get(ident).and_then(|pin| {
                let resolved = leading_magnitude(&resolve_unit_suffix(pin));
                if resolved.is_none() {
                    tracing::debug!(
                        interface = %edge.upper,
                        field = %name,
                        param = %ident,
                        pin = %pin,
                        "generic pin does not resolve to a quantity; no spec-side bound"
                    );
                }
                resolved
            }),
        };
        let Some(spec_bound) = spec_bound else {
            continue;
        };
        if let Some((impl_sense, impl_bound)) = impl_fields.get(name) {
            if spec_sense == impl_sense {
                if both.is_none() {
                    both = Some(ConformanceWindow::Both {
                        sense: spec_sense.clone(),
                        spec: spec_bound,
                        imp: *impl_bound,
                        field: name.clone(),
                    });
                }
            } else {
                sense_disagreement = true;
            }
        } else {
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
            // error -- the obligation simply has no Both window for
            // THIS name; the resolved spec side is still carried as
            // SpecOnly so the deferral can teach (D195).
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
            if spec_only.is_none() {
                spec_only = Some(ConformanceWindow::SpecOnly {
                    sense: spec_sense.clone(),
                    spec: spec_bound,
                    field: name.clone(),
                });
            }
        }
    }
    if both.is_none() && spec_only.is_none() && sense_disagreement {
        tracing::debug!(
            interface = %edge.upper,
            lower = %edge.lower,
            "promised/impl bounds disagree in sense; no refinement window (honest defer)"
        );
    }
    both.or(spec_only)
}

/// A promise's spec-side bound expression: a literal magnitude, or a
/// reference to a generic parameter the impl header's pin closes (D195,
/// `power: <= watts` against `impl HeaterDrive<watts=50W>`).
enum PromisedBound {
    Literal(f64),
    Param(String),
}

/// The leading numeric magnitude of `text` (`50W` -> 50, `-3.5 mm` ->
/// -3.5); `None` when `text` does not open with a number. The unit
/// suffix is NOT interpreted here -- callers that need SI-base values
/// run [`resolve_unit_suffix`] first.
fn leading_magnitude(text: &str) -> Option<f64> {
    let number: String = text
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+')
        .collect();
    number.parse().ok()
}

/// Parse a leading one-sided comparator bound (`<= 20`, `>= 6`, `< 3`)
/// off a field's value text into `(sense, magnitude)`; `sense` is
/// `"upper"` for `<`/`<=` and `"lower"` for `>`/`>=`. `None` when the
/// text is not a leading comparator over a bare number.
fn bound_from_value_text(text: &str) -> Option<(String, f64)> {
    if let Some((sense, PromisedBound::Literal(magnitude))) = promised_bound_from_value_text(text) {
        return Some((sense, magnitude));
    }
    None
}

/// Parse a leading one-sided comparator bound off a field's value text
/// into `(sense, bound-expression)`: a bare number is
/// [`PromisedBound::Literal`], a bare identifier (`<= watts`) is
/// [`PromisedBound::Param`] awaiting the impl header's generic pin
/// (D195). `None` when the text is neither shape -- a compound
/// expression (`<= watts * 1.1`) is honestly not extracted rather than
/// half-parsed.
fn promised_bound_from_value_text(text: &str) -> Option<(String, PromisedBound)> {
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
    if let Some(magnitude) = leading_magnitude(rest) {
        return Some((sense.to_string(), PromisedBound::Literal(magnitude)));
    }
    let ident = rest.trim();
    let is_ident = !ident.is_empty()
        && ident
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && ident.chars().all(|c| c.is_ascii_alphanumeric() || c == '_');
    if is_ident {
        return Some((sense.to_string(), PromisedBound::Param(ident.to_string())));
    }
    None
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
/// (literal or parametric, D195) of the `interface <name>` declaration,
/// by name, in source order.
fn interface_promised_bounds(
    name: &str,
    files: &[ParsedFile],
) -> Vec<(String, (String, PromisedBound))> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw)
                && decl.name().as_deref() == Some(name)
            {
                let mut fields = Vec::new();
                for descendant in decl.syntax().descendants() {
                    if let Some(field) = Field::cast(descendant) {
                        if let Some(value) = field.value() {
                            if let Some(bound) =
                                promised_bound_from_value_text(&value.text().to_string())
                            {
                                fields.push((field.name(), bound));
                            }
                        }
                    }
                }
                if !fields.is_empty() {
                    return fields;
                }
            }
        }
    }
    Vec::new()
}

/// Every impl node (top-level `impl` [`Decl`] or in-body `ImplStmt`)
/// whose extracted edge matches `edge`, in file/source order. Duplicate
/// edges (two `impl HeaterDrive<...> for self` instantiations in one
/// board) all appear; consumers take the first node that carries what
/// they need, the same first-wins convention D104 set.
fn matching_impl_nodes(edge: &ConformanceEdge, files: &[ParsedFile]) -> Vec<SyntaxNode> {
    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let decl_name = decl.name().unwrap_or_default();
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw)
                && impl_edge(decl.syntax(), &decl_name).as_ref() == Some(edge)
            {
                out.push(decl.syntax().clone());
            }
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt
                    && impl_edge(&node, &decl_name).as_ref() == Some(edge)
                {
                    out.push(node);
                }
            }
        }
    }
    out
}

/// The lower realization's declared bounds: every comparator-bound
/// field of the first matching impl node that declares any, keyed by
/// name (the D104 first-wins convention over [`matching_impl_nodes`]).
fn impl_bound_fields(impl_nodes: &[SyntaxNode]) -> BTreeMap<String, (String, f64)> {
    impl_nodes
        .iter()
        .map(collect_bound_fields)
        .find(|fields| !fields.is_empty())
        .map(Vec::into_iter)
        .map(Iterator::collect)
        .unwrap_or_default()
}

/// The `<name=value, ...>` generic-argument pins of the first matching
/// impl node that carries any (`impl HeaterDrive<watts=50W> for self`
/// -> `{watts: "50W"}`). Bare positional arguments (`<M5, ...>`) carry
/// no name to pin and are skipped. Text-level, single-header-line scan
/// (the module's convention): the pin list is read off the node's first
/// source line, between the first `<` and its matching `>` at bracket
/// depth 0, split at top-level commas.
fn impl_generic_pins(impl_nodes: &[SyntaxNode]) -> BTreeMap<String, String> {
    for node in impl_nodes {
        let text = node.text().to_string();
        let header = text.lines().next().unwrap_or_default();
        let Some(open) = header.find('<') else {
            continue;
        };
        let bytes = header.as_bytes();
        let mut depth = 0i32;
        let mut close = None;
        for (i, &b) in bytes.iter().enumerate().skip(open + 1) {
            match b {
                b'(' | b'[' => depth += 1,
                b')' | b']' => depth -= 1,
                b'>' if depth == 0 => {
                    close = Some(i);
                    break;
                }
                _ => {}
            }
        }
        let Some(close) = close else {
            continue;
        };
        let inside = &header[open + 1..close];
        // Split at top-level commas (a pinned value may itself carry a
        // call with commas, e.g. `pattern=grid(2, 2)`).
        let mut pins = BTreeMap::new();
        let mut depth = 0i32;
        let mut start = 0usize;
        let mut parts = Vec::new();
        for (i, &b) in inside.as_bytes().iter().enumerate() {
            match b {
                b'(' | b'[' => depth += 1,
                b')' | b']' => depth -= 1,
                b',' if depth == 0 => {
                    parts.push(&inside[start..i]);
                    start = i + 1;
                }
                _ => {}
            }
        }
        parts.push(&inside[start..]);
        for part in parts {
            if let Some((name, value)) = part.split_once('=') {
                pins.insert(name.trim().to_string(), value.trim().to_string());
            }
        }
        if !pins.is_empty() {
            tracing::debug!(pins = ?pins, "extracted impl-header generic pins (D195)");
            return pins;
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
    // WO-80 deliverable 2: a trailing `, model=<ident>` rung-5 pin is now
    // a typed `ModelPin` child (WO-80 deliverable 1) instead of raw text
    // -- exclude its span here so it never re-enters the comparison RHS
    // (WO-76's audit finding: it used to be swallowed whole into the
    // predicate/rhs text). Every other trailing attribute (`sf=`,
    // `scatter_factor=`) is still un-typed `OpaqueIsland` text and stays
    // exactly as before.
    let mut full = String::new();
    for elem in field.syntax().children_with_tokens() {
        match elem {
            rowan::NodeOrToken::Node(n) if n.kind() == SyntaxKind::ModelPin => {}
            rowan::NodeOrToken::Node(n) => full.push_str(&n.text().to_string()),
            rowan::NodeOrToken::Token(t) => full.push_str(t.text()),
        }
    }
    match full.split_once(':') {
        Some((_, rest)) => rest.trim().to_string(),
        None => String::new(),
    }
}

/// Split a `<quantity expr> within [lo, hi] ...` predicate into its
/// leading quantity expression (`thermo.temperature(eps.store.cells)`)
/// and the two literal bracket endpoints, ignoring whatever
/// quantifier/window text follows the bracket (`forall op`, `during
/// ...`). The `within` keyword is matched as a whole word (not a
/// substring of a longer identifier) so it can appear anywhere in the
/// predicate, not just at its head. Returns `None` when no such bracketed
/// two-endpoint window is present (a bare `within` used as a tolerance
/// form elsewhere, or any other comparator, is left untouched).
///
/// WO-thermo (batt_window residual): the leading expression is carried
/// out so the split obligations' `lhs` is the full call expression
/// (`thermo.temperature(...)`), NOT the bare claim label -- otherwise
/// translate's call-form recognition (`_match_call_lhs`) can never fire
/// on a windowed claim.
fn within_window_bounds(predicate: &str) -> Option<(String, String, String)> {
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
                let lhs = predicate[..idx].trim().to_string();
                return Some((lhs, lo.trim().to_string(), hi.trim().to_string()));
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
    // A nonzero magnitude that rounded to zero at 10 decimals (sub-1e-10
    // SI values: the WO-78 termination claims size capacitors in pF)
    // falls back to Rust's deterministic scientific rendering -- a claim
    // bound is never silently zeroed by formatting.
    if value != 0.0 && (s == "0" || s == "-0") {
        return format!("{value:e}");
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

    /// The full [`ObligationSet`] (diagnostics included), with an
    /// optional realized-geometry input for the decl named `subject`
    /// (WO-69: proves the `geometry.realized` `PayloadRef` only appears
    /// when the build actually supplied one).
    fn plan_obligation_set(src: &str, realized_geometry_for: Option<&str>) -> super::ObligationSet {
        let files = parsed(src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let mut realized_inputs = crate::realized_input::RealizedInputs::new();
        if let Some(subject) = realized_geometry_for {
            realized_inputs.insert(
                "blake3:plantarget".to_string(),
                crate::realized_input::RealizedInput {
                    kind: "geometry.realized".to_string(),
                    subject: subject.to_string(),
                    bytes: vec![1, 2, 3],
                },
            );
        }
        build_obligations(&files, &snaps, &checks, &graph, &realized_inputs)
    }

    /// A calcite `.calx` source's obligations (WO-68 regression
    /// coverage): calcite's top-level `require` group rides the same
    /// `File::fluid_requires`/`push_calcite_frame_obligations` path as
    /// fluorite, so this is the live footbridge-repro shape end to end.
    fn calx_obligations(src: &str) -> Vec<super::Obligation> {
        let path = Utf8PathBuf::from("t.calx");
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
    fn fluid_claim_suffix_givens_thread_into_given_loads() {
        // WO-94 escalation 1: a `given <ident> = <expr>` suffix on a fluid
        // claim threads quantity-valued bindings into `given.loads` (the
        // translate call-kwargs fallback channel) and is stripped from the
        // comparison text, while a regime-selector given (`v3 = brew`)
        // stays dropped so the generic scalar path never hard-defers.
        let src = "medium Water: liquid\n\
            \x20   props: registry(potable_water_nist)\n\
            flownet Loop(medium=Water):\n\
            \x20   reference: ambient(101kPa, 293K)\n\
            \x20   nodes: a, b\n\
            \x20   edges:\n\
            \x20       supply: Pipe(from=line.run) (a -> b)\n\
            require Margin:\n\
            \x20   dp: fluids.dp(a -> b) <= 40kPa given T_group = 90degC, v3 = brew\n";
        let obls = fluid_obligations(src);
        assert_eq!(obls.len(), 1);
        let obl = &obls[0];
        assert_eq!(
            obl.given.loads,
            vec!["T_group: 90degC".to_string()],
            "quantity given threaded; regime selector `v3 = brew` dropped"
        );
        let super::ClaimForm::Comparison { lhs, rhs, .. } = &obl.claim.form else {
            panic!("comparison form");
        };
        assert_eq!(lhs, "fluids.dp(a -> b)", "given suffix stripped from LHS");
        assert_eq!(rhs, "40000", "given suffix never pollutes the RHS bound");
    }

    #[test]
    fn fluid_comparator_after_call_lowers_to_a_real_comparator_op() {
        // WO-92 deliverable 2: a fluid predicate whose comparator sits
        // after the `fluids.*(...)` call (`fluids.dp(a -> b) <= 40kPa`)
        // must lower with a REAL comparator op + the call as LHS, not the
        // opaque `op="require"` blob -- otherwise the translate-side
        // head-only `_split_comparator` cannot see the comparator and
        // defers `unsupported_op`. The `->` inside the call parens is at
        // bracket depth > 0, so it is not mistaken for a comparator.
        let obls = fluid_obligations(FLUID_SRC);
        let super::ClaimForm::Comparison { lhs, op, rhs } = &obls[0].claim.form else {
            panic!("fluid claim lowers to a Comparison form");
        };
        assert_eq!(op, "<=", "structural comparator recovered, not `require`");
        assert_eq!(lhs, "fluids.dp(a -> b)", "LHS is the whole call expression");
        assert_eq!(
            rhs, "40000",
            "RHS is the unit-resolved bound (40kPa -> 40000 Pa)"
        );
        // Claim identity (the model-routing key) stays the field name.
        assert_eq!(obls[0].claim.name.as_deref(), Some("dp"));
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
    fn generic_pin_resolves_the_spec_side_only() {
        // D195 (WO-92): `impl Drive<watts=50W>` against the parametric
        // promise `power: <= watts` resolves the SPEC side (sense +
        // spec_bound + field name in given.loads) and NEVER fabricates
        // an impl_bound -- the impl body asserts nothing (`= todo!`),
        // and a fabricated 50 <= 50 would discharge vacuously.
        let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=50W> for self as d = todo!\n";
        let set = obligation_set(src);
        let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
        assert!(
            conforms
                .given
                .loads
                .iter()
                .any(|l| l == "conformance_sense: upper"),
            "sense carried: {:?}",
            conforms.given.loads
        );
        assert!(
            conforms.given.loads.iter().any(|l| l == "spec_bound: 50"),
            "pin-resolved spec bound (50W -> 50) carried: {:?}",
            conforms.given.loads
        );
        assert!(
            conforms
                .given
                .loads
                .iter()
                .any(|l| l == "conformance_field: power"),
            "field name carried for the teaching deferral: {:?}",
            conforms.given.loads
        );
        assert!(
            !conforms
                .given
                .loads
                .iter()
                .any(|l| l.starts_with("impl_bound:")),
            "NEVER a fabricated impl bound: {:?}",
            conforms.given.loads
        );
    }

    #[test]
    fn unresolvable_generic_pin_emits_no_spec_bound() {
        // D195: a pin whose value is not a leading quantity (`watts=` a
        // bare identifier) cannot resolve the parametric promise -- no
        // window lines at all, the existing blanket deferral stands.
        let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=unknown_budget> for self as d = todo!\n";
        let set = obligation_set(src);
        let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
        assert!(
            conforms.given.loads.is_empty(),
            "unresolvable pin -> no window lines, never a guess: {:?}",
            conforms.given.loads
        );
    }

    #[test]
    fn generic_pin_spec_side_with_impl_body_bound_is_a_full_window() {
        // D195 rule 2a: the impl side arrives via an explicit re-declared
        // bound in the impl BODY; combined with the pin-resolved spec
        // side this is a dischargeable Both window (spec 50, impl 45).
        let src = "interface Drive<watts: power>:\n\
            \x20   promises:\n\
            \x20       power: <= watts\n\
            part p:\n\
            \x20   impl Drive<watts=50W> for self as d:\n\
            \x20       power: <= 45\n";
        let set = obligation_set(src);
        let conforms = set
            .obligations
            .iter()
            .find(|o| {
                matches!(&o.claim.form, super::ClaimForm::Comparison { op, .. } if op == "conforms")
            })
            .expect("a conformance obligation is emitted");
        assert!(
            conforms.given.loads.iter().any(|l| l == "spec_bound: 50"),
            "pin-resolved spec side: {:?}",
            conforms.given.loads
        );
        assert!(
            conforms.given.loads.iter().any(|l| l == "impl_bound: 45"),
            "impl-BODY-declared bound (never the pin): {:?}",
            conforms.given.loads
        );
    }

    #[test]
    fn literal_promise_with_no_impl_bound_carries_the_spec_only_window() {
        // D195: a LITERAL promise the impl body never refines (the
        // FittingPort.leak shape) now carries sense + spec_bound + field
        // (no impl_bound) so translate can defer teaching what the impl
        // owes -- distinct from the nothing-scalar-to-compare shape.
        let src = "interface Seat:\n    y: <= 20\npart p:\n    impl Seat for self = todo!\n";
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
            "{:?}",
            conforms.given.loads
        );
        assert!(
            conforms
                .given
                .loads
                .iter()
                .any(|l| l == "conformance_field: y"),
            "{:?}",
            conforms.given.loads
        );
        assert!(
            !conforms
                .given
                .loads
                .iter()
                .any(|l| l.starts_with("impl_bound:")),
            "{:?}",
            conforms.given.loads
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
        let named: Vec<(String, String, String, String)> = obl
            .iter()
            .filter_map(|o| match &o.claim.form {
                super::ClaimForm::Comparison { lhs, op, rhs } => Some((
                    o.claim.name.clone().unwrap_or_default(),
                    lhs.clone(),
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
        assert_eq!(lo.2, ">=");
        assert_eq!(lo.3, "273.15", "0degC resolved to Kelvin");
        let hi = named
            .iter()
            .find(|(name, ..)| name == "batt_window.hi")
            .expect("hi half present");
        assert_eq!(hi.2, "<=");
        assert_eq!(hi.3, "318.15", "45degC resolved to Kelvin");
        // batt_window residual: each half's LHS is the full call
        // expression, NOT the bare `batt_window` label, so translate's
        // `_match_call_lhs` can route it to `thermo.junction_temperature`.
        assert_eq!(lo.1, "thermo.temperature(eps.store.cells)");
        assert_eq!(hi.1, "thermo.temperature(eps.store.cells)");
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

    /// WO-80 deliverable 2 (regolith/12 sec. 2 rung 5): a claim's
    /// trailing `, model=<ident>` pin lowers into `Claim::model_pin`
    /// AND never re-enters the comparison rhs -- WO-76's audit finding
    /// (the pin text used to be swallowed whole into the rhs) is fixed.
    #[test]
    fn model_pin_lowers_into_the_claim_and_never_into_rhs() {
        let src = "part gear:\n    \
                   require Mesh:\n        \
                   contact: mech.contact_stress(mesh) < 1400 MPa, sf=1.2, model=fea_contact\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        assert_eq!(obl[0].claim.model_pin.as_deref(), Some("fea_contact"));
        match &obl[0].claim.form {
            super::ClaimForm::Comparison { lhs, op, rhs } => {
                assert_eq!(lhs, "mech.contact_stress(mesh)");
                assert_eq!(op, "<");
                assert!(
                    !rhs.contains("model"),
                    "model= must not leak into rhs: {rhs:?}"
                );
                assert!(
                    rhs.contains("sf=1.2"),
                    "sf= is unaffected (still opaque, WO-80 scope is model= only): {rhs:?}"
                );
            }
            other => panic!("expected general Comparison, got {other:?}"),
        }
    }

    /// A claim line with no `model=` attribute lowers with
    /// `model_pin: None` (the un-pinned baseline).
    #[test]
    fn no_model_attr_lowers_with_no_model_pin() {
        let src = "part gear:\n    \
                   require Life:\n        \
                   bearings: mech.l10_life([b]) >= design_life\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1);
        assert_eq!(obl[0].claim.model_pin, None);
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
    fn cost_claim_threads_subject_profile_and_bom_into_given() {
        // WO-54 deliverable 1: `mfg.cost(<subject>, profile=<name>)`
        // threads `cost_subject`/`cost_profile` plus the decl's
        // `parts:` BOM into `given.loads` (the conformance-windows
        // precedent), so the orchestrator reads structured fields.
        let src = "part p:\n    parts:\n        panel: vendor(sqd_qo142m200)\n        \
                   brk: vendor(sqd_qo120)\n    require Cost:\n        \
                   bom: mfg.cost(p, profile=construction) <= 6000\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1, "{obl:?}");
        let loads = &obl[0].given.loads;
        assert!(loads.iter().any(|l| l == "cost_subject: p"), "{loads:?}");
        assert!(
            loads.iter().any(|l| l == "cost_profile: construction"),
            "{loads:?}"
        );
        assert!(
            loads
                .iter()
                .any(|l| l == "cost_bom.panel: vendor(sqd_qo142m200)"),
            "{loads:?}"
        );
        assert!(
            loads.iter().any(|l| l == "cost_bom.brk: vendor(sqd_qo120)"),
            "{loads:?}"
        );
    }

    #[test]
    fn cost_claim_without_profile_threads_subject_only() {
        // The `profile=` argument is optional (the manifest default
        // profile applies, toolchain/27 sec. 1.2): no `cost_profile`
        // line is invented for its absence.
        let src = "part p:\n    require Cost:\n        bom: mfg.cost(p) <= 100\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1, "{obl:?}");
        let loads = &obl[0].given.loads;
        assert!(loads.iter().any(|l| l == "cost_subject: p"), "{loads:?}");
        assert!(
            !loads.iter().any(|l| l.starts_with("cost_profile:")),
            "{loads:?}"
        );
    }

    #[test]
    fn malformed_cost_claim_arguments_are_a_compile_diagnostic() {
        // E0438 (WO-54): an unknown keyword argument is rejected at
        // compile time naming the offender, never silently deferred.
        let src = "part p:\n    require Cost:\n        \
                   bom: mfg.cost(p, quantity=5) <= 100\n";
        let set = obligation_set(src);
        assert!(set.obligations.is_empty(), "{:?}", set.obligations);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::COST_CLAIM_MALFORMED),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn top_level_cost_claim_lowers_with_threaded_given() {
        // WO-54: a cost claim in a TOP-LEVEL require group (the
        // calcite program.calx shape) lowers through the dedicated
        // pass -- the frame/fluid passes skip non-frame/non-fluids
        // predicates, so without it the claim would silently vanish.
        let src = "require Budgeting:\n    \
                   construction: mfg.cost(all, profile=construction) <= 850000\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1, "{obl:?}");
        let loads = &obl[0].given.loads;
        assert!(loads.iter().any(|l| l == "cost_subject: all"), "{loads:?}");
        assert!(
            loads.iter().any(|l| l == "cost_profile: construction"),
            "{loads:?}"
        );
    }

    #[test]
    fn top_level_malformed_cost_claim_is_a_compile_diagnostic() {
        let src = "require Budgeting:\n    bad: mfg.cost(all, extra=1) <= 10\n";
        let set = obligation_set(src);
        assert!(set.obligations.is_empty(), "{:?}", set.obligations);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::COST_CLAIM_MALFORMED),
            "{:?}",
            set.diagnostics
        );
    }

    #[test]
    fn forall_sweep_block_nested_named_claim_emits_an_obligation() {
        // WO-68: the emission bug's minimal repro -- a `forall <var> in
        // <domain>:` BLOCK (header on its own line, no inline
        // predicate) whose nested body is a NAMED claim
        // (`strength: ...`). Before the fix, this named claim was
        // swallowed whole into an `OpaqueIsland` by the parser and
        // never reached this pass at all (zero obligations from it,
        // silently). `demo` mirrors the decl-level (hematite/cuprite)
        // `RequireClaim` shape `push_require_obligations` lowers.
        let src = "part p:\n    require Strength:\n        \
                   forall combo in std.pack.family:\n            \
                   strength: p.stress(under=combo) <= 100MPa\n        \
                   plain: p.mass <= 5kg\n";
        let obl = obligations(src);
        let strength = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("strength"))
            .unwrap_or_else(|| panic!("no `strength` obligation among {obl:?}"));
        let sweep = strength.sweep.as_ref().expect("sweep domain present");
        assert_eq!(sweep.axis, "combo");
        assert_eq!(sweep.domain, "std.pack.family");
        // The sibling DIRECT claim (not nested in any sweep) still
        // lowers exactly as before -- the fix only ADDS reachability
        // for the nested form, it does not change direct-claim lowering.
        assert!(
            obl.iter().any(|o| o.claim.name.as_deref() == Some("plain")),
            "{obl:?}"
        );
    }

    #[test]
    fn multiline_bracketed_claim_captures_the_whole_predicate() {
        // WO-90 deliverable 1: a claim whose call expression wraps onto a
        // second physical line INSIDE the open paren must capture whole
        // -- before the layout fix the arg list truncated at the interior
        // newline and the trailing comparator (`< 25mm`) was lost, so the
        // claim mis-lowered to the opaque `require` form with a truncated
        // RHS. Now the comparator is visible and the claim lowers to a
        // real `<` comparison.
        let src = "part p:\n    require Structural:\n        \
                   tip: mech.deflection(cut.blank,\n                      \
                   under=envelope(Mount)) < 25mm\n";
        let obl = obligations(src);
        let tip = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("tip"))
            .unwrap_or_else(|| panic!("no `tip` obligation among {obl:?}"));
        match &tip.claim.form {
            super::ClaimForm::Comparison { lhs, op, rhs } => {
                assert_eq!(op, "<", "the wrapped comparator must survive: {tip:?}");
                assert!(
                    lhs.contains("under=envelope(Mount)"),
                    "the continuation line must be captured in the LHS: {lhs:?}"
                );
                assert_eq!(rhs, "0.025", "25mm resolved to metres on the RHS: {rhs:?}");
            }
            other => panic!("expected a `<` comparison, got {other:?}"),
        }
    }

    #[test]
    fn bare_plural_forall_domain_is_e0450() {
        // WO-90 deliverable 2: a `forall <var> in boards:` sweep whose
        // domain is a BARE PLURAL naming no declared domain covers zero
        // points -- a vacuous pass. It must trip the constructive E0450
        // diagnostic, once for the block.
        let src = "part p:\n    require Boards:\n        \
                   forall b in boards:\n            \
                   ok: b.stress <= 100MPa\n";
        let set = obligation_set(src);
        let hits: Vec<_> = set
            .diagnostics
            .iter()
            .filter(|d| d.code == regolith_diag::codes::FORALL_DOMAIN_UNDECLARED)
            .collect();
        assert_eq!(
            hits.len(),
            1,
            "exactly one E0450 per block: {:?}",
            set.diagnostics
        );
        assert!(
            hits[0].message.contains("boards"),
            "message names the undeclared domain: {}",
            hits[0].message
        );
    }

    #[test]
    fn declared_forall_domains_are_not_e0450() {
        // WO-90 deliverable 2 / acceptance: every DECLARED domain form
        // stays legal -- a discrete set, an interval, a dotted pack ref,
        // a `registry(...)` family, and a `.members.all` collection must
        // NOT trip E0450 (WO-68's forms stay green).
        for domain in [
            "{trail, race}",
            "[0rpm, 6000rpm]",
            "std.pack.family",
            "registry(std.civil.aisc.strength)",
            "Bridge.members.all",
        ] {
            assert!(
                !super::is_undeclared_bare_plural_domain(domain),
                "declared domain wrongly flagged: {domain}"
            );
        }
        // And the trap forms ARE flagged.
        assert!(super::is_undeclared_bare_plural_domain("boards"));
        assert!(super::is_undeclared_bare_plural_domain("assemblies"));
    }

    #[test]
    fn explicitly_empty_declared_domain_is_not_e0450() {
        // WO-90 deliverable 2: an explicitly EMPTY declared domain (an
        // empty discrete set) is a legal, honest zero-obligation sweep,
        // NOT the bare-plural trap.
        assert!(!super::is_undeclared_bare_plural_domain("{}"));
        assert!(!super::is_undeclared_bare_plural_domain("[]"));
        // A missing/blank domain (malformed header, parser-degraded) is
        // also not this diagnostic's concern.
        assert!(!super::is_undeclared_bare_plural_domain(""));
    }

    #[test]
    fn forall_sweep_block_over_calcite_frame_claims_flips_the_live_repro() {
        // WO-68 acceptance: the exact live repro named in the WO/D181
        // (footbridge `compiler.check` emitting 4 obligations, zero
        // `strength`) -- reusing `frame_lower`'s own `FOOTBRIDGE_SRC`
        // shape inline (this module has no access to that private
        // const) so a regression here is caught at the obligation
        // layer, not just the frame-payload layer.
        let src = "import std.civil (Pinned, Bearing)\n\
site Greenway:\n\
\x20   boundary:\n\
\x20       wind_speed: [0m/s, 43m/s] by catalog(asce7_fig26)\n\
grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: free\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   forall combo in std.civil.aisc.strength:\n\
\x20       strength: civil.utilization(Bridge.members.all, under=combo) <= 1.0\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";
        let obl = calx_obligations(src);
        // WO-85/D194 ruling 3: the `.members.all` group subject expands
        // per member at lowering -- the one-member footbridge repro's
        // `strength` claim now lands as `strength[G1]` with the member
        // pinned in the predicate subject.
        assert!(
            obl.iter()
                .any(|o| o.claim.name.as_deref() == Some("strength[G1]")),
            "strength[G1] obligation missing: {obl:?}"
        );
        let strength = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("strength[G1]"))
            .unwrap();
        let sweep = strength.sweep.as_ref().expect("sweep domain present");
        assert_eq!(sweep.axis, "combo");
        assert_eq!(sweep.domain, "std.civil.aisc.strength");
        match &strength.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert!(rhs.contains("Bridge.members.G1"), "{rhs}");
                assert!(!rhs.contains(".members.all"), "{rhs}");
            }
            other => panic!("unexpected claim form {other:?}"),
        }
        assert!(
            obl.iter()
                .any(|o| o.claim.name.as_deref() == Some("bearing")),
            "{obl:?}"
        );
    }

    #[test]
    fn members_all_group_expands_one_obligation_per_member() {
        // WO-85/D194 ruling 3: a mixed-role group subject (beam + slab)
        // yields one obligation per member, each pinned by name and
        // predicate, sharing the sweep and the frame payload ref --
        // so one indeterminate member can no longer defer the group
        // wholesale downstream.
        let src = "grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
member Deck: slab\n\
\x20   section: registry(comp_deck_140mm)\n\
\x20   material: registry(concrete_c30)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1, Deck\n\
\x20   transfers:\n\
\x20       d_g1: Bearing(tributary=10.8m2) (Deck -> G1)\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   pedestrian: 4.1kPa on [Deck] by catalog(aashto_ped)\n\
require Structure:\n\
\x20   forall combo in std.civil.aisc.strength:\n\
\x20       strength: civil.utilization(Bridge.members.all, under=combo) <= 1.0\n";
        let obl = calx_obligations(src);
        let strength: Vec<_> = obl
            .iter()
            .filter(|o| {
                o.claim
                    .name
                    .as_deref()
                    .is_some_and(|n| n.starts_with("strength["))
            })
            .collect();
        assert_eq!(strength.len(), 2, "{obl:?}");
        let names: Vec<_> = strength
            .iter()
            .filter_map(|o| o.claim.name.as_deref())
            .collect();
        assert!(names.contains(&"strength[G1]"), "{names:?}");
        assert!(names.contains(&"strength[Deck]"), "{names:?}");
        // Every instance keeps the sweep and the frame payload ref, and
        // the two instances hash distinctly (INV-1).
        for o in &strength {
            assert!(o.sweep.is_some());
            assert!(o.payloads.iter().any(|p| p.kind == "frame"));
        }
        assert_ne!(strength[0].content_hash(), strength[1].content_hash());
    }

    #[test]
    fn embedment_claim_lowers_with_site_bound_resolved() {
        // WO-85/D194 ruling 4: `civil.embedment(P1) >= site.frost_depth`
        // lowers as a frame obligation with the site datum's declared
        // quantity substituted into the bound (leaf-name match against
        // the project's `site` decls; `frost_depth` nests under
        // `boundary:` in the corpus spelling).
        let src = "import std.civil (EmbeddedPost)\n\
site Township:\n\
\x20   boundary:\n\
\x20       frost_depth: 1.2m by catalog(county_gis)\n\
grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
        let obl = calx_obligations(src);
        let frost = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("frost"))
            .unwrap_or_else(|| panic!("no frost obligation among {obl:?}"));
        assert!(frost.payloads.iter().any(|p| p.kind == "frame"));
        match &frost.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert!(
                    rhs.contains(">= 1.2") && !rhs.contains("site.frost_depth"),
                    "{rhs}"
                );
            }
            other => panic!("unexpected claim form {other:?}"),
        }
    }

    #[test]
    fn embedment_site_bound_prefers_the_claims_own_file() {
        // WO-85: a multi-design directory (examples/tracks/calcite)
        // declares one site per design file with COLLIDING leaf names
        // (three different `frost_depth`s) -- the claim's own file's
        // datum wins; the project-wide index is only the fallback for
        // the site.calx/frame.calx split.
        let barn = "site Township:\n\
\x20   boundary:\n\
\x20       frost_depth: 1.2m by catalog(county_gis)\n\
grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
        let other = "site Elsewhere:\n\
\x20   boundary:\n\
\x20       frost_depth: 0.9m by catalog(county_gis)\n";
        let files: Vec<ParsedFile> = [("barn.calx", barn), ("other.calx", other)]
            .into_iter()
            .map(|(path, src)| {
                let path = Utf8PathBuf::from(path);
                ParsedFile {
                    path: path.clone(),
                    parse: regolith_syntax::parse(src, &path),
                }
            })
            .collect();
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obl = build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let frost = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("frost"))
            .unwrap_or_else(|| panic!("no frost obligation among {obl:?}"));
        match &frost.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert!(rhs.contains(">= 1.2"), "own file's 1.2m must win: {rhs}");
            }
            other => panic!("unexpected claim form {other:?}"),
        }
    }

    #[test]
    fn embedment_unknown_site_datum_stays_symbolic() {
        // An unresolvable site path is left verbatim (the claim defers
        // downstream with an honest unresolved bound), never guessed.
        let src = "grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
        let obl = calx_obligations(src);
        let frost = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("frost"))
            .unwrap();
        match &frost.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert!(rhs.contains("site.frost_depth"), "{rhs}");
            }
            other => panic!("unexpected claim form {other:?}"),
        }
    }

    #[test]
    fn bearing_claim_lowers_with_interval_site_bound_resolved() {
        // WO-96 bearing close-out: `civil.bearing_pressure(F) <=
        // site.soil.bearing` literalizes the interval capacity datum to
        // its CONSERVATIVE (lower) endpoint for a `<=` allowable, and the
        // BasePlate `bearing=` area threads onto the transfer's tributary
        // field. A `ShopFloor.`-prefixed (site-name) path resolves the
        // same way as a `site.`-prefixed one.
        let src = "import std.civil (Moment, BasePlate)\n\
site ShopFloor:\n\
\x20   soil:\n\
\x20       bearing: [100kPa, 150kPa] by test(slab_typ)\n\
grid legs: L spacing 0.7m\n\
level base: 0m\n\
level head: 1.4m\n\
member Col_L: column\n\
\x20   section: registry(hss127x127x8)\n\
\x20   material: registry(astm_a500c)\n\
\x20   from (L, base) to (L, head)\n\
structure Frame:\n\
\x20   support: F_L: footing\n\
\x20   members: Col_L\n\
\x20   transfers:\n\
\x20       col_l_f: BasePlate(anchors=registry(a), bearing=1.0m2) (Col_L -> F_L)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing_l: civil.bearing_pressure(F_L) <= ShopFloor.soil.bearing\n";
        let obl = calx_obligations(src);
        let bearing = obl
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("bearing_l"))
            .unwrap_or_else(|| panic!("no bearing_l obligation among {obl:?}"));
        assert!(bearing.payloads.iter().any(|p| p.kind == "frame"));
        match &bearing.claim.form {
            super::ClaimForm::Comparison { rhs, .. } => {
                assert!(
                    rhs.contains("100000") && !rhs.contains("soil.bearing"),
                    "conservative lo endpoint (100kPa) substituted, not the \
                     symbolic bound: {rhs}"
                );
                assert!(
                    !rhs.contains("150000"),
                    "the hi endpoint (150kPa) is NOT used for a <= allowable: {rhs}"
                );
            }
            other => panic!("unexpected claim form {other:?}"),
        }
    }

    #[test]
    fn cost_claim_forall_profile_prefix_carries_a_discrete_sweep() {
        // D95/D105a: `forall profile in {a, b}:` is ONE obligation
        // whose `sweep` carries the discrete profile domain -- the
        // per-profile axis points are the orchestrator/estimator's
        // to expand (toolchain/27 sec. 1.1).
        let src = "part p:\n    require Cost:\n        \
                   sweep: forall profile in {prototype, construction}: \
                   mfg.cost(p) <= 100\n";
        let obl = obligations(src);
        assert_eq!(obl.len(), 1, "{obl:?}");
        let sweep = obl[0].sweep.as_ref().expect("sweep domain present");
        assert_eq!(sweep.axis, "profile");
        assert_eq!(sweep.domain, "{prototype, construction}");
        assert!(
            obl[0].given.loads.iter().any(|l| l == "cost_subject: p"),
            "{:?}",
            obl[0].given.loads
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

    // -- WO-69: plan: linkage lowering -----------------------------------

    const PLAN_SRC: &str = "part p:\n    plan: extern(\"op10.nc\", gcode_fanuc) machine=std.machines.haas_vf2, tooling=std.tooling.endmill_6mm, resolution=0.05mm\n";

    #[test]
    fn plan_field_emits_exactly_five_cam_obligations_keyed_distinctly() {
        let set = plan_obligation_set(PLAN_SRC, None);
        assert!(set.diagnostics.is_empty(), "diags: {:?}", set.diagnostics);
        let kinds: Vec<&str> = set
            .obligations
            .iter()
            .map(|o| o.claim.name.as_deref().unwrap_or(""))
            .collect();
        assert_eq!(
            kinds,
            vec![
                "cam.parse",
                "cam.envelope",
                "cam.collision_coarse",
                "cam.removal",
                "cam.coverage",
            ],
            "exactly five, keyed by their cam.* claim kind, in source order"
        );
        let hashes: std::collections::BTreeSet<String> = set
            .obligations
            .iter()
            .map(super::Obligation::content_hash)
            .collect();
        assert_eq!(hashes.len(), 5, "INV-1: all five key distinctly");
    }

    #[test]
    fn plan_obligations_carry_plan_ref_dialect_and_kwargs_in_given() {
        let set = plan_obligation_set(PLAN_SRC, None);
        let parse = &set.obligations[0];
        assert!(parse.given.loads.contains(&"plan_ref: op10.nc".to_string()));
        assert!(parse
            .given
            .loads
            .contains(&"plan_dialect: gcode_fanuc".to_string()));
        assert!(parse
            .given
            .loads
            .contains(&"cam_machine_ref: std.machines.haas_vf2".to_string()));
        assert!(parse
            .given
            .loads
            .contains(&"cam_tooling_ref: std.tooling.endmill_6mm".to_string()));
        assert!(parse
            .given
            .loads
            .contains(&"resolution_mm: 0.05mm".to_string()));
        assert!(parse
            .payloads
            .iter()
            .any(|p| p.kind == "plan" && p.origin == "op10.nc"));
    }

    #[test]
    fn plan_obligations_gain_a_geometry_realized_payload_when_target_supplied() {
        let with_target = plan_obligation_set(PLAN_SRC, Some("p"));
        for o in &with_target.obligations {
            assert!(
                o.payloads.iter().any(|p| p.kind == "geometry.realized"
                    && p.origin == "p"
                    && p.digest == "blake3:plantarget"),
                "obligation {:?} missing its target geometry ref",
                o.claim.name
            );
        }
        let without_target = plan_obligation_set(PLAN_SRC, None);
        for o in &without_target.obligations {
            assert!(
                !o.payloads.iter().any(|p| p.kind == "geometry.realized"),
                "no realized input supplied for this build -> no fabricated digest"
            );
        }
    }

    #[test]
    fn removing_the_plan_field_removes_all_five_obligations() {
        let with_plan = obligations(PLAN_SRC);
        assert_eq!(with_plan.len(), 5);
        let without_plan = obligations("part p:\n    material: AISI_304\n");
        assert!(
            without_plan.is_empty(),
            "a plain part with no plan: field emits no cam.* obligations: {without_plan:?}"
        );
    }

    #[test]
    fn plan_clause_missing_ref_is_e0449_and_emits_no_obligations() {
        let src = "part p:\n    plan: extern(gcode_fanuc)\n";
        let set = plan_obligation_set(src, None);
        assert!(set.obligations.is_empty());
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::PLAN_CLAUSE_MALFORMED),
            "diags: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn plan_clause_unknown_dialect_is_e0449_and_emits_no_obligations() {
        let src = "part p:\n    plan: extern(\"op10.nc\", not_a_dialect)\n";
        let set = plan_obligation_set(src, None);
        assert!(set.obligations.is_empty());
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::PLAN_CLAUSE_MALFORMED),
            "diags: {:?}",
            set.diagnostics
        );
    }

    // ---- WO-78: `elec.impedance(...) within [lo, hi]` lowering ----

    #[test]
    fn impedance_window_splits_preserving_call_text() {
        let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(clk, role=microstrip, \
                   stackup=jlc04161h_7628, layer=outer, w=0.28mm) \
                   within [45ohm, 55ohm]\n";
        let obs = obligations(src);
        assert_eq!(obs.len(), 2, "obligations: {obs:?}");
        let (lo, hi) = (&obs[0], &obs[1]);
        assert_eq!(lo.claim.name.as_deref(), Some("clk_z0.lo"));
        assert_eq!(hi.claim.name.as_deref(), Some("clk_z0.hi"));
        for (ob, op, rhs) in [(lo, ">=", "45"), (hi, "<=", "55")] {
            let super::ClaimForm::Comparison {
                lhs,
                op: got_op,
                rhs: got_rhs,
            } = &ob.claim.form
            else {
                panic!("expected Comparison, got {:?}", ob.claim.form);
            };
            assert!(
                lhs.starts_with("elec.impedance(clk"),
                "lhs must preserve the call: {lhs}"
            );
            // The kwarg's unit suffix resolves like every other bound
            // (`0.28mm` -> `0.00028`).
            assert!(lhs.contains("w=0.00028"), "lhs: {lhs}");
            assert_eq!(got_op, op);
            assert_eq!(got_rhs, rhs);
        }
    }

    #[test]
    fn impedance_window_with_no_net_is_e0452_and_emits_no_obligations() {
        let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(role=microstrip) within [45ohm, 55ohm]\n";
        let set = plan_obligation_set(src, None);
        assert!(set.obligations.is_empty(), "{:?}", set.obligations);
        assert!(
            set.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::SI_IMPEDANCE_MALFORMED),
            "diags: {:?}",
            set.diagnostics
        );
    }

    #[test]
    fn impedance_with_plain_comparator_falls_through_to_general_comparison() {
        let src = "board si:\n    require SI:\n        clk_z0: \
                   elec.impedance(clk, role=microstrip, w=0.28mm) <= 60ohm\n";
        let obs = obligations(src);
        assert_eq!(obs.len(), 1, "obligations: {obs:?}");
        let super::ClaimForm::Comparison { lhs, op, .. } = &obs[0].claim.form else {
            panic!("expected Comparison, got {:?}", obs[0].claim.form);
        };
        assert!(lhs.starts_with("elec.impedance(clk"), "lhs: {lhs}");
        assert_eq!(op, "<=");
    }
}
