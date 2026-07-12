//! Pass 5b: `waive ...:` blocks -> the waiver ledger + honesty checks.
//!
//! Regolith reference: `docs/spec/regolith/12-overrides-and-hints.md` sec.
//! 3 (the rung-7 `waive` construct) and `docs/spec/regolith/13` INV-2
//! (ladder safety) / INV-12 (waiver honesty). This pass runs AFTER
//! claim lowering so it can match each declared waiver against the
//! obligations the pipeline actually emitted.
//!
//! The two invariants are realized here structurally:
//!
//! * **INV-2 (ladder safety).** A waiver only ever produces a
//!   [`WaiverRecord`] -- an acceptance record referencing the matched
//!   obligations' content hashes. This pass NEVER touches the obligation
//!   or evidence set, so a waiver cannot convert `violated` into
//!   `discharged`; the worst it does is record an attributed, release-
//!   gated acceptance. An overreaching waiver (no mandatory `basis:`)
//!   is itself a diagnostic (`WAIVER_MISSING_BASIS`), not an acceptance.
//!   The re-keying half reduces to INV-1: a waiver keyed to a claim
//!   whose obligation was re-keyed (e.g. its material changed) no longer
//!   matches, so it becomes `Stale` -- a diagnostic, never a silent pass.
//! * **INV-12 (waiver honesty).** Every waiver is recorded in the
//!   ledger as waived-with-reason (its `basis` and match set); a waiver
//!   that matches a claim the pipeline emits obligations for yet accepts
//!   none is `Stale` (`STALE_WAIVER`). Rule-pack targets the static core
//!   cannot see (`dfm`/`drc`/`erc`) are recorded as `DeferredRulePack`
//!   -- release-gated, never falsely stale.

use regolith_diag::{codes, Diagnostic, LabeledSpan, Span};
use regolith_oblig::{LedgerEntry, Obligation, WaiveLedger, Waiver, WaiverKind, WaiverRecord};
use regolith_syntax::ast::{AstNode, Decl, File, WaiveBlock};

use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;

/// The waiver ledger and any honesty diagnostics from this pass.
#[derive(Debug, Clone, Default)]
pub struct WaiverReport {
    /// The build's waiver ledger (the INV-12 audit surface).
    pub ledger: WaiveLedger,
    /// Stale-waiver / missing-basis diagnostics (INV-2/INV-12).
    pub diagnostics: Vec<Diagnostic>,
}

/// Build the waiver ledger by matching every `waive ...:` block against
/// the emitted `obligations`, and collect the honesty diagnostics.
#[must_use]
pub fn build_ledger(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
    obligations: &[Obligation],
) -> WaiverReport {
    let span = tracing::info_span!("lower.waivers");
    let _enter = span.enter();

    let mut report = WaiverReport::default();

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let Some(decl_name) = decl.name() else {
                continue;
            };
            if decl_is_poisoned(&decl) {
                continue;
            }
            let subject_ref = snapshots
                .scopes
                .get(&decl_name)
                .map(regolith_sem::EntityDb::snapshot_hash)
                .unwrap_or_default();

            for block in decl.waivers() {
                lower_one_waiver(
                    &pf.path,
                    &decl,
                    &block,
                    &subject_ref,
                    obligations,
                    &mut report,
                );
            }
        }
    }

    // INV-12: surface every stale waiver as a diagnostic (kept in one
    // home on the ledger so the classification and the diagnostic can
    // never desync).
    report
        .diagnostics
        .extend(report.ledger.stale_waiver_diagnostics());

    tracing::info!(
        waivers = report.ledger.entries().len(),
        diagnostics = report.diagnostics.len(),
        "lower: waiver ledger built"
    );

    report
}

