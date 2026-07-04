//! The coarse compile API: `Session` and `BuildOutput` (AD-4).
//!
//! Substrate reference: `docs/substrate/06-execution-model.md`. This
//! is the single, pure-Rust surface the PyO3 layer wraps -- one
//! crossing per build. It is fully testable without Python. WO-18
//! grows the real `check`/`compile` surface; WO-01 ships the version
//! and schema-version accessors the smoke test crosses on.

pub mod session;

pub use session::{BuildOutput, BuildPayload, CoreError, Session};

/// The compiler core version -- the workspace package version, the one
/// truth the Python `rockhead.core_version()` smoke test reads back.
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
    rockhead_oblig::SCHEMA_VERSION
}

#[cfg(test)]
mod tests {
    #[test]
    fn core_version_matches_cargo() {
        assert_eq!(super::core_version(), env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn schema_version_exposed() {
        assert_eq!(super::schema_version(), 1);
    }
}
