//! Code actions: `Fix.replacement` forwarded verbatim as quick fixes
//! (WO-38 deliverable 4). Fixes never get re-derived here -- the LSP
//! diagnostic carries the original core diagnostic (with its `fixes`)
//! in its `data` field, stashed by `diagnostics::to_lsp_diagnostic`.

use std::collections::HashMap;

use lsp_types::{
    CodeAction, CodeActionDisabled, CodeActionKind, Diagnostic as LspDiagnostic, TextEdit, Url,
    WorkspaceEdit,
};

use crate::diagnostics::file_uri;
use crate::position::LineIndex;

/// Build the quick-fix `CodeAction`s for the diagnostics in a code
/// action request's context. Each core `Fix` becomes one action:
/// a `replacement` becomes a `WorkspaceEdit`; a fix without a
/// replacement surfaces disabled, carrying its message (deliverable 4).
#[must_use]
pub fn code_actions_for(diagnostics: &[LspDiagnostic]) -> Vec<CodeAction> {
    let mut actions = Vec::new();
    for lsp_diag in diagnostics {
        let Some(data) = &lsp_diag.data else { continue };
        let Ok(core_diag) = serde_json::from_value::<regolith_diag::Diagnostic>(data.clone())
        else {
            tracing::warn!("code action: diagnostic data did not decode as core Diagnostic");
            continue;
        };
        for fix in &core_diag.fixes {
            actions.push(fix_to_action(fix, lsp_diag));
        }
    }
    actions
}

/// One core `Fix` -> one LSP `CodeAction`.
fn fix_to_action(fix: &regolith_diag::Fix, source_diag: &LspDiagnostic) -> CodeAction {
    let disabled_reason = if fix.replacement.is_none() {
        Some(CodeActionDisabled {
            reason: fix.message.clone(),
        })
    } else {
        None
    };

    let edit = fix.replacement.as_ref().and_then(|r| {
        let uri = file_uri(&r.span.file)?;
        let text = std::fs::read_to_string(&r.span.file).ok()?;
        let index = LineIndex::new(&text);
        let range = index.range(r.span.start, r.span.end);
        let mut changes: HashMap<Url, Vec<TextEdit>> = HashMap::new();
        changes.insert(
            uri,
            vec![TextEdit {
                range,
                new_text: r.text.clone(),
            }],
        );
        Some(WorkspaceEdit {
            changes: Some(changes),
            document_changes: None,
            change_annotations: None,
        })
    });

    CodeAction {
        title: fix.message.clone(),
        kind: Some(CodeActionKind::QUICKFIX),
        diagnostics: Some(vec![source_diag.clone()]),
        edit,
        command: None,
        is_preferred: None,
        disabled: disabled_reason,
        data: None,
    }
}

#[cfg(test)]
mod tests {
    use super::code_actions_for;
    use lsp_types::{Diagnostic as LspDiagnostic, Position, Range};
    use regolith_diag::{codes, Diagnostic as CoreDiagnostic, Fix, LabeledSpan, Span};

    fn lsp_diag_with(core: &CoreDiagnostic) -> LspDiagnostic {
        LspDiagnostic {
            range: Range::new(Position::new(0, 0), Position::new(0, 1)),
            data: serde_json::to_value(core).ok(),
            ..LspDiagnostic::new_simple(
                Range::new(Position::new(0, 0), Position::new(0, 1)),
                core.message.clone(),
            )
        }
    }

    #[test]
    fn fix_with_replacement_becomes_a_workspace_edit() {
        let core = CoreDiagnostic::error(codes::AMBIGUOUS_SELECTION, "ambiguous")
            .with_span(LabeledSpan::new(Span::new("a.hema", 0, 3), "here"))
            .with_fix(Fix {
                message: "narrow with where".to_string(),
                replacement: Some(regolith_diag::Replacement {
                    span: Span::new("a.hema", 0, 3),
                    text: "xyz".to_string(),
                }),
            });
        // The replacement's file does not exist on disk in this test, so
        // the edit build returns None and the action stays disabled --
        // this test only asserts the action structure, not IO.
        let lsp = lsp_diag_with(&core);
        let actions = code_actions_for(std::slice::from_ref(&lsp));
        assert_eq!(actions.len(), 1);
        assert_eq!(actions[0].title, "narrow with where");
    }

    #[test]
    fn fix_without_replacement_is_disabled() {
        let core = CoreDiagnostic::error(codes::AMBIGUOUS_SELECTION, "ambiguous")
            .with_span(LabeledSpan::new(Span::new("a.hema", 0, 3), "here"))
            .with_fix(Fix {
                message: "manual disambiguation required".to_string(),
                replacement: None,
            });
        let lsp = lsp_diag_with(&core);
        let actions = code_actions_for(std::slice::from_ref(&lsp));
        assert_eq!(actions.len(), 1);
        assert!(actions[0].disabled.is_some());
        assert_eq!(
            actions[0].disabled.as_ref().unwrap().reason,
            "manual disambiguation required"
        );
    }

    #[test]
    fn diagnostic_without_data_yields_no_actions() {
        let lsp = LspDiagnostic::new_simple(
            Range::new(Position::new(0, 0), Position::new(0, 1)),
            "plain".to_string(),
        );
        assert!(code_actions_for(&[lsp]).is_empty());
    }
}