/// Lower a single `waive` block: validate its mandatory basis (INV-2
/// overreach guard), classify it against the obligation set (INV-12),
/// and record it. Never mutates `obligations` (INV-2 ladder safety).
fn lower_one_waiver(
    path: &camino::Utf8Path,
    decl: &Decl,
    block: &WaiveBlock,
    subject_ref: &str,
    obligations: &[Obligation],
    report: &mut WaiverReport,
) {
    let target = block.target();

    // D117: the waive ladder cannot silence its own audit -- a `waive`
    // whose target spells a lint code (`Lxxxx`) is rejected outright,
    // before basis/matching, so it can never be recorded as an
    // acceptance (`[lints]` is the only channel that tunes a lint
    // code's severity).
    if let Some(code_text) = lint_code_shaped(&target) {
        let range = block.syntax().text_range();
        let span = Span::new(
            path.to_owned(),
            usize::from(range.start()),
            usize::from(range.end()),
        );
        report.diagnostics.push(
            Diagnostic::error(
                codes::WAIVE_NAMES_LINT_CODE,
                format!(
                    "`waive` cannot name lint code `{code_text}`; \
                     configure it in `magnetite.toml [lints]` instead"
                ),
            )
            .with_span(LabeledSpan::new(
                span,
                "lint codes are tuned by [lints], never waived",
            )),
        );
        tracing::debug!(target = %target, "rejected waive naming a lint code (D117)");
        return;
    }

    // INV-2 overreach: an unjustified concession (no mandatory `basis:`)
    // is rejected as a diagnostic, never recorded as an acceptance.
    let Some(basis) = block.basis().filter(|b| !b.is_empty()) else {
        let range = block.syntax().text_range();
        let span = Span::new(
            path.to_owned(),
            usize::from(range.start()),
            usize::from(range.end()),
        );
        report.diagnostics.push(
            Diagnostic::error(
                codes::WAIVER_MISSING_BASIS,
                format!("waiver `{target}` has no mandatory `basis:` clause"),
            )
            .with_span(LabeledSpan::new(
                span,
                "a waiver must state its basis (regolith/12 rule 2)",
            )),
        );
        tracing::debug!(target = %target, "rejected basis-less waiver (INV-2 overreach)");
        return;
    };

    let waiver = Waiver {
        target: target.clone(),
        scope: block.scope(),
        basis,
        evidence: block.evidence(),
        expires: block.expires(),
    };

    let (kind, matched) = classify(&target, subject_ref, obligations);
    tracing::debug!(
        decl = %decl.name().unwrap_or_default(),
        target = %target,
        kind = ?kind,
        matched = matched.len(),
        "recorded waiver"
    );
    // D105(d): `match_set` is the sorted entity-ref record for the
    // INV-12 growth diff. The diff PASS is the WO-26 remainder's job;
    // this WO lands only the schema field, so the authored match set
    // is derived from the evaluation-time `matched` hashes for now
    // (a faithful placeholder, never a guess -- WO-26 replaces this
    // with the true authored entity refs).
    let mut match_set = matched.clone();
    match_set.sort();
    report.ledger.record(LedgerEntry::Waived(WaiverRecord {
        waiver,
        kind,
        matched,
        match_set,
    }));
}

/// If `target` is exactly shaped like a lint code (`L` or `l` followed
/// by four ASCII digits, e.g. `L0801`/`l0801`), return its canonical
/// uppercase spelling (D117: `waive` cannot name one). A `Group.claim`
/// or rule-pack target never collides with this shape (both always
/// carry at least one `.`/`(` character).
fn lint_code_shaped(target: &str) -> Option<String> {
    let bytes = target.as_bytes();
    if bytes.len() != 5 {
        return None;
    }
    if !matches!(bytes[0], b'L' | b'l') {
        return None;
    }
    if !bytes[1..].iter().all(u8::is_ascii_digit) {
        return None;
    }
    Some(target.to_uppercase())
}

/// Classify a waiver `target` against the obligation set and collect the
/// content hashes it accepts. A rule-pack target (`dfm(pack.rule)` /
/// `drc(...)`/`erc(...)`) matches the rule obligations the WO-28 engine
/// now lowers (their claim name IS the waive-target spelling, D-D);
/// one that matches nothing stays `DeferredRulePack` -- release-gated,
/// never falsely stale, because the rule may live on a realized-fact
/// tier the static core cannot see yet. A `Group.claim` target matches
/// obligations in the SAME declaration whose claim name is the
/// target's trailing segment; a claim target that matches nothing is
/// `Stale` (INV-12).
fn classify(
    target: &str,
    subject_ref: &str,
    obligations: &[Obligation],
) -> (WaiverKind, Vec<String>) {
    if is_rule_pack(target) {
        let matched: Vec<String> = obligations
            .iter()
            .filter(|o| o.subject_ref == subject_ref && rule_target_matches(target, o))
            .map(Obligation::content_hash)
            .collect();
        if matched.is_empty() {
            return (WaiverKind::DeferredRulePack, Vec::new());
        }
        return (WaiverKind::Matched, matched);
    }

    let claim_name = target.rsplit('.').next().unwrap_or(target);
    let matched: Vec<String> = obligations
        .iter()
        .filter(|o| o.subject_ref == subject_ref && o.claim.name.as_deref() == Some(claim_name))
        .map(Obligation::content_hash)
        .collect();

    if matched.is_empty() {
        (WaiverKind::Stale, Vec::new())
    } else {
        (WaiverKind::Matched, matched)
    }
}

