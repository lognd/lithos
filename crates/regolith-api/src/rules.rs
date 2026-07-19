//! The `regolith rules test|try` API surface (WO-28 deliverable 5,
//! AD-4: one pure-Rust function per CLI verb; the PyO3 layer is
//! marshalling only). Both return a deterministic JSON report string
//! -- stdout is data, rendering is the CLI's job, and the golden suite
//! freezes the JSON.
//!
//! Regolith reference: `docs/implementation/design/21-rule-packs.md`
//! D-H (the expert authoring loop): `rules test` runs every rule's
//! `expect:` fixtures (a rule missing a pass or fail case is a lint
//! warning); `rules try` runs ONE pack against one design -- every
//! match, verdict, and near-miss margin -- with no build.

use camino::{Utf8Path, Utf8PathBuf};
use regolith_lower::rule_engine::{
    evaluate_pack_for_decl, run_expect_cases, CaseOutcome, PackIndex,
};
use regolith_lower::{parse_sources, SourceFile};
use serde::Serialize;

use crate::CoreError;

/// One `expect:` case's JSON row.
#[derive(Debug, Serialize)]
struct CaseRow {
    rule: String,
    expected: String,
    fixture: String,
    /// `ok` | `wrong_verdict` | `not_evaluable`.
    outcome: String,
    /// The observed detail / blocking reason, when not `ok`.
    detail: Option<String>,
}

/// The `rules test` JSON report.
#[derive(Debug, Serialize)]
struct TestReport {
    pack: String,
    ok: bool,
    cases: Vec<CaseRow>,
    lints: Vec<String>,
}

/// One `rules try` match row.
#[derive(Debug, Serialize)]
struct TryRow {
    rule: String,
    subject: String,
    entity: String,
    /// `pass` | `violated` | `deferred`.
    verdict: String,
    /// The evaluated `lhs op rhs` detail, or the blocking fact.
    detail: String,
    /// Relative margin to the bound, when evaluated.
    margin: Option<f64>,
    /// True for a PASSING match within 20% of its limit (the
    /// projector-friendly conversation starter, guide sec. 3).
    near_miss: bool,
}

/// The `rules try` JSON report.
#[derive(Debug, Serialize)]
struct TryReport {
    pack: String,
    design: Vec<String>,
    matches: Vec<TryRow>,
}

/// Margin fraction under which a passing match is a near miss.
const NEAR_MISS_MARGIN: f64 = 0.20;

/// Read and parse `paths` into the lowering pipeline's input shape.
fn read_sources(paths: &[Utf8PathBuf]) -> Result<Vec<SourceFile>, CoreError> {
    paths
        .iter()
        .map(|path| {
            std::fs::read_to_string(path)
                .map(|text| SourceFile {
                    path: path.clone(),
                    text,
                })
                .map_err(|e| CoreError::Io {
                    path: path.clone(),
                    message: e.to_string(),
                })
        })
        .collect()
}

/// Run every pack's `expect:` fixtures in `paths` (the `rules test`
/// verb). Returns a JSON array with one [`TestReport`] per pack, in
/// file-then-source order.
///
/// # Errors
/// [`CoreError::Io`] when a path cannot be read. A failing fixture is
/// DATA in the report (`ok: false`), never an error (AD-7).
///
/// # Panics
/// Never in practice: serializing our own report shape cannot fail.
// frob:doc docs/modules/regolith-api.md#rule-pack-test-and-try-verbs
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn rules_test(paths: &[Utf8PathBuf]) -> Result<String, CoreError> {
    let span = tracing::info_span!("rules.test", files = paths.len());
    let _enter = span.enter();

    let sources = read_sources(paths)?;
    let parsed = parse_sources(&sources);
    let index = PackIndex::build(&parsed);

    let mut reports = Vec::new();
    for pack in index.iter() {
        let run = run_expect_cases(pack);
        let cases = run
            .cases
            .iter()
            .map(|c| {
                let (outcome, detail) = match &c.outcome {
                    CaseOutcome::Ok => ("ok".to_string(), None),
                    CaseOutcome::WrongVerdict { observed } => {
                        ("wrong_verdict".to_string(), Some(observed.clone()))
                    }
                    CaseOutcome::NotEvaluable { reason } => {
                        ("not_evaluable".to_string(), Some(reason.clone()))
                    }
                };
                CaseRow {
                    rule: c.rule.clone(),
                    expected: c.expected.clone(),
                    fixture: c.fixture.clone(),
                    outcome,
                    detail,
                }
            })
            .collect();
        tracing::info!(
            pack = %pack.name,
            ok = run.ok(),
            cases = run.cases.len(),
            lints = run.lints.len(),
            "rules test complete for pack"
        );
        reports.push(TestReport {
            pack: pack.name.clone(),
            ok: run.ok(),
            cases,
            lints: run.lints.clone(),
        });
    }

    Ok(serde_json::to_string_pretty(&reports).expect("own report shape serializes"))
}

