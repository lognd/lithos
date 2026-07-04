//! Semantic layer: entity database, queries, ownership/borrows,
//! stages/scopes, monomorphization, symmetry, sketch ledger.
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`
//! and `docs/substrate/06`. This crate runs entirely on the
//! pre-realization IR using per-construct predicted deltas (WO-07): the
//! anti-ambiguity checks (ownership/borrows WO-09, queries WO-08, stages
//! WO-10, profile ledgers WO-11) all execute before any realizer exists.

pub mod entity;
pub mod ownership;
pub mod query;
pub mod symmetry;

pub use entity::{Entity, EntityDb, EntityId, EntityKind, Measures, PredictedDelta, RegionPolicy};
pub use ownership::{
    check_single_driver, Borrow, BorrowKind, BorrowTable, MergeSign,
};
pub use query::{
    Cardinality, CardinalityIntent, Predicate, PredicateRegistry, Query, QueryOp, QueryResult,
};
pub use symmetry::{OrbitId, OrbitTable, SymmetryGroup};
