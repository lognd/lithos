//! Pass 2: AST -> declaration table -> per-scope `EntityDb` snapshots.
//!
//! Regolith reference: `docs/regolith/05` sec. 1/3, `docs/regolith/13`
//! INV-18 (ambiguity is data), INV-21 (every non-literal slot carries a
//! `Cause`). One scope per top-level `Decl` (its name); a duplicate
//! declaration name is `E0301` data, not a panic. Only the structured
//! subset (`Field`/`CtorStmt`) is walked -- everything else in a decl
//! body is an `OpaqueIsland` and contributes no entities (recorded as
//! skipped, never hand-parsed; see the WO-19 partial-lowering note).

use regolith_diag::{Diagnostic, MatchedEntity};
use regolith_qty::{Cause, Qty, Resolution, Unit};
use regolith_sem::{Entity, EntityDb, EntityId, EntityKind, Measures, PredictedDelta};
use regolith_syntax::ast::{AstNode, CtorStmt, Decl, Field, File};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_util::{IndexMap, IndexSet};

use crate::claim_scope::{keyword_value, positional_value};
use crate::output::ParsedFile;

/// Every committed entity-DB scope (keyed by declaration name, source
/// order) plus the diagnostics and resolutions pass 2 produced.
#[derive(Debug, Clone, Default)]
pub struct EntitySnapshots {
    /// One committed snapshot per declaration scope, in first-seen
    /// (source) order.
    pub scopes: IndexMap<String, EntityDb>,
    /// Diagnostics from name resolution (duplicate/ambiguous names).
    pub diagnostics: Vec<Diagnostic>,
    /// Every non-literal field's resolution (Cause-typed, INV-21).
    pub resolutions: Vec<Resolution>,
}

/// Build entity-DB snapshots for every declaration across every parsed
/// file, in sorted-file then source-decl order (AD-6).
#[must_use]
pub fn build_entities(files: &[ParsedFile]) -> EntitySnapshots {
    let span = tracing::info_span!("lower.entities");
    let _enter = span.enter();

    let mut out = EntitySnapshots::default();
    let mut next_id: u32 = 1;
    let mut seen_names: IndexSet<String> = IndexSet::new();

    for pf in files {
        let root = pf.parse.syntax();
        let Some(file) = File::cast(root) else {
            tracing::debug!(file = %pf.path, "root node is not a File; skipping entity pass");
            continue;
        };

        for decl in file.decls() {
            let Some(name) = decl.name() else {
                tracing::debug!(file = %pf.path, "declaration with no name; skipping");
                continue;
            };

            // Per-subject INV-20 gating (AD-17): a declaration whose CST
            // subtree carries a parse-error node (an attributed
            // `SubjectError`/`parse:0193`, or a bare `Error` recovery
            // node) is POISONED -- it is excluded from this and every
            // later pass, so no snapshot, check, or obligation is
            // produced for it, while clean sibling declarations proceed
            // normally. Gating here (pass 2) is the single choke point:
            // downstream passes iterate `scopes`, so a poisoned subject
            // simply never appears in later-pass records (the WO-19
            // acceptance criterion: "zero later-pass span records").
            if decl_is_poisoned(&decl) {
                tracing::info!(
                    file = %pf.path,
                    subject = %name,
                    "INV-20 gate: subject has a parse error; excluded from later passes"
                );
                continue;
            }

            // A repeated name is NOT an error: the language scopes names
            // (INV-18 is scope-aware, not globally unique), and several
            // legitimate forms reuse a name -- e.g. multiple `impl X for
            // self as ...` blocks whose `name()` currently surfaces the
            // interface `X`. Proper scope-aware resolution is pending
            // (WO-19 closure); until then, disambiguate the scope key so
            // snapshots do not overwrite, and emit no false diagnostic.
            let scope_key = if seen_names.insert(name.clone()) {
                name.clone()
            } else {
                let mut n = 2;
                loop {
                    let candidate = format!("{name}#{n}");
                    if seen_names.insert(candidate.clone()) {
                        break candidate;
                    }
                    n += 1;
                }
            };

            let (decl_entity, resolutions) = lower_decl_to_entity(&decl, &name, EntityId(next_id));
            next_id += 1;
            out.resolutions.extend(resolutions);

            // WO-29 deliverable 2: materialize the domain feature
            // entities (`Hole`/`Bend`) the `then:` claim scopes construct,
            // so a rule pack's `forall h in holes` enumerates real
            // features over this part (WO-28) instead of the single
            // per-decl entity. The shared claim-scope walk
            // (`claim_scope`) is the ONE traversal deliverables 2/3/5
            // read (design/23 Q4(a) corollary).
            let mut entities = vec![decl_entity];
            for feature in feature_entities(&decl, &name, &mut next_id) {
                entities.push(feature);
            }

            let delta = PredictedDelta {
                creates: entities.iter().map(|e| e.id).collect(),
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            };
            let db = EntityDb::empty().commit(&delta, &entities);
            tracing::debug!(
                scope = %scope_key,
                hash = %db.snapshot_hash(),
                entities = entities.len(),
                "committed entity scope"
            );
            out.scopes.insert(scope_key, db);
        }
    }

    out
}