/// Run ONE pack against one design file (the `rules try` verb):
/// attachment is FORCED (that is the point of try -- no build, no
/// `process=` edit needed), every rule evaluates over every design
/// declaration's committed entities, and each match reports its
/// verdict, detail, and near-miss margin.
///
/// # Errors
/// [`CoreError::Io`] when a path cannot be read.
///
/// # Panics
/// Never in practice: serializing our own report shape cannot fail.
// frob:doc docs/modules/regolith-api.md#rule-pack-test-and-try-verbs
pub fn rules_try(pack_path: &Utf8Path, design_path: &Utf8Path) -> Result<String, CoreError> {
    let span = tracing::info_span!("rules.try", pack = %pack_path, design = %design_path);
    let _enter = span.enter();

    let pack_sources = read_sources(&[pack_path.to_path_buf()])?;
    let design_sources = read_sources(&[design_path.to_path_buf()])?;
    let pack_parsed = parse_sources(&pack_sources);
    let design_parsed = parse_sources(&design_sources);

    let index = PackIndex::build(&pack_parsed);
    let snapshots = regolith_lower::entities::build_entities(&design_parsed);

    let mut matches = Vec::new();
    let mut pack_names = Vec::new();
    for pack in index.iter() {
        pack_names.push(pack.name.clone());
        for pf in &design_parsed {
            use regolith_syntax::ast::AstNode as _;
            let Some(file) = regolith_syntax::ast::File::cast(pf.parse.syntax()) else {
                continue;
            };
            for decl in file.decls() {
                if regolith_lower::entities::decl_is_poisoned(&decl) {
                    continue;
                }
                if decl.process_name().is_some() {
                    continue;
                }
                let Some(decl_name) = decl.name() else {
                    continue;
                };
                let entities = snapshots.scopes.get(&decl_name);
                for eval in evaluate_pack_for_decl(pack, &decl, &decl_name, &pf.path, entities) {
                    for (entity, detail, margin) in &eval.passes {
                        matches.push(TryRow {
                            rule: eval.rule.qualified(),
                            subject: decl_name.clone(),
                            entity: entity.clone(),
                            verdict: "pass".to_string(),
                            detail: detail.clone(),
                            margin: *margin,
                            near_miss: margin.is_some_and(|m| m <= NEAR_MISS_MARGIN),
                        });
                    }
                    for (entity, detail, margin) in &eval.violations {
                        matches.push(TryRow {
                            rule: eval.rule.qualified(),
                            subject: decl_name.clone(),
                            entity: entity.clone(),
                            verdict: "violated".to_string(),
                            detail: detail.clone(),
                            margin: *margin,
                            near_miss: false,
                        });
                    }
                    for (entity, fact) in &eval.deferrals {
                        matches.push(TryRow {
                            rule: eval.rule.qualified(),
                            subject: decl_name.clone(),
                            entity: entity.clone(),
                            verdict: "deferred".to_string(),
                            detail: fact.clone(),
                            margin: None,
                            near_miss: false,
                        });
                    }
                }
            }
        }
    }

    tracing::info!(matches = matches.len(), "rules try complete");
    let report = TryReport {
        pack: pack_names.join(", "),
        design: vec![design_path.to_string()],
        matches,
    };
    Ok(serde_json::to_string_pretty(&report).expect("own report shape serializes"))
}

#[cfg(test)]
mod tests {
    use super::{rules_test, rules_try};
    use camino::Utf8PathBuf;

    const PACK: &str = "process sheet_metal:\n    capability:\n        min_bend_ratio: 1.6\n    dfm:\n        rule min_bend_radius:\n            forall b in bends\n            demand: b.radius >= capability.min_bend_ratio * sheet\n            why: \"press pack minimum inside radius\"\n            expect:\n                pass: bend(radius=2.4mm, sheet=1.5mm)\n                fail: bend(radius=1.0mm, sheet=1.5mm)\n";

    const DESIGN: &str = "part p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n    stage formed: process=press_brake, from=cut\n        flange = Bend(edge=cut.top, angle=90deg, radius=2.5mm)\n";

    fn write_temp(name: &str, text: &str) -> Utf8PathBuf {
        let dir = std::env::temp_dir().join("regolith-rules-api-tests");
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join(name);
        std::fs::write(&path, text).unwrap();
        Utf8PathBuf::from_path_buf(path).unwrap()
    }

    // frob:tests crates/regolith-api/src/rules.rs::rules_test kind="unit"
    #[test]
    fn rules_test_reports_green_fixtures() {
        let path = write_temp("pack_green.hema", PACK);
        let json = rules_test(&[path]).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(v[0]["pack"], "sheet_metal");
        assert_eq!(v[0]["ok"], true, "{json}");
        assert_eq!(v[0]["cases"].as_array().unwrap().len(), 2);
    }

    #[test]
    fn rules_try_reports_forced_matches_with_margins() {
        let pack = write_temp("pack_try.hema", PACK);
        let design = write_temp("design_try.hema", DESIGN);
        let json = rules_try(&pack, &design).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();
        let matches = v["matches"].as_array().unwrap();
        assert_eq!(matches.len(), 1, "{json}");
        assert_eq!(matches[0]["verdict"], "pass");
        assert_eq!(
            matches[0]["near_miss"], true,
            "2.5mm vs a 2.4mm limit is a near miss: {json}"
        );
    }

    #[test]
    fn unreadable_path_is_an_io_error_value() {
        let missing = Utf8PathBuf::from("/nonexistent/definitely/not/here.hema");
        assert!(rules_test(&[missing]).is_err());
    }
}