/// Whether a rule-pack waive target accepts an obligation: exact
/// claim-name match (`dfm(std.sheet_metal.min_bend_radius)`), or the
/// corpus's unqualified spelling (`dfm(min_bend_radius)`) matching a
/// claim of the same family whose qualified rule name ENDS with the
/// target's inner name (`.min_bend_radius`). Never a substring match.
fn rule_target_matches(target: &str, obligation: &Obligation) -> bool {
    let Some(claim_name) = obligation.claim.name.as_deref() else {
        return false;
    };
    if claim_name == target {
        return true;
    }
    let split = |s: &str| -> Option<(String, String)> {
        let (family, rest) = s.split_once('(')?;
        Some((family.to_string(), rest.strip_suffix(')')?.to_string()))
    };
    let (Some((t_family, t_inner)), Some((c_family, c_inner))) = (split(target), split(claim_name))
    else {
        return false;
    };
    t_family == c_family && (c_inner == t_inner || c_inner.ends_with(&format!(".{t_inner}")))
}

/// Whether a waiver target names a rule-pack rule (`dfm(...)`,
/// `drc(...)`, `erc(...)`).
fn is_rule_pack(target: &str) -> bool {
    ["dfm(", "drc(", "erc("]
        .iter()
        .any(|p| target.starts_with(p))
}

#[cfg(test)]
mod tests {
    use super::build_ledger;
    use crate::checks::run_checks;
    use crate::claims::build_obligations;
    use crate::contracts::build_contract_ir;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_oblig::{LedgerEntry, WaiverKind};

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn report(src: &str) -> super::WaiverReport {
        let files = parsed(src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obl = build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        build_ledger(&files, &snaps, &obl)
    }

    #[test]
    fn a_matching_claim_waiver_is_recorded_matched() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        basis: \"proto lot\"\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert_eq!(rec.matched.len(), 1, "accepted the yield obligation");
        assert!(r.diagnostics.is_empty(), "a matching waiver is clean");
    }

