use super::common::{
    field_span, full_predicate_text, match_call, resolve_unit_suffix, split_top_level_args,
};
use super::comparison::{
    expression_ref_terms, find_top_level, parse_temporal_form, split_general_comparison,
    GeneralComparison, TemporalOutcome,
};
use super::compute::with_field_refs;
use super::{
    codes, push_cost_claim_obligation, AstNode, BTreeMap, Claim, ClaimForm, Decl, Diagnostic,
    Field, File, Given, LabeledSpan, Obligation, ParsedFile, Span, SweepDomain,
};

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
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) struct ClaimLoweringCtx<'a> {
    pub(crate) path: &'a camino::Utf8Path,
    pub(crate) decl_name: &'a str,
    pub(crate) subject_ref: &'a str,
    pub(crate) compute_producers: &'a BTreeMap<String, Obligation>,
    /// The enclosing declaration (D103: its `parts:` entries map a
    /// reference head like `comms` to the declared part type).
    pub(crate) decl: &'a Decl,
    /// Every parsed file (D103: cross-file entity-field resolution).
    pub(crate) files: &'a [ParsedFile],
}

// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_require_obligations(
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

    // The `within [lo, hi]` window family (WO-26 deliverable 2 generic
    // split + WO-78's impedance-specific branch), one dispatch helper
    // so this function stays inside clippy's line budget.
    if push_window_family_obligations(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_opaque_require_obligation(
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

/// The `within [lo, hi]` window dispatch (one home, so
/// [`push_require_obligations`] stays inside clippy's line budget):
/// WO-78's impedance-specific branch first (unit-resolved call kwargs +
/// the E0452 netless check), then WO-26 deliverable 2's generic split
/// (two one-sided obligations `>= lo` / `<= hi`, the windowed call
/// EXPRESSION carried as each half's LHS so translate's
/// `_match_call_lhs` routes call-form windows to their model; an empty
/// leading expression keeps the claim label). Returns `true` when the
/// predicate was a window claim (obligations or a diagnostic pushed).
#[allow(
    clippy::too_many_arguments,
    reason = "the per-line lowering context (subject/predicate/given/sweep) \
              is one call site's locals; bundling them into a struct would \
              only rename the same nine things"
)]
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_window_family_obligations(
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
    // WO-78 (charter 35 sec. 1.2): an `elec.impedance(<net>, ...)
    // within [lo, hi]` claim wins first -- it preserves the RESOLVED
    // call expression (the generic path carries raw text) and
    // validates the net argument (E0452). An `elec.impedance(...)`
    // with a plain comparator falls through to the D103
    // general-comparison path, which already preserves call text.
    if push_impedance_window_obligations(
        out,
        diagnostics,
        ctx,
        line,
        subject,
        predicate,
        given,
        sweep,
        model_pin,
    ) {
        return true;
    }
    if let Some((window_lhs, lo, hi)) = within_window_bounds(predicate) {
        push_within_window_obligations(
            out,
            ctx,
            subject,
            &window_lhs,
            given,
            sweep,
            (&lo, &hi),
            model_pin,
        );
        return true;
    }
    false
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_impedance_window_obligations(
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
    // `after` starts at the `within` keyword, so the 3-tuple's leading
    // expression is empty here -- the call text is `args`' job.
    let Some((_, lo, hi)) = within_window_bounds(after) else {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_within_window_obligations(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_temporal_obligation(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_general_comparison_obligation(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn sweep_domain_from_ast(
    sweep: &regolith_syntax::ast::ForallSweepClaim,
) -> Option<SweepDomain> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub(crate) fn is_undeclared_bare_plural_domain(domain: &str) -> bool {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn check_forall_domain(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_forall_prefix(predicate: &str) -> Option<(String, String, String)> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn resolve_entity_ref(ctx: &ClaimLoweringCtx<'_>, reference: &str) -> Option<String> {
    let (head, field_name) = reference.split_once('.')?;
    let target = part_type_of(ctx.decl, head).unwrap_or_else(|| head.to_string());
    let decl = find_decl(ctx.files, &target)?;
    let text = find_field_value_text(&decl, field_name)?;
    Some(bound_or_value_text(&text))
}

/// The declared type name of the enclosing decl's part/field `name`
/// (`comms: CommsPcb(...)` -> `CommsPcb`), if any.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn part_type_of(decl: &Decl, name: &str) -> Option<String> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn find_decl(files: &[ParsedFile], name: &str) -> Option<Decl> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn find_field_value_text(decl: &Decl, field_name: &str) -> Option<String> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn bound_or_value_text(text: &str) -> String {
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
/// Lower one `require` group's claim lines into obligations (F124.1
/// extraction). A group `trust: >= <tier>` line is a DIRECTIVE that floors
/// the required evidence trust of every SIBLING claim in the group
/// (populating `Claim.trust_floor`), not a claim of its own: the Python
/// release gate binds `result.trust_floor` (INV-24 / regolith/12 rule 7),
/// so until this field is populated from source a `trust:` requirement was
/// memo-waivable end-to-end (F124 hole). We extract the floor, skip the
/// directive line, lower every other claim, then stamp the floor onto each
/// obligation the group emitted.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_group_obligations(
    obligations: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    ctx: &ClaimLoweringCtx<'_>,
    group: &regolith_syntax::ast::RequireClaim,
    given: &Given,
    path: &camino::Utf8Path,
) {
    let group_trust_floor = group_trust_floor(group);
    let group_start = obligations.len();
    // WO-68: `all_claims()` walks direct Field claims AND every claim
    // nested inside a `forall <var> in <domain>:` BLOCK claim (previously
    // invisible to this pass -- swallowed whole into an `OpaqueIsland` by
    // the parser, the silent-no-obligation bug WO-68 fixes).
    for (line, block_sweep) in group.all_claims() {
        if is_trust_directive(&line) {
            continue;
        }
        push_require_obligations(
            obligations,
            diagnostics,
            ctx,
            &line,
            block_sweep
                .as_ref()
                .and_then(sweep_domain_from_ast)
                .as_ref(),
            given,
        );
    }
    if let Some(floor) = &group_trust_floor {
        for obligation in &mut obligations[group_start..] {
            if obligation.claim.trust_floor.is_none() {
                obligation.claim.trust_floor = Some(floor.clone());
            }
        }
    }
    // WO-90 deliverable 2: a `forall <var> in <domain>:` sweep whose domain
    // is a BARE PLURAL naming no declared domain (`boards`, `assemblies`)
    // covers zero points -- a vacuous pass. Emit E0450 ONCE per such block
    // (not per nested claim), constructively naming the declared forms.
    for sweep in group.sweeps() {
        check_forall_domain(diagnostics, path, &sweep);
    }
}

/// True iff `line` is a group `trust: >= <tier>` DIRECTIVE (F124.1): a
/// claim line whose subject is literally `trust` and whose predicate is a
/// `>= <tier>` floor. Such a line sets its group's `Claim.trust_floor`
/// instead of lowering to a standalone claim obligation.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn is_trust_directive(line: &Field) -> bool {
    line.name() == "trust" && trust_floor_tier(&full_predicate_text(line)).is_some()
}

/// The trust-floor tier a group declares (F124.1), or `None` when no
/// direct `trust: >= <tier>` directive is present. Only DIRECT claim
/// lines are scanned -- a floor is a group-level property, so a directive
/// nested inside a `forall` block is not a group floor.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn group_trust_floor(group: &regolith_syntax::ast::RequireClaim) -> Option<String> {
    group
        .claims()
        .iter()
        .filter(|line| line.name() == "trust")
        .find_map(|line| trust_floor_tier(&full_predicate_text(line)))
}

/// Parse the tier word out of a `>= <tier>` trust-floor predicate. Returns
/// the tier name verbatim (`certified`, `tested`, ...) so the Python gate
/// resolves it through the ONE tier table (`magnetite.trust`); the tier
/// vocabulary is deliberately NOT re-encoded here. `None` for any predicate
/// that is not a single `>= <identifier>` floor.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn trust_floor_tier(predicate: &str) -> Option<String> {
    let rest = predicate.trim().strip_prefix(">=")?.trim();
    if rest.is_empty() || !rest.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
        return None;
    }
    Some(rest.to_string())
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn within_window_bounds(predicate: &str) -> Option<(String, String, String)> {
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
