use super::{
    codes, field_span, full_predicate_text, match_call, parse_cost_claim_args, parse_forall_prefix,
    plan_clause, resolve_unit_suffix, split_general_comparison, sweep_domain_from_ast, AstNode,
    Claim, ClaimForm, ConformanceEdge, Decl, Diagnostic, EntitySnapshots, File, GeneralComparison,
    Given, LabeledSpan, Obligation, ParsedFile, PayloadRef, PlanClause, SweepDomain,
    KNOWN_PLAN_DIALECTS,
};

/// The five `cam.*` claim kinds a `plan:` clause discharges through
/// (33-cam-verification.md, WO-67's landed `std.cam` pack; WO-69
/// wires the source-level linkage the pack's models already expect).
/// ONE list, source order fixed, so "exactly five obligations, keyed
/// distinctly" (this WO's acceptance criterion) is provable by
/// construction rather than by convention.
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const CAM_CLAIM_KINDS: [&str; 5] = [
    "cam.parse",
    "cam.envelope",
    "cam.collision_coarse",
    "cam.removal",
    "cam.coverage",
];

/// The HDL format tags an `impl ... by extern("ref", <dialect>)` edge
/// may carry that WO-89 routes to the `std.hdl` verilator pack (WO-82).
/// A dialect outside this set (a mechanical `gcode_*`, a non-HDL
/// format, or a bare extern with no dialect) emits NO `hdl.*`
/// obligation -- the ordinary INV-13 conformance obligation is the only
/// one, exactly as before this WO. cuprite/09 sec. 3 names these
/// transparent/embedded formats; the string tags match the `std.hdl`
/// pack's `FixtureSpec.regime` tags verbatim (single-sourced there).
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const KNOWN_HDL_REGIMES: &[&str] =
    &["verilog2001", "verilog2005", "sv2012", "sv2017", "vhdl2008"];

/// The single `hdl.*` claim kind a `by extern` HDL edge forms (WO-89).
/// Only `hdl.build` (verilate/lint, the tier that discharges for every
/// non-VHDL source; WO-82 deliverable 1) is emitted from the source
/// linkage: `hdl.sim_assert`/`hdl.equiv_directed` need a per-fixture
/// testbench + oracle the compiler cannot author, so they stay pack-
/// internal (WO-82's own scope shape). ONE kind, so "one added
/// obligation per HDL extern edge" is provable by construction.
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const HDL_BUILD_KIND: &str = "hdl.build";

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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_plan_obligations(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn plan_obligation(
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

/// WO-89: form one `hdl.build` obligation from an `impl ... by
/// extern("ref", <dialect>)` conformance edge whose dialect is a known
/// HDL format ([`KNOWN_HDL_REGIMES`]). Returns `None` for any non-extern
/// edge, an extern with no dialect, or a non-HDL dialect (a mechanical
/// `gcode_*` plan dialect, say) -- honest silence, never a guess.
///
/// The obligation carries the extern ref + dialect as `given.loads`
/// fields (`hdl_src_ref`/`hdl_regime`, the exact spelling
/// `orchestrator/translate.py::_translate_hdl` reads); the compiler has
/// no IO to hash the foreign bytes (AD-17), so the digest is resolved
/// orchestrator-side exactly like a `plan:` ref. Mirrors
/// [`plan_obligation`]'s shape (NO DUPLICATION of the given-threading
/// idiom -- same `key: value` loads convention `_load_fields` parses).
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) fn hdl_build_obligation(
    edge: &ConformanceEdge,
    snapshots: &EntitySnapshots,
) -> Option<Obligation> {
    if edge.kind != "extern" {
        return None;
    }
    let dialect = edge.dialect.as_deref()?;
    if !KNOWN_HDL_REGIMES.contains(&dialect) {
        return None;
    }
    let subject_ref = snapshots
        .scopes
        .get(&edge.subject)
        .map(regolith_sem::EntityDb::snapshot_hash)
        .unwrap_or_default();
    let obligation = Obligation {
        claim: Claim {
            name: Some(HDL_BUILD_KIND.to_string()),
            form: ClaimForm::Comparison {
                lhs: HDL_BUILD_KIND.to_string(),
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
        subject_ref,
        given: Given {
            materials: Vec::new(),
            loads: vec![
                format!("hdl_src_ref: {}", edge.lower),
                format!("hdl_regime: {dialect}"),
            ],
            backing: Vec::new(),
            refs: Vec::new(),
        },
        hints: Vec::new(),
        sweep: None,
        payloads: Vec::new(),
    };
    tracing::debug!(
        subject = %edge.subject,
        upper = %edge.upper,
        src = %edge.lower,
        dialect = %dialect,
        hash = %obligation.content_hash(),
        "built hdl.build obligation from an HDL extern edge"
    );
    Some(obligation)
}

/// WO-54 deliverable 1 (see the call site above): lower every
/// `mfg.cost(...)` comparison claim in a top-level `require` group,
/// with the D105a `forall` sweep prefix honored and E0438 argument
/// validation. `subject_ref` stays empty (the fluorite/calcite passes
/// key their obligations on payload digests; a top-level cost claim's
/// priced content is resolved orchestrator-side, where the staged
/// inputs doc's digest folds it into the evidence hash).
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_top_level_cost_obligations(
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
