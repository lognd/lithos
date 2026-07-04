//! Pass 2: AST -> declaration table -> per-scope `EntityDb` snapshots.
//!
//! Substrate reference: `docs/substrate/05` sec. 1/3, `docs/substrate/13`
//! INV-18 (ambiguity is data), INV-21 (every non-literal slot carries a
//! `Cause`). One scope per top-level `Decl` (its name); a duplicate
//! declaration name is `E0301` data, not a panic. Only the structured
//! subset (`Field`/`CtorStmt`) is walked -- everything else in a decl
//! body is an `OpaqueIsland` and contributes no entities (recorded as
//! skipped, never hand-parsed; see the WO-19 partial-lowering note).

use rockhead_diag::{codes, Diagnostic, MatchedEntity};
use rockhead_qty::{Cause, Qty, Resolution, Unit};
use rockhead_sem::{Entity, EntityDb, EntityId, EntityKind, Measures, PredictedDelta};
use rockhead_syntax::ast::{AstNode, Decl, File};
use rockhead_syntax::syntax_kind::SyntaxKind;
use rockhead_util::{IndexMap, IndexSet};

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

            if !seen_names.insert(name.clone()) {
                out.diagnostics.push(Diagnostic::error(
                    codes::AMBIGUOUS_SELECTION,
                    format!(
                        "duplicate declaration name `{name}` in `{}`: names must be unique \
                         across the artifact for entity/scope resolution",
                        pf.path
                    ),
                ));
                tracing::warn!(file = %pf.path, name = %name, "duplicate declaration name");
                continue;
            }

            let (entity, resolutions) = lower_decl_to_entity(&decl, &name, EntityId(next_id));
            next_id += 1;
            out.resolutions.extend(resolutions);

            let delta = PredictedDelta {
                creates: vec![entity.id],
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            };
            let db = EntityDb::empty().commit(&delta, &[entity]);
            tracing::debug!(scope = %name, hash = %db.snapshot_hash(), "committed entity scope");
            out.scopes.insert(name, db);
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

    for field in decl.fields() {
        let field_name = field.name();
        let Some(value_node) = field.value() else {
            continue;
        };
        measures.insert(field_name.clone(), value_node.text().to_string());

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

/// Build the `Resolution` a non-literal (`ValueSource`-kinded) field
/// value produces. ESCALATED (documented, WO-19-lowering-pipeline.md):
/// the grammar's `default`/`derived`/`free`/`allocated`/`in[..]` cause
/// KEYWORDS do not correspond 1:1 to `rockhead_qty::Cause`'s
/// provenance variants (`Dfm`/`Drc`/`Obligation`/`Budget`/`Topology`/
/// `Planner`) -- those name WHO resolved a value (a rule/obligation/
/// planner), not the grammar's declared freedom kind, and no realizer
/// exists yet to say which rule actually fired. This is a best-effort,
/// clearly-documented mapping satisfying INV-21 mechanically (every
/// non-literal slot gets *some* `Cause`) rather than inventing false
/// specificity; the magnitude is left at zero (dimensionless) since no
/// value is actually resolved by this static pass.
fn resolution_for_value_source(
    scope: &str,
    field_name: &str,
    value_node: &rockhead_syntax::cst::SyntaxNode,
) -> Resolution {
    let text = value_node.text().to_string();
    let reference = format!("{scope}.{field_name}");
    let cause = if text.contains("derived") {
        Cause::Obligation(reference)
    } else if text.contains("allocated") {
        Cause::Budget(reference)
    } else if text.contains("in") && (text.contains('[') || text.contains('(')) {
        Cause::Planner(reference)
    } else {
        // `free` and any other bare cause keyword: DFM/DRC decide
        // cheapest-legal values in the real pipeline; no rule registry
        // exists in this static pass, so this is the documented default.
        Cause::Dfm(reference)
    };
    Resolution::new(Qty::new(0.0, Unit::dimensionless()), cause)
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
