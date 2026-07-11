//! The pipeline's input/output surface: source files in, parsed files
//! and the assembled build payload out.
//!
//! Regolith reference: `docs/spec/regolith/06`, `docs/spec/regolith/07` sec.
//! 2. `LowerOutput` is the pure-Rust, no-IO shape `regolith-api` wraps
//! into `BuildPayload` (AD-17).

use camino::Utf8PathBuf;
use indexmap::IndexMap;
use regolith_diag::Diagnostic;
use regolith_ir::{BlockRequirement, FeatureProgram, TestDeclPayload};
use regolith_oblig::{
    ChoicePoint, ContractGraphPayload, Evidence, FieldDatum, FlownetPayload, FramePayload,
    HarnessPayload, Obligation, SnapshotRecord, WaiveLedger,
};
use regolith_qty::Resolution;
use regolith_sem::ConverterGraph;
use regolith_syntax::Parse;

/// One source file's path and raw text, as read by `Session` (IO stays
/// there; this crate is pure).
#[derive(Debug, Clone)]
pub struct SourceFile {
    /// The file's path (used for diagnostics and stable ordering).
    pub path: Utf8PathBuf,
    /// The file's raw text.
    pub text: String,
}

/// A parsed source file: its path and the resulting CST + parse
/// diagnostics.
#[derive(Debug, Clone)]
pub struct ParsedFile {
    /// The file's path.
    pub path: Utf8PathBuf,
    /// The parse result (CST + diagnostics).
    pub parse: Parse,
}

/// The pipeline's total output: every diagnostic, resolution,
/// obligation, snapshot record, and (compile only) evidence produced
/// across all six passes, in deterministic order (AD-6).
#[derive(Debug, Clone, Default)]
pub struct LowerOutput {
    /// Diagnostics from every pass, in pass order then source order.
    pub diagnostics: Vec<Diagnostic>,
    /// Every resolution produced (Cause-typed, INV-21).
    pub resolutions: Vec<Resolution>,
    /// Every obligation produced (one per claim/sweep-point, INV-1).
    pub obligations: Vec<Obligation>,
    /// One snapshot record per committed `EntityDb` scope.
    pub snapshots: Vec<SnapshotRecord>,
    /// Evidence from static discharge (empty for `check`, populated for
    /// `compile`).
    pub evidence: Vec<Evidence>,
    /// The waiver ledger: every declared `waive` with its basis and
    /// accepted match set (the INV-12 audit surface, INV-2 acceptance
    /// records).
    pub ledger: WaiveLedger,
    /// WO-29 deliverable 3: the (partial, scalar-only -- see
    /// `regolith_ir::feature_program`'s module doc) feature program per
    /// declaration whose `then:` claim scopes construct domain features.
    pub feature_programs: Vec<FeatureProgram>,
    /// WO-29 deliverable 4: the raw capability demand per
    /// `architecture for ...:` resource block, projected from its
    /// `promises:` argument (cuprite/05 sec. 2). The Rust half of the
    /// D90 binding-requirement bridge; Python derives the candidate
    /// screen from magnetite records.
    pub block_requirements: Vec<BlockRequirement>,
    /// WO-32 deliverable 4b: every elaborated flownet, by name, in
    /// elaboration (source) order (AD-6) -- the payload emission
    /// `BuildPayload.flownets` mirrors verbatim. Obligations reference
    /// a flownet by content digest (`PayloadRef{ kind: "flownet", .. }`,
    /// D129); this map is what the orchestrator `put`s into the WO-30
    /// store so `resolve(digest)` succeeds at discharge time.
    pub flownets: IndexMap<String, FlownetPayload>,
    /// WO-33 deliverable 3: one [`FieldDatum`] ledger entry per
    /// `compute` claim (the computed-indexed-field datum ledger,
    /// regolith/02 sec. 5 precedent).
    pub field_datums: Vec<FieldDatum>,
    /// WO-34 deliverable 3 (D99): every elaborated `harness:` block, by
    /// name, in elaboration (source) order (AD-6) -- the payload
    /// emission `BuildPayload.harnesses` mirrors verbatim (same
    /// convention as `flownets`).
    pub harnesses: IndexMap<String, HarnessPayload>,
    /// WO-48 deliverable 3: every elaborated calcite `structure`, by
    /// name, in elaboration (source) order (AD-6) -- the payload
    /// emission `BuildPayload.frames` mirrors verbatim (same convention
    /// as `flownets`/`harnesses`).
    pub frames: IndexMap<String, FramePayload>,
    /// WO-61 deliverable 2 (D165/D167): the readable L2 contract-graph
    /// surface (interaction-surface/29 sec. 1.6) -- built once per
    /// build from `lower.contracts`'s own `ContractGraph`, mirroring
    /// `BuildPayload.frames`'s single-owner-pass convention (no second
    /// read path into `regolith-ir` state, AD-22).
    pub contract_graph: ContractGraphPayload,
    /// WO-56 deliverable 3 (D161/D168): every declared `by select(...)`
    /// choice point, subject-keyed (`"<subject>.<interface>"`), in file
    /// then source order (AD-6) -- the payload emission
    /// `BuildPayload.choice_points` mirrors verbatim (same convention as
    /// `flownets`/`harnesses`/`frames`). `optimize_discrete`'s domains
    /// (Python, `regolith.orchestrator.optimize`) read this field.
    pub choice_points: IndexMap<String, ChoicePoint>,
    /// WO-83 deliverable 2 (charter toolchain/37, D190): every `test
    /// <name>:` declaration's raw structural surface (subject file,
    /// name, scenario entries, expectations), in file then source order
    /// (AD-6) -- the payload emission `BuildPayload.tests` mirrors
    /// verbatim (`block_requirements`'s plain-`Vec` convention: no
    /// content addressing, this is a readable structural list, not an
    /// obligation-referenced payload).
    pub tests: Vec<TestDeclPayload>,
    /// WO-88 deliverable 2 (F112, INV-16): every elec behavioral body's
    /// converter graph, keyed by declaration name in file then source
    /// order (AD-6). WO-36 builds and acyclicity-checks this graph
    /// Rust-side but never exposed it; this field carries it across the
    /// FFI so a Python harness model (the buck family) resolves a
    /// design's topology from the compiled graph instead of taking it
    /// hand-supplied. Empty for a build with no behavioral `spec:` body.
    pub converter_graphs: IndexMap<String, ConverterGraph>,
}
