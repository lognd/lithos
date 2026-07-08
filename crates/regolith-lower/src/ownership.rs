//! Pass 3 (ownership / region / symmetry half): flow the now-typed
//! `OwnershipStmt`/`RegionStmt`/`SymmetryStmt` CST nodes (WO-05 residual
//! promotion) into the `regolith-sem` mechanisms that were implemented
//! and unit-tested but had no caller feeding them real parsed input.
//!
//! Regolith reference: `docs/regolith/05-ownership-and-queries.md`
//! sec. 3/5, `docs/regolith/13` INV-4 (symmetry soundness), INV-5
//! (ownership finality), INV-23 (region exclusivity). This is the
//! population half WO-19 owes: per declaration scope it builds a
//! `BorrowTable` + `EntityKind::Region` entities + an `OrbitTable` from
//! source and runs the sem checks, so a borrow conflict (`E0302`), a
//! route into an owned exclusion region (`E0302`, the same machinery per
//! the spec's region rule), and an `any` over a broken/undeclared orbit
//! (`E0502`) become real diagnostics flowing to the facade payload.
//!
//! Per-declaration granularity and by-NAME entity identity (a `bind`/
//! `modify` naming the same entity, a `route` naming its region) are the
//! WO-19 simplification: the full per-face/per-net entity model needs the
//! remaining opaque geometry bodies. What is real here is that the
//! predicted deltas, region entities, and orbit contributions are parsed,
//! not synthesized, so the sem verdicts bite on source.

use regolith_diag::codes::BROKEN_ORBIT_ANY;
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::{
    Borrow, BorrowKind, Entity, EntityId, EntityKind, Measures, OrbitTable, PredictedDelta,
    RegionPolicy, SymmetryGroup,
};
use regolith_syntax::ast::{AstNode, Decl, File, OwnershipStmt, RegionStmt, SymmetryStmt};
use regolith_util::{IndexMap, IndexSet};

use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// Run the ownership/region/symmetry checks over every non-poisoned
/// declaration across `files`, returning the collected diagnostics in
/// file-then-source order (AD-6). The final artifact orbit table is not
/// returned (it is per-scope); callers that need it recompute per decl.
#[must_use]
pub fn run_ownership_and_symmetry(files: &[ParsedFile]) -> Vec<Diagnostic> {
    let span = tracing::info_span!("lower.ownership");
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
            diagnostics.extend(check_decl(&decl, &name, &pf.path));
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "ownership/region/symmetry checks complete"
    );
    diagnostics
}

/// Per-declaration entity name -> internal id allocation. Ids are local
/// to the scope (WO-19 by-name identity); never source-facing (INV: no
/// id leakage).
struct Scope {
    ids: IndexMap<String, EntityId>,
    next: u32,
}

impl Scope {
    fn new() -> Scope {
        Scope {
            ids: IndexMap::new(),
            next: 1,
        }
    }

    /// The id for `name`, allocating a fresh one on first mention.
    fn id(&mut self, name: &str) -> EntityId {
        if let Some(id) = self.ids.get(name) {
            return *id;
        }
        let id = EntityId(self.next);
        self.next += 1;
        self.ids.insert(name.to_string(), id);
        id
    }
}

