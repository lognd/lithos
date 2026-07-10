//! The coarse compile API: `Session` and `BuildOutput` (AD-4). One
//! crossing per build; pure Rust, fully testable without Python.
//!
//! Regolith reference: `docs/spec/regolith/06-execution-model.md` and
//! AD-4. A failing build is a SUCCESSFUL call whose `BuildOutput` holds
//! violated/indeterminate results and diagnostics (claims-as-data);
//! only infrastructure errors are `Err` (AD-7). Diagnostics are
//! pre-rendered HERE (the one renderer, AD-7); structured payloads
//! cross as JSON bytes that parse into the generated pydantic models.

use camino::{Utf8Path, Utf8PathBuf};
use regolith_diag::{render_batch, ColorMode, Diagnostic, Severity};
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
    /// `realized_inputs` (WO-42 deliverable 3, AD-25/D128) is the
    /// caller-resolved set of realized-domain IR bytes (digest to bytes
    /// plus kind/subject) for this build; resolving a digest against the
    /// WO-30 content store is the CALLER's IO -- `Session` itself does
    /// no store lookups (AD-17 purity is `lower`'s, not `Session`'s,
    /// but the resolved-content discipline holds here too: this is
    /// content the caller already has in hand, not a store handle).
    /// Pass an empty map for a build with no realized-domain inputs
    /// (the D128 placeholder path).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures (unreadable
    /// file, cache corruption) -- never for a failing check.
    pub fn check(
        &self,
        realized_inputs: &regolith_lower::RealizedInputs,
    ) -> Result<BuildOutput, CoreError> {
        self.check_with_lints(realized_inputs, &regolith_diag::LintConfig::new())
    }

    /// Same as [`Session::check`], applying `magnetite.toml [lints]`
    /// (WO-40 deliverable 4): `lint_config` is the resolved code-name ->
    /// action table (empty means every lint stays at its `Warning`
    /// default -- the no-manifest path).
    ///
    /// # Errors
    /// Same as [`Session::check`].
    pub fn check_with_lints(
        &self,
        realized_inputs: &regolith_lower::RealizedInputs,
        lint_config: &regolith_diag::LintConfig,
    ) -> Result<BuildOutput, CoreError> {
        let sources = self.read_sources()?;
        let lowered =
            regolith_lower::lower_with_lint_config(&sources, realized_inputs, lint_config);
        Ok(build_output(&sources, lowered))
    }

    /// Run the full `compile` pipeline (check + static discharge). The
    /// toy closed-form subset is discharged against a persisted evidence
    /// cache under `.regolith/`, so a second compile over unchanged
    /// sources is a cache hit (WO-13 acceptance, end-to-end).
    ///
    /// `registry_version` is the harness model-registry version
    /// (Python-side, AD-1), threaded into every evidence-cache key so a
    /// model fix/upgrade forces re-verification instead of reusing stale
    /// cached evidence (BE-1/INV-1). `realized_inputs` is the same
    /// caller-resolved realized-domain IR channel `check` takes (WO-42
    /// deliverable 3).
    ///
    /// # Errors
    /// Returns [`CoreError`] only for infrastructure failures (unreadable
    /// source, corrupt cache).
    pub fn compile(
        &self,
        registry_version: &str,
        realized_inputs: &regolith_lower::RealizedInputs,
    ) -> Result<BuildOutput, CoreError> {
        self.compile_with_lints(
            registry_version,
            realized_inputs,
            &regolith_diag::LintConfig::new(),
        )
    }

    /// Same as [`Session::compile`], applying `[lints]` (see
    /// [`Session::check_with_lints`]).
    ///
    /// # Errors
    /// Same as [`Session::compile`].
    pub fn compile_with_lints(
        &self,
        registry_version: &str,
        realized_inputs: &regolith_lower::RealizedInputs,
        lint_config: &regolith_diag::LintConfig,
    ) -> Result<BuildOutput, CoreError> {
        let sources = self.read_sources()?;
        let mut cache = self.load_cache()?;
        let lowered = regolith_lower::lower_and_discharge_with_lint_config(
            &sources,
            &mut cache,
            registry_version,
            realized_inputs,
            lint_config,
        );
        self.save_cache(&cache)?;
        Ok(build_output(&sources, lowered))
    }

    /// Discover and read every source file into a [`regolith_lower::SourceFile`],
    /// in deterministic (sorted) path order (AD-6). IO is the only thing
    /// `Session` owns; the pipeline itself is pure.
    fn read_sources(&self) -> Result<Vec<regolith_lower::SourceFile>, CoreError> {
        let files = self.discover_files()?;
        let mut sources = Vec::with_capacity(files.len());
        for file in files {
            let text = std::fs::read_to_string(&file).map_err(|e| CoreError::Io {
                path: file.clone(),
                message: e.to_string(),
            })?;
            sources.push(regolith_lower::SourceFile { path: file, text });
        }
        Ok(sources)
    }

    /// The evidence-cache path (`<first-root-dir>/.regolith/evidence.json`),
    /// or `None` when there is no root to anchor it (in-memory only).
    fn cache_path(&self) -> Option<Utf8PathBuf> {
        let root = self.roots.first()?;
        let dir = if root.is_dir() {
            root.clone()
        } else {
            root.parent()?.to_path_buf()
        };
        Some(dir.join(".regolith").join("evidence.json"))
    }

    /// Load the persisted evidence cache, or an empty one if none exists.
    ///
    /// # Errors
    /// [`CoreError::CacheCorrupt`] if the cache file exists but does not
    /// parse; [`CoreError::Io`] on an unreadable cache file.
    fn load_cache(&self) -> Result<regolith_oblig::EvidenceCache, CoreError> {
        let Some(path) = self.cache_path() else {
            return Ok(regolith_oblig::EvidenceCache::new());
        };
        match std::fs::read_to_string(&path) {
            Ok(text) => serde_json::from_str(&text)
                .map_err(|e| CoreError::CacheCorrupt(format!("{path}: {e}"))),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                Ok(regolith_oblig::EvidenceCache::new())
            }
            Err(e) => Err(CoreError::Io {
                path,
                message: e.to_string(),
            }),
        }
    }

    /// Persist the evidence cache under `.regolith/` (best-effort dir
    /// creation). A no-op when there is no root to anchor the cache.
    ///
    /// # Errors
    /// [`CoreError::Io`] if the cache directory or file cannot be written.
    fn save_cache(&self, cache: &regolith_oblig::EvidenceCache) -> Result<(), CoreError> {
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
    /// source file (`.hema`/`.cupr`, per the one extension registry),
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
            .is_some_and(|ext| regolith_syntax::language_for_extension(ext).is_some())
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
    pub resolutions: Vec<regolith_qty::Resolution>,
    /// Content-addressed obligations, source order (INV-1 keys).
    pub obligations: Vec<regolith_oblig::Obligation>,
    /// One canonical snapshot record per committed scope (AD-18 hash).
    pub snapshots: Vec<regolith_oblig::SnapshotRecord>,
    /// Evidence from static discharge (empty for `check`).
    pub evidence: Vec<regolith_oblig::Evidence>,
    /// The waiver ledger: every declared `waive` with its basis and
    /// accepted match set (INV-12 audit surface / INV-2 acceptance).
    pub ledger: regolith_oblig::WaiveLedger,
    /// WO-29 deliverable 3: the (partial -- see
    /// `regolith_ir::feature_program`'s module doc) feature program per
    /// declaration whose `then:` claim scopes construct domain features.
    pub feature_programs: Vec<regolith_ir::FeatureProgram>,
    /// WO-29 deliverable 4: the raw capability demand per
    /// `architecture for ...:` resource block (cuprite/05 sec. 2), the
    /// Rust half of the D90 binding-requirement bridge -- Python derives
    /// the `ComponentCandidate` screen from magnetite records.
    pub block_requirements: Vec<regolith_ir::BlockRequirement>,
    /// WO-32 deliverable 4b: every elaborated flownet, by name, in
    /// source order (AD-6). Obligations reference a flownet by content
    /// digest (`PayloadRef{ kind: "flownet", .. }`, D129); the
    /// orchestrator `put`s each of these into the WO-30 payload store
    /// at build time (the FIRST orchestrator `PayloadStore` producer)
    /// so discharge-time `resolve` succeeds. Per D128: an edge whose
    /// realized geometry was available as a compile input carries
    /// concrete extracted params here; an edge without one keeps its
    /// `GeomExtract` placeholder and its obligations stay honestly
    /// indeterminate.
    pub flownets: indexmap::IndexMap<String, regolith_oblig::FlownetPayload>,
    /// WO-33 deliverable 3: one `FieldDatum` ledger entry per `compute`
    /// claim -- the computed-indexed-field datum ledger (regolith/02
    /// sec. 5 precedent: borrow-exempt, referenced by both tracks).
    pub field_datums: Vec<regolith_oblig::FieldDatum>,
    /// WO-34 deliverable 3 (D99): every elaborated `harness:` block, by
    /// name, in source order (AD-6) -- mirrors `flownets`'s convention.
    /// Rule packs / mass budgets read `run.length`/`run.bundle` off
    /// these payloads (AD-22).
    pub harnesses: indexmap::IndexMap<String, regolith_oblig::HarnessPayload>,
    /// WO-48 deliverable 3 (calcite/03 sec. 4): every elaborated
    /// calcite `structure`, by name, in source order (AD-6) -- mirrors
    /// `flownets`/`harnesses`'s convention. Structural obligations
    /// reference a frame by content digest (`PayloadRef{ kind: "frame",
    /// .. }`); the orchestrator `put`s each of these into the WO-30
    /// payload store at build time.
    pub frames: indexmap::IndexMap<String, regolith_oblig::FramePayload>,
    /// WO-61 deliverable 2 (D165/D167): the readable L2 contract-graph
    /// surface (interaction-surface/29 sec. 1.6) -- interfaces/
    /// artifacts by name, matings as labeled edges. Carried unchanged
    /// from `LowerOutput.contract_graph` (AD-17); the `diagram.
    /// contract_graph` producer (WO-61 deliverable 3) is its consumer.
    pub contract_graph: regolith_oblig::ContractGraphPayload,
    /// WO-56 deliverable 3 (D161/D168): every declared `by select(...)`
    /// choice point, subject-keyed (`"<subject>.<interface>"`), in
    /// source order (AD-6) -- mirrors `flownets`/`harnesses`/`frames`'s
    /// convention. `regolith.orchestrator.optimize`'s discrete driver
    /// reads this field as its domain-of-candidates input (charter
    /// `28-optimization.md` sec. 2).
    pub choice_points: indexmap::IndexMap<String, regolith_oblig::ChoicePoint>,
    /// WO-83 deliverable 2 (D190, charter toolchain/37): every `test
    /// <name>:` declaration's raw structural surface, in file then
    /// source order (AD-6). `regolith.orchestrator`'s slice-B runner (a
    /// later dispatch) is this field's consumer.
    pub tests: Vec<regolith_ir::TestDeclPayload>,
}

