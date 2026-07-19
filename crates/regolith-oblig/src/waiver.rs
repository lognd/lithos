//! The todo/assume/waive ledger and `--release` refusal semantics.
//!
//! Regolith reference: `docs/spec/regolith/07-claims-and-evidence.md` and
//! `docs/spec/regolith/12` sec. 3 (waivers). A `--release` build REFUSES
//! while any todo/assume/unwaived-indeterminate remains. Waivers match
//! scoped against claims/rules; an evidence-carrying waiver yields a
//! deviation status; a waiver matching NOTHING is an error (stale
//! waiver). The flag is set on the report here; CLI wiring is WO-15.
//!
//! INV-2 (ladder safety) and INV-12 (waiver honesty) live on this
//! ledger's shape: a [`WaiverRecord`] carries the accepted *match set*
//! (obligation content hashes) and a [`WaiverKind`] classification, and
//! NOTHING here can carry a `Status` -- an acceptance record references
//! evidence but never modifies it, so no waiver can convert `violated`
//! into `discharged`. Every waiver surfaces as waived-with-reason (its
//! `basis`), never as a clean pass.

use regolith_diag::{codes, Diagnostic};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A source-declared waiver: it matches some set of claims/rules and
/// carries a basis (and optionally evidence, making it a deviation).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#waiver
pub struct Waiver {
    /// The rule or claim being waived (`dfm(min_web_thickness)`,
    /// `Group.claim`).
    pub target: String,
    /// The `on <query>` scope pattern, if any; `None` is an unscoped
    /// waiver covering the target wherever it fails in the artifact.
    pub scope: Option<String>,
    /// The stated basis (regolith/12 rule 2 -- mandatory; an absent
    /// basis is an INV-2 overreach diagnostic raised at lowering).
    pub basis: String,
    /// Backing evidence reference, if this is a deviation (a `by`
    /// clause) rather than a bare, release-gated waiver.
    pub evidence: Option<String>,
    /// Expiry marker, if any (regolith/12 rule 8).
    pub expires: Option<String>,
}

/// How a declared waiver relates to the obligation set: the honesty
/// classification INV-12 surfaces. Deliberately carries NO `Status`
/// (INV-2: an acceptance never names a verdict, so it cannot forge
/// `discharged`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#waiver
pub enum WaiverKind {
    /// The waiver matched one or more emitted obligations (recorded as
    /// the accepted match set); their true status is untouched.
    Matched,
    /// The target is a rule-pack rule (`dfm`/`drc`/`erc`) the static
    /// core does not lower to obligations: recorded and release-gated,
    /// but NOT stale -- the core simply cannot see the target here.
    DeferredRulePack,
    /// The target is a claim the pipeline emits obligations for, yet the
    /// waiver matched none of them: a stale-waiver error (INV-12).
    Stale,
}

/// A declared waiver plus its honesty outcome: the classification and
/// the exact obligation content-hashes it accepted. This is the audit
/// surface INV-12 requires -- every waiver appears here with its reason
/// and match set; no waiver silently vanishes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#waiver
pub struct WaiverRecord {
    /// The declared waiver.
    pub waiver: Waiver,
    /// Its relationship to the obligation set.
    pub kind: WaiverKind,
    /// The content hashes of the obligations this waiver accepted
    /// (empty for `DeferredRulePack`/`Stale`), in source order.
    pub matched: Vec<String>,
    /// D105(d): the sorted entity refs the waiver matched AT
    /// AUTHORSHIP time, so a later `regolith build` can diff prior
    /// lockfile match sets and report GROWTH as a named diagnostic
    /// (the waiver ladder's anti-rot residual). Schema field only
    /// here (WO-30); the diff pass is the WO-26 remainder's job.
    #[serde(default)]
    pub match_set: Vec<String>,
}

/// A ledger entry recording an un-discharged obligation that blocks
/// `--release`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#waiver
pub enum LedgerEntry {
    /// A `todo!` placeholder.
    Todo(String),
    /// An `assume!` assumption.
    Assume(String),
    /// An unwaived indeterminate discharge.
    Indeterminate(String),
    /// A waiver that matched and shadowed a claim/rule, with its match
    /// set (INV-12 audit surface).
    Waived(WaiverRecord),
}