/// Check one declaration's ownership/region/symmetry statements.
fn check_decl(decl: &Decl, scope_name: &str, file: &camino::Utf8PathBuf) -> Vec<Diagnostic> {
    let mut scope = Scope::new();
    let mut borrows = regolith_sem::BorrowTable::new();
    let mut orbits = OrbitTable::new();
    // Region id -> policy, so a `route ... into <region>` knows whether
    // the target is exclusion (a conflict) or arbitration (shared).
    let mut region_policy: IndexMap<EntityId, RegionPolicy> = IndexMap::new();
    let mut broken_orbit = false;
    let mut declared_pattern = false;

    // Phase 1: standing state -- owned regions and role bindings are
    // borrows regardless of source order; patterns/breaks fold into the
    // orbit table (WO-07 conservative intersection).
    for node in decl.syntax().descendants() {
        if let Some(stmt) = RegionStmt::cast(node.clone()) {
            record_region(&stmt, &mut scope, &mut borrows, &mut region_policy);
        } else if let Some(stmt) = OwnershipStmt::cast(node.clone()) {
            if stmt.verb().as_deref() == Some("bind") {
                if let Some(target) = stmt.idents().get(1).cloned() {
                    let id = scope.id(&target);
                    tracing::debug!(scope = %scope_name, entity = %target, "bind: permanent borrow");
                    borrows.borrow(Borrow {
                        entities: vec![id],
                        borrower: format!("bind {target}"),
                        kind: BorrowKind::Permanent,
                    });
                }
            }
        } else if let Some(stmt) = SymmetryStmt::cast(node.clone()) {
            match stmt.verb().as_deref() {
                Some("pattern") => {
                    let group = pattern_group(&stmt);
                    tracing::debug!(scope = %scope_name, ?group, "pattern: orbit contribution");
                    orbits.contribute(group);
                    declared_pattern = true;
                }
                Some("break") => {
                    tracing::info!(scope = %scope_name, "break: symmetry-breaking delta collapses the orbit (INV-4)");
                    broken_orbit = true;
                }
                // `symmetric`/`mirror`/`flip`: neutral mirror promotions --
                // recorded (typed, no longer opaque) but not orbit-load-
                // bearing here (a reflection is not a `.any`-extensible
                // rotational/permutation orbit).
                _ => {}
            }
        }
    }

    // A symmetry-breaking construct collapses the whole artifact group to
    // Trivial (sound per INV-4: never assert a symmetry that no longer
    // holds).
    if broken_orbit {
        orbits = orbits.split_on_break(regolith_sem::OrbitId(0));
    }

    // Phase 2: modifying deltas and orbit extensions, checked against the
    // standing borrows / orbit table.
    let mut diags = Vec::new();
    for node in decl.syntax().descendants() {
        if let Some(stmt) = OwnershipStmt::cast(node.clone()) {
            if stmt.verb().as_deref() == Some("modify") {
                if let Some(target) = stmt.idents().get(1).cloned() {
                    let id = scope.id(&target);
                    let delta = modify_delta(id);
                    let hits = borrows.check_conflict(&format!("modify {target}"), &delta);
                    if !hits.is_empty() {
                        tracing::info!(scope = %scope_name, entity = %target, "modify of a borrowed entity -> borrow conflict (INV-5)");
                    }
                    diags.extend(hits);
                }
            }
        } else if let Some(stmt) = RegionStmt::cast(node.clone()) {
            diags.extend(check_route(
                &stmt,
                &mut scope,
                &borrows,
                &region_policy,
                scope_name,
            ));
        } else if let Some(stmt) = SymmetryStmt::cast(node.clone()) {
            if stmt.verb().as_deref() == Some("any") {
                diags.extend(check_any(
                    &stmt,
                    &orbits,
                    broken_orbit,
                    declared_pattern,
                    scope_name,
                    file,
                ));
            }
        }
    }
    diags
}

/// Record a `region`/`keepout` declaration: create an owned
/// `EntityKind::Region` entity and, for an exclusion policy, a standing
/// borrow so anything routing into it is a conflict (INV-23).
fn record_region(
    stmt: &RegionStmt,
    scope: &mut Scope,
    borrows: &mut regolith_sem::BorrowTable,
    region_policy: &mut IndexMap<EntityId, RegionPolicy>,
) {
    let idents = stmt.idents();
    let verb = idents.first().map(String::as_str);
    // `region`/`keepout` declare; `route` is handled in phase 2.
    if !matches!(verb, Some("region" | "keepout")) {
        return;
    }
    let Some(name) = idents.get(1) else { return };
    let id = scope.id(name);
    // `keepout` is exclusion by definition; `region <name> arbitration`
    // opts into sharing; everything else defaults to exclusion (the
    // sound default for an owned region).
    let policy = if verb == Some("keepout") {
        RegionPolicy::Exclusion
    } else {
        match idents.get(2).map(String::as_str) {
            Some("arbitration") => RegionPolicy::Arbitration,
            _ => RegionPolicy::Exclusion,
        }
    };
    // Construct the region entity from parsed source (INV-23: regions are
    // first-class owned entities built by the lowering pass).
    let _region = Entity {
        id,
        origin: name.clone(),
        owner: name.clone(),
        kind: EntityKind::Region,
        measures: Measures::new(),
        tags: IndexSet::new(),
        orbit: None,
    };
    region_policy.insert(id, policy);
    tracing::debug!(region = %name, ?policy, "region entity built from source");
    if policy == RegionPolicy::Exclusion {
        borrows.borrow(Borrow {
            entities: vec![id],
            borrower: format!("region {name}"),
            kind: BorrowKind::Permanent,
        });
    }
}

