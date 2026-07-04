//! The todo/assume/waive ledger and `--release` refusal semantics.
//!
//! Substrate reference: `docs/substrate/07-claims-and-evidence.md` and
//! `docs/substrate/12` sec. 3 (waivers). A `--release` build REFUSES
//! while any todo/assume/unwaived-indeterminate remains. Waivers match
//! scoped against claims/rules; an evidence-carrying waiver yields a
//! deviation status; a waiver matching NOTHING is an error (stale
//! waiver). The flag is set on the report here; CLI wiring is WO-15.

use rockhead_diag::Diagnostic;
use serde::{Deserialize, Serialize};

/// A source-declared waiver: it matches some set of claims/rules and
/// carries a basis (and optionally evidence, making it a deviation).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Waiver {
    /// The scope pattern the waiver matches (claim/rule selector text).
    pub scope: String,
    /// The stated basis.
    pub basis: String,
    /// Backing evidence reference, if this is a deviation (vs a bare
    /// waiver).
    pub evidence: Option<String>,
    /// Expiry marker, if any.
    pub expires: Option<String>,
}

/// A ledger entry recording an un-discharged obligation that blocks
/// `--release`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LedgerEntry {
    /// A `todo!` placeholder.
    Todo(String),
    /// An `assume!` assumption.
    Assume(String),
    /// An unwaived indeterminate discharge.
    Indeterminate(String),
    /// A waiver that matched and shadowed a claim/rule.
    Waived(Waiver),
}

/// The build's todo/assume/waive ledger.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct WaiveLedger {
    entries: Vec<LedgerEntry>,
}

impl WaiveLedger {
    /// An empty ledger.
    #[must_use]
    pub fn new() -> WaiveLedger {
        WaiveLedger {
            entries: Vec::new(),
        }
    }

    /// Record a ledger entry.
    pub fn record(&mut self, entry: LedgerEntry) {
        self.entries.push(entry);
    }

    /// Whether a `--release` build must refuse: true if any todo,
    /// assume, or unwaived indeterminate remains.
    #[must_use]
    pub fn release_blocked(&self) -> bool {
        todo!("STUB WO-13: true if any Todo/Assume/Indeterminate (not fully Waived) remains")
    }

    /// Check waivers for staleness: a waiver matching nothing is an
    /// error.
    #[must_use]
    pub fn check_stale_waivers(&self, _matched: &[&Waiver]) -> Vec<Diagnostic> {
        todo!("STUB WO-13: any declared waiver that matched no claim/rule -> stale-waiver error")
    }
}

#[cfg(test)]
mod tests {
    use super::{LedgerEntry, WaiveLedger, Waiver};

    #[test]
    fn ledger_round_trips_json() {
        let mut l = WaiveLedger::new();
        l.record(LedgerEntry::Todo("thermal model".to_string()));
        l.record(LedgerEntry::Waived(Waiver {
            scope: "emc.*".to_string(),
            basis: "deferred".to_string(),
            evidence: None,
            expires: Some("2027-01-01".to_string()),
        }));
        let json = serde_json::to_string(&l).unwrap();
        let back: WaiveLedger = serde_json::from_str(&json).unwrap();
        assert_eq!(back, l);
    }
}
