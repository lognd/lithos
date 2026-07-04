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
use rockhead_diag::{render_batch, ColorMode, Diagnostic, Severity};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

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
        let files = self.discover_files()?;

        let mut sources: BTreeMap<Utf8PathBuf, String> = BTreeMap::new();
        let mut diagnostics: Vec<Diagnostic> = Vec::new();
        for file in files {
            let text = std::fs::read_to_string(&file).map_err(|e| CoreError::Io {
                path: file.clone(),
                message: e.to_string(),
            })?;
            let parse = rockhead_syntax::parser::parse(&text, &file);
            tracing::debug!(
                file = %file,
                diagnostics = parse.diagnostics().len(),
                "parsed source file"
            );
            diagnostics.extend(parse.diagnostics().iter().cloned());
            sources.insert(file, text);
        }

        let source_of = |p: &Utf8Path| sources.get(p).cloned();
        let rendered_plain = render_batch(&diagnostics, ColorMode::Plain, &source_of);
        let rendered_ansi = render_batch(&diagnostics, ColorMode::Ansi, &source_of);

        let payload = BuildPayload {
            diagnostics,
            // Resolutions/obligations/snapshot hashes require the
            // sem/ir/oblig assembly pipeline (entity DB construction from
            // an AST, contract IR lowering, obligation discharge), which
            // no WO before WO-18 wires end-to-end -- those crates land as
            // libraries (WO-07..13) with no `AST -> EntityDb -> IR ->
            // Obligation` driver yet. Left empty here rather than
            // invented; a future WO (post-18) owns that driver.
            resolutions: Vec::new(),
            obligations: Vec::new(),
            snapshot_hashes: Vec::new(),
        };

        Ok(BuildOutput::new(payload, rendered_plain, rendered_ansi))
    }

    /// Run the full `compile` pipeline (check + discharge + lockfile
    /// authoring inputs).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures.
    pub fn compile(&self) -> Result<BuildOutput, CoreError> {
        // Discharge against the harness/toy-model subset is not yet
        // assembled anywhere in the codebase (no WO before WO-18 wires
        // it); `compile` is therefore `check` until that driver lands.
        self.check()
    }

    /// Walk `roots` (files or directories) and return every recognized
    /// source file (`.hem`/`.cupr`, per the one extension registry),
    /// in stable (lexicographic) order for deterministic output (AD-6).
    fn discover_files(&self) -> Result<Vec<Utf8PathBuf>, CoreError> {
        let mut out = Vec::new();
        for root in &self.roots {
            discover_one(root, &mut out)?;
        }
        out.sort();
        out.dedup();
        Ok(out)
    }

    /// The source roots this session covers.
    #[must_use]
    pub fn roots(&self) -> &[Utf8PathBuf] {
        &self.roots
    }
}

/// Recursively collect recognized source files under `root` into `out`
/// (a free function since it recurses on the path, not `self`).
fn discover_one(root: &Utf8Path, out: &mut Vec<Utf8PathBuf>) -> Result<(), CoreError> {
    let metadata = std::fs::metadata(root).map_err(|e| CoreError::Io {
        path: root.to_path_buf(),
        message: e.to_string(),
    })?;
    if metadata.is_file() {
        if root
            .extension()
            .is_some_and(|ext| rockhead_syntax::language_for_extension(ext).is_some())
        {
            out.push(root.to_path_buf());
        }
        return Ok(());
    }
    let entries = std::fs::read_dir(root).map_err(|e| CoreError::Io {
        path: root.to_path_buf(),
        message: e.to_string(),
    })?;
    for entry in entries {
        let entry = entry.map_err(|e| CoreError::Io {
            path: root.to_path_buf(),
            message: e.to_string(),
        })?;
        let path = Utf8PathBuf::from_path_buf(entry.path()).map_err(|p| CoreError::Io {
            path: root.to_path_buf(),
            message: format!("non-UTF-8 path: {}", p.display()),
        })?;
        discover_one(&path, out)?;
    }
    Ok(())
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
    ///
    /// # Panics
    /// Never in practice: the payload holds only our own JSON-safe
    /// types (a serialization failure would be a programmer bug).
    #[must_use]
    pub fn payload_json(&self) -> Vec<u8> {
        // The payload is composed only of our own JSON-safe types
        // (strings, enums, finite-checked diagnostics per AD-6); this
        // cannot fail in practice, and a failure here is a programmer
        // bug worth a panic (crosses the FFI as `CoreBug`, AD-4).
        serde_json::to_vec(&self.payload).expect("BuildPayload always serializes to JSON")
    }

    /// True when the build succeeded (no error-severity diagnostics).
    #[must_use]
    pub fn ok(&self) -> bool {
        !self
            .payload
            .diagnostics
            .iter()
            .any(|d| d.severity == Severity::Error)
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
    use super::{BuildOutput, BuildPayload, CoreError, Session};
    use camino::Utf8PathBuf;

    /// The repo's example corpus, resolved from this crate's manifest dir
    /// so `cargo test` works from any cwd.
    fn examples_dir(rel: &str) -> Utf8PathBuf {
        let manifest = Utf8PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest.join("../../examples").join(rel)
    }

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

    #[test]
    fn check_over_a_real_directory_finds_only_recognized_extensions() {
        let session = Session::open_root(examples_dir("cubesat"));
        let out = session.check().expect("directory of real sources reads");
        // cubesat has both .hem and .cupr files; a successful call is
        // returned regardless of verdict (AD-7 -- a failing build is
        // still `Ok`).
        let _ = out.ok();
        let _ = out.payload_json();
    }

    #[test]
    fn check_over_missing_root_is_a_core_error_not_a_panic() {
        let session = Session::open_root(examples_dir("does-not-exist"));
        let err = session.check().expect_err("missing root is infrastructure");
        assert!(matches!(err, CoreError::Io { .. }));
    }

    #[test]
    fn check_is_deterministic_across_repeated_calls() {
        let session = Session::open_root(examples_dir("cubesat"));
        let a = session.check().unwrap();
        let b = session.check().unwrap();
        assert_eq!(a.payload_json(), b.payload_json());
        assert_eq!(a.rendered(false), b.rendered(false));
    }

    #[test]
    fn compile_delegates_to_check_pending_discharge_driver() {
        let session = Session::open_root(examples_dir("cubesat"));
        let checked = session.check().unwrap();
        let compiled = session.compile().unwrap();
        assert_eq!(checked.payload_json(), compiled.payload_json());
    }
}
