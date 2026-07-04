//! Diagnostic model and the single diagnostic renderer (AD-7).
//!
//! Substrate reference: `docs/substrate/09-build-and-lockfile.md`
//! sec. 4 (batch-emitted diagnostics). There is exactly ONE renderer
//! in the whole toolchain and it lives here (annotate-snippets); the
//! Python side prints returned strings verbatim, never re-renders.
//!
//! WO-06 fills in the real model, codes, and rendering. This file is
//! the WO-01 placeholder that fixes the crate's place in the layering.

use serde::{Deserialize, Serialize};

/// Severity of a diagnostic. User-facing failures are diagnostics
/// (data), not `Err` (AD-7).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// Blocks a successful build.
    Error,
    /// Advisory; does not block.
    Warning,
}

#[cfg(test)]
mod tests {
    use super::Severity;

    #[test]
    fn severity_serializes_snake_case() {
        let json = serde_json::to_string(&Severity::Error).unwrap();
        assert_eq!(json, "\"error\"");
    }
}
