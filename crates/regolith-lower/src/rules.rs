//! Rule-pack static checks (WO-28 partial): the checks that need only
//! the typed `RuleDecl` CST plus the [`EntityKind`] measure vocabulary,
//! not full query-engine matching or demand-expression evaluation.
//!
//! Regolith reference: `docs/spec/toolchain/21-rule-packs.md` sec. 3
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
//! - [`codes::RULE_VIOLATION`] (E0601) from [`evaluate_static_rules`]:
//!   every ATTACHED rule evaluated over the consuming declaration's
//!   committed entities through the shared engine
//!   (`crate::rule_engine`); a failing `demand:` is an error carrying
//!   `pack.rule` provenance plus the `why:`/`per:` text, a failing
//!   `advise:` is a warning (verdict-inert, D-B), and an unevaluable
//!   rule DEFERS (an outcome `claims.rs` lowers to an indeterminate
//!   obligation naming the blocking fact -- never a silent skip).
//!
//! E0604 (stale resolver) lives in `entities.rs`, where `resolves:`
//! runs and the pre-resolution free-ness is still observable. E0603
//! here stays deliberately narrow (dotted-field-reference scanning,
//! matching the text-based-predicate stance
//! `claims.rs::extract_projection_heads` already takes).

use std::collections::BTreeMap;

use regolith_diag::codes::{RULE_FACT_UNPROVIDED, RULE_NAME_COLLISION, RULE_VIOLATION};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::EntityKind;
use regolith_syntax::ast::{AstNode, Field, File, RuleDecl};

use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;
use crate::rule_engine::{evaluate_rules_for_decl, PackIndex, RuleEvaluation};

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
    field
        .value()
        .map(|v| v.text().to_string())
        .unwrap_or_default()
}

/// The leading identifier run of `text` (ASCII alnum/underscore), the
/// base kind word of a `forall ... in <base>...` query before any
/// `.where(...)`/method tail.
fn leading_ident(text: &str) -> String {
    text.chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect()
}

/// Evaluate every attached rule over every consuming declaration's
/// committed entity scope (the D-E static tier), returning the E0601
/// diagnostics (error for `demand:`, warning for `advise:`) plus the
/// full per-rule outcomes for `claims.rs` to lower into obligations
/// (violated AND deferred -- the release gate and waive machinery see
/// both). File-then-source order (AD-6).
#[must_use]
pub fn evaluate_static_rules(
    files: &[ParsedFile],
    snapshots: &EntitySnapshots,
) -> (Vec<Diagnostic>, Vec<RuleEvaluation>) {
    let span = tracing::info_span!("lower.checks.rules.eval");
    let _enter = span.enter();

    let index = PackIndex::build(files);
    let mut diagnostics = Vec::new();
    let mut outcomes = Vec::new();
    if index.is_empty() {
        return (diagnostics, outcomes);
    }

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            if decl.process_name().is_some() {
                // A pack does not consume itself.
                continue;
            }
            let Some(decl_name) = decl.name() else {
                continue;
            };
            let entities = snapshots.scopes.get(&decl_name);
            let evals = evaluate_rules_for_decl(&decl, &decl_name, &pf.path, entities, &index);
            for eval in &evals {
                diagnostics.extend(violation_diagnostics(eval));
            }
            outcomes.extend(evals);
        }
    }

    tracing::info!(
        diagnostics = diagnostics.len(),
        outcomes = outcomes.len(),
        "static rule evaluation complete"
    );
    (diagnostics, outcomes)
}

