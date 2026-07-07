//! Pass 3 (query-resolution half): resolve `refer <name>` references
//! against each declaration scope's committed entity-DB snapshot
//! (WO-08 semantics, INV-06/18).
//!
//! Regolith reference: `docs/regolith/05-ownership-and-queries.md`
//! sec. 2/5, `docs/regolith/13` INV-6 (snapshot isolation), INV-18
//! (reference determinism). This is the caller WO-08's query engine
//! (`regolith-sem::query`) never had: it feeds real, parsed references
//! into `Query::resolve` against a per-scope snapshot.
//!
//! Model (WO-19 by-name granularity, matching `ownership.rs`): a
//! `feature <name>` statement commits one entity of the kind
//! `EntityKind::from_kind_word(<name>)` maps to (`Other(<name>)` for
//! non-kind words) into THIS declaration's snapshot via
//! `PredictedDelta`; a
//! `refer <name>` statement is a `.only` query whose base name selects
//! entities of that kind. Two consequences fall straight out of the
//! proof arguments and become `E0301` diagnostics flowing to the facade:
//!
//! - INV-18 (reference determinism): `.only` demands exactly one match.
//!   Over-match (two `feature hole`) and under-match (no `feature hole`)
//!   are both `E0301` -- resolution is deterministic or it fails, never a
//!   heuristic pick.
//! - INV-6 (snapshot isolation): each scope's snapshot is built ONLY from
//!   that scope's own features. A `refer` naming a SIBLING declaration's
//!   feature resolves against a snapshot that does not contain it, so it
//!   under-matches and is refused -- a sibling's committed (let alone
//!   uncommitted) state is not name-resolvable across the scope boundary.
//!
//! The predicted deltas and the snapshot are the real WO-07 mechanism;
//! the by-name entity identity is the WO-19 simplification (a full
//! per-face/per-net model needs the opaque geometry bodies WO-05 does not
//! yet structure), so what is real here is that the reference is RESOLVED
//! against a committed snapshot, not synthesized.

use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::{
    Cardinality, CardinalityIntent, Entity, EntityDb, EntityId, EntityKind, Measures, OrbitTable,
    PredicateRegistry, PredictedDelta, Query, QueryOp,
};
use regolith_syntax::ast::{AstNode, Decl, File, QueryStmt};
use regolith_util::IndexSet;

use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// Resolve every `refer` query against its declaration scope's snapshot
/// across `files`, returning the collected diagnostics in file-then-
/// source order (AD-6). Poisoned subjects are skipped (INV-20 gating).
#[must_use]
pub fn run_query_resolution(files: &[ParsedFile]) -> Vec<Diagnostic> {
    let span = tracing::info_span!("lower.query");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            diagnostics.extend(resolve_decl(&decl, &name, &pf.path));
        }
    }
    tracing::debug!(diagnostics = diagnostics.len(), "query resolution complete");
    diagnostics
}

/// Resolve one declaration's `refer` queries against a snapshot built
/// from its own `feature` statements. The snapshot is the scope-entry
/// state (INV-6): it is committed once, up front, from every feature in
/// the scope, and every reference resolves against THAT immutable
/// snapshot.
fn resolve_decl(decl: &Decl, scope_name: &str, file: &camino::Utf8PathBuf) -> Vec<Diagnostic> {
    // Phase 1: commit the scope-entry snapshot from `feature` statements.
    let mut features: Vec<Entity> = Vec::new();
    let mut next_id: u32 = 1;
    for stmt in query_stmts(decl) {
        if stmt.verb().as_deref() != Some("feature") {
            continue;
        }
        let Some(feature_name) = stmt.idents().get(1).cloned() else {
            continue;
        };
        let id = EntityId(next_id);
        next_id += 1;
        tracing::debug!(scope = %scope_name, feature = %feature_name, "feature: committing scope entity");
        // The committed kind and the query base selector MUST use the
        // same word-to-kind mapping (`feature hole` commits a Hole so
        // `refer hole` -- which selects EntityKind::Hole -- finds it);
        // regolith-sem::EntityKind::from_kind_word is the one home.
        features.push(Entity {
            id,
            origin: feature_name.clone(),
            owner: scope_name.to_string(),
            kind: EntityKind::from_kind_word(&feature_name),
            measures: Measures::new(),
            tags: IndexSet::new(),
            orbit: None,
        });
    }
    let ids: Vec<EntityId> = features.iter().map(|e| e.id).collect();
    let delta = PredictedDelta {
        creates: ids,
        modifies: vec![],
        consumes: vec![],
        regions_touched: vec![],
        symmetry: None,
        data_dependent: false,
    };
    let snapshot = EntityDb::empty().commit(&delta, &features);
    tracing::debug!(scope = %scope_name, hash = %snapshot.snapshot_hash(), features = features.len(), "scope-entry snapshot committed");

    // Phase 2: resolve each `refer` query against that snapshot. The
    // engine, registry, and orbit table come from `regolith-sem`; only
    // the `.only` cardinality intent is exercised at this tier (a bare
    // reference demands a unique interpretation, INV-18).
    let registry = PredicateRegistry::new();
    let orbits = OrbitTable::new();
    let mut diags = Vec::new();
    for stmt in query_stmts(decl) {
        if stmt.verb().as_deref() != Some("refer") {
            continue;
        }
        let Some(target) = stmt.idents().get(1).cloned() else {
            continue;
        };
        let query = Query {
            base: target.clone(),
            ops: vec![QueryOp::Cardinality(CardinalityIntent::Only)],
        };
        match query.resolve(&snapshot, &registry, &orbits) {
            Ok(result) => {
                debug_assert_eq!(result.cardinality, Cardinality::One);
                tracing::debug!(scope = %scope_name, target = %target, "refer resolved to a unique entity");
            }
            Err(errs) => {
                tracing::info!(
                    scope = %scope_name,
                    target = %target,
                    "refer over/under-matched against the scope snapshot -> E0301 (INV-18; sibling isolation is INV-6)"
                );
                let sp = stmt_span(&stmt, file);
                diags.extend(errs.into_iter().map(|d| attach_span(d, &sp)));
            }
        }
    }
    diags
}