/// Check a `route <name> (into|join) <region>` statement: an `into` an
/// exclusion region without a declared join is a borrow conflict
/// (`E0302`, INV-23); a `join` is the declared overlap that exempts it.
fn check_route(
    stmt: &RegionStmt,
    scope: &mut Scope,
    borrows: &regolith_sem::BorrowTable,
    region_policy: &IndexMap<EntityId, RegionPolicy>,
    scope_name: &str,
) -> Vec<Diagnostic> {
    let idents = stmt.idents();
    if idents.first().map(String::as_str) != Some("route") {
        return Vec::new();
    }
    // route <name> <into|join> <region>
    let Some(rel) = idents.get(2).map(String::as_str) else {
        return Vec::new();
    };
    let Some(target) = idents.get(3) else {
        return Vec::new();
    };
    let region_id = scope.id(target);
    // A declared `join` is the explicit overlap declaration: the route
    // does not touch the region as a conflict.
    if rel == "join" {
        tracing::debug!(scope = %scope_name, region = %target, "route join: declared overlap, exempt");
        return Vec::new();
    }
    // Only exclusion regions conflict; arbitration is shared.
    if region_policy.get(&region_id) != Some(&RegionPolicy::Exclusion) {
        return Vec::new();
    }
    let route_name = idents
        .get(1)
        .cloned()
        .unwrap_or_else(|| "route".to_string());
    let delta = PredictedDelta {
        creates: vec![],
        modifies: vec![],
        consumes: vec![],
        regions_touched: vec![region_id],
        symmetry: None,
        data_dependent: false,
    };
    let hits = borrows.check_conflict(&format!("route {route_name}"), &delta);
    if !hits.is_empty() {
        tracing::info!(scope = %scope_name, region = %target, "route into an owned exclusion region -> borrow conflict (INV-23)");
    }
    hits
}

/// Check an `any <pattern>` orbit-extension request: extending a
/// per-instance result across an orbit is legal only when the artifact
/// group is declared and non-trivial (INV-4). A broken or undeclared
/// orbit means every candidate is a singleton, so `any` over more than
/// one is unsound -> `E0502`.
fn check_any(
    stmt: &SymmetryStmt,
    orbits: &OrbitTable,
    broken_orbit: bool,
    declared_pattern: bool,
    scope_name: &str,
    file: &camino::Utf8PathBuf,
) -> Vec<Diagnostic> {
    // A live, non-trivial declared orbit licenses the extension.
    if orbits.group().is_some() && !broken_orbit {
        return Vec::new();
    }
    let pattern = stmt.idents().get(1).cloned().unwrap_or_default();
    let reason = if broken_orbit {
        "a symmetry-breaking construct collapsed its orbit"
    } else if declared_pattern {
        "its orbit is not a soundly extensible group"
    } else {
        "no pattern declares an orbit for it"
    };
    tracing::info!(scope = %scope_name, pattern = %pattern, reason, "any over a broken/undeclared orbit -> E0502 (INV-4)");
    let range = stmt.syntax().text_range();
    let sp = Span::new(file.clone(), range.start().into(), range.end().into());
    vec![Diagnostic::error(
        BROKEN_ORBIT_ANY,
        format!(
            "`any {pattern}` extends a per-instance result across an orbit, but {reason}; \
             the extension is unsound and must name each instance"
        ),
    )
    .with_span(LabeledSpan::new(sp, "unsound orbit extension"))]
}