/// The E0601 diagnostics for one rule evaluation: one per violating
/// match, rendering the rule's `why:` explanation and `per:` citation
/// (D-H: the expert's provenance survives into the error message).
/// `advise:` rules render as warnings and stay verdict-inert.
fn violation_diagnostics(eval: &RuleEvaluation) -> Vec<Diagnostic> {
    use std::fmt::Write as _;

    let rule = &eval.rule;
    let is_advise = rule.demand.is_none() && rule.advise.is_some();
    eval.violations
        .iter()
        .map(|(origin, detail, _margin)| {
            let mut message = format!(
                "rule `{}` {} on `{}`: {}",
                rule.qualified(),
                if is_advise {
                    "advises against"
                } else {
                    "violated"
                },
                origin,
                detail,
            );
            if let Some(why) = &rule.why {
                let _ = write!(message, " -- {why}");
            }
            if let Some(per) = &rule.per {
                let _ = write!(message, " [per: {per}]");
            }
            tracing::info!(
                rule = %rule.qualified(),
                subject = %eval.decl_name,
                entity = %origin,
                advise = is_advise,
                "E0601: rule violation"
            );
            let decl_sp = Span::new(eval.decl_file.clone(), eval.decl_range.0, eval.decl_range.1);
            let rule_sp = Span::new(rule.file.clone(), rule.range.0, rule.range.1);
            let diag = if is_advise {
                Diagnostic::warning(RULE_VIOLATION, message)
            } else {
                Diagnostic::error(RULE_VIOLATION, message)
            };
            diag.with_span(LabeledSpan::new(decl_sp, "violating design declared here"))
                .with_span(LabeledSpan::new(rule_sp, "rule declared here"))
        })
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
        // `at_free_edge` joined the Bend vocabulary (the reference
        // pack's relief rule), so the unknown field here is a typo-like
        // `at_free_edg` -- the check guards spelling, not the filter.
        let src = "process sheet_metal:\n    dfm:\n        rule a:\n            forall b in bends.where(not b.at_free_edg)\n            demand: b.radius >= 1mm\n";
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

#[cfg(test)]
mod eval_tests {
    use super::evaluate_static_rules;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::RULE_VIOLATION;
    use regolith_diag::Severity;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    const PACK: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            why: \"press pack minimum inside radius\"\n            per: \"press pack table\"\n";

    #[test]
    fn violated_attached_rule_is_e0601_with_provenance() {
        let src = format!(
            "{PACK}part p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=1mm)\n"
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let (diags, outcomes) = evaluate_static_rules(&files, &snaps);
        let violation = diags
            .iter()
            .find(|d| d.code == RULE_VIOLATION)
            .expect("E0601 fired");
        assert_eq!(violation.severity, Severity::Error);
        assert!(
            violation.message.contains("sheet_metal.min_bend_radius"),
            "{}",
            violation.message
        );
        assert!(
            violation
                .message
                .contains("press pack minimum inside radius"),
            "why: rendered: {}",
            violation.message
        );
        assert!(
            violation.message.contains("per: press pack table"),
            "per: rendered: {}",
            violation.message
        );
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].violations.len(), 1);
    }

    #[test]
    fn satisfied_attached_rule_is_silent_and_a_clean_pass() {
        let src = format!(
            "{PACK}part p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=3mm)\n"
        );
        let files = parsed(&src);
        let snaps = build_entities(&files);
        let (diags, outcomes) = evaluate_static_rules(&files, &snaps);
        assert!(diags.is_empty(), "{diags:?}");
        assert_eq!(outcomes.len(), 1);
        assert!(outcomes[0].is_clean_pass(), "{outcomes:?}");
    }

    #[test]
    fn resolved_free_value_passes_its_own_resolving_rule() {
        // The resolves: pass pins radius=free at the bound BEFORE the
        // static evaluation runs, so the same rule then passes -- the
        // corpus's flagship path end to end within the lower passes.
        let src = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            resolves: b.radius from free\n            why: \"press pack minimum inside radius\"\npart p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake(sheet_metal), from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=free)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let (diags, outcomes) = evaluate_static_rules(&files, &snaps);
        assert!(diags.is_empty(), "{diags:?}");
        assert!(outcomes[0].is_clean_pass(), "{outcomes:?}");
    }

    #[test]
    fn unquantified_false_demand_fires_e0601() {
        // The negative corpus's fixture-35 shape: an unquantified rule
        // evaluated once per consuming decl.
        let src = "process sheet_metal:\n    dfm:\n        rule min_web:\n            demand: false\npart p:\n    material: AISI_304\n    stage cut: process=sheet_metal\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let (diags, _) = evaluate_static_rules(&files, &snaps);
        assert!(diags.iter().any(|d| d.code == RULE_VIOLATION), "{diags:?}");
    }

    #[test]
    fn advise_violation_is_a_warning_not_an_error() {
        let src = "process sheet_metal:\n    dfm:\n        rule soft_hint:\n            advise: false\npart p:\n    stage cut: process=sheet_metal\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let (diags, _) = evaluate_static_rules(&files, &snaps);
        let d = diags.iter().find(|d| d.code == RULE_VIOLATION).unwrap();
        assert_eq!(d.severity, Severity::Warning);
    }

    #[test]
    fn unpopulated_domain_defers_never_vacuously_passes() {
        // INV-29's honest-deferral half: `nets` carries no populated
        // entities today, so the rule DEFERS (an outcome claims.rs
        // lowers), never a silent empty-match pass.
        let src = "process jlc_2l:\n    erc:\n        rule fanout:\n            forall n in nets\n            demand: sum(n.loads.i) <= n.driver.i\npart ctrl:\n    stage bare: process=pcb_fab(jlc_2l)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let (diags, outcomes) = evaluate_static_rules(&files, &snaps);
        assert!(diags.is_empty(), "deferral is not a diagnostic: {diags:?}");
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].deferrals.len(), 1, "{outcomes:?}");
    }
}
