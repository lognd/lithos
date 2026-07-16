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
//!
//! This pass is split by obligation family across the submodules below
//! (mechanical DX split only -- no behavior changes): `plan` (cam.*),
//! `fluid` (fluids.*), `frame` (calcite structural), `require`
//! (require-group + window/forall plumbing), `comparison` (temporal/
//! reduction/settles/stays_within/general-comparison predicate
//! parsers), `cost` (mfg.cost), `compute` (compute-field producers +
//! cycle check), `conformance` (INV-13 conformance + EOPEN-15
//! realization obligations), `rule` (WO-28 rule obligations), and
//! `common` (helpers shared across two or more families).

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

use regolith_util::canon::content_address;

use crate::checks::CheckReport;
use crate::contracts::{
    impl_edge, plan_clause, ConformanceEdge, ContractGraph, PlanClause, RealizationEdge,
    KNOWN_PLAN_DIALECTS,
};
use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::flownet_lower::elaborate_flownets;
use crate::frame_lower::elaborate_frames;
use crate::output::ParsedFile;

mod common;
mod comparison;
mod compute;
mod conformance;
mod cost;
mod fluid;
mod frame;
mod plan;
mod require;
mod rule;
#[cfg(test)]
mod tests;

use common::{
    field_span, full_predicate_text, match_call, resolve_unit_suffix, split_top_level_args,
    transient_compliance_edges,
};
use comparison::{split_general_comparison, GeneralComparison};
use compute::{check_compute_field_cycles, collect_compute_producers};
use conformance::{conformance_obligation, realization_obligation};
use cost::{parse_cost_claim_args, push_cost_claim_obligation};
use fluid::push_fluid_obligations;
use frame::push_calcite_frame_obligations;
use plan::{hdl_build_obligation, push_plan_obligations, push_top_level_cost_obligations};
use require::{
    parse_forall_prefix, push_general_comparison_obligation, push_group_obligations,
    sweep_domain_from_ast, ClaimLoweringCtx,
};
use rule::{given_for_decl, push_rule_obligations};

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

/// Push one [`SnapshotRecord`] per committed entity scope (AD-18 hash),
/// in the entity DB's iteration order.
fn push_snapshot_records(snapshots: &EntitySnapshots, out: &mut Vec<SnapshotRecord>) {
    for (scope, db) in &snapshots.scopes {
        out.push(SnapshotRecord {
            scope: scope.clone(),
            hash: db.snapshot_hash(),
        });
    }
}

/// The payload kind + content-address domain tag of an elec behavioral
/// body's converter graph (WO-88, F112). One home for the string; the
/// Python side mirrors it verbatim (`orchestrator/orchestrate.py`'s
/// `_put_converter_graph_payloads`, the buck model's `GRAPH_KIND`), the
/// same hand-kept-in-sync convention the flownet/frame kinds already use.
const CONVERTER_GRAPH_KIND: &str = "converter_graph";

/// Attach a `converter_graph` [`PayloadRef`] to every obligation in
/// `obligations` when `decl` has a non-empty elec behavioral converter
/// graph (WO-88 deliverable 2/3). The digest is the AD-18 content
/// address of the graph (the orchestrator stores the graph bytes under
/// this exact digest, `_put_converter_graph_payloads`); a decl with no
/// `spec:` body or an empty graph attaches nothing. A digest-encoding
/// failure is logged and skipped -- the obligation stays honestly
/// graph-less rather than crashing the build (parity with the
/// flownet/frame producers' recoverable posture).
fn attach_converter_graph_ref(obligations: &mut [Obligation], decl: &Decl, decl_name: &str) {
    if obligations.is_empty() {
        return;
    }
    let Some(graph) = crate::converter::build_decl_graph(decl, decl_name) else {
        return;
    };
    if graph.nodes.is_empty() {
        return;
    }
    let digest = match content_address(CONVERTER_GRAPH_KIND, &graph) {
        Ok(digest) => digest,
        Err(err) => {
            tracing::warn!(
                subject = %decl_name,
                error = ?err,
                "WO-88: could not content-address converter graph; obligations stay graph-less"
            );
            return;
        }
    };
    let payload_ref = PayloadRef {
        kind: CONVERTER_GRAPH_KIND.to_string(),
        digest,
        origin: decl_name.to_string(),
    };
    for obligation in obligations.iter_mut() {
        obligation.payloads.push(payload_ref.clone());
    }
    tracing::debug!(
        subject = %decl_name,
        obligations = obligations.len(),
        nodes = graph.nodes.len(),
        "WO-88: attached converter_graph PayloadRef to require obligations"
    );
}

/// Lower every structured `require` group into obligations.
///
/// `realized_inputs` (WO-42 deliverable 3) is the caller-resolved set
/// of realized-domain IR bytes this build was supplied; it backs the
/// fluid-claim pass's `from=` geometry extraction (D128 -- extraction
/// runs in-pipeline when a realized-geometry record is available, and
/// stays the pre-realization `GeomExtract` placeholder otherwise).
/// Dispatches every obligation family (plan, fluid, frame, require+window,
/// cost, conformance, rule); to add a new claim family, add a
/// `push_*_obligations` fn and wire it here.
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
    push_snapshot_records(snapshots, &mut out.snapshots);

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
            // WO-88 deliverable 2/3: the range of require obligations
            // this decl emits (for the converter_graph attach below).
            let converter_obl_start = out.obligations.len();
            for group in decl.claims() {
                push_group_obligations(
                    &mut out.obligations,
                    &mut out.diagnostics,
                    &ctx,
                    &group,
                    &given,
                    &pf.path,
                );
            }

            // WO-88 deliverable 2/3 (F112): pin this decl's compiled
            // converter graph onto every require obligation it emitted.
            let new = &mut out.obligations[converter_obl_start..];
            attach_converter_graph_ref(new, &decl, &decl_name);

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
        // WO-89: an `impl ... by extern("ref", <hdl dialect>)` edge ALSO
        // forms one `hdl.build` obligation, routed (orchestrator-side,
        // `_translate_hdl`) to the std.hdl verilator pack. The INV-13
        // conformance obligation above is unchanged; this is the digital
        // sibling of WO-69's `plan:` -> `cam.*` emission.
        if let Some(hdl) = hdl_build_obligation(edge, snapshots) {
            out.obligations.push(hdl);
        }
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