/// Lower one declaration's structured fields into a single `Entity`
/// (WO-19's simplified per-decl granularity -- see the partial-lowering
/// note: a full per-face/per-net entity model needs the domain-specific
/// `OpaqueIsland` bodies WO-05 does not yet structure) plus one
/// `Resolution` per non-literal field value.
fn lower_decl_to_entity(decl: &Decl, name: &str, id: EntityId) -> (Entity, Vec<Resolution>) {
    let kind = decl.kind_keyword().map_or_else(
        || EntityKind::Other("unknown".to_string()),
        |k| EntityKind::Other(format!("{k:?}")),
    );

    let mut measures: Measures = IndexMap::new();
    let mut resolutions = Vec::new();

    // Walk EVERY descendant field, not just direct children: value
    // sources (default/derived/free/allocated/in[..]) frequently live in
    // nested field blocks (now structured, cycle 11), and each one is a
    // non-literal slot that must appear in the lockfile with its cause
    // (INV-21). Direct-child fields still populate the entity's measures.
    for field in decl.fields() {
        let Some(value_node) = field.value() else {
            continue;
        };
        measures.insert(field.name(), value_node.text().to_string());
    }
    for node in decl.syntax().descendants() {
        // Both `name: value` fields and `name = value` ctor statements
        // can carry a value source; take whichever this node is.
        let named_value = Field::cast(node.clone())
            .map(|f| (f.name(), f.value()))
            .or_else(|| CtorStmt::cast(node.clone()).map(|c| (c.name(), c.value())));
        let Some((field_name, Some(value_node))) = named_value else {
            continue;
        };
        if value_node.kind() == SyntaxKind::ValueSource {
            resolutions.push(resolution_for_value_source(name, &field_name, &value_node));
        }
    }

    let entity = Entity {
        id,
        origin: name.to_string(),
        owner: name.to_string(),
        kind,
        measures,
        tags: IndexSet::new(),
        orbit: None,
    };

    (entity, resolutions)
}

/// Materialize the domain feature entities a declaration's `then:`
/// claim scopes construct (WO-29 deliverable 2). Each feature
/// constructor whose head maps to a domain [`EntityKind`]
/// (`EntityKind::from_constructor_word`: `Bore`/`CBore`/... -> `Hole`,
/// `Bend` -> `Bend`) becomes `count` entities (a `PatternOf<...>(n=N)`
/// orbit -> N identical features), each carrying the well-known typed
/// measures the constructor spelled (`diameter`/`depth`/... for a hole,
/// `angle`/`radius` for a bend, per Q1). Constructors outside the
/// hole/bend families yield nothing here (they stay non-domain / opaque)
/// -- a `forall` domain enumerates ONLY the kinds it names.
///
/// `next_id` is advanced past every id this allocates, so the caller's
/// id sequence stays gap-free and deterministic (AD-6).
fn feature_entities(decl: &Decl, owner: &str, next_id: &mut u32) -> Vec<Entity> {
    let mut out = Vec::new();
    for call in crate::claim_scope::feature_calls_in_decl(decl) {
        let Some(kind) = EntityKind::from_constructor_word(call.effective_constructor()) else {
            tracing::debug!(
                owner = %owner,
                binding = %call.binding,
                constructor = %call.effective_constructor(),
                "then: constructor is not a hole/bend feature verb; not a domain entity"
            );
            continue;
        };
        let measures = feature_measures(&kind, &call.args_text);
        for _ in 0..call.count {
            let id = EntityId(*next_id);
            *next_id += 1;
            tracing::debug!(
                owner = %owner,
                binding = %call.binding,
                ?kind,
                id = id.0,
                "materialized then: feature entity"
            );
            out.push(Entity {
                id,
                origin: call.binding.clone(),
                owner: owner.to_string(),
                kind: kind.clone(),
                measures: measures.clone(),
                tags: IndexSet::new(),
                orbit: None,
            });
        }
    }
    out
}

