//! The coarse compile API: `Session` and `BuildOutput` (AD-4).
//!
//! Regolith reference: `docs/spec/regolith/06-execution-model.md`. This
//! is the single, pure-Rust surface the PyO3 layer wraps -- one
//! crossing per build. It is fully testable without Python. WO-18
//! grows the real `check`/`compile` surface; WO-01 ships the version
//! and schema-version accessors the smoke test crosses on.

pub mod docextract;
pub mod net_core;
pub mod session;

pub use docextract::doc_extract;
pub use net_core::{check_elec_single_driver, ElecViolation};
pub use session::{BuildOutput, BuildPayload, CoreError, Session};

use camino::Utf8Path;

/// Format source `text` into its canonical spelling (the boundary
/// `format(text) -> text`, AD-4). Thin delegation to the one formatter.
#[must_use]
pub fn format(text: &str) -> String {
    regolith_syntax::formatter::format(text, &camino::Utf8PathBuf::from("<stdin>"))
}

/// Dump an intermediate pipeline stage of `path`'s source as text
/// (`regolith debug tokens|cst|ast|ir`, AD-13). Thin delegation.
///
/// # Errors
/// Returns [`CoreError`] if the source file cannot be read.
///
/// # Panics
/// Panics if `stage` is not one of `tokens`/`cst`/`ast` -- an invalid
/// stage name is a caller (programmer) bug, not a user error, and
/// crosses the FFI as `CoreBug` (AD-4).
pub fn debug_dump(stage: &str, path: &Utf8Path) -> Result<String, CoreError> {
    // An unknown stage name is a caller (programmer) bug, not a user
    // error -- it never reaches CoreError; it panics, which crosses the
    // FFI as `CoreBug` (AD-4).
    let stage = match stage {
        "tokens" => regolith_syntax::debug::Stage::Tokens,
        "cst" => regolith_syntax::debug::Stage::Cst,
        "ast" => regolith_syntax::debug::Stage::Ast,
        other => panic!("unknown debug stage {other:?}: expected tokens|cst|ast"),
    };
    let source = std::fs::read_to_string(path).map_err(|e| CoreError::Io {
        path: path.to_path_buf(),
        message: e.to_string(),
    })?;
    Ok(regolith_syntax::debug::dump(
        stage,
        &source,
        &path.to_path_buf(),
    ))
}

/// Dump the `regolith debug ir` report for the sources at `paths`
/// (WO-42 deliverable 3, AD-25's inspectability item): runs `check()`
/// over the given roots and renders a summary of the compiler's own IR
/// stages (obligation/snapshot/feature-program counts) plus a section
/// listing every realized-domain IR SUPPLIED to the build -- kind,
/// digest, subject -- so a build with realized inputs is inspectable
/// exactly like every other pipeline stage (AD-13). An empty
/// `realized_inputs` renders an explicit "(none supplied)" line rather
/// than an empty section, naming the D128 placeholder path.
///
/// # Errors
/// Returns [`CoreError`] only for infrastructure failures (unreadable
/// source), never for a failing check (AD-7).
///
/// # Panics
/// Never in practice: `BuildOutput::payload_json` always emits our own
/// JSON-safe `BuildPayload` shape, so re-parsing it back can only fail
/// on a programmer bug (a payload/schema drift), worth a panic here.
pub fn debug_ir(
    paths: &[&Utf8Path],
    realized_inputs: &regolith_lower::RealizedInputs,
) -> Result<String, CoreError> {
    use std::fmt::Write as _;

    let session = Session::open_files(paths.iter().map(|p| (*p).to_path_buf()));
    let out = session.check(realized_inputs)?;
    let payload: BuildPayload =
        serde_json::from_slice(&out.payload_json()).expect("BuildOutput payload is valid JSON");

    let mut text = String::new();
    text.push_str("== compiler IR ==\n");
    let _ = writeln!(text, "obligations: {}", payload.obligations.len());
    let _ = writeln!(text, "snapshots: {}", payload.snapshots.len());
    let _ = writeln!(text, "feature_programs: {}", payload.feature_programs.len());
    text.push_str("\n== realized IRs supplied ==\n");
    if realized_inputs.is_empty() {
        text.push_str("(none supplied)\n");
    } else {
        for (digest, input) in realized_inputs {
            let _ = writeln!(
                text,
                "kind={} digest={digest} subject={}",
                input.kind, input.subject
            );
        }
    }
    Ok(text)
}

/// The compiler core version -- the workspace package version, the one
/// truth the Python `regolith.core_version()` smoke test reads back.
#[must_use]
pub fn core_version() -> &'static str {
    let version = env!("CARGO_PKG_VERSION");
    tracing::debug!(version, "core_version requested");
    version
}

/// The serialized-schema version the boundary is speaking (AD-5). The
/// facade asserts this against the generated pydantic models at import.
#[must_use]
pub fn schema_version() -> u32 {
    regolith_oblig::SCHEMA_VERSION
}

/// Every recognized `(extension, language)` pair, read from the ONE
/// registry (`regolith-syntax::extension`, ground rule 6 / AD-14) so
/// `magnetite new` never hard-codes an extension string (WO-41's
/// tripwire). `language` is the lower-case variant name (`"hematite"`,
/// `"cuprite"`, `"fluorite"`).
#[must_use]
pub fn extensions() -> Vec<(&'static str, &'static str)> {
    regolith_syntax::EXTENSIONS
        .iter()
        .map(|&(ext, lang)| {
            let name = match lang {
                regolith_syntax::Language::Hematite => "hematite",
                regolith_syntax::Language::Cuprite => "cuprite",
                regolith_syntax::Language::Fluorite => "fluorite",
                regolith_syntax::Language::Calcite => "calcite",
            };
            (ext, name)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use camino::Utf8PathBuf;

    #[test]
    fn core_version_matches_cargo() {
        assert_eq!(super::core_version(), env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn schema_version_exposed() {
        assert_eq!(
            super::schema_version(),
            regolith_util::canon::SCHEMA_VERSION
        );
    }

    /// WO-42 deliverable 3: `debug ir` lists no realized IRs when none
    /// were supplied (the D128 placeholder path stays honest about it).
    #[test]
    fn debug_ir_reports_no_realized_inputs_when_none_supplied() {
        let dir = std::env::temp_dir().join(format!("regolith-wo42-dbg-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

        let empty = regolith_lower::RealizedInputs::new();
        let file = dir.join("m.hema");
        let text = super::debug_ir(&[file.as_path()], &empty).unwrap();
        assert!(text.contains("(none supplied)"));

        std::fs::remove_dir_all(&dir).ok();
    }

    /// A supplied realized IR is listed with its kind, digest, subject.
    #[test]
    fn debug_ir_lists_every_supplied_realized_input() {
        let dir = std::env::temp_dir().join(format!("regolith-wo42-dbg2-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

        let mut realized = regolith_lower::RealizedInputs::new();
        realized.insert(
            "blake3:aa".to_string(),
            regolith_lower::RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: "Widget".to_string(),
                bytes: vec![1, 2, 3],
            },
        );
        let file = dir.join("m.hema");
        let text = super::debug_ir(&[file.as_path()], &realized).unwrap();
        assert!(text.contains("kind=geometry.realized"));
        assert!(text.contains("digest=blake3:aa"));
        assert!(text.contains("subject=Widget"));

        std::fs::remove_dir_all(&dir).ok();
    }
}
