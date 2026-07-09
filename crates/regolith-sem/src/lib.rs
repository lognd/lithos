//! Semantic layer: entity database, queries, ownership/borrows,
//! stages/scopes, monomorphization, symmetry, sketch ledger, and the
//! continuous/discrete converter graph (INV-16 acyclicity).
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! and `docs/spec/regolith/06`. This crate runs entirely on the
//! pre-realization IR using per-construct predicted deltas (WO-07): the
//! anti-ambiguity checks (ownership/borrows WO-09, queries WO-08, stages
//! WO-10, profile ledgers WO-11) all execute before any realizer exists.

pub mod converter;
pub mod entity;
pub mod net_core;
pub mod ownership;
pub mod profile;
pub mod query;
pub mod resolve;
pub mod stage;
pub mod symmetry;

pub use converter::{ConverterGraph, Domain, Edge, EdgeKind, Node};
pub use entity::{Entity, EntityDb, EntityId, EntityKind, Measures, PredictedDelta, RegionPolicy};
pub use net_core::{
    first_violation, ElecDiscipline, FluidDiscipline, NetDiscipline, NetEntry, Terminal, Violation,
};
pub use ownership::{check_single_driver, Borrow, BorrowKind, BorrowTable, MergeSign};
pub use profile::{DofLedger, InstantiationContext};
pub use query::{
    Cardinality, CardinalityIntent, Predicate, PredicateRegistry, Query, QueryOp, QueryResult,
};
pub use resolve::{check_equality_ban, classify_value, field_classes, QuantityClass};
pub use stage::{Piece, Scope, Setup, Stage, StageEntry, StageGraph, StageId};
pub use symmetry::{OrbitId, OrbitTable, SymmetryGroup};
