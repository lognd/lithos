use super::{
    elaborate_flownets, field_span, full_predicate_text, resolve_unit_suffix,
    split_general_comparison, split_top_level_args, sweep_domain_from_ast,
    transient_compliance_edges, AstNode, Claim, ClaimForm, Diagnostic, Field, File, FlownetPayload,
    GeneralComparison, Given, LabeledSpan, Obligation, ParsedFile, PayloadRef, SweepDomain,
    TRANSIENT_NO_COMPLIANCE,
};

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
pub(crate) fn push_fluid_obligations(
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
pub(crate) fn push_fluid_obligation(
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
pub(crate) fn split_claim_suffix_givens(predicate: &str) -> (String, Vec<String>) {
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
pub(crate) fn value_is_quantity(value: &str) -> bool {
    let trimmed = value.trim_start_matches(['+', '-']).trim_start();
    trimmed
        .chars()
        .next()
        .is_some_and(|c| c.is_ascii_digit() || c == '.' || c == '[')
}