/// Extract the well-known typed measures (WO-29 Q1) a feature
/// constructor's argument text spells, keyed by the entity kind. Only
/// measures actually present in the source are populated -- an absent
/// argument yields no key rather than an invented zero, so a query's
/// `.where(diameter ...)` predicate matches exactly the features that
/// declared one. The `constructor` key always records the spelled verb
/// (a stable, queryable discriminant alongside the coarse kind).
fn feature_measures(kind: &EntityKind, args_text: &str) -> Measures {
    let mut measures: Measures = IndexMap::new();
    match kind {
        EntityKind::Hole => {
            // `dia <qty>` positional (`Bore(dia 32mm H7, ...)`): the
            // diameter is the quantity right after the `dia` label.
            if let Some(v) = positional_value(args_text, "dia") {
                measures.insert("diameter".to_string(), v);
            }
            if let Some(v) = keyword_value(args_text, "depth") {
                measures.insert("depth".to_string(), v);
            }
            if let Some(v) = keyword_value(args_text, "edge_distance") {
                measures.insert("edge_distance".to_string(), v);
            }
        }
        EntityKind::Bend => {
            if let Some(v) = keyword_value(args_text, "angle") {
                measures.insert("angle".to_string(), v);
            }
            if let Some(v) = keyword_value(args_text, "radius") {
                measures.insert("radius".to_string(), v);
            }
        }
        _ => {}
    }
    measures
}

/// Build the `Resolution` a non-literal (`ValueSource`-kinded) field
/// value produces, deriving its [`Cause`] STRUCTURALLY from the typed
/// value-source grammar (BE-5, INV-21): the `ValueSource` node's shape
/// -- an `in [...]` planner form, or a `CauseValue` leaf carrying one of
/// `default`/`derived`/`free`/`allocated` -- decides the provenance, not
/// a scan of the raw source text. The mapping follows regolith/03's
/// own value-source table (sec. 2): `in [..]` (the optimizer decides) ->
/// `Planner`; `derived` (a consequence of L2 system analysis, pinned by
/// the contract solver) -> `Obligation`; `allocated` (a share of a
/// declared budget) -> `Budget`; `free`/`default` (the process-rule
/// minimum, DFM/DRC eager propagation) -> `Dfm`. The magnitude is left
/// at zero (dimensionless) since no value is actually resolved by this
/// static pass -- only its provenance is known.
///
/// Not structurally reachable here (all opaque or out of the value-source
/// grammar, so never mis-attributed): the `(policy)` refinement on
/// `allocated` (parsed as trailing opaque tokens, not inside the
/// `ValueSource`, so `allocated` maps to `Budget` not `Policy`);
/// `derived(intent <name>)` (`DerivedIntent`); `by extern` linkage
/// (`Extern`); and `Topology`/`Drc` provenances, which arise from
/// constructs (topology boundaries, DRC rules) with no value-source
/// syntax. These stay unproduced rather than guessed.
fn resolution_for_value_source(
    scope: &str,
    field_name: &str,
    value_node: &regolith_syntax::cst::SyntaxNode,
) -> Resolution {
    let reference = format!("{scope}.{field_name}");
    let cause = cause_from_value_source(value_node, reference);
    Resolution::new(Qty::new(0.0, Unit::dimensionless()), cause)
}

/// Derive a [`Cause`] from a `ValueSource` node's structure (BE-5): an
/// `in` token opens the planner-bounded form; otherwise the node's
/// `CauseValue` child's keyword names the provenance. A `ValueSource`
/// with neither recognized shape falls back to `Dfm` (the process-rule
/// default), logged so the fallback is never silent.
fn cause_from_value_source(
    value_node: &regolith_syntax::cst::SyntaxNode,
    reference: String,
) -> Cause {
    for child in value_node.children_with_tokens() {
        if let Some(t) = child.as_token() {
            if t.kind() == SyntaxKind::InKw {
                return Cause::Planner(reference);
            }
        } else if let Some(n) = child.as_node() {
            if n.kind() == SyntaxKind::CauseValue {
                return cause_from_keyword(n, reference);
            }
        }
    }
    tracing::debug!(reference = %reference, "value-source has no recognized cause shape; defaulting to Dfm");
    Cause::Dfm(reference)
}

