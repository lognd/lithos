//! Method-chain queries: static validation and symbolic resolution
//! against entity-DB snapshots. All source-level entity references are
//! queries (no positional indexing, no id literals).
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`
//! sec. 2, 5. Validation is STATIC (predicate names, entity kinds,
//! operand types, cardinality) on the pre-realization IR; resolution is
//! symbolic against a snapshot. Cardinality mismatch is an E0301-family
//! diagnostic carrying the matched-entity table; a broken-orbit `.any`
//! is E0502 with pinning suggestions.

use rockhead_diag::Diagnostic;
use rockhead_util::IndexMap;
use serde::{Deserialize, Serialize};

use crate::entity::{EntityId, EntityKind};

/// The cardinality intent a query terminates in.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
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
pub struct PredicateRegistry {
    predicates: IndexMap<String, Predicate>,
}

impl PredicateRegistry {
    /// An empty registry.
    #[must_use]
    pub fn new() -> PredicateRegistry {
        PredicateRegistry {
            predicates: IndexMap::new(),
        }
    }

    /// Register a predicate (domain packs call this at load).
    pub fn register(&mut self, predicate: Predicate) {
        self.predicates.insert(predicate.name.clone(), predicate);
    }

    /// Look up a predicate by name.
    #[must_use]
    pub fn get(&self, name: &str) -> Option<&Predicate> {
        self.predicates.get(name)
    }
}

/// One operation in a query method chain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
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
pub struct Query {
    /// The base name the chain starts from (`shell.edges`, `nets`).
    pub base: String,
    /// The ordered method chain.
    pub ops: Vec<QueryOp>,
}

/// The resolved result of a query against a snapshot.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QueryResult {
    /// The matched entities, in canonical order.
    pub matched: Vec<EntityId>,
    /// The static cardinality of the result.
    pub cardinality: Cardinality,
}

impl Query {
    /// Statically validate the chain against the registry: predicate
    /// names exist, operand types match, kinds apply, cardinality is
    /// consistent. Returns diagnostics (empty = valid).
    #[must_use]
    pub fn validate(&self, _registry: &PredicateRegistry) -> Vec<Diagnostic> {
        todo!("STUB WO-08: walk ops; unknown predicate/kind/operand -> E0301-family diagnostics")
    }

    /// Resolve the query against a snapshot. Cross-owner selection
    /// without a join is an E03xx error; a broken-orbit `.any` is E0502.
    ///
    /// # Errors
    /// Returns diagnostics (as data) when the query cannot resolve to
    /// its declared cardinality.
    pub fn resolve(
        &self,
        _db: &crate::entity::EntityDb,
        _registry: &PredicateRegistry,
        _orbits: &crate::symmetry::OrbitTable,
    ) -> Result<QueryResult, Vec<Diagnostic>> {
        todo!("STUB WO-08: apply ops over the snapshot; enforce cardinality + orbit legality")
    }
}

#[cfg(test)]
mod tests {
    use super::{CardinalityIntent, PredicateRegistry, Predicate, Query, QueryOp};
    use crate::entity::EntityKind;
    use rockhead_util::IndexMap;

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
