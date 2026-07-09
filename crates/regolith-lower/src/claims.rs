//! Pass 5: `RequireClaim` -> `Claim` -> `Obligation`, one per claim
//! line; one `SnapshotRecord` per committed entity scope.
//!
//! Regolith reference: `docs/regolith/07-claims-and-evidence.md` sec.
//! 2, `docs/regolith/13` INV-1 (obligation-key sensitivity). Each
//! `RequireClaim` group's `Field` lines (`subject: predicate`) become
//! one `Obligation` each; `subject_ref` is the enclosing declaration's
//! `EntityDb::snapshot_hash()` (AD-18). Sweep-domain detection
//! (`forall ...`) needs structure this WO's grammar surface does not
//! expose at the claim-line level, so every obligation here is a
//! single-point obligation (`sweep: None`) -- see the WO-19
//! partial-lowering note.

use std::collections::BTreeMap;

use regolith_diag::codes::{self, TRANSIENT_NO_COMPLIANCE};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_oblig::{
    Claim, ClaimForm, CoverageAxis, CoverageDomain, CoverageMethod, FieldDatum, FlownetPayload,
    Given, Obligation, PayloadRef, SnapshotRecord, SweepDomain,
};
use regolith_qty::Unit;
use regolith_syntax::ast::{AstNode, Decl, Field, File};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::checks::CheckReport;
use crate::contracts::{impl_edge, ConformanceEdge, ContractGraph, RealizationEdge};
use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::flownet_lower::elaborate_flownets;
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

            for group in decl.claims() {
                for line in group.claims() {
                    push_require_obligations(
                        &mut out.obligations,
                        &mut out.diagnostics,
                        &decl_name,
                        &line,
                        &subject_ref,
                        &given,
                        &compute_producers,
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
fn field_span(path: &camino::Utf8Path, line: &Field) -> Span {
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
fn push_require_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    decl_name: &str,
    line: &Field,
    subject_ref: &str,
    given: &Given,
    compute_producers: &BTreeMap<String, Obligation>,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);
    let given = &with_field_refs(
        given,
        decl_name,
        &subject,
        &predicate,
        compute_producers,
        diagnostics,
    );

    // WO-26 deliverable 2: a `within [lo, hi] ...` demanded window splits
    // into TWO one-sided obligations (`>= lo`, `<= hi`) over the SAME
    // subject, reusing the existing scalar-comparison path end to end
    // (the orchestrator never needs a two-sided request type). Each
    // half's bound goes through the same unit-suffix resolution as an
    // ordinary comparator bound.
    if let Some((lo, hi)) = within_window_bounds(&predicate) {
        for (suffix, op, bound) in [("lo", ">=", lo), ("hi", "<=", hi)] {
            let bound_si = resolve_unit_suffix(bound.trim());
            let name = format!("{subject}.{suffix}");
            let claim = Claim {
                name: Some(name.clone()),
                form: ClaimForm::Comparison {
                    lhs: subject.clone(),
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
                subject_ref: subject_ref.to_string(),
                given: given.clone(),
                hints: Vec::new(),
                sweep: None,
                payloads: vec![],
            };
            tracing::debug!(
                decl = %decl_name,
                subject = %name,
                hash = %obligation.content_hash(),
                "built obligation from within[lo,hi] window half"
            );
            out.push(obligation);
        }
        return;
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
        subject_ref: subject_ref.to_string(),
        given: given.clone(),
        hints: Vec::new(),
        sweep: None,
        payloads: vec![],
    };

    tracing::debug!(
        decl = %decl_name,
        subject = %subject,
        hash = %obligation.content_hash(),
        "built obligation from require claim"
    );
    out.push(obligation);
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
fn full_predicate_text(field: &Field) -> String {
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
}
