//! The coarse compile API: `Session` and `BuildOutput` (AD-4). One
//! crossing per build; pure Rust, fully testable without Python.
//!
//! Substrate reference: `docs/substrate/06-execution-model.md` and
//! AD-4. A failing build is a SUCCESSFUL call whose `BuildOutput` holds
//! violated/indeterminate results and diagnostics (claims-as-data);
//! only infrastructure errors are `Err` (AD-7). Diagnostics are
//! pre-rendered HERE (the one renderer, AD-7); structured payloads
//! cross as JSON bytes that parse into the generated pydantic models.

use camino::{Utf8Path, Utf8PathBuf};
use rockhead_diag::Diagnostic;
use serde::{Deserialize, Serialize};

/// A compile session over a project root or explicit file set. Opening
/// a session does no work; `check`/`compile` do.
#[derive(Debug, Clone)]
pub struct Session {
    roots: Vec<Utf8PathBuf>,
}

impl Session {
    /// Open a session over a project root directory.
    #[must_use]
    pub fn open_root(root: impl Into<Utf8PathBuf>) -> Session {
        Session {
            roots: vec![root.into()],
        }
    }

    /// Open a session over an explicit set of source files.
    #[must_use]
    pub fn open_files(files: impl IntoIterator<Item = Utf8PathBuf>) -> Session {
        Session {
            roots: files.into_iter().collect(),
        }
    }

    /// Run the static `check` pipeline (parse -> sem -> ir -> obligation
    /// construction, no discharge). Returns a `BuildOutput`; a failing
    /// check is a successful call (AD-7).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures (unreadable
    /// file, cache corruption) -- never for a failing check.
    pub fn check(&self) -> Result<BuildOutput, CoreError> {
        todo!("STUB WO-18: discover+parse roots, run the sem/ir passes, collect diagnostics + payloads")
    }

    /// Run the full `compile` pipeline (check + discharge + lockfile
    /// authoring inputs).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures.
    pub fn compile(&self) -> Result<BuildOutput, CoreError> {
        todo!("STUB WO-18: check() then discharge the toy-model subset; assemble resolutions")
    }

    /// The source roots this session covers.
    #[must_use]
    pub fn roots(&self) -> &[Utf8PathBuf] {
        &self.roots
    }
}

/// The structured payloads a build emits, serialized to JSON for the
/// boundary (these mirror the generated pydantic models, AD-5).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BuildPayload {
    /// The batch of diagnostics (structured form).
    pub diagnostics: Vec<Diagnostic>,
    /// Resolution rows (value + cause), as JSON values.
    pub resolutions: Vec<serde_json::Value>,
    /// Obligations produced, as JSON values.
    pub obligations: Vec<serde_json::Value>,
    /// Snapshot content hashes, in order.
    pub snapshot_hashes: Vec<String>,
}

/// The result of a build: pre-rendered diagnostics, structured payload,
/// and scalar verdicts. Handed across the FFI as one object.
#[derive(Debug, Clone)]
pub struct BuildOutput {
    payload: BuildPayload,
    rendered_plain: String,
    rendered_ansi: String,
}

impl BuildOutput {
    /// Construct a build output from its parts (the pipeline builds
    /// this; tests build it directly).
    #[must_use]
    pub fn new(
        payload: BuildPayload,
        rendered_plain: String,
        rendered_ansi: String,
    ) -> BuildOutput {
        BuildOutput {
            payload,
            rendered_plain,
            rendered_ansi,
        }
    }

    /// The diagnostics rendered to text (the ONE renderer, AD-7). Python
    /// prints this verbatim.
    #[must_use]
    pub fn rendered(&self, ansi: bool) -> &str {
        if ansi {
            &self.rendered_ansi
        } else {
            &self.rendered_plain
        }
    }

    /// The structured payload as JSON bytes (parses into pydantic on the
    /// Python side).
    #[must_use]
    pub fn payload_json(&self) -> Vec<u8> {
        todo!("STUB WO-18: serde_json::to_vec of the payload (the boundary interchange bytes)")
    }

    /// True when the build succeeded (no error-severity diagnostics).
    #[must_use]
    pub fn ok(&self) -> bool {
        todo!("STUB WO-18: no error-severity diagnostic in payload.diagnostics")
    }

    /// Number of diagnostics.
    #[must_use]
    pub fn diagnostic_count(&self) -> usize {
        self.payload.diagnostics.len()
    }
}

/// An infrastructure error at the API boundary (NOT a failing build).
/// Crosses the FFI as a `rockhead.CoreError` exception (AD-4).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CoreError {
    /// A source file or root could not be read.
    Io {
        /// The path that failed.
        path: Utf8PathBuf,
        /// The OS-level message.
        message: String,
    },
    /// The evidence cache was unreadable or corrupt.
    CacheCorrupt(String),
}

impl CoreError {
    /// The path this error concerns, if any.
    #[must_use]
    pub fn path(&self) -> Option<&Utf8Path> {
        match self {
            CoreError::Io { path, .. } => Some(path.as_path()),
            CoreError::CacheCorrupt(_) => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{BuildOutput, BuildPayload, Session};

    #[test]
    fn session_records_roots() {
        let s = Session::open_root("examples/cubesat");
        assert_eq!(s.roots().len(), 1);
    }

    #[test]
    fn build_output_exposes_rendered_and_count() {
        let out = BuildOutput::new(
            BuildPayload::default(),
            "plain".to_string(),
            "ansi".to_string(),
        );
        assert_eq!(out.rendered(false), "plain");
        assert_eq!(out.rendered(true), "ansi");
        assert_eq!(out.diagnostic_count(), 0);
    }
}
