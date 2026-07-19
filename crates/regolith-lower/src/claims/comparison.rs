use super::common::{
    field_span, match_call, parse_window_arg, resolve_unit_suffix, split_kwarg,
    split_top_level_args,
};
use super::{codes, ClaimForm, Diagnostic, Field, LabeledSpan, Window};

/// The outcome of scanning a claim predicate for top-level comparators
/// (WO-26 D103).
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) enum GeneralComparison {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn split_general_comparison(predicate: &str) -> GeneralComparison {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn expression_ref_terms(side: &str) -> Vec<String> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn find_top_level(haystack: &str, needle: &str) -> Option<usize> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn is_dotted_ref(term: &str) -> bool {
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

/// The result of attempting to recognize `predicate` as one of the
/// D102 temporal claim-form calls.
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) enum TemporalOutcome {
    /// Recognized and lowered to a typed `ClaimForm`.
    Form(ClaimForm),
    /// Recognized but shape-invalid (missing/unexpected comparator);
    /// the diagnostic to emit instead of an obligation.
    Diagnosed(Diagnostic),
    /// Not a recognized temporal call at all -- fall through to the
    /// existing untyped paths.
    NotTemporal,
}

/// The comparator tokens a REDUCTION form's trailing text may lead
/// with, longest first (`<=`/`>=` before `<`/`>`).
// frob:doc docs/modules/regolith-lower.md#claims
pub(crate) const TEMPORAL_COMPARATORS: [&str; 4] = ["<=", ">=", "<", ">"];

/// Split `after` (the text following a recognized call's closing
/// paren) into `(op, rhs)` if it leads with a comparator, else `None`.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn split_trailing_comparator(after: &str) -> Option<(String, String)> {
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_temporal_form(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_reduction_form(
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
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_settles_form(
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

/// WO-112 Class 3 (F131 item 1a): resolve unit suffixes INSIDE an
/// inline SCALAR mask constructor -- `floor(5.0V - 150mV)` ->
/// `floor(5 - 0.15)` -- so the orchestrator can read the level as a
/// scalar request limit without re-implementing units (units are this
/// core's job, `resolve_unit_suffix`). Scoped to the `floor(`/
/// `ceiling(` constructors ONLY: a NAMED mask (`CISPR_11_A`,
/// `cell_ovp(4.2V, 2)`) is a hash-pinned reference whose text is
/// never rewritten -- its containment semantics stay the recorded
/// payload-channel residual.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn resolve_scalar_mask_units(mask: &str) -> String {
    let trimmed = mask.trim();
    for head in ["floor(", "ceiling("] {
        if let Some(inner) = trimmed.strip_prefix(head) {
            if let Some(inner) = inner.strip_suffix(')') {
                let resolved = resolve_unit_suffix(inner);
                tracing::debug!(
                    mask = %trimmed,
                    resolved = %resolved,
                    "scalar mask constructor units resolved (D102/WO-112)"
                );
                return format!("{head}{resolved})");
            }
        }
    }
    trimmed.to_string()
}

/// D102 CONTAINMENT form `stays_within(x, mask=<ref>)`: self-
/// contained, NO trailing comparator allowed. WO-54 rider: a windowed
/// use (`, during ...`/`, within .. after ..`/`, until ...`) now types
/// through the schema's `window` field (the dune_buggy/buck_converter
/// corpus shape); the WO-26 D102 residual recording it as untyped is
/// closed.
// frob:doc docs/modules/regolith-lower.md#claims
// frob:waive TEST001 reason="predicate-scanning helper exercised transitively through the claims lowering pipeline (claims/tests.rs, lower() integration test); no isolated unit test calls it directly"
pub(crate) fn parse_stays_within_form(
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
            mask = Some(resolve_scalar_mask_units(value));
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
