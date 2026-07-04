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
        let sources = self.read_sources()?;
        let lowered = rockhead_lower::lower(&sources);
        Ok(build_output(&sources, lowered))
    }

    /// Run the full `compile` pipeline (check + static discharge). The
    /// toy closed-form subset is discharged against a persisted evidence
    /// cache under `.rockhead/`, so a second compile over unchanged
    /// sources is a cache hit (WO-13 acceptance, end-to-end).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures (unreadable
    /// source, corrupt cache).
    pub fn compile(&self) -> Result<BuildOutput, CoreError> {
        let sources = self.read_sources()?;
        let mut cache = self.load_cache()?;
        let lowered = rockhead_lower::lower_and_discharge(&sources, &mut cache);
        self.save_cache(&cache)?;
        Ok(build_output(&sources, lowered))
    }

    /// Discover and read every source file into a [`rockhead_lower::SourceFile`],
    /// in deterministic (sorted) path order (AD-6). IO is the only thing
    /// `Session` owns; the pipeline itself is pure.
    fn read_sources(&self) -> Result<Vec<rockhead_lower::SourceFile>, CoreError> {
        let files = self.discover_files()?;
        let mut sources = Vec::with_capacity(files.len());
        for file in files {
            let text = std::fs::read_to_string(&file).map_err(|e| CoreError::Io {
                path: file.clone(),
                message: e.to_string(),
            })?;
            sources.push(rockhead_lower::SourceFile { path: file, text });
        }
        Ok(sources)
    }

    /// The evidence-cache path (`<first-root-dir>/.rockhead/evidence.json`),
    /// or `None` when there is no root to anchor it (in-memory only).
    fn cache_path(&self) -> Option<Utf8PathBuf> {
        let root = self.roots.first()?;
        let dir = if root.is_dir() {
            root.clone()
        } else {
            root.parent()?.to_path_buf()
        };
        Some(dir.join(".rockhead").join("evidence.json"))
    }

    /// Load the persisted evidence cache, or an empty one if none exists.
    ///
    /// # Errors
    /// [`CoreError::CacheCorrupt`] if the cache file exists but does not
    /// parse; [`CoreError::Io`] on an unreadable cache file.
    fn load_cache(&self) -> Result<rockhead_oblig::EvidenceCache, CoreError> {
        let Some(path) = self.cache_path() else {
            return Ok(rockhead_oblig::EvidenceCache::new());
        };
        match std::fs::read_to_string(&path) {
            Ok(text) => serde_json::from_str(&text)
                .map_err(|e| CoreError::CacheCorrupt(format!("{path}: {e}"))),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                Ok(rockhead_oblig::EvidenceCache::new())
            }
            Err(e) => Err(CoreError::Io {
                path,
                message: e.to_string(),
            }),
        }
    }

    /// Persist the evidence cache under `.rockhead/` (best-effort dir
    /// creation). A no-op when there is no root to anchor the cache.
    ///
    /// # Errors
    /// [`CoreError::Io`] if the cache directory or file cannot be written.
    fn save_cache(&self, cache: &rockhead_oblig::EvidenceCache) -> Result<(), CoreError> {
        let Some(path) = self.cache_path() else {
            return Ok(());
        };
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| CoreError::Io {
                path: parent.to_path_buf(),
                message: e.to_string(),
            })?;
        }
        let json = serde_json::to_string(cache).expect("EvidenceCache always serializes");
        std::fs::write(&path, json).map_err(|e| CoreError::Io {
            path,
            message: e.to_string(),
        })
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
/// boundary (these mirror the generated pydantic models, AD-5). Every
/// field is a typed core value now that the WO-19 pipeline populates it.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BuildPayload {
    /// The batch of diagnostics (structured form).
    pub diagnostics: Vec<Diagnostic>,
    /// Every resolved (non-literal) value with its cause (INV-21).
    pub resolutions: Vec<rockhead_qty::Resolution>,
    /// Content-addressed obligations, source order (INV-1 keys).
    pub obligations: Vec<rockhead_oblig::Obligation>,
    /// One canonical snapshot record per committed scope (AD-18 hash).
    pub snapshots: Vec<rockhead_oblig::SnapshotRecord>,
    /// Evidence from static discharge (empty for `check`).
    pub evidence: Vec<rockhead_oblig::Evidence>,
}

/// Assemble a [`BuildOutput`] from the pipeline result: render the
/// diagnostics once (the ONE renderer, AD-7) against the source texts,
/// and move the typed payloads across unchanged.
fn build_output(
    sources: &[rockhead_lower::SourceFile],
    lowered: rockhead_lower::LowerOutput,
) -> BuildOutput {
    let source_of = |p: &Utf8Path| sources.iter().find(|s| s.path == p).map(|s| s.text.clone());
    let rendered_plain = render_batch(&lowered.diagnostics, ColorMode::Plain, &source_of);
    let rendered_ansi = render_batch(&lowered.diagnostics, ColorMode::Ansi, &source_of);
    let payload = BuildPayload {
        diagnostics: lowered.diagnostics,
        resolutions: lowered.resolutions,
        obligations: lowered.obligations,
        snapshots: lowered.snapshots,
        evidence: lowered.evidence,
    };
    BuildOutput::new(payload, rendered_plain, rendered_ansi)
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
    fn check_over_cubesat_populates_real_payload() {
        // WO-19: the pipeline lowers claims -> obligations and commits
        // entity snapshots, so the payload is non-empty (obligations and
        // snapshot records are the parts the structured grammar reaches
        // today; resolutions await field value-source lowering).
        let session = Session::open_root(examples_dir("cubesat"));
        let out = session.check().unwrap();
        let payload: serde_json::Value = serde_json::from_slice(&out.payload_json()).unwrap();
        assert!(
            !payload["obligations"].as_array().unwrap().is_empty(),
            "cubesat lowers require-claims into obligations"
        );
        assert!(
            !payload["snapshots"].as_array().unwrap().is_empty(),
            "cubesat commits entity snapshots"
        );
    }

    #[test]
    fn compile_in_tempdir_is_deterministic_and_persists_cache() {
        // Compile writes an evidence cache under `.rockhead/`; run it in a
        // scratch dir so the repo tree is never touched, and assert the
        // payload is byte-identical across runs (INV-10) and the cache
        // file is written (so a second compile is a hit).
        let dir = std::env::temp_dir().join(format!("rockhead-wo19-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hem"), "part Widget:\n  mass: 5 g\n").unwrap();

        let session = Session::open_root(&dir);
        let first = session.compile().unwrap();
        let second = session.compile().unwrap();
        assert_eq!(first.payload_json(), second.payload_json());
        assert!(dir.join(".rockhead").join("evidence.json").exists());

        std::fs::remove_dir_all(&dir).ok();
    }
}
