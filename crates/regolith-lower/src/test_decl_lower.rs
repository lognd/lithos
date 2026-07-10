//! Pass (WO-83 deliverable 2; charter toolchain/37-design-testing.md,
//! D190): the design-test lowering surface. Turns every `test <name>:`
//! declaration (`regolith_syntax::ast::TestDecl`, deliverable 1) into a
//! [`TestDeclPayload`] -- subject file, name, the scenario block's
//! direct-statement lines, and the expect block's expectation lines.
//! Nothing here elaborates or solves; this is the raw structural
//! surface `regolith.orchestrator`'s slice-B runner (a later dispatch)
//! consumes to plan and execute scenario builds (charter 37 sec. 1's
//! "the expert ladder IS the scenario vocabulary" -- scenario entries
//! resolve through the ORDINARY ladder machinery at scenario-build
//! time, never a duplicated reading here).

use regolith_ir::{TestDeclPayload, TestExpectationPayload};
use regolith_syntax::ast::{header_line_text, AstNode, File, TestDecl};

use crate::output::ParsedFile;

/// Build every [`TestDeclPayload`] across every file's `test <name>:`
/// declarations, in sorted-file (caller-provided order, AD-6) then
/// source order.
#[must_use]
pub fn build_test_decls(files: &[ParsedFile]) -> Vec<TestDeclPayload> {
    let span = tracing::info_span!("lower.test_decl");
    let _enter = span.enter();

    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for test in file.tests() {
            let payload = build_one(&test, pf.path.as_str());
            tracing::debug!(
                subject_file = %payload.subject_file,
                name = %payload.name,
                scenario_entries = payload.scenario_entries.len(),
                expectations = payload.expectations.len(),
                "design test declaration lowered"
            );
            out.push(payload);
        }
    }
    out
}

/// One `TestDecl`'s payload: name + subject file + its scenario/expect
/// entries, each read back off the typed AST views deliverable 1 built.
fn build_one(test: &TestDecl, subject_file: &str) -> TestDeclPayload {
    let name = test.name().unwrap_or_default();
    let scenario_entries = test
        .scenario()
        .map(|s| {
            s.syntax()
                .children()
                .map(|c| header_line_text(&c))
                .filter(|l| !l.is_empty())
                .collect()
        })
        .unwrap_or_default();
    let expectations = test
        .expect()
        .map(|e| {
            e.cases()
                .into_iter()
                .map(|case| TestExpectationPayload {
                    form: case.form(),
                    tail: case.tail(),
                    text: case.text(),
                })
                .collect()
        })
        .unwrap_or_default();
    TestDeclPayload {
        subject_file: subject_file.to_string(),
        name,
        scenario_entries,
        expectations,
    }
}
