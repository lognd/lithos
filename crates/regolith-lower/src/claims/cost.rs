use super::common::{field_span, match_call, split_kwarg, split_top_level_args};
use super::{
    codes, push_general_comparison_obligation, AstNode, ClaimLoweringCtx, Decl, Diagnostic, Field,
    Given, LabeledSpan, Obligation, SweepDomain, SyntaxKind,
};

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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn push_cost_claim_obligation(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_cost_claim_args(args: &str) -> Result<(String, Option<String>), String> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn cost_bom_lines(decl: &Decl) -> Vec<(String, String)> {
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
