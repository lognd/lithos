//! The pipeline's input/output surface: source files in, parsed files
//! and the assembled build payload out.
//!
//! Regolith reference: `docs/spec/regolith/06`, `docs/spec/regolith/07` sec.
//! 2. `LowerOutput` is the pure-Rust, no-IO shape `regolith-api` wraps
//! into `BuildPayload` (AD-17).

use camino::Utf8PathBuf;
use indexmap::IndexMap;
use regolith_diag::Diagnostic;
use regolith_ir::{BlockRequirement, FeatureProgram};
use regolith_oblig::{
    Evidence, FieldDatum, FlownetPayload, Obligation, SnapshotRecord, WaiveLedger,
};
use regolith_qty::Resolution;
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
}