/// Assemble a [`BuildOutput`] from the pipeline result: render the
/// diagnostics once (the ONE renderer, AD-7) against the source texts,
/// and move the typed payloads across unchanged.
fn build_output(
    sources: &[regolith_lower::SourceFile],
    lowered: regolith_lower::LowerOutput,
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
        ledger: lowered.ledger,
        feature_programs: lowered.feature_programs,
        block_requirements: lowered.block_requirements,
        flownets: lowered.flownets,
        field_datums: lowered.field_datums,
        harnesses: lowered.harnesses,
        frames: lowered.frames,
        contract_graph: lowered.contract_graph,
        choice_points: lowered.choice_points,
        tests: lowered.tests,
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
/// Crosses the FFI as a `regolith.CoreError` exception (AD-4).
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
        let s = Session::open_root("examples/systems/cubesat");
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
        let session = Session::open_root(examples_dir("systems/cubesat"));
        let empty = regolith_lower::RealizedInputs::new();
        let out = session
            .check(&empty)
            .expect("directory of real sources reads");
        // cubesat has both .hema and .cupr files; a successful call is
        // returned regardless of verdict (AD-7 -- a failing build is
        // still `Ok`).
        let _ = out.ok();
        let _ = out.payload_json();
    }

    #[test]
    fn check_over_missing_root_is_a_core_error_not_a_panic() {
        let session = Session::open_root(examples_dir("does-not-exist"));
        let empty = regolith_lower::RealizedInputs::new();
        let err = session
            .check(&empty)
            .expect_err("missing root is infrastructure");
        assert!(matches!(err, CoreError::Io { .. }));
    }

    #[test]
    fn check_is_deterministic_across_repeated_calls() {
        let session = Session::open_root(examples_dir("systems/cubesat"));
        let empty = regolith_lower::RealizedInputs::new();
        let a = session.check(&empty).unwrap();
        let b = session.check(&empty).unwrap();
        assert_eq!(a.payload_json(), b.payload_json());
        assert_eq!(a.rendered(false), b.rendered(false));
    }

    #[test]
    fn check_over_cubesat_populates_real_payload() {
        // WO-19: the pipeline lowers claims -> obligations and commits
        // entity snapshots, so the payload is non-empty (obligations and
        // snapshot records are the parts the structured grammar reaches
        // today; resolutions await field value-source lowering).
        let session = Session::open_root(examples_dir("systems/cubesat"));
        let empty = regolith_lower::RealizedInputs::new();
        let out = session.check(&empty).unwrap();
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
        // Compile writes an evidence cache under `.regolith/`; run it in a
        // scratch dir so the repo tree is never touched, and assert the
        // payload is byte-identical across runs (INV-10) and the cache
        // file is written (so a second compile is a hit).
        let dir = std::env::temp_dir().join(format!("regolith-wo19-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

        let session = Session::open_root(&dir);
        let empty = regolith_lower::RealizedInputs::new();
        let first = session.compile("model-registry@test", &empty).unwrap();
        let second = session.compile("model-registry@test", &empty).unwrap();
        assert_eq!(first.payload_json(), second.payload_json());
        assert!(dir.join(".regolith").join("evidence.json").exists());

        std::fs::remove_dir_all(&dir).ok();
    }

    /// WO-42 deliverable 3: `Session::check`'s `realized_inputs` channel
    /// threads all the way to `regolith-lower::extract` -- a `from=`
    /// edge whose subject matches a supplied realized-geometry input
    /// extracts in-pipeline (D128), where an empty map leaves the same
    /// edge deferred (checked first as the baseline).
    #[test]
    fn check_threads_realized_inputs_to_in_pipeline_extraction() {
        let dir = std::env::temp_dir().join(format!("regolith-wo42-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        let src = "medium Water: liquid\n\
                   \x20   props: registry(potable_water_nist)\n\
                   flownet Loop(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       supply: Pipe(from=line.run) (a -> b)\n\
                   require Margin:\n\
                   \x20   dp: fluids.dp(a -> b) <= 40kPa\n";
        std::fs::write(dir.join("m.fluo"), src).unwrap();
        let session = Session::open_root(&dir);

        let empty = regolith_lower::RealizedInputs::new();
        let deferred = session.check(&empty).unwrap();
        let deferred_json: serde_json::Value =
            serde_json::from_slice(&deferred.payload_json()).unwrap();
        assert!(
            !deferred_json["obligations"].as_array().unwrap().is_empty(),
            "the fluid claim still lowers to an obligation without realized inputs"
        );

        let tube_bytes = serde_json::json!({
            "snapshot_hash": "blake3:snap-tube",
            "paths": {
                "line.run": {
                    "segments": [{
                        "role": "run",
                        "flow_area": [1.0e-4, 1.0e-4],
                        "length": [2.0, 2.0],
                        "roughness_class": "drawn_tube",
                        "elevation_change": [0.3, 0.3],
                        "wall": {"youngs_modulus": [2.0e11, 2.0e11],
                                 "thickness": [1.0e-3, 1.0e-3],
                                 "diameter": [0.02, 0.02]}
                    }]
                }
            }
        })
        .to_string()
        .into_bytes();
        let mut realized = regolith_lower::RealizedInputs::new();
        realized.insert(
            "blake3:tube-digest".to_string(),
            regolith_lower::RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: "line.run".to_string(),
                bytes: tube_bytes,
            },
        );
        let extracted = session.check(&realized).unwrap();
        assert!(extracted.ok(), "check still passes with realized inputs");

        std::fs::remove_dir_all(&dir).ok();
    }
}
