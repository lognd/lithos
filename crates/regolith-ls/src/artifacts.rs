//! WO-120 deliverable 4: the WO-38 residual "artifact-fed hover" is
//! re-assessed and landed here, via a DIFFERENT path than the one WO-38
//! cut. WO-38's cut needed `Obligation::evidence_cache_key`, keyed on a
//! `registry_version` only the Python orchestrator computes (no
//! read-only sidecar existed for a Rust reader) -- an architecture gap,
//! not implementable inside a WO-38/WO-120 dispatch.
//!
//! WO-114 (calc package + audit index, landed since) changed the
//! ground: `regolith ship` now writes `dist/calc/calc_book.json`, a
//! self-contained JSON artifact keyed by `claim_name`/`subject_anchor`
//! carrying verdict, margin, disposition, and (for a discharged claim)
//! the full calc sheet -- no `registry_version` or evidence-cache key
//! needed at all. This module reads THAT artifact, read-only, exactly
//! the same discipline the rest of `regolith-ls` already follows (D111:
//! missing/stale artifacts degrade to the static form, never a guess,
//! never a Python call).
//!
//! The types below mirror `python/regolith/backends/calc.py`'s
//! `CalcSheet`/`AuditRow`/`AuditSummary`/`AuditIndex`/`CalcBook`
//! pydantic models FIELD FOR FIELD (house rule: no duplication of the
//! shape without a pointer back to the one source -- any field
//! renamed/added there must be mirrored here, and in
//! `editors/vscode/src/artifacts.ts`, in the same change).

use camino::{Utf8Path, Utf8PathBuf};
use serde::Deserialize;

/// One discharged obligation's calc sheet (mirrors `calc.py::CalcSheet`,
/// the fields a hover actually renders -- inputs/chain are read by the
/// `calc` CLI viewer, not by this hover, so they are omitted here).
#[derive(Debug, Deserialize)]
// frob:doc docs/modules/regolith-ls.md#artifacts
pub struct CalcSheet {
    /// The sheet's id (matches an `AuditRow::detail` for a `calc_sheet`
    /// disposition, and the shipped PDF's filename stem).
    pub sheet_id: String,
    /// The claim's declared name, or its reconstructed source text.
    pub claim_name: String,
    /// The claim's reconstructed source text (`lhs op rhs`).
    pub claim_text: String,
    /// The obligation's human-readable source anchor.
    pub subject_anchor: String,
    /// The discharging model's dotted id.
    pub model_id: String,
    /// The discharging model's version string.
    pub model_version: String,
    /// The model's citation, or the `UNCITED` marker.
    pub citation: String,
    /// The solver/backend that computed this sheet's value.
    pub solver: String,
    /// The evidence tier (e.g. `certified`).
    pub tier: String,
    /// The computed margin, rendered unit-carrying text.
    pub margin: String,
    /// `PASS`/`FAIL` (or the model's own verdict vocabulary).
    pub verdict: String,
}

/// One obligation's disposition in the audit index (mirrors
/// `calc.py::AuditRow`).
#[derive(Debug, Deserialize)]
// frob:doc docs/modules/regolith-ls.md#artifacts
pub struct AuditRow {
    /// The claim's declared name, or its reconstructed source text.
    pub claim_name: String,
    /// The obligation's human-readable source anchor.
    pub subject_anchor: String,
    /// `calc_sheet` | `accepted_deviation` | `deferred` | `violated`.
    pub disposition: String,
    /// The sheet id (`calc_sheet`), the waiver+memo reference
    /// (`accepted_deviation`), or the named reason (else).
    pub detail: String,
}

/// The package-level audit index (mirrors `calc.py::AuditIndex`; the
/// summary counts are the census tree view's concern, not hover's, so
/// only `rows` is read here).
#[derive(Debug, Deserialize)]
// frob:doc docs/modules/regolith-ls.md#artifacts
pub struct AuditIndex {
    /// Every obligation's disposition row.
    pub rows: Vec<AuditRow>,
}

/// The whole calc package (mirrors `calc.py::CalcBook`): every calc
/// sheet plus the audit index, read verbatim from `dist/calc/
/// calc_book.json`.
#[derive(Debug, Deserialize)]
// frob:doc docs/modules/regolith-ls.md#artifacts
pub struct CalcBook {
    /// Every discharged obligation's calc sheet.
    pub sheets: Vec<CalcSheet>,
    /// The total obligation accounting + per-obligation rows.
    pub index: AuditIndex,
}

