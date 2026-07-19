//! Diagnostics: the ONE `regolith-diag` pipeline, mapped verbatim to
//! LSP `Diagnostic` values (D111 -- code -> code, severity -> severity,
//! spans -> ranges, `related` -> relatedInformation). No server-side
//! filtering or re-ranking (WO-38 deliverable 3).

use std::collections::BTreeMap;

use camino::Utf8PathBuf;
use lsp_types::{
    Diagnostic, DiagnosticRelatedInformation, DiagnosticSeverity, Location, NumberOrString, Url,
};
use regolith_diag::Severity as CoreSeverity;

use crate::position::LineIndex;

/// Run `regolith check` over `root` (a workspace directory or a single
/// file) and return every diagnostic grouped by absolute file path, in
/// the LSP shape -- the same values `regolith check` renders, mapped
/// through the F111 converter (never re-derived).
///
/// Returns `None` when the session cannot even be opened (infrastructure
/// failure, e.g. missing root); the caller logs and skips publishing.
///
/// # Panics
/// Never in practice: `BuildOutput::payload_json` serializes only the
/// core's own JSON-safe `BuildPayload` shape, so deserializing it back
/// into the same type cannot fail (a failure would be a programmer bug).
#[must_use]
// frob:doc docs/modules/regolith-ls.md#diagnostics
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn check_workspace(root: &Utf8PathBuf) -> Option<BTreeMap<Utf8PathBuf, Vec<Diagnostic>>> {
    let session = regolith_api::Session::open_root(root.clone());
    let realized_inputs = regolith_lower::RealizedInputs::new();
    match session.check(&realized_inputs) {
        Ok(output) => {
            let payload_json = output.payload_json();
            let payload: regolith_api::BuildPayload = serde_json::from_slice(&payload_json)
                .expect("BuildPayload always round-trips through its own JSON shape");
            Some(group_by_file(&payload.diagnostics))
        }
        Err(err) => {
            tracing::warn!(?err, %root, "check_workspace: session infrastructure error");
            None
        }
    }
}

/// Syntax-tier diagnostics (WO-38 deliverable 3): reparse ONE file with
/// `regolith_syntax::parse` (lex -> layout -> parse -> L1 static checks
/// only, no `regolith-sem`/`regolith-ir`/`regolith-oblig` passes) and
/// map its diagnostics verbatim, the same D111 mapping the full
/// workspace check uses. This is the immediate-publish half of the
/// two-tier SLO: it never touches disk beyond the caller-supplied text,
/// so it is fast enough to run on every keystroke while the debounced
/// workspace-level `check_workspace` runs in the background.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#diagnostics
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn syntax_diagnostics_for_text(path: &Utf8PathBuf, text: &str) -> Vec<Diagnostic> {
    let parse = regolith_syntax::parse(text, path);
    let index = LineIndex::new(text);
    parse
        .diagnostics()
        .iter()
        .filter(|diag| diag.primary_span().is_some())
        .map(|diag| to_lsp_diagnostic_with_index(diag, &index))
        .collect()
}

/// Group a diagnostic batch by primary-span file and map each to the
/// LSP shape. Diagnostics with no span are dropped (LSP has nowhere to
/// anchor them; this never happens for real compiler diagnostics but is
/// handled rather than panicking).
fn group_by_file(
    diagnostics: &[regolith_diag::Diagnostic],
) -> BTreeMap<Utf8PathBuf, Vec<Diagnostic>> {
    let mut by_file: BTreeMap<Utf8PathBuf, Vec<Diagnostic>> = BTreeMap::new();
    for diag in diagnostics {
        let Some(primary) = diag.primary_span() else {
            tracing::warn!(code = %diag.code, "diagnostic with no primary span, cannot publish");
            continue;
        };
        let file = primary.file.clone();
        let lsp_diag = to_lsp_diagnostic(diag);
        by_file.entry(file).or_default().push(lsp_diag);
    }
    by_file
}

/// Map one core [`regolith_diag::Diagnostic`] to an LSP `Diagnostic`,
/// using each span's OWN file to build its line index (spans may cross
/// files in `related`).
fn to_lsp_diagnostic(diag: &regolith_diag::Diagnostic) -> Diagnostic {
    let primary = diag
        .primary_span()
        .expect("caller filtered diagnostics with no primary span");
    let index = line_index_for(&primary.file);
    to_lsp_diagnostic_with_index(diag, &index)
}

/// Same mapping as [`to_lsp_diagnostic`], but the PRIMARY span's line
/// index is caller-supplied rather than read from disk -- lets the
/// syntax tier map diagnostics against unsaved editor text. `related`
/// spans (which may name other files) still read fresh from disk.
fn to_lsp_diagnostic_with_index(diag: &regolith_diag::Diagnostic, index: &LineIndex) -> Diagnostic {
    let primary = diag
        .primary_span()
        .expect("caller filtered diagnostics with no primary span");
    let range = index.range(primary.start, primary.end);

    let related_information = if diag.related.is_empty() {
        None
    } else {
        Some(
            diag.related
                .iter()
                .filter_map(|r| {
                    let idx = line_index_for(&r.span.file);
                    let uri = file_uri(&r.span.file)?;
                    Some(DiagnosticRelatedInformation {
                        location: Location {
                            uri,
                            range: idx.range(r.span.start, r.span.end),
                        },
                        message: r.note.clone(),
                    })
                })
                .collect(),
        )
    };

    Diagnostic {
        range,
        severity: Some(match diag.severity {
            CoreSeverity::Error => DiagnosticSeverity::ERROR,
            CoreSeverity::Warning => DiagnosticSeverity::WARNING,
        }),
        code: Some(NumberOrString::String(diag.code.to_string())),
        code_description: None,
        source: Some("regolith".to_string()),
        message: diag.message.clone(),
        related_information,
        tags: None,
        data: serde_json::to_value(diag).ok(),
    }
}

