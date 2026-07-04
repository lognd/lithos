//! The pipeline's input/output surface: source files in, parsed files
//! and the assembled build payload out.
//!
//! Substrate reference: `docs/substrate/06`, `docs/substrate/07` sec.
//! 2. `LowerOutput` is the pure-Rust, no-IO shape `regolith-api` wraps
//! into `BuildPayload` (AD-17).

use camino::Utf8PathBuf;
use regolith_diag::Diagnostic;
use regolith_oblig::{Evidence, Obligation, SnapshotRecord};
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
}
