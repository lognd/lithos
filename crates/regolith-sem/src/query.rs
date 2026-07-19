//! Method-chain queries: static validation and symbolic resolution
//! against entity-DB snapshots. All source-level entity references are
//! queries (no positional indexing, no id literals).
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! sec. 2, 5. Validation is STATIC (predicate names, entity kinds,
//! operand types, cardinality) on the pre-realization IR; resolution is
//! symbolic against a snapshot. Cardinality mismatch is an E0301-family
//! diagnostic carrying the matched-entity table; a broken-orbit `.any`
//! is E0502 with pinning suggestions.

use regolith_diag::{codes, Diagnostic, MatchedEntity};
use regolith_util::IndexMap;
use serde::{Deserialize, Serialize};

use crate::entity::{EntityId, EntityKind};

/// The cardinality intent a query terminates in.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-sem.md#query
pub enum CardinalityIntent {
    /// `.all` -- explicitly everything matched.
    All,
    /// `.only` -- exactly one; over/under-match is an error.
    Only,
    /// `.any` -- an orbit-checked representative (section 5).
    Any,
}

/// The static cardinality type of a query result.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#query
pub enum Cardinality {
    /// Exactly one entity.
    One,
    /// A set whose size is tied to an integer variable (consumers must
    /// be cardinality-polymorphic).
    FixedN(String),
    /// A dynamically sized set (consumers must accept `.all`).
    Dynamic,
}

/// A registered predicate: its name, the operand types it takes, and the
/// entity kinds it applies to. Predicates are DECLARED per domain
/// (registry data), never hard-coded in the engine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#query
pub struct Predicate {
    /// Predicate name (`parallel_to`, `direction`, `domain`).
    pub name: String,
    /// Names of the operand types it accepts (typed by the qty core /
    /// pack vocabulary).
    pub operand_types: Vec<String>,
    /// Entity kinds it is meaningful on.
    pub applies_to: Vec<EntityKind>,
}

/// The per-domain predicate registry (declared, not hard-coded).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#query
pub struct PredicateRegistry {
    predicates: IndexMap<String, Predicate>,
}

impl PredicateRegistry {
    /// An empty registry.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#query
    pub fn new() -> PredicateRegistry {
        PredicateRegistry {
            predicates: IndexMap::new(),
        }
    }

    /// Register a predicate (domain packs call this at load).
    // frob:doc docs/modules/regolith-sem.md#query
    pub fn register(&mut self, predicate: Predicate) {
        self.predicates.insert(predicate.name.clone(), predicate);
    }

    /// Look up a predicate by name.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#query
    pub fn get(&self, name: &str) -> Option<&Predicate> {
        self.predicates.get(name)
    }
}

/// One operation in a query method chain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#query
pub enum QueryOp {
    /// `.where(pred=..)` filter with predicate arguments (name -> value
    /// text, typed against the registry).
    Where(IndexMap<String, String>),
    /// `.nearest(datum)` instance addressing.
    Nearest(String),
    /// `at_intersection(a, b)` explicit cross-owner join.
    AtIntersection(Box<Query>, Box<Query>),
    /// `&` set join with another query.
    Join(Box<Query>),
    /// `.instances` of a pattern/orbit.
    Instances,
    /// `.bits` of a bus.
    Bits,
    /// `[i .. j]` positional bus-range selection.
    BusRange {
        /// Inclusive start bit.
        start: u64,
        /// Exclusive end bit.
        end: u64,
    },
    /// `.as_datum()` capture as a borrow-exempt datum.
    AsDatum,
    /// Terminal cardinality intent (`.all` / `.only` / `.any`).
    Cardinality(CardinalityIntent),
}

/// A query: a base name reference followed by a chain of operations.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#query
pub struct Query {
    /// The base name the chain starts from (`shell.edges`, `nets`).
    pub base: String,
    /// The ordered method chain.
    pub ops: Vec<QueryOp>,
}

/// The resolved result of a query against a snapshot.
#[derive(Debug, Clone, PartialEq, Eq)]
// frob:doc docs/modules/regolith-sem.md#query
pub struct QueryResult {
    /// The matched entities, in canonical order.
    pub matched: Vec<EntityId>,
    /// The static cardinality of the result.
    pub cardinality: Cardinality,
}

/// Map a query's base name (`shell.edges`, `nets`, `regions`) to the
/// entity kind it selects and, when the base is owner-qualified, the
/// owner it is scoped to. Unrecognized kind words map to
/// [`EntityKind::Other`] so pack-defined kinds still validate.
fn base_selector(base: &str) -> (Option<&str>, EntityKind) {
    let (owner, kind_word) = match base.rsplit_once('.') {
        Some((owner, word)) => (Some(owner), word),
        None => (None, base),
    };
    (owner, EntityKind::from_kind_word(kind_word))
}

impl Query {
    /// Statically validate the chain against the registry: predicate
    /// names exist. Operand-type/kind checking against a predicate's
    /// declared `applies_to`/`operand_types` needs the base's resolved
    /// entity kind, which is available structurally (see
    /// [`base_selector`]); unknown predicate names are E0301-family
    /// (`AMBIGUOUS_SELECTION` is the only References-family code this
    /// crate has a registered slot for; a dedicated "unknown predicate"
    /// code belongs in `regolith-diag` and is out of this crate's
    /// scope). Returns diagnostics (empty = valid).
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#query
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn validate(&self, registry: &PredicateRegistry) -> Vec<Diagnostic> {
        let mut diags = Vec::new();
        let (_owner, kind) = base_selector(&self.base);
        for op in &self.ops {
            match op {
                QueryOp::Where(args) => {
                    for name in args.keys() {
                        match registry.get(name) {
                            None => diags.push(Diagnostic::error(
                                codes::AMBIGUOUS_SELECTION,
                                format!(
                                    "unknown predicate `{name}` in `.where(...)` on `{}`",
                                    self.base
                                ),
                            )),
                            Some(pred) if !pred.applies_to.contains(&kind) => {
                                diags.push(Diagnostic::error(
                                    codes::AMBIGUOUS_SELECTION,
                                    format!("predicate `{name}` does not apply to `{}`", self.base),
                                ));
                            }
                            Some(_) => {}
                        }
                    }
                }
                QueryOp::AtIntersection(a, b) => {
                    diags.extend(a.validate(registry));
                    diags.extend(b.validate(registry));
                }
                QueryOp::Join(q) => diags.extend(q.validate(registry)),
                QueryOp::Nearest(_)
                | QueryOp::Instances
                | QueryOp::Bits
                | QueryOp::BusRange { .. }
                | QueryOp::AsDatum
                | QueryOp::Cardinality(_) => {}
            }
        }
        diags
    }

    /// Resolve the query against a snapshot. Cross-owner selection
    /// without a join is an E03xx error; a broken-orbit `.any` is E0502.
    ///
    /// # Errors
    /// Returns diagnostics (as data) when the query cannot resolve to
    /// its declared cardinality.
    // `registry` is threaded through only to recurse into sub-queries
    // (`AtIntersection`/`Join`); resolution itself is symbolic against
    // the snapshot; static predicate validation is `Query::validate`'s
    // job. Kept in the signature (not underscored) because it names a
    // real, load-bearing part of the resolve contract.
    #[allow(clippy::only_used_in_recursion)]
    // frob:doc docs/modules/regolith-sem.md#query
    pub fn resolve(
        &self,
        db: &crate::entity::EntityDb,
        registry: &PredicateRegistry,
        orbits: &crate::symmetry::OrbitTable,
    ) -> Result<QueryResult, Vec<Diagnostic>> {
        let (owner, kind) = base_selector(&self.base);
        let mut matched: Vec<EntityId> = db
            .iter()
            .filter(|e| e.kind == kind && owner.is_none_or(|o| e.owner == o))
            .map(|e| e.id)
            .collect();

        let mut explicit_join = false;
        let mut cardinality = Cardinality::Dynamic;

        for op in &self.ops {
            match op {
                QueryOp::Where(args) => Self::apply_where(db, &mut matched, args),
                QueryOp::Nearest(_) | QueryOp::Instances | QueryOp::Bits | QueryOp::AsDatum => {
                    // No geometric/bus model at this layer (predicted
                    // deltas only, WO-08 static tier): the entity set
                    // itself is unaffected.
                }
                QueryOp::BusRange { start, end } => {
                    Self::apply_bus_range(&mut matched, *start, *end);
                }
                QueryOp::AtIntersection(a, b) => {
                    let ra = a.resolve(db, registry, orbits)?;
                    let rb = b.resolve(db, registry, orbits)?;
                    let set: std::collections::BTreeSet<_> = ra.matched.into_iter().collect();
                    matched.retain(|id| set.contains(id) && rb.matched.contains(id));
                    explicit_join = true;
                }
                QueryOp::Join(q) => {
                    let r = q.resolve(db, registry, orbits)?;
                    let set: std::collections::BTreeSet<_> = r.matched.into_iter().collect();
                    matched.retain(|id| set.contains(id));
                    explicit_join = true;
                }
                QueryOp::Cardinality(intent) => {
                    cardinality = Self::cardinality_of(*intent);
                    self.apply_cardinality(db, orbits, *intent, &mut matched)?;
                }
            }
        }

        if !explicit_join && Self::has_cross_owner_match(db, &matched) {
            return Err(vec![Self::ambiguous_diag(db, &self.base, &matched)
                .with_fix(regolith_diag::Fix {
                    message: "join explicitly with `&` or `at_intersection(...)`".to_string(),
                    replacement: None,
                })]);
        }

        Ok(QueryResult {
            matched,
            cardinality,
        })
    }

    /// Filter `matched` by a `.where(...)` predicate-argument map,
    /// matching each argument against the entity's measures.
    fn apply_where(
        db: &crate::entity::EntityDb,
        matched: &mut Vec<EntityId>,
        args: &IndexMap<String, String>,
    ) {
        matched.retain(|id| {
            db.get(*id).is_some_and(|entity| {
                args.iter()
                    .all(|(k, v)| entity.measures.get(k).is_some_and(|mv| mv == v))
            })
        });
    }

    /// Apply a `[start .. end]` positional bus-range selection to the
    /// current in-order match set.
    fn apply_bus_range(matched: &mut Vec<EntityId>, start: u64, end: u64) {
        let start = usize::try_from(start).unwrap_or(usize::MAX);
        let end = usize::try_from(end)
            .unwrap_or(usize::MAX)
            .min(matched.len());
        *matched = if start >= matched.len() || start >= end {
            Vec::new()
        } else {
            matched[start..end].to_vec()
        };
    }

    /// The static [`Cardinality`] a terminal [`CardinalityIntent`] types
    /// the result as.
    fn cardinality_of(intent: CardinalityIntent) -> Cardinality {
        match intent {
            CardinalityIntent::All => Cardinality::Dynamic,
            CardinalityIntent::Only | CardinalityIntent::Any => Cardinality::One,
        }
    }

    /// Enforce a terminal cardinality intent against the current match
    /// set: `.only` demands exactly one; `.any` demands an intact orbit
    /// and collapses to its canonical (lowest-id, deterministic per
    /// INV-10) representative.
    fn apply_cardinality(
        &self,
        db: &crate::entity::EntityDb,
        orbits: &crate::symmetry::OrbitTable,
        intent: CardinalityIntent,
        matched: &mut Vec<EntityId>,
    ) -> Result<(), Vec<Diagnostic>> {
        match intent {
            CardinalityIntent::All => Ok(()),
            CardinalityIntent::Only => {
                if matched.len() == 1 {
                    Ok(())
                } else {
                    Err(vec![Self::ambiguous_diag(db, &self.base, matched)])
                }
            }
            CardinalityIntent::Any => {
                let orbit = matched
                    .iter()
                    .find_map(|id| db.get(*id).and_then(|e| e.orbit));
                let uniform = matched
                    .iter()
                    .all(|id| db.get(*id).and_then(|e| e.orbit) == orbit);
                let legal = matched.len() <= 1
                    || (uniform && orbit.is_some_and(|o| orbits.any_is_legal(o)));
                if !legal {
                    return Err(vec![Diagnostic::error(
                        codes::BROKEN_ORBIT_ANY,
                        format!(
                            "`.any` over `{}` is not legal: the orbit is broken",
                            self.base
                        ),
                    )
                    .with_fix(regolith_diag::Fix {
                        message: "pin a specific instance instead of `.any`".to_string(),
                        replacement: None,
                    })]);
                }
                if let Some(&rep) = matched.iter().min() {
                    *matched = vec![rep];
                }
                Ok(())
            }
        }
    }

    /// Whether the current match set spans more than one owner (a
    /// cross-owner selection that needs an explicit join).
    fn has_cross_owner_match(db: &crate::entity::EntityDb, matched: &[EntityId]) -> bool {
        let owners: std::collections::BTreeSet<&str> = matched
            .iter()
            .filter_map(|id| db.get(*id).map(|e| e.owner.as_str()))
            .collect();
        owners.len() > 1
    }

    /// Build the ambiguous-selection diagnostic with its matched-entity
    /// table (regolith/05 sec. 6).
    fn ambiguous_diag(
        db: &crate::entity::EntityDb,
        base: &str,
        matched: &[EntityId],
    ) -> Diagnostic {
        let mut diag = Diagnostic::error(
            codes::AMBIGUOUS_SELECTION,
            format!("query on `{base}` matched {} entities", matched.len()),
        );
        for id in matched {
            if let Some(entity) = db.get(*id) {
                diag = diag.with_match(MatchedEntity {
                    origin: entity.origin.clone(),
                    measures: entity
                        .measures
                        .iter()
                        .map(|(k, v)| format!("{k} = {v}"))
                        .collect(),
                });
            }
        }
        diag
    }
}

#[cfg(test)]
mod tests {
    use super::{CardinalityIntent, Predicate, PredicateRegistry, Query, QueryOp};
    use crate::entity::EntityKind;
    use regolith_util::IndexMap;

    #[test]
    fn registry_registers_and_looks_up() {
        let mut reg = PredicateRegistry::new();
        reg.register(Predicate {
            name: "direction".to_string(),
            operand_types: vec!["net_direction".to_string()],
            applies_to: vec![EntityKind::Net, EntityKind::Port],
        });
        assert!(reg.get("direction").is_some());
        assert!(reg.get("nonesuch").is_none());
    }

    // frob:tests crates/regolith-sem/src/query.rs::Query.validate kind="unit"
    #[test]
    fn validate_flags_unknown_and_misapplied_predicates() {
        let mut reg = PredicateRegistry::new();
        reg.register(Predicate {
            name: "direction".to_string(),
            operand_types: vec!["net_direction".to_string()],
            applies_to: vec![EntityKind::Net],
        });

        let ok = Query {
            base: "nets".to_string(),
            ops: vec![QueryOp::Where(IndexMap::new())],
        };
        assert!(ok.validate(&reg).is_empty(), "no ops reference predicates");

        let mut unknown_args = IndexMap::new();
        unknown_args.insert("nonesuch".to_string(), "x".to_string());
        let unknown = Query {
            base: "nets".to_string(),
            ops: vec![QueryOp::Where(unknown_args)],
        };
        assert_eq!(unknown.validate(&reg).len(), 1, "unknown predicate flagged");

        let mut misapplied_args = IndexMap::new();
        misapplied_args.insert("direction".to_string(), "x".to_string());
        let misapplied = Query {
            base: "faces".to_string(),
            ops: vec![QueryOp::Where(misapplied_args)],
        };
        assert_eq!(
            misapplied.validate(&reg).len(),
            1,
            "predicate applies_to mismatch flagged"
        );
    }

    #[test]
    fn query_round_trips_json() {
        let q = Query {
            base: "nets".to_string(),
            ops: vec![
                QueryOp::Where(IndexMap::new()),
                QueryOp::Cardinality(CardinalityIntent::Any),
            ],
        };
        let json = serde_json::to_string(&q).unwrap();
        let back: Query = serde_json::from_str(&json).unwrap();
        assert_eq!(back, q);
    }
}