/// Locate a workspace's calc book: `<root>/dist/calc/calc_book.json`
/// first (single-project layout), else one level of immediate
/// subdirectories (a fleet workspace, WO-105 layout) -- the first
/// found wins, matching the editor-side resolver
/// (`editors/vscode/src/artifacts.ts::findDistProjects`).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#artifacts
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn find_calc_book_path(root: &Utf8Path) -> Option<Utf8PathBuf> {
    let direct = root.join("dist").join("calc").join("calc_book.json");
    if direct.is_file() {
        return Some(direct);
    }
    let entries = std::fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = Utf8PathBuf::from_path_buf(entry.path()).ok()?;
        if !path.is_dir() {
            continue;
        }
        let candidate = path.join("dist").join("calc").join("calc_book.json");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

/// Read + parse the calc book at `path`. Returns `None` on any I/O or
/// parse failure -- a malformed/partial artifact degrades to the
/// static hover form, never a hard error (D111 discipline).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#artifacts
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn load_calc_book(path: &Utf8Path) -> Option<CalcBook> {
    let bytes = std::fs::read(path).ok()?;
    serde_json::from_slice(&bytes).ok()
}

/// Normalize whitespace for a loose claim-name/claim-text match: the
/// CST-derived claim text a hover reads and the calc book's
/// `claim_name` are not guaranteed byte-identical, so both sides are
/// trimmed and whitespace-collapsed before comparing -- never fuzzy
/// beyond that (mirrors the TS resolver's `normalize`).
fn normalize(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Find `needle` (a claim's subject text or reconstructed source text)
/// in `book`'s audit rows, pairing it with its calc sheet when
/// discharged.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#artifacts
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn find_claim_row<'a>(
    book: &'a CalcBook,
    needle: &str,
) -> Option<(&'a AuditRow, Option<&'a CalcSheet>)> {
    let target = normalize(needle);
    let row = book
        .index
        .rows
        .iter()
        .find(|row| normalize(&row.claim_name) == target)?;
    let sheet = if row.disposition == "calc_sheet" {
        book.sheets.iter().find(|s| s.sheet_id == row.detail)
    } else {
        None
    };
    Some((row, sheet))
}

/// Render the markdown hover body for a matched claim row: verdict +
/// margin for a discharged claim, the waiver/deferral/violation detail
/// otherwise -- consumed verbatim, never recomputed (D229).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#artifacts
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn render_claim_hover(row: &AuditRow, sheet: Option<&CalcSheet>) -> String {
    match sheet {
        Some(sheet) => format!(
            "**verdict: {}**  margin: {}\n\nmodel: `{}` v{} ({})\n\nsolver: {} / tier: {}",
            sheet.verdict,
            sheet.margin,
            sheet.model_id,
            sheet.model_version,
            sheet.citation,
            sheet.solver,
            sheet.tier,
        ),
        None => format!("**{}**: {}", row.disposition, row.detail),
    }
}

#[cfg(test)]
mod tests {
    use super::{find_calc_book_path, find_claim_row, load_calc_book, render_claim_hover};
    use camino::Utf8PathBuf;

    fn fixture_book() -> &'static str {
        r#"{
            "sheets": [{
                "sheet_id": "mass under_limit::abc123def456",
                "claim_name": "mass under_limit",
                "claim_text": "mass < 5 kg",
                "subject_anchor": "Widget",
                "model_id": "std.mech.mass",
                "model_version": "1",
                "citation": "uncited built-in",
                "solver": "closed-form",
                "tier": "certified",
                "margin": "1.8 kg",
                "verdict": "PASS"
            }],
            "index": {
                "rows": [
                    {
                        "claim_name": "mass under_limit",
                        "subject_anchor": "Widget",
                        "disposition": "calc_sheet",
                        "detail": "mass under_limit::abc123def456"
                    },
                    {
                        "claim_name": "clearance ok",
                        "subject_anchor": "Bracket",
                        "disposition": "accepted_deviation",
                        "detail": "waiver:bracket-clearance memo=acc-2026-07-01"
                    }
                ]
            }
        }"#
    }

    // frob:tests crates/regolith-ls/src/artifacts.rs::find_calc_book_path kind="unit"
    #[test]
    fn finds_calc_book_at_workspace_root() {
        let dir =
            std::env::temp_dir().join(format!("regolith-ls-artifacts-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(dir.join("dist").join("calc")).unwrap();
        std::fs::write(
            dir.join("dist").join("calc").join("calc_book.json"),
            fixture_book(),
        )
        .unwrap();
        let found = find_calc_book_path(&dir);
        assert_eq!(
            found,
            Some(dir.join("dist").join("calc").join("calc_book.json"))
        );
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn no_calc_book_is_none() {
        let dir = std::env::temp_dir().join(format!(
            "regolith-ls-artifacts-empty-{}",
            std::process::id()
        ));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        assert_eq!(find_calc_book_path(&dir), None);
        std::fs::remove_dir_all(&dir).ok();
    }

    // frob:tests crates/regolith-ls/src/artifacts.rs::find_claim_row kind="unit"
    // frob:tests crates/regolith-ls/src/artifacts.rs::render_claim_hover kind="unit"
    #[test]
    fn matches_a_discharged_claim_and_renders_verdict_margin() {
        let book: super::CalcBook = serde_json::from_str(fixture_book()).unwrap();
        let (row, sheet) = find_claim_row(&book, "  mass  under_limit ").expect("match");
        assert_eq!(row.disposition, "calc_sheet");
        let sheet = sheet.expect("discharged claim has a sheet");
        let rendered = render_claim_hover(row, Some(sheet));
        assert!(rendered.contains("PASS"));
        assert!(rendered.contains("1.8 kg"));
    }

    #[test]
    fn matches_a_waived_claim_and_renders_the_memo_reference() {
        let book: super::CalcBook = serde_json::from_str(fixture_book()).unwrap();
        let (row, sheet) = find_claim_row(&book, "clearance ok").expect("match");
        assert!(sheet.is_none());
        let rendered = render_claim_hover(row, sheet);
        assert!(rendered.contains("accepted_deviation"));
        assert!(rendered.contains("memo=acc-2026-07-01"));
    }

    #[test]
    fn unmatched_claim_is_none() {
        let book: super::CalcBook = serde_json::from_str(fixture_book()).unwrap();
        assert!(find_claim_row(&book, "nonexistent claim").is_none());
    }

    // frob:tests crates/regolith-ls/src/artifacts.rs::load_calc_book kind="unit"
    #[test]
    fn load_calc_book_returns_none_on_malformed_json() {
        let path = Utf8PathBuf::from_path_buf(
            std::env::temp_dir().join(format!("regolith-ls-bad-{}.json", std::process::id())),
        )
        .unwrap();
        std::fs::write(&path, "not json").unwrap();
        assert!(load_calc_book(&path).is_none());
        std::fs::remove_file(&path).ok();
    }
}
