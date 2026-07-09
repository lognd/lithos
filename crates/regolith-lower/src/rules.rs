//! Rule-pack static checks (WO-28 partial): the checks that need only
//! the typed `RuleDecl` CST plus the [`EntityKind`] measure vocabulary,
//! not full query-engine matching or demand-expression evaluation.
//!
//! Regolith reference: `docs/implementation/design/21-rule-packs.md` sec. 3
//! (E06xx family), design doc D-C (union composition, collision is an
//! error), D-E (a predicate referencing an unprovided fact is a compile
//! error on the rule, E0603). This module emits:
//!
//! - [`codes::RULE_NAME_COLLISION`] (E0602) over every `process` decl's
//!   attached `dfm:`/`drc:`/`erc:` rule packs, in file-then-source order
//!   (AD-6 determinism).
//! - [`codes::RULE_FACT_UNPROVIDED`] (E0603) for a rule whose `forall`
//!   domain resolves to a structured [`EntityKind`] (`Hole`/`Bend`, the
//!   WO-29 domain kinds with a documented [`EntityKind::known_measure_keys`]
//!   vocabulary) and whose `demand:`/`advise:`/filter text dereferences
//!   the bound variable with a field NOT in that vocabulary.
//!
//! What this module does NOT do (see WO-28's close-out cut list): match
//! rules against real entities and evaluate the demand predicate to a
//! verdict (E0601), or check `resolves:` staleness against the
//! entity-DB resolution set (E0604) -- both need a general
//! demand-expression evaluator (comparisons, aggregates, registry
//! dereference) that does not exist anywhere in the codebase yet; see
//! this WO's ledger for the scoping argument. E0603 here is
//! deliberately narrow (dotted-field-reference scanning, matching the
//! text-based-predicate stance `claims.rs::extract_projection_heads`
//! already takes) rather than a step toward that evaluator.

use std::collections::BTreeMap;

use regolith_diag::codes::{RULE_FACT_UNPROVIDED, RULE_NAME_COLLISION};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::EntityKind;
use regolith_syntax::ast::{AstNode, Field, File, RuleDecl};

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

    diagnostics.extend(check_rule_fact_references(files));
    diagnostics
}

/// E0603: for each rule whose `forall` domain resolves to a structured
/// [`EntityKind`] with a documented measure vocabulary
/// ([`EntityKind::known_measure_keys`]), scan the rule's `demand:`/
/// `advise:` text and the `forall`'s own filter tail for a
/// `<bound-var>.<field>` reference naming a field NOT in that
/// vocabulary. Rules whose domain is not one of the modeled kinds (no
/// vocabulary yet) are not checked here -- absence of a table is not
/// evidence of an unprovided fact (see the module doc).
#[must_use]
fn check_rule_fact_references(files: &[ParsedFile]) -> Vec<Diagnostic> {
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
                    diagnostics.extend(fact_reference_diagnostics(&rule, &pack_name, &pf.path));
                }
            }
        }
    }

    diagnostics
}

/// The E0603 diagnostics for one rule, if its domain is checkable.
fn fact_reference_diagnostics(
    rule: &RuleDecl,
    pack_name: &str,
    path: &camino::Utf8Path,
) -> Vec<Diagnostic> {
    let Some(forall) = rule.forall() else {
        return Vec::new();
    };
    let Some(var) = forall.var() else {
        return Vec::new();
    };
    let query_text = forall.query_text();
    let base_word = leading_ident(&query_text);
    let kind = EntityKind::from_kind_word(&base_word);
    let Some(known) = kind.known_measure_keys() else {
        // Not a modeled domain kind (Face/Edge/Net/Other/...): no
        // vocabulary to check unprovided fields against.
        return Vec::new();
    };

    let rule_name = rule.name().unwrap_or_default();
    let qualified = format!("{pack_name}.{rule_name}");
    let mut texts: Vec<String> = vec![query_text];
    if let Some(f) = rule.demand() {
        texts.push(field_text(&f));
    }
    if let Some(f) = rule.advise() {
        texts.push(field_text(&f));
    }

    let mut seen_fields: Vec<String> = Vec::new();
    for text in &texts {
        for field in dotted_field_refs(text, &var) {
            if !known.contains(&field.as_str()) && !seen_fields.contains(&field) {
                seen_fields.push(field);
            }
        }
    }

    if seen_fields.is_empty() {
        return Vec::new();
    }

    let range = rule.syntax().text_range();
    let sp = Span::new(path.to_path_buf(), range.start().into(), range.end().into());
    seen_fields
        .into_iter()
        .map(|field| {
            tracing::info!(
                rule = %qualified,
                field = %field,
                kind = ?kind,
                "E0603: rule predicate references a fact no layer provides"
            );
            Diagnostic::error(
                RULE_FACT_UNPROVIDED,
                format!(
                    "rule `{qualified}` references `{var}.{field}`, which no layer \
                     provides for `{kind:?}` entities (known fields: {known:?}); a \
                     predicate referencing an unmodeled fact is a compile error on \
                     the rule, not a deferral"
                ),
            )
            .with_span(LabeledSpan::new(sp.clone(), "rule declared here"))
        })
        .collect()
}

