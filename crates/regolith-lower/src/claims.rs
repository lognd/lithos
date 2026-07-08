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

use regolith_diag::Diagnostic;
use regolith_oblig::{Claim, ClaimForm, Given, Obligation, SnapshotRecord};
use regolith_qty::Unit;
use regolith_syntax::ast::{AstNode, Decl, Field, File};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::checks::CheckReport;
use crate::contracts::{impl_edge, ConformanceEdge, ContractGraph, RealizationEdge};
use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;

/// Every obligation this pass produced, the snapshot records for every
/// committed scope, and any diagnostics.
#[derive(Debug, Clone, Default)]
pub struct ObligationSet {
    /// One obligation per structured claim line.
    pub obligations: Vec<Obligation>,
    /// One record per committed `EntityDb` scope.
    pub snapshots: Vec<SnapshotRecord>,
    /// Diagnostics from claim lowering (currently none -- claim lines
    /// are lowered structurally, with no ambiguity to report yet).
    pub diagnostics: Vec<Diagnostic>,
}

/// Lower every structured `require` group into obligations.
#[must_use]
pub fn build_obligations(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
    _checks: &CheckReport,
    graph: &ContractGraph,
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

            for group in decl.claims() {
                for line in group.claims() {
                    push_require_obligations(
                        &mut out.obligations,
                        &decl_name,
                        &line,
                        &subject_ref,
                        &given,
                    );
                }
            }
        }
    }

    // BE-6/INV-13: one conformance obligation per impl/extern/import
    // binding the contract pass discovered, in its collected (file then
    // source) order, appended after the require-claim obligations.
    for edge in &graph.conformance {
        out.obligations
            .push(conformance_obligation(edge, snapshots, files));
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

    out
}

/// Lower one `require` group's `Field` line (`subject: predicate`) into
/// one or more obligations, appending them to `out`. A `within [lo, hi]`
/// predicate (deliverable 2) splits into two one-sided obligations; every
/// other predicate's unit-suffixed bound resolves through `regolith-qty`
/// (deliverable 1) before becoming the obligation's `Comparison` claim.
fn push_require_obligations(
    out: &mut Vec<Obligation>,
    decl_name: &str,
    line: &Field,
    subject_ref: &str,
    given: &Given,
) {
    let subject = line.name();
    let predicate = full_predicate_text(line);

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
    let loads = conformance_windows(edge, files).map_or_else(Vec::new, |(sense, spec, imp)| {
        vec![
            format!("conformance_sense: {sense}"),
            format!("spec_bound: {spec}"),
            format!("impl_bound: {imp}"),
        ]
    });
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

/// Extract the `(sense, spec_bound, impl_bound)` refinement windows for
/// an `impl` conformance edge, when the upper contract (the interface
/// named by `edge.upper`) and the lower realization (the impl body) each
/// declare a leading scalar comparator bound with the SAME sense
/// (`q: <= 20` refined by `q: <= 14`). Returns `None` for import/extern
/// edges, or when either side lacks a comparable literal bound, or when
/// the two senses disagree -- the orchestrator then defers the conformance
/// obligation rather than the compiler inventing a window (INV-13/26).
///
/// The heuristic is deliberately positional (the FIRST comparator-bound
/// field on each side): matching promised bounds by name across interface
/// and impl bodies is contract-IR work (WO-12) not yet built, an honest
/// cut recorded in the WO-19 partial-lowering note.
fn conformance_windows(edge: &ConformanceEdge, files: &[ParsedFile]) -> Option<(String, f64, f64)> {
    if edge.kind != "impl" {
        return None;
    }
    let (spec_sense, spec_bound) = interface_bound(&edge.upper, files)?;
    let (impl_sense, impl_bound) = impl_realization_bound(edge, files)?;
    if spec_sense != impl_sense {
        return None;
    }
    Some((spec_sense, spec_bound, impl_bound))
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

/// The first comparator-bound field anywhere under `node` (interface
/// decl body or impl body), or `None`.
fn first_field_bound(node: &SyntaxNode) -> Option<(String, f64)> {
    for descendant in node.descendants() {
        if let Some(field) = Field::cast(descendant) {
            if let Some(value) = field.value() {
                if let Some(bound) = bound_from_value_text(&value.text().to_string()) {
                    return Some(bound);
                }
            }
        }
    }
    None
}

/// The upper contract's promised bound: the first comparator-bound field
/// of the `interface <name>` declaration.
fn interface_bound(name: &str, files: &[ParsedFile]) -> Option<(String, f64)> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw)
                && decl.name().as_deref() == Some(name)
            {
                if let Some(bound) = first_field_bound(decl.syntax()) {
                    return Some(bound);
                }
            }
        }
    }
    None
}

/// The lower realization's declared bound: the first comparator-bound
/// field of the impl body (`impl <upper> for <lower>`) matching `edge`,
/// whether the impl is a top-level decl or an in-body `ImplStmt`.
fn impl_realization_bound(edge: &ConformanceEdge, files: &[ParsedFile]) -> Option<(String, f64)> {
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let decl_name = decl.name().unwrap_or_default();
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw) {
                if let Some(candidate) = impl_edge(decl.syntax(), &decl_name) {
                    if &candidate == edge {
                        if let Some(bound) = first_field_bound(decl.syntax()) {
                            return Some(bound);
                        }
                    }
                }
            }
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt {
                    if let Some(candidate) = impl_edge(&node, &decl_name) {
                        if &candidate == edge {
                            if let Some(bound) = first_field_bound(&node) {
                                return Some(bound);
                            }
                        }
                    }
                }
            }
        }
    }
    None
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
        build_obligations(&files, &snaps, &checks, &graph).obligations
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