/// The build's todo/assume/waive ledger.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#waiver
pub struct WaiveLedger {
    entries: Vec<LedgerEntry>,
}

impl WaiveLedger {
    /// An empty ledger.
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#waiver
    pub fn new() -> WaiveLedger {
        WaiveLedger {
            entries: Vec::new(),
        }
    }

    /// Record a ledger entry.
    // frob:doc docs/modules/regolith-oblig.md#waiver
    pub fn record(&mut self, entry: LedgerEntry) {
        self.entries.push(entry);
    }

    /// Every ledger entry, in record order (the audit surface).
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#waiver
    pub fn entries(&self) -> &[LedgerEntry] {
        &self.entries
    }

    /// Whether a `--release` build must refuse: true if any todo,
    /// assume, or unwaived indeterminate remains, if any waiver is stale,
    /// or if any accepted waiver is evidence-less (a bare rung-7 waiver
    /// is release-gated per regolith/12 rule 3; a deviation with
    /// evidence passes).
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#waiver
    pub fn release_blocked(&self) -> bool {
        self.entries.iter().any(|entry| match entry {
            LedgerEntry::Todo(_) | LedgerEntry::Assume(_) | LedgerEntry::Indeterminate(_) => true,
            LedgerEntry::Waived(record) => {
                record.kind == WaiverKind::Stale || record.waiver.evidence.is_none()
            }
        })
    }

    /// The stale-waiver diagnostics (INV-12): every recorded waiver whose
    /// [`WaiverKind::Stale`] classification means it matched a claim the
    /// pipeline emits obligations for, yet accepted none.
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#waiver
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn stale_waiver_diagnostics(&self) -> Vec<Diagnostic> {
        self.entries
            .iter()
            .filter_map(|entry| match entry {
                LedgerEntry::Waived(record) if record.kind == WaiverKind::Stale => {
                    Some(Diagnostic::error(
                        codes::STALE_WAIVER,
                        format!("waiver `{}` matched no claim or rule", record.waiver.target),
                    ))
                }
                _ => None,
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::{LedgerEntry, WaiveLedger, Waiver, WaiverKind, WaiverRecord};

    fn record(kind: WaiverKind, evidence: Option<String>) -> WaiverRecord {
        WaiverRecord {
            waiver: Waiver {
                target: "Group.claim".to_string(),
                scope: Some("q".to_string()),
                basis: "deferred".to_string(),
                evidence,
                expires: Some("2027-01-01".to_string()),
            },
            kind,
            matched: vec!["blake3:ab".to_string()],
            match_set: vec!["comps.q".to_string()],
        }
    }

    #[test]
    fn ledger_round_trips_json() {
        let mut l = WaiveLedger::new();
        l.record(LedgerEntry::Todo("thermal model".to_string()));
        l.record(LedgerEntry::Waived(record(WaiverKind::Matched, None)));
        let json = serde_json::to_string(&l).unwrap();
        let back: WaiveLedger = serde_json::from_str(&json).unwrap();
        assert_eq!(back, l);
    }

    // frob:tests crates/regolith-oblig/src/waiver.rs::WaiveLedger.stale_waiver_diagnostics kind="unit"
    #[test]
    fn stale_waiver_is_a_diagnostic() {
        let mut l = WaiveLedger::new();
        l.record(LedgerEntry::Waived(record(WaiverKind::Stale, None)));
        assert_eq!(l.stale_waiver_diagnostics().len(), 1);
    }

    #[test]
    fn a_matched_deviation_does_not_block_release() {
        // Evidence-carrying, matched: a deviation, not release-gated.
        let mut l = WaiveLedger::new();
        l.record(LedgerEntry::Waived(record(
            WaiverKind::Matched,
            Some("test(fai)".to_string()),
        )));
        assert!(!l.release_blocked());
    }

    #[test]
    fn a_bare_waiver_is_release_gated() {
        let mut l = WaiveLedger::new();
        l.record(LedgerEntry::Waived(record(WaiverKind::Matched, None)));
        assert!(l.release_blocked());
    }
}