/// Build a [`LineIndex`] for `file` by reading it fresh from disk. Small
/// corpus files (D110 SLO scope) make this cheap; a resident-document
/// cache is the natural next step if profiling ever demands it.
fn line_index_for(file: &Utf8PathBuf) -> LineIndex {
    let text = std::fs::read_to_string(file).unwrap_or_default();
    LineIndex::new(&text)
}

/// Convert an absolute file path to a `file://` URI.
#[must_use]
// frob:doc docs/modules/regolith-ls.md#diagnostics
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn file_uri(path: &Utf8PathBuf) -> Option<Url> {
    Url::from_file_path(path).ok()
}

/// Convert a `file://` URI back to an absolute [`Utf8PathBuf`].
#[must_use]
// frob:doc docs/modules/regolith-ls.md#diagnostics
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn uri_to_path(uri: &Url) -> Option<Utf8PathBuf> {
    uri.to_file_path()
        .ok()
        .and_then(|p| Utf8PathBuf::from_path_buf(p).ok())
}

#[cfg(test)]
mod tests {
    use super::{check_workspace, file_uri, uri_to_path};
    use camino::Utf8PathBuf;

    fn examples_dir(rel: &str) -> Utf8PathBuf {
        let manifest = Utf8PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest.join("../../examples").join(rel)
    }

    // frob:tests crates/regolith-ls/src/diagnostics.rs::file_uri kind="unit"
    // frob:tests crates/regolith-ls/src/diagnostics.rs::uri_to_path kind="unit"
    #[test]
    fn file_uri_and_uri_to_path_round_trip_an_absolute_path() {
        let path = examples_dir("flagships/cubesat");
        let uri = file_uri(&path).expect("an absolute path converts to a file:// URI");
        let back = uri_to_path(&uri).expect("the URI converts back to a path");
        assert_eq!(back, path);
    }

    // frob:tests crates/regolith-ls/src/diagnostics.rs::check_workspace kind="unit"
    #[test]
    fn check_workspace_groups_diagnostics_by_file() {
        let root = examples_dir("flagships/cubesat");
        let by_file = check_workspace(&root).expect("session opens over a real directory");
        // Whatever the current diagnostic count is, every entry must key
        // on a real file under the root and carry a mapped range.
        for (file, diags) in &by_file {
            assert!(file.as_str().starts_with(root.as_str()) || file.exists());
            for d in diags {
                assert!(d.source.as_deref() == Some("regolith"));
            }
        }
    }

    #[test]
    fn check_workspace_missing_root_returns_none() {
        let root = examples_dir("does-not-exist");
        assert!(check_workspace(&root).is_none());
    }

    /// Deliverable 3's SLO: syntax-tier reparse of the largest corpus
    /// file publishes in under 100ms. Generous margin over the charter
    /// number so this stays a real regression guard, not a flaky timer.
    // frob:tests crates/regolith-ls/src/diagnostics.rs::syntax_diagnostics_for_text kind="unit"
    #[test]
    fn syntax_tier_meets_the_100ms_slo_on_the_largest_corpus_file() {
        use super::syntax_diagnostics_for_text;
        use std::time::Instant;

        let examples = Utf8PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../examples");
        let mut largest: Option<(Utf8PathBuf, String)> = None;
        for entry in walkdir(&examples) {
            let Some(ext) = entry.extension() else {
                continue;
            };
            if regolith_syntax::language_for_extension(ext).is_none() {
                continue;
            }
            let Ok(text) = std::fs::read_to_string(&entry) else {
                continue;
            };
            if largest.as_ref().is_none_or(|(_, t)| text.len() > t.len()) {
                largest = Some((entry, text));
            }
        }
        let Some((path, text)) = largest else {
            return; // corpus shape may change; this is a smoke/perf test
        };
        let start = Instant::now();
        let _ = syntax_diagnostics_for_text(&path, &text);
        let elapsed = start.elapsed();
        assert!(
            elapsed.as_millis() < 100,
            "syntax-tier reparse of {path} took {elapsed:?}, exceeds the 100ms SLO"
        );
    }

    fn walkdir(root: &Utf8PathBuf) -> Vec<Utf8PathBuf> {
        let mut out = Vec::new();
        let Ok(entries) = std::fs::read_dir(root) else {
            return out;
        };
        for entry in entries.flatten() {
            let Ok(p) = Utf8PathBuf::from_path_buf(entry.path()) else {
                continue;
            };
            if p.is_dir() {
                out.extend(walkdir(&p));
            } else {
                out.push(p);
            }
        }
        out
    }
}
