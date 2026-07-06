//! Pass 5b: `waive ...:` blocks -> the waiver ledger + honesty checks.
//!
//! Regolith reference: `docs/regolith/12-overrides-and-hints.md` sec.
//! 3 (the rung-7 `waive` construct) and `docs/regolith/13` INV-2
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
        evidence: block.has_evidence().then(|| "by".to_string()),
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
    report.ledger.record(LedgerEntry::Waived(WaiverRecord {
        waiver,
        kind,
        matched,
    }));
}

/// Classify a waiver `target` against the obligation set and collect the
/// content hashes it accepts. Rule-pack targets (`dfm`/`drc`/`erc(...)`)
/// are `DeferredRulePack` (the static core lowers no rule obligations);
/// a `Group.claim` target matches obligations in the SAME declaration
/// whose claim name is the target's trailing segment. A claim target
/// that matches nothing is `Stale` (INV-12).
fn classify(
    target: &str,
    subject_ref: &str,
    obligations: &[Obligation],
) -> (WaiverKind, Vec<String>) {
    if is_rule_pack(target) {
        return (WaiverKind::DeferredRulePack, Vec::new());
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

/// Whether a waiver target names a rule-pack rule (`dfm(...)`,
/// `drc(...)`, `erc(...)`) the static core does not lower to
/// obligations.
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
        let path = Utf8PathBuf::from("t.hem");
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
        let obl = build_obligations(&files, &snaps, &checks, &graph).obligations;
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
        let obl_w = build_obligations(&files_w, &snaps_w, &checks_w, &graph_w).obligations;

        let files_n = parsed(without);
        let snaps_n = build_entities(&files_n);
        let checks_n = run_checks(&files_n, &snaps_n);
        let graph_n = build_contract_ir(&files_n, &snaps_n);
        let obl_n = build_obligations(&files_n, &snaps_n, &checks_n, &graph_n).obligations;

        assert_eq!(
            obl_w, obl_n,
            "declaring a waiver must not alter any obligation (INV-2)"
        );
    }
}