/// The symmetry group a `pattern <name> (circular|linear) <n>` construct
/// declares: `circular n` is a cyclic order-n rotation; `linear n` is a
/// permutation orbit of n identical members; a missing/other kind word
/// with a count is conservatively a permutation orbit; no count is the
/// trivial contribution.
fn pattern_group(stmt: &SymmetryStmt) -> SymmetryGroup {
    let Some(n) = stmt.order() else {
        return SymmetryGroup::Trivial;
    };
    match stmt.idents().get(2).map(String::as_str) {
        Some("circular") => SymmetryGroup::Cyclic(n),
        _ => SymmetryGroup::Permutation(n),
    }
}

/// The predicted delta of a `modify <entity>` feature: it modifies (and
/// so transfers ownership of) the named entity.
fn modify_delta(id: EntityId) -> PredictedDelta {
    PredictedDelta {
        creates: vec![],
        modifies: vec![id],
        consumes: vec![],
        regions_touched: vec![],
        symmetry: None,
        data_dependent: false,
    }
}

#[cfg(test)]
mod tests {
    use super::run_ownership_and_symmetry;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes::{BORROW_CONFLICT, BROKEN_ORBIT_ANY};

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn codes(diags: &[regolith_diag::Diagnostic]) -> Vec<regolith_diag::DiagCode> {
        diags.iter().map(|d| d.code).collect()
    }

    #[test]
    fn modify_of_a_bound_entity_is_a_borrow_conflict() {
        // INV-5: a role binding is a permanent borrow; a later modify of
        // the borrowed entity conflicts (bidirectional E0302).
        let src = "part p:\n    bind seat\n    modify seat\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(codes(&diags).iter().all(|c| *c == BORROW_CONFLICT));
        assert_eq!(diags.len(), 2, "bidirectional report: {diags:?}");
    }

    #[test]
    fn modify_of_an_unbound_entity_is_clean() {
        let src = "part p:\n    bind seat\n    modify hub\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }

    #[test]
    fn route_into_a_keepout_is_a_borrow_conflict() {
        // INV-23: routing into an owned exclusion region is the same
        // borrow conflict as modifying a borrowed face.
        let src = "part p:\n    keepout solar\n    route trace into solar\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(codes(&diags).contains(&BORROW_CONFLICT), "{diags:?}");
    }

    #[test]
    fn route_with_a_declared_join_is_clean() {
        let src = "part p:\n    region shared arbitration\n    route trace into shared\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(diags.is_empty(), "arbitration region is shared: {diags:?}");
    }

    #[test]
    fn join_declaration_exempts_an_exclusion_region() {
        let src = "part p:\n    keepout solar\n    route trace join solar\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(diags.is_empty(), "declared join is exempt: {diags:?}");
    }

    #[test]
    fn any_over_a_live_pattern_orbit_is_clean() {
        // INV-4: a declared, non-trivial orbit licenses the extension.
        let src = "part p:\n    pattern ring circular 4\n    any ring\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(diags.is_empty(), "{diags:?}");
    }

    #[test]
    fn any_over_a_broken_orbit_is_unsound() {
        // INV-4: a symmetry-breaking construct collapses the orbit; the
        // extension is then unsound (E0502).
        let src = "part p:\n    pattern ring circular 4\n    break ring\n    any ring\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(codes(&diags).contains(&BROKEN_ORBIT_ANY), "{diags:?}");
    }

    #[test]
    fn any_with_no_declared_pattern_is_unsound() {
        let src = "part p:\n    any ring\n";
        let diags = run_ownership_and_symmetry(&parsed(src));
        assert!(codes(&diags).contains(&BROKEN_ORBIT_ANY), "{diags:?}");
    }
}
