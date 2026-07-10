//! `TestDeclPayload`: the design-test lowering surface (WO-83
//! deliverable 2; charter toolchain/37-design-testing.md, D190).
//!
//! Slice A's lowering pass (`regolith_lower::test_decl_lower`, a later
//! module in the same crate) turns every `test <name>:` declaration
//! (grammar/CST landed by deliverable 1: `regolith_syntax::ast::TestDecl`)
//! into this raw, un-elaborated structural record: subject file, name,
//! the scenario block's entries, and the expect block's expectation
//! lines. Nothing here SOLVES anything -- no obligation is built, no
//! value is resolved -- this is only the structure-recorded surface
//! `regolith.orchestrator`'s slice-B runner (a later dispatch) consumes
//! to plan and execute scenario builds. Split per `feature_program`'s
//! precedent: raw spelled text + structural attribution, never a
//! resolved value at this layer.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// One expectation line inside a [`TestDeclPayload`]'s `expect:` block:
/// charter 37 sec. 1 names five forms (`diagnostic`/`verdict`/`value`/
/// `count`/`winner`). Kept as the raw leading word plus the recorded
/// tail text -- exactly what `regolith_syntax::ast::TestExpectCase`
/// exposes -- rather than five distinct typed variants, since slice A
/// does not interpret the tail (that is the slice-B runner's job); an
/// unrecognized `form` is the negative-fixture case, surfaced honestly
/// rather than dropped.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct TestExpectationPayload {
    /// The leading form word (`"diagnostic"`, `"verdict"`, `"value"`,
    /// `"count"`, `"winner"`), or `None` if the line's leading word was
    /// not one of the five recognized forms (still recorded, per
    /// AD-3 -- never silently dropped).
    pub form: Option<String>,
    /// The text after the leading form word (charter 37 sec. 1's
    /// per-form tail: `<CODE> on <subject>`, `<path> = <rhs>`, `<path>
    /// within [lo, hi] [cause <class>]`), unparsed -- the runner
    /// re-tokenizes it per `form`.
    pub tail: Option<String>,
    /// The full expectation line's significant text (comment stripped),
    /// for a diagnostic render or a re-derivation the split fields lose
    /// nothing against.
    pub text: String,
}

/// One `test <name>:` declaration's raw structural surface (WO-83
/// deliverable 2): the scenario's declared entries and the expect
/// block's expectation lines, both un-elaborated. `regolith.orchestrator`
/// resolves `scenario_entries` against the ordinary ladder machinery at
/// scenario-build time (charter 37 sec. 1: "the expert ladder IS the
/// scenario vocabulary" -- no test-only backdoor, so nothing here needs
/// to duplicate ladder semantics).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct TestDeclPayload {
    /// The source file this test was declared in (relative or absolute
    /// per the caller's `Session` roots -- carried verbatim, not
    /// normalized here).
    pub subject_file: String,
    /// The test's declared name (`test spar_gust_case:` -> `"spar_gust_case"`).
    pub name: String,
    /// The `scenario:` block's direct statement lines, in source order
    /// (AD-6): config-axis selections, rung-1 assertions, rung-2 pins,
    /// `seed =`/`budget_evals =`, realized-input refs -- every entry the
    /// shared statement grammar already types, recorded as its
    /// significant header-line text (comment stripped). Empty when no
    /// `scenario:` block was declared (the negative "empty scenario"
    /// fixture).
    pub scenario_entries: Vec<String>,
    /// The `expect:` block's expectation lines, in source order (AD-6).
    /// Empty when no `expect:` block was declared.
    pub expectations: Vec<TestExpectationPayload>,
}
