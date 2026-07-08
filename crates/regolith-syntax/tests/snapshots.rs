//! insta snapshots for the front-end (AD-11): CST/AST dumps, token
//! streams, diagnostics, and formatter output over representative corpus
//! files. Review drift with `make snapshots` (cargo insta review); these
//! are the human-readable companion to the byte-hashed golden corpus.

use std::path::PathBuf;

use camino::Utf8PathBuf;
use regolith_syntax::debug::{dump, Stage};
use regolith_syntax::formatter::format;
use regolith_syntax::parser::parse;

/// Read one corpus source file by its workspace-relative path.
fn corpus(rel: &str) -> (String, Utf8PathBuf) {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("crates/regolith-syntax is two levels under the workspace root")
        .to_path_buf();
    let text = std::fs::read_to_string(root.join(rel))
        .unwrap_or_else(|e| panic!("readable corpus file {rel}: {e}"));
    (text, Utf8PathBuf::from(rel))
}

/// Representative slice of the corpus: one mechanical file, one
/// electrical file, and the Kestrel integration file -- kept small so
/// the snapshot set stays reviewable (AD-11).
const REPRESENTATIVE: &[&str] = &[
    "examples/tracks/hematite/gear_reducer.hema",
    "examples/tracks/cuprite/buck_converter.cupr",
    "examples/systems/cubesat/kestrel.cupr",
];

#[test]
fn snapshot_tokens() {
    for rel in REPRESENTATIVE {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("tokens", dump(Stage::Tokens, &source, &file));
        });
    }
}

#[test]
fn snapshot_cst() {
    for rel in REPRESENTATIVE {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("cst", dump(Stage::Cst, &source, &file));
        });
    }
}

#[test]
fn snapshot_ast() {
    for rel in REPRESENTATIVE {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("ast", dump(Stage::Ast, &source, &file));
        });
    }
}

#[test]
fn snapshot_formatter() {
    for rel in REPRESENTATIVE {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("format", format(&source, &file));
        });
    }
}

/// Representative process-pack fixtures (WO-28 deliverable 2): the
/// rule grammar over one mech pack (dfm, resolves-from-free, expect)
/// and one elec pack (current-driven erc + realized-fact drc).
/// Deliberately NOT under `examples/` -- the golden corpus is a build
/// input, and the in-corpus reference packs are the engine wave's
/// deliverable 6.
const RULE_PACK_FIXTURES: &[&str] = &[
    "crates/regolith-syntax/tests/fixtures/process_pack.hema",
    "crates/regolith-syntax/tests/fixtures/process_pack.cupr",
];

#[test]
fn snapshot_rule_pack_cst() {
    for rel in RULE_PACK_FIXTURES {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("cst", dump(Stage::Cst, &source, &file));
        });
    }
}

#[test]
fn snapshot_rule_pack_ast() {
    for rel in RULE_PACK_FIXTURES {
        let (source, file) = corpus(rel);
        insta::with_settings!({ snapshot_suffix => rel.replace(['/', '.'], "_") }, {
            insta::assert_snapshot!("ast", dump(Stage::Ast, &source, &file));
        });
    }
}

#[test]
fn snapshot_diagnostics() {
    // A deliberately broken source exercises the diagnostic renderer path
    // (AD-7): the parse still yields a tree, and the diagnostics are data.
    let file = Utf8PathBuf::from("broken.cupr");
    let source = "component Widget\n  value = = 3\n\tbad_tab = 1\n";
    let parse = parse(source, &file);
    let rendered: Vec<String> = parse
        .diagnostics()
        .iter()
        .map(|d| format!("{d:?}"))
        .collect();
    insta::assert_snapshot!("diagnostics_broken", rendered.join("\n"));
}