/// The field's value node text, or the empty string when the field has
/// no value (should not happen for a well-formed `demand:`/`advise:`,
/// but this scan is best-effort text matching, not a parser).
fn field_text(field: &Field) -> String {
    field.value().map(|v| v.text().to_string()).unwrap_or_default()
}

/// The leading identifier run of `text` (ASCII alnum/underscore), the
/// base kind word of a `forall ... in <base>...` query before any
/// `.where(...)`/method tail.
fn leading_ident(text: &str) -> String {
    text.chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect()
}

/// Every `<var>.<field>` dotted reference in `text` naming exactly
/// `var` as the receiver, in source order (duplicates included; callers
/// dedupe). Text-only scanning, matching `claims.rs`'s predicate-text
/// stance -- not a general expression parser.
fn dotted_field_refs(text: &str, var: &str) -> Vec<String> {
    let mut refs = Vec::new();
    let prefix = format!("{var}.");
    let mut search_from = 0usize;
    while let Some(rel) = text[search_from..].find(prefix.as_str()) {
        let idx = search_from + rel;
        let before_ok = text[..idx]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_ascii_alphanumeric() && c != '_');
        let field_start = idx + prefix.len();
        let field_end = text[field_start..]
            .find(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
            .map_or(text.len(), |i| field_start + i);
        let field = &text[field_start..field_end];
        if before_ok && !field.is_empty() {
            refs.push(field.to_string());
        }
        search_from = field_end.max(field_start);
    }
    refs
}

#[cfg(test)]
mod tests {
    use super::check_rule_packs;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::{RULE_FACT_UNPROVIDED, RULE_NAME_COLLISION};

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
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }

    #[test]
    fn collision_within_one_pack_is_e0602() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, RULE_NAME_COLLISION);
    }

    #[test]
    fn collision_across_files_is_e0602() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hema", src), parsed("b.hema", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, RULE_NAME_COLLISION);
    }

    #[test]
    fn same_rule_name_different_pack_is_not_a_collision() {
        let src_a = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: true\n";
        let src_b = "process jlc_2l:\n    dfm:\n        rule a:\n            demand: true\n";
        let files = vec![parsed("a.hema", src_a), parsed("b.hema", src_b)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }

    #[test]
    fn forall_over_holes_with_a_known_field_is_clean() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            forall h in holes\n            demand: h.diameter >= 1mm\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }

    #[test]
    fn forall_over_holes_with_an_unprovided_field_is_e0603() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            forall h in holes\n            demand: h.chamfer >= 1mm\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1, "{diags:?}");
        assert_eq!(diags[0].code, RULE_FACT_UNPROVIDED);
        assert!(diags[0].message.contains("h.chamfer"), "{diags:?}");
    }

    #[test]
    fn forall_over_bends_with_a_filter_referencing_an_unprovided_field_is_e0603() {
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            forall b in bends.where(not b.at_free_edge)\n            demand: b.radius >= 1mm\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert_eq!(diags.len(), 1, "{diags:?}");
        assert_eq!(diags[0].code, RULE_FACT_UNPROVIDED);
    }

    #[test]
    fn forall_over_an_unmodeled_kind_is_not_checked() {
        // `nets` has no `known_measure_keys` table yet (WO-29 only
        // documented Hole/Bend) -- absence of a table is not evidence
        // of an unprovided fact, so this stays silent rather than a
        // false positive.
        let src = "process jlc_2l:\n    erc:\n        rule a:\n            forall n in nets\n            demand: n.whatever >= 1\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }

    #[test]
    fn rule_with_no_forall_is_not_checked_by_this_pass() {
        // No domain to classify the field reference against; this is
        // the still-cut shape (E0603 for non-forall rules is out of
        // this dispatch's narrower scope, see the module doc).
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            demand: unprovided_fact_xyz\n";
        let files = vec![parsed("a.hema", src)];
        let diags = check_rule_packs(&files);
        assert!(diags.is_empty(), "unexpected diagnostics: {diags:?}");
    }
}
