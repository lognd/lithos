//! Rule-pack static checks (WO-28 partial): the checks that need only
//! the typed `RuleDecl` CST, not entity-DB/query evaluation.
//!
//! Regolith reference: `docs/implementation/21-rule-packs.md` sec. 3
//! (E06xx family), design doc D-C (union composition, collision is an
//! error). This module currently emits [`codes::RULE_NAME_COLLISION`]
//! (E0602) over every `process` decl's attached `dfm:`/`drc:`/`erc:`
//! rule packs, in file-then-source order (AD-6 determinism).
//!
//! What this module does NOT do (see WO-28's close-out cut list): match
//! rules against real entities (E0601 evaluation), classify a rule's
//! fact level (E0603), or check `resolves:` staleness against the
//! entity-DB resolution set (E0604) -- those need query-engine
//! evaluation over structured domain entities (holes, bends, nets) that
//! do not exist yet (the same `OpaqueIsland` gap `checks.rs` documents
//! for stage/mating bodies).

use std::collections::BTreeMap;

use regolith_diag::codes::RULE_NAME_COLLISION;
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_syntax::ast::{AstNode, File};

use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// One rule's qualified-name provenance, kept for the collision report.
struct RuleSite {
    file: camino::Utf8PathBuf,
    start: usize,
    end: usize,
}

/// Check every `process` decl's attached rule packs for qualified-name
/// (`pack.rule`) collisions (E0602). Non-process decls and poisoned
/// (parse-error) decls are skipped, matching the INV-20 gating the rest
/// of `lower.checks` uses.
#[must_use]
pub fn check_rule_packs(files: &[ParsedFile]) -> Vec<Diagnostic> {
    let span = tracing::info_span!("lower.checks.rules");
    let _enter = span.enter();

    let mut seen: BTreeMap<String, RuleSite> = BTreeMap::new();
    let mut diagnostics = Vec::new();

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(pack_name) = decl.process_name() else {
                continue;
            };
            for pack in decl.rule_packs() {
                for rule in pack.rules() {
                    let Some(rule_name) = rule.name() else {
                        tracing::debug!(
                            file = %pf.path,
                            pack = %pack_name,
                            "rule decl with no name; skipping collision check for it"
                        );
                        continue;
                    };
                    let qualified = format!("{pack_name}.{rule_name}");
                    let range = rule.syntax().text_range();
                    let site = RuleSite {
                        file: pf.path.clone(),
                        start: range.start().into(),
                        end: range.end().into(),
                    };

                    if let Some(prior) = seen.get(&qualified) {
                        tracing::info!(
                            rule = %qualified,
                            first = %prior.file,
                            second = %pf.path,
                            "E0602: rule name collision"
                        );
                        let sp = Span::new(site.file.clone(), site.start, site.end);
                        let prior_sp = Span::new(prior.file.clone(), prior.start, prior.end);
                        diagnostics.push(
                            Diagnostic::error(
                                RULE_NAME_COLLISION,
                                format!(
                                    "rule `{qualified}` is declared more than once; \
                                     attached packs union their rules and a repeated \
                                     qualified name is ambiguous, never a silent override"
                                ),
                            )
                            .with_span(LabeledSpan::new(sp, "duplicate declared here"))
                            .with_span(LabeledSpan::new(prior_sp, "first declared here")),
                        );
                        // Keep the first site as the canonical entry so a
                        // third duplicate reports against the original,
                        // not the most recent duplicate.
                        continue;
                    }
                    seen.insert(qualified, site);
                }
            }
        }
    }

    diagnostics
}

#[cfg(test)]
mod tests {
    use super::check_rule_packs;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::RULE_NAME_COLLISION;

    fn parsed(path: &str, src: &str) -> ParsedFile {
        let path = Utf8PathBuf::from(path);
        ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }
    }

    #[test]
    fn no_collision_for_distinct_rule_names() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n        rule b:\n            demand: true\n";
        let files = vec![parsed("a.hem", src)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }

    #[test]
    fn collision_within_one_pack_is_e0602() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hem", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, RULE_NAME_COLLISION);
    }

    #[test]
    fn collision_across_files_is_e0602() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hem", src), parsed("b.hem", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, RULE_NAME_COLLISION);
    }

    #[test]
    fn same_rule_name_different_pack_is_not_a_collision() {
        let src_a = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n";
        let src_b = "process jlc_2l:\n    dfm:\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hem", src_a), parsed("b.hem", src_b)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }
}
