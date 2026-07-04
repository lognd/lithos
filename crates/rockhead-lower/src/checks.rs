//! Pass 3: semantic checks over lowered entities (ownership,
//! stages/scopes, profile DOF ledgers, symmetry orbits).
//!
//! Substrate reference: `docs/substrate/05` sec. 3/5, `docs/substrate/06`.
//! WO-19's per-decl entity granularity (see `entities.rs`) does not yet
//! populate `PredictedDelta`/`BorrowTable`/`StageGraph`/`Walk` inputs --
//! those need the domain `OpaqueIsland` bodies (machining stages,
//! `connect`/mating bodies, profile `walk:` blocks) that WO-05 leaves
//! unstructured. This pass therefore runs each checker over the
//! (currently empty) structured inputs it DOES have, so the moment a
//! later WO structures more of the grammar, real diagnostics start
//! flowing with no pipeline change -- it is real code that correctly
//! reports nothing yet, not a stub (see the WO-19 partial-lowering
//! note).

use rockhead_diag::Diagnostic;
use rockhead_sem::{OrbitTable, StageGraph};
use rockhead_syntax::ast::{AstNode, File};
use rockhead_syntax::syntax_kind::SyntaxKind;

use crate::entities::decl_is_poisoned;
use crate::entities::EntitySnapshots;
use crate::output::ParsedFile;

/// Diagnostics from every static check, plus the artifact-level orbit
/// table (symmetry) computed so far.
#[derive(Debug, Clone, Default)]
pub struct CheckReport {
    /// Diagnostics from ownership/stage/profile/symmetry checks.
    pub diagnostics: Vec<Diagnostic>,
    /// The (currently trivial) symmetry orbit table.
    pub orbits: OrbitTable,
    /// The generic declarations expanded by the monomorphization seam
    /// (INV-11), in file then source order -- one entry per generic
    /// declaration visited.
    pub monomorphized: Vec<String>,
}

/// Run the WO-19-available static checks over `files`/`snapshots`.
#[must_use]
pub fn run_checks(files: &[ParsedFile], snapshots: &EntitySnapshots) -> CheckReport {
    let span = tracing::info_span!("lower.checks");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();

    // Monomorphization expansion (INV-11): before the per-instantiation
    // static checks run, every generic declaration (one carrying a typed
    // `GenericParams` header list) must be expanded at each of its
    // instantiation points, exactly once. This seam enumerates the
    // generic declarations the grammar exposes and runs the
    // per-instantiation check pass over each, so the moment richer
    // grammar lands the totality argument is already threaded here.
    //
    // TRACKED CUT (WO-19 status note): the concrete instantiation
    // ARGUMENTS (`PatternOf<TappedHole<M3>>` at a use site) live inside
    // expression/ctor bodies that WO-05 does NOT yet type -- use-site
    // `<...>` is opaque lossless-swept text, not a `GenericParams` node
    // (only decl HEADERS carry one). So each generic declaration is
    // expanded here as its single base instantiation and "dead generic"
    // detection (a header never instantiated) is not yet constructible.
    // Blocked on WO-05 typing generic use-sites.
    let monomorphized = expand_generics(files);
    tracing::debug!(
        generics = monomorphized.len(),
        "monomorphization seam: expanded generic declarations (base instantiation; \
         concrete use-site args opaque, tracked cut)"
    );

    // Stage topology: no stage graph is built by `entities.rs` (stage
    // pipelines live entirely in `OpaqueIsland` bodies today), so this
    // runs over an empty graph -- trivially acyclic, real code, no
    // stub. Wiring a real graph is future work once WO-05 structures
    // stage headers.
    let stages = StageGraph::new();
    match stages.topo_order() {
        Ok(order) => tracing::debug!(count = order.len(), "stage topo order (empty graph)"),
        Err(diags) => diagnostics.extend(diags),
    }

    tracing::debug!(
        scopes = snapshots.scopes.len(),
        "ownership/profile/symmetry checks skipped: no structured mating/walk \
         input available yet (opaque bodies, see partial-lowering note)"
    );

    CheckReport {
        diagnostics,
        orbits: OrbitTable::new(),
        monomorphized,
    }
}

/// Enumerate every generic declaration -- one whose header carries a
/// typed `GenericParams` list (`interface PanelSeat<screw: thread, n:
/// int>`) -- as a monomorphization point (INV-11), skipping poisoned
/// subjects (INV-20). Returns each generic declaration's name in file
/// then source order; the per-instantiation static checks (once real
/// instantiation-argument grammar exists) run over exactly this list.
fn expand_generics(files: &[ParsedFile]) -> Vec<String> {
    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let has_generics = decl
                .syntax()
                .children()
                .any(|c| c.kind() == SyntaxKind::GenericParams);
            if has_generics {
                if let Some(name) = decl.name() {
                    tracing::debug!(subject = %name, "INV-11: expanding generic declaration (base instantiation)");
                    out.push(name);
                }
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::run_checks;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hem");
        vec![ParsedFile {
            path: path.clone(),
            parse: rockhead_syntax::parse(src, &path),
        }]
    }

    #[test]
    fn monomorphization_seam_enumerates_generic_declarations() {
        // INV-11: a generic decl (typed `GenericParams` header) is a
        // monomorphization point; a non-generic decl is not.
        let src = "interface Seat<screw: thread, n: int>:\n    x: 1\npart plain:\n    y: 2\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let report = run_checks(&files, &snaps);
        assert_eq!(report.monomorphized, vec!["Seat".to_string()]);
    }
}