/// Map a `CauseValue` leaf's keyword token to its INV-21 provenance
/// (regolith/03 sec. 2's value-source table).
fn cause_from_keyword(cause_value: &regolith_syntax::cst::SyntaxNode, reference: String) -> Cause {
    let keyword = cause_value
        .children_with_tokens()
        .filter_map(regolith_syntax::cst::SyntaxElement::into_token)
        .map(|t| t.kind())
        .find(|k| !k.is_trivia());
    match keyword {
        // `derived`: a consequence of L2 system analysis, pinned by the
        // contract solver (regolith/03: "contract solver at L2").
        Some(SyntaxKind::DerivedKw) => Cause::Obligation(reference),
        // `allocated`: a share of a declared budget (the `(policy)`
        // refinement is trailing opaque syntax, not reachable here).
        Some(SyntaxKind::AllocatedKw) => Cause::Budget(reference),
        // `free`/`default`: the process-rule minimum, DFM/DRC eager
        // propagation decides the cheapest legal value.
        Some(SyntaxKind::FreeKw | SyntaxKind::DefaultKw) => Cause::Dfm(reference),
        other => {
            tracing::debug!(reference = %reference, ?other, "unexpected cause keyword; defaulting to Dfm");
            Cause::Dfm(reference)
        }
    }
}

/// True when a declaration's CST subtree contains a parse-error node --
/// an attributed in-body `SubjectError` (`parse:0193`) or a bare `Error`
/// recovery node. Such a subject is POISONED and excluded from every
/// pass by per-subject INV-20 gating (AD-17). Shared by every pass so
/// they agree exactly on which subjects are gated out.
#[must_use]
pub fn decl_is_poisoned(decl: &Decl) -> bool {
    decl.syntax()
        .descendants()
        .any(|n| matches!(n.kind(), SyntaxKind::SubjectError | SyntaxKind::Error))
}

