//! The coarse compile API: `Session` and `BuildOutput` (AD-4).
//!
//! Regolith reference: `docs/regolith/06-execution-model.md`. This
//! is the single, pure-Rust surface the PyO3 layer wraps -- one
//! crossing per build. It is fully testable without Python. WO-18
//! grows the real `check`/`compile` surface; WO-01 ships the version
//! and schema-version accessors the smoke test crosses on.

pub mod session;

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

#[cfg(test)]
mod tests {
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
}
