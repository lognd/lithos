//! WO-155 (D264): the cuprite functional simulation gate --
//! `hdl.sim_assert` auto-emission for a declared stimulus.
//!
//! Spec: `docs/spec/cuprite/03-behavioral-layer.md` sec. 2, the `by
//! sim(<stimulus-ref>)`-shaped clause. Grammar-wise this rides the
//! EXISTING require-claim mechanism verbatim (a `sim(<ref>)` predicate
//! parses exactly like `manufacturable(milled)` does today -- an
//! opaque call-shaped predicate, `require.rs`'s `NotComparison` path);
//! no new CST/parser surface is needed for the call syntax itself. One
//! IMPLEMENTATION NOTE against the spec's prose example (which shows
//! the clause nested directly under `impl ... by spec` with no claim
//! name): `consume_header_line` swallows a single-line `require: X`
//! header's ENTIRE remaining line as opaque header text with no
//! `Indent` block following it, so a bare same-line `require: sim(...)`
//! attaches NO `Field` children (`RequireClaim::claims()` returns
//! empty) -- verified empirically against the parser (this WO's own
//! recon, not assumed). The clause is therefore attached the same way
//! every other multi-word claim group is, on the enclosing DECL (a
//! named claim line inside a `require:` block, e.g. `require:\n
//! stimulus: sim(mux_directed_vectors)`), which the compiler already
//! parses without any grammar change. Since a decl's `impl` and its
//! HDL extern edge share the same `decl_name`/`subject`, this is
//! functionally equivalent to an impl-scoped clause for the one-impl-
//! per-decl shape the corpus uses today; a true impl-scoped `by
//! sim(...)` binding (multiple impls of one decl needing distinct
//! stimuli) is new parser surface this WO does not open -- flagged as
//! a named follow-on rather than guessed at here.
//!
//! The new work is HERE: recognizing the `sim(...)` call among a decl's
//! ordinary claim lines and, mirroring [`super::plan::hdl_build_obligation`]
//! (WO-89's precedent), auto-emitting one `hdl.sim_assert` obligation
//! per declared stimulus WHEN this decl also carries a known-HDL `by
//! extern(ref, <dialect>)` conformance edge (D264 ruling 3: v1 = declared-
//! stimulus discharge + named-absence coverage, never a fabricated
//! obligation for an undeclared stimulus).
//!
//! A malformed `sim(...)` argument (empty, or not a bare identifier)
//! emits [`codes::SIM_CLAUSE_MALFORMED`] (E0453) and no obligation --
//! the same honest-silence posture [`super::plan::push_plan_obligations`]
//! uses for a malformed `plan:` clause. Whether the named ref actually
//! RESOLVES inside the built package is an orchestrator-side concern
//! (the compiler has no IO, AD-17, exactly like `hdl_src_ref`/`plan_ref`)
//! -- that check raises `STIMULUS_REF_UNRESOLVED` (E1106) Python-side.

use super::plan::KNOWN_HDL_REGIMES;
use super::{
    codes, field_span, full_predicate_text, match_call, Claim, ClaimForm, ConformanceEdge, Decl,
    Diagnostic, Given, LabeledSpan, Obligation,
};

/// The claim kind an `hdl.sim_assert` obligation carries (unchanged
/// from the fixture-bound pack, WO-82) -- this WO generalizes WHO
/// emits it, never the kind string itself.
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const HDL_SIM_ASSERT_KIND: &str = "hdl.sim_assert";

/// A bare identifier check for the `sim(<ref>)` argument: ASCII
/// alnum/underscore, not starting with a digit, non-empty. Matches the
/// spelling every other bare-ref clause in this pass accepts (plan
/// refs, extern refs) -- quoting is deliberately NOT accepted here
/// (the spec's `sim(mux_directed_vectors)` example is unquoted,
/// distinguishing a stimulus-record NAME from `extern("path", ...)`'s
/// quoted foreign FILE path).
fn is_bare_ident(s: &str) -> bool {
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_ascii_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// WO-155 deliverable 2: scan `decl`'s ordinary claim lines for a
/// `sim(<stimulus-ref>)`-shaped predicate and, for each one, auto-emit
/// one `hdl.sim_assert` obligation IF `decl_name` also carries a known-
/// HDL `extern` conformance edge (the same structural trigger
/// [`super::plan::hdl_build_obligation`] uses) -- a stimulus declared on
/// a decl with no HDL extern edge produces no obligation here (honest
/// silence; WO-157's coverage sweep is the totality check, not this
/// pass). A malformed `sim(...)` argument emits E0453 and no
/// obligation regardless of the extern edge's presence.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_hdl_sim_assert_obligations(
    out: &mut Vec<Obligation>,
    diagnostics: &mut Vec<Diagnostic>,
    path: &camino::Utf8Path,
    decl: &Decl,
    decl_name: &str,
    subject_ref: &str,
    conformance: &[ConformanceEdge],
) {
    let hdl_edge = conformance.iter().find(|edge| {
        edge.kind == "extern"
            && edge.subject == decl_name
            && edge
                .dialect
                .as_deref()
                .is_some_and(|d| KNOWN_HDL_REGIMES.contains(&d))
    });

    for group in decl.claims() {
        for (line, _sweep) in group.all_claims() {
            let predicate = full_predicate_text(&line);
            let Some((args, _after)) = match_call(predicate.trim(), "sim") else {
                continue;
            };
            let stimulus_ref = args.trim();
            let sp = field_span(path, &line);
            if stimulus_ref.is_empty() || !is_bare_ident(stimulus_ref) {
                diagnostics.push(
                    Diagnostic::error(
                        codes::SIM_CLAUSE_MALFORMED,
                        format!(
                            "`sim({stimulus_ref:?})` is not a bare stimulus-record \
                             identifier"
                        ),
                    )
                    .with_span(LabeledSpan::new(sp, "malformed sim(...) argument")),
                );
                continue;
            }
            let Some(edge) = hdl_edge else {
                // No known-HDL extern edge on this decl: the structural
                // trigger is absent, so no obligation is auto-emitted
                // (D264 ruling 3 -- never a fabricated obligation).
                // WO-157's coverage sweep names this as an absence, not
                // this pass.
                tracing::debug!(
                    decl = %decl_name,
                    stimulus_ref = %stimulus_ref,
                    "sim(...) declared but no known-HDL extern edge on this decl; \
                     no hdl.sim_assert obligation emitted (WO-157 coverage sweep territory)"
                );
                continue;
            };
            let obligation = Obligation {
                claim: Claim {
                    name: Some(HDL_SIM_ASSERT_KIND.to_string()),
                    form: ClaimForm::Comparison {
                        lhs: HDL_SIM_ASSERT_KIND.to_string(),
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
                    loads: vec![
                        format!("hdl_src_ref: {}", edge.lower),
                        format!("hdl_regime: {}", edge.dialect.clone().unwrap_or_default()),
                        format!("stimulus_ref: {stimulus_ref}"),
                    ],
                    backing: Vec::new(),
                    refs: Vec::new(),
                },
                hints: Vec::new(),
                sweep: None,
                payloads: Vec::new(),
            };
            tracing::debug!(
                decl = %decl_name,
                stimulus_ref = %stimulus_ref,
                hash = %obligation.content_hash(),
                "built hdl.sim_assert obligation from a declared sim(...) stimulus"
            );
            out.push(obligation);
        }
    }
}