/// A helper the golden/invariant suite can use to build a `MatchedEntity`
/// row for a diagnostic naming a scope's entities (kept here so
/// `checks.rs`/`claims.rs` share one rendering rule rather than each
/// inventing their own).
#[must_use]
pub fn matched_entity_row(scope: &str, entity: &Entity) -> MatchedEntity {
    MatchedEntity {
        origin: format!("{scope} ({})", entity.origin),
        measures: entity
            .measures
            .iter()
            .map(|(k, v)| format!("{k} = {v}"))
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::{build_entities, Cause};
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn cause_tag(c: &Cause) -> &'static str {
        match c {
            Cause::Dfm(_) => "dfm",
            Cause::Drc(_) => "drc",
            Cause::Obligation(_) => "obligation",
            Cause::Budget(_) => "budget",
            Cause::Topology(_) => "topology",
            Cause::Planner(_) => "planner",
            Cause::Extern(_) => "extern",
            Cause::DerivedIntent(_) => "derived_intent",
            Cause::Policy(_) => "policy",
        }
    }

    #[test]
    fn cause_is_derived_structurally_from_the_value_source_kind() {
        // Each value-source form maps to its INV-21 provenance by
        // structure, not a text scan (BE-5).
        let src = "part p:\n    a: derived\n    b: free\n    c: allocated\n    d: in [1mm, 2mm]\n";
        let snaps = build_entities(&parsed(src));
        let tags: Vec<&str> = snaps
            .resolutions
            .iter()
            .map(|r| cause_tag(r.cause()))
            .collect();
        assert!(
            tags.contains(&"obligation"),
            "derived -> obligation: {tags:?}"
        );
        assert!(tags.contains(&"dfm"), "free -> dfm: {tags:?}");
        assert!(tags.contains(&"budget"), "allocated -> budget: {tags:?}");
        assert!(tags.contains(&"planner"), "in [..] -> planner: {tags:?}");
    }

    #[test]
    fn then_scope_bore_materializes_a_queryable_hole_with_typed_measures() {
        // WO-29 deliverable 2: a `Bore(...)` in a `then:` claim scope
        // becomes a `Hole` entity in the part's scope db, enumerable via
        // the WO-08 query engine as `holes` with its diameter/depth
        // measures projected (the domain the WO-28 engine will evaluate).
        use regolith_sem::query::{PredicateRegistry, Query};
        use regolith_sem::symmetry::OrbitTable;
        use regolith_sem::EntityKind;

        let src = "part p:\n    stage s1:\n        then:\n            pilot = Bore(dia 28mm, depth=12mm, through)\n";
        let snaps = build_entities(&parsed(src));
        let db = snaps.scopes.get("p").expect("part p committed");

        let holes: Vec<_> = db.iter().filter(|e| e.kind == EntityKind::Hole).collect();
        assert_eq!(holes.len(), 1, "one Bore -> one Hole entity");
        assert_eq!(
            holes[0].measures.get("diameter").map(String::as_str),
            Some("28mm"),
            "diameter measure projected from `dia 28mm`"
        );
        assert_eq!(
            holes[0].measures.get("depth").map(String::as_str),
            Some("12mm"),
            "depth measure projected from `depth=12mm`"
        );

        // The same Hole is reachable through the query engine's `holes`
        // base selector (INV: emitted kind == queried kind, one home).
        let query = Query {
            base: "holes".to_string(),
            ops: Vec::new(),
        };
        let result = query
            .resolve(db, &PredicateRegistry::new(), &OrbitTable::new())
            .expect("holes query resolves");
        assert_eq!(result.matched.len(), 1, "query enumerates the hole");
    }

    #[test]
    fn patternof_orbit_materializes_n_features() {
        // A `PatternOf<CBore<M8>>(n=4, ...)` orbit -> 4 Hole entities.
        use regolith_sem::EntityKind;
        let src = "part p:\n    stage s1:\n        then:\n            mounts = PatternOf<CBore<M8>>(n=4, rect(100mm x 70mm))\n";
        let snaps = build_entities(&parsed(src));
        let db = snaps.scopes.get("p").expect("part p committed");
        let holes = db.iter().filter(|e| e.kind == EntityKind::Hole).count();
        assert_eq!(holes, 4, "n=4 orbit -> four Hole entities");
    }

    #[test]
    fn then_scope_bend_materializes_a_bend_with_angle_measure() {
        use regolith_sem::EntityKind;
        let src = "part p:\n    stage s1:\n        then:\n            flange = Bend(edge=cut.top, angle=90deg, radius=free)\n";
        let snaps = build_entities(&parsed(src));
        let db = snaps.scopes.get("p").expect("part p committed");
        let bends: Vec<_> = db.iter().filter(|e| e.kind == EntityKind::Bend).collect();
        assert_eq!(bends.len(), 1, "one Bend -> one Bend entity");
        assert_eq!(
            bends[0].measures.get("angle").map(String::as_str),
            Some("90deg"),
            "angle measure projected"
        );
        assert_eq!(
            bends[0].measures.get("radius").map(String::as_str),
            Some("free"),
            "radius=free captured verbatim (DFM defers it later)"
        );
    }

    #[test]
    fn non_feature_ctor_outside_then_scope_yields_no_domain_entity() {
        use regolith_sem::EntityKind;
        // A `=` ctor NOT under a `then:` scope is not a feature line.
        let src = "part p:\n    seat = Bore(dia 10mm)\n";
        let snaps = build_entities(&parsed(src));
        let db = snaps.scopes.get("p").expect("part p committed");
        let holes = db.iter().filter(|e| e.kind == EntityKind::Hole).count();
        assert_eq!(holes, 0, "a top-level ctor is not a then: feature line");
    }

    #[test]
    fn a_poisoned_subject_is_gated_out_but_a_clean_sibling_is_not() {
        // A stray operator inside `bad`'s body is a `SubjectError`
        // (parse:0193); `good` stays clean. INV-20 per-subject gating.
        let src = "part bad:\n    )\n    x: 1\npart good:\n    y: 2\n";
        let snaps = build_entities(&parsed(src));
        assert!(snaps.scopes.contains_key("good"), "clean sibling kept");
        assert!(
            !snaps.scopes.contains_key("bad"),
            "poisoned subject gated out"
        );
    }
}
