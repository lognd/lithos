//! `[lints]` configuration (WO-40): `magnetite.toml`'s `code -> allow|
//! warn|deny` table, and the ONE place `deny` promotes a [`Diagnostic`]'s
//! [`Severity`] to `Error` at emission time (charter sec. 5, D112:
//! lints are configuration, not an engineering deviation -- the
//! `waive` ladder never touches this table).
//!
//! Regolith reference: `docs/spec/toolchain/24-developer-tooling.md`
//! sec. 5.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::code::Family;
use crate::{Diagnostic, Severity};

/// One `[lints]` table entry's configured action.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LintAction {
    /// Silence the code entirely (removed from the emitted batch).
    Allow,
    /// Emit at its default `Warning` severity (the no-config default).
    Warn,
    /// Promote to `Error` (build-blocking).
    Deny,
}

impl LintAction {
    /// Parse a `[lints]` value string (`"allow"`/`"warn"`/`"deny"`).
    /// Anything else is not this type's job to reject -- the config
    /// loader names the code and value in its own diagnostic.
    #[must_use]
    pub fn parse(value: &str) -> Option<LintAction> {
        match value {
            "allow" => Some(LintAction::Allow),
            "warn" => Some(LintAction::Warn),
            "deny" => Some(LintAction::Deny),
            _ => None,
        }
    }
}

/// A resolved `[lints]` table: lint-code-name (the `codes::` symbol's
/// snake_case spelling, e.g. `"unused_import"`) -> configured action.
/// Built Python-side from `magnetite.toml` (WO-16's manifest reader)
/// and threaded through the FFI boundary as plain string pairs (AD-4);
/// this type is the Rust-side resolved form.
pub type LintConfig = BTreeMap<String, LintAction>;

/// Promote/silence lint-family diagnostics per `config`, in place, at
/// emission time -- the ONE place severity changes (charter sec. 5).
/// Non-lint-family diagnostics are never touched (a `deny`/`allow`
/// entry only ever names a lint code; `waive` cannot name one at all,
/// enforced where the manifest is validated, not here).
#[must_use]
pub fn apply_lint_config(diagnostics: Vec<Diagnostic>, config: &LintConfig) -> Vec<Diagnostic> {
    diagnostics
        .into_iter()
        .filter_map(|mut d| {
            if d.code.family != Family::Lint {
                return Some(d);
            }
            let name = lint_code_name(&d);
            let action = config.get(&name).copied().unwrap_or(LintAction::Warn);
            match action {
                LintAction::Allow => None,
                LintAction::Warn => Some(d),
                LintAction::Deny => {
                    d.severity = Severity::Error;
                    Some(d)
                }
            }
        })
        .collect()
}

/// The stable `[lints]` config-table key for a lint diagnostic: its
/// rendered code (`"L0801"`), lowercased -- the manifest key format
/// (WO-40 deliverable 4 names codes by their `Lxxxx` spelling; a
/// family-glob form is a documented reopen, not v1).
#[must_use]
pub fn lint_code_name(diagnostic: &Diagnostic) -> String {
    diagnostic.code.to_string().to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::{apply_lint_config, LintAction, LintConfig};
    use crate::code::codes;
    use crate::{Diagnostic, Severity};

    #[test]
    fn deny_promotes_to_error() {
        let mut config: LintConfig = LintConfig::new();
        config.insert("l0801".to_string(), LintAction::Deny);
        let diags = vec![Diagnostic::warning(codes::UNUSED_IMPORT, "unused import x")];
        let out = apply_lint_config(diags, &config);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].severity, Severity::Error);
    }

    #[test]
    fn allow_silences() {
        let mut config: LintConfig = LintConfig::new();
        config.insert("l0801".to_string(), LintAction::Allow);
        let diags = vec![Diagnostic::warning(codes::UNUSED_IMPORT, "unused import x")];
        assert!(apply_lint_config(diags, &config).is_empty());
    }

    #[test]
    fn default_stays_warning() {
        let diags = vec![Diagnostic::warning(codes::UNUSED_IMPORT, "unused import x")];
        let out = apply_lint_config(diags, &LintConfig::new());
        assert_eq!(out[0].severity, Severity::Warning);
    }

    #[test]
    fn non_lint_family_untouched_even_if_named() {
        let mut config: LintConfig = LintConfig::new();
        config.insert("e0301".to_string(), LintAction::Deny);
        let diags = vec![Diagnostic::error(codes::AMBIGUOUS_SELECTION, "ambiguous")];
        let out = apply_lint_config(diags, &config);
        assert_eq!(out[0].severity, Severity::Error);
    }
}