/// Every `QueryStmt` in a declaration's subtree, in source order.
fn query_stmts(decl: &Decl) -> impl Iterator<Item = QueryStmt> {
    decl.syntax().descendants().filter_map(QueryStmt::cast)
}

/// The byte span of a `refer` statement (the reference site), for the
/// diagnostic's primary anchor.
fn stmt_span(stmt: &QueryStmt, file: &camino::Utf8PathBuf) -> Span {
    let range = stmt.syntax().text_range();
    Span::new(file.clone(), range.start().into(), range.end().into())
}

/// Anchor a span-less resolution diagnostic at the reference site so the
/// facade renders it against real source (the engine builds the matched-
/// entity table but has no span of its own).
fn attach_span(diag: Diagnostic, sp: &Span) -> Diagnostic {
    if diag.primary_span().is_some() {
        diag
    } else {
        diag.with_span(LabeledSpan::new(sp.clone(), "unresolved reference"))
    }
}

#[cfg(test)]
mod tests {
    use super::run_query_resolution;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::AMBIGUOUS_SELECTION;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hem");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn codes(diags: &[regolith_diag::Diagnostic]) -> Vec<regolith_diag::DiagCode> {
        diags.iter().map(|d| d.code).collect()
    }

    #[test]
    fn refer_to_a_unique_feature_resolves_cleanly() {
        // INV-18: exactly one match -> a unique interpretation.
        let src = "part p:\n    feature hole\n    refer hole\n";
        let diags = run_query_resolution(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }

    #[test]
    fn refer_over_matching_two_features_is_ambiguous() {
        // INV-18: over-match -> E0301, never a heuristic pick.
        let src = "part p:\n    feature hole\n    feature hole\n    refer hole\n";
        let diags = run_query_resolution(&parsed(src));
        assert!(codes(&diags).contains(&AMBIGUOUS_SELECTION), "{diags:?}");
    }

    #[test]
    fn refer_under_matching_nothing_is_refused() {
        // INV-18: under-match -> E0301 (a bare reference must resolve).
        let src = "part p:\n    refer hole\n";
        let diags = run_query_resolution(&parsed(src));
        assert!(codes(&diags).contains(&AMBIGUOUS_SELECTION), "{diags:?}");
    }

    #[test]
    fn refer_across_a_sibling_scope_is_isolated() {
        // INV-6: `hole` is a feature of sibling `p`; scope `q`'s snapshot
        // does not contain it, so the reference under-matches and is
        // refused -- snapshot isolation, not a cross-scope read.
        let src = "part p:\n    feature hole\npart q:\n    refer hole\n";
        let diags = run_query_resolution(&parsed(src));
        assert!(
            codes(&diags).contains(&AMBIGUOUS_SELECTION),
            "sibling feature must not be name-resolvable: {diags:?}"
        );
    }

    #[test]
    fn refer_within_its_own_scope_after_a_sibling_declares_is_clean() {
        // INV-6 honest control: `q` refers to its OWN `hole`; the sibling
        // `p` also declaring `hole` does not leak in either direction.
        let src = "part p:\n    feature hole\npart q:\n    feature hole\n    refer hole\n";
        let diags = run_query_resolution(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }
}