    #[test]
    fn a_waiver_naming_a_lint_code_is_rejected_not_recorded() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive L0801 on self:\n        basis: \"nope\"\n";
        let r = report(src);
        assert!(
            r.ledger.entries().is_empty(),
            "a waive naming a lint code is never recorded as an acceptance"
        );
        assert_eq!(r.diagnostics.len(), 1);
        assert_eq!(r.diagnostics[0].code, super::codes::WAIVE_NAMES_LINT_CODE);
    }

    #[test]
    fn a_claim_waiver_matching_nothing_is_stale() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.ghost on self:\n        basis: \"typo\"\n";
        let r = report(src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a claim target matching nothing must be a stale diagnostic"
        );
    }

    #[test]
    fn a_rule_pack_waiver_is_deferred_not_stale() {
        // The static core lowers no dfm obligations, so a dfm waiver is
        // recorded (release-gated) but NEVER falsely stale.
        let src = "part p:\n    waive dfm(min_web) on milled.wall:\n        basis: \"qual unit\"\n        by test(vr081)\n";
        let r = report(src);
        let LedgerEntry::Waived(rec) = &r.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::DeferredRulePack);
        assert!(rec.waiver.evidence.is_some(), "the `by` clause is evidence");
        assert!(
            !r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::STALE_WAIVER),
            "a rule-pack waiver is not stale"
        );
    }

    #[test]
    fn a_basis_less_waiver_is_an_overreach_diagnostic() {
        let src = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        note: \"no basis here\"\n";
        let r = report(src);
        assert!(
            r.diagnostics
                .iter()
                .any(|d| d.code == regolith_diag::codes::WAIVER_MISSING_BASIS),
            "a waiver without basis must be rejected (INV-2 overreach)"
        );
        assert!(
            r.ledger.entries().is_empty(),
            "a rejected waiver is not recorded as an acceptance"
        );
    }

    #[test]
    fn a_waiver_never_changes_the_obligation_set() {
        // INV-2 ladder safety: the obligations are byte-identical with
        // and without the waiver -- the waiver adds only a ledger entry.
        let with = "part p:\n    require Strength:\n        yield: >= 200\n    waive Strength.yield on self:\n        basis: \"ok\"\n";
        let without = "part p:\n    require Strength:\n        yield: >= 200\n";
        let files_w = parsed(with);
        let snaps_w = build_entities(&files_w);
        let checks_w = run_checks(&files_w, &snaps_w);
        let graph_w = build_contract_ir(&files_w, &snaps_w);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obl_w = build_obligations(&files_w, &snaps_w, &checks_w, &graph_w, &realized_inputs)
            .obligations;

        let files_n = parsed(without);
        let snaps_n = build_entities(&files_n);
        let checks_n = run_checks(&files_n, &snaps_n);
        let graph_n = build_contract_ir(&files_n, &snaps_n);
        let obl_n = build_obligations(&files_n, &snaps_n, &checks_n, &graph_n, &realized_inputs)
            .obligations;

        assert_eq!(
            obl_w, obl_n,
            "declaring a waiver must not alter any obligation (INV-2)"
        );
    }

    /// WO-28 deliverable 4: the violated-rule -> waive -> release
    /// ladder, end to end through the existing machinery (nothing new
    /// to learn, nothing bypassed).
    const VIOLATED_RULE: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            why: \"press pack minimum inside radius\"\npart p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n";

    fn rule_report(waive_tail: &str) -> (super::WaiverReport, Vec<regolith_oblig::Obligation>) {
        let src = format!("{VIOLATED_RULE}{waive_tail}");
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        (report, obligations)
    }

    #[test]
    fn a_violated_rule_lowers_a_waivable_obligation() {
        let (_, obligations) = rule_report("");
        let rule_obl = obligations
            .iter()
            .find(|o| o.claim.name.as_deref() == Some("dfm(sheet_metal.min_bend_radius)"))
            .expect("violated rule lowered to an obligation");
        assert!(
            rule_obl
                .given
                .refs
                .iter()
                .any(|(origin, detail)| origin == "flange" && detail.starts_with("violated:")),
            "{:?}",
            rule_obl.given.refs
        );
    }

    #[test]
    fn a_basis_less_rule_waiver_is_rejected_not_recorded() {
        let (report, _) = rule_report(
            "part q:\n    waive dfm(sheet_metal.min_bend_radius) on p.flange:\n        note: \"no basis\"\n",
        );
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == regolith_diag::codes::WAIVER_MISSING_BASIS));
    }

    #[test]
    fn an_evidence_less_rule_waiver_matches_and_release_gates() {
        // The waive is declared in the SAME decl whose obligation it
        // accepts (subject_ref scoping).
        let src = VIOLATED_RULE.replace(
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n",
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n    waive dfm(sheet_metal.min_bend_radius) on formed.flange:\n        basis: \"prototype lot only, EV-31\"\n",
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        let LedgerEntry::Waived(rec) = &report.ledger.entries()[0] else {
            panic!("expected a waived entry: {:?}", report.ledger.entries());
        };
        assert_eq!(rec.kind, WaiverKind::Matched, "{rec:?}");
        assert_eq!(rec.matched.len(), 1, "accepted the rule obligation");
        assert!(
            report.ledger.release_blocked(),
            "an evidence-less waiver is release-gated (regolith/12 rule 3)"
        );
        // The unqualified corpus spelling matches the same obligation.
        let src2 = src.replace(
            "waive dfm(sheet_metal.min_bend_radius)",
            "waive dfm(min_bend_radius)",
        );
        let files2 = parsed(&src2);
        let snaps2 = build_entities(&files2);
        let checks2 = run_checks(&files2, &snaps2);
        let graph2 = build_contract_ir(&files2, &snaps2);
        let obligations2 =
            build_obligations(&files2, &snaps2, &checks2, &graph2, &realized_inputs).obligations;
        let report2 = build_ledger(&files2, &snaps2, &obligations2);
        let LedgerEntry::Waived(rec2) = &report2.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(
            rec2.kind,
            WaiverKind::Matched,
            "unqualified spelling matches"
        );
    }

    #[test]
    fn an_evidence_carrying_rule_waiver_is_a_listed_deviation() {
        let src = VIOLATED_RULE.replace(
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n",
            "        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n    waive dfm(sheet_metal.min_bend_radius) on formed.flange:\n        basis: \"qualified by test, EV-32\"\n        by test(vr090)\n"
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let checks = run_checks(&files, &snaps);
        let graph = build_contract_ir(&files, &snaps);
        let realized_inputs = crate::realized_input::RealizedInputs::new();
        let obligations =
            build_obligations(&files, &snaps, &checks, &graph, &realized_inputs).obligations;
        let report = build_ledger(&files, &snaps, &obligations);
        let LedgerEntry::Waived(rec) = &report.ledger.entries()[0] else {
            panic!("expected a waived entry");
        };
        assert_eq!(rec.kind, WaiverKind::Matched);
        assert!(rec.waiver.evidence.is_some(), "the `by` clause is evidence");
        assert!(
            !report.ledger.release_blocked(),
            "an evidence-carrying waiver is a listed deviation, not a release block"
        );
    }
}
