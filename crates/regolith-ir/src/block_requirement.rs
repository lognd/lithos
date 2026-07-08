//! The binding-requirement bridge IR (WO-29 deliverable 4): a schema-
//! versioned, `BuildPayload`-carried record of the RAW capability demands
//! a `.cupr` `architecture for <Computer>:` declaration projects onto its
//! abstract resource blocks (cuprite/05 sec. 2 -- "execution resources
//! are abstract blocks with promises"; regolith/10 sec. 1's `interface
//! promises` / `interface demands` rows, NOT the `budget` row, which is a
//! closure-arithmetic ceiling, D4 investigation 2026-07-08).
//!
//! SPLIT NOTE (Q3/D90, honored here): this is the RUST half only. Rust
//! emits the raw, un-unit-resolved capability demands spelled in each
//! resource's `promises:` keyword argument; the Python side
//! (`regolith.realizer.elec.binding`) derives the `ComponentCandidate`
//! screening table from magnetite `RecordStore` records and turns these raw
//! demands into the numeric `min_capabilities` screen. Mirrors
//! `feature_program`'s discipline: raw spelled `value` text + structural
//! attribution, never a resolved float (unit resolution is Python/harness
//! territory, not this pass's).

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// One raw capability demand from a resource block's `promises:` bound.
/// `>= 20Mops f32 sustained` -> `{capability: "", comparator: ">=",
/// value: "20Mops f32 sustained"}`; `latency <= 2 cycles` ->
/// `{capability: "latency", comparator: "<=", value: "2 cycles"}`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct CapabilityDemand {
    /// The named subject of the bound (`latency`, `context_switch`), or
    /// empty for the block-kind's implicit primary bound (an `executor`'s
    /// throughput, a `mover`'s bandwidth): a bare `>= <value>` names no
    /// left-hand subject.
    pub capability: String,
    /// The comparator spelled (`>=`, `<=`, `==`, `>`, `<`): the demand's
    /// direction, preserved verbatim for the Python screen to interpret.
    pub comparator: String,
    /// The raw right-hand value text as spelled (`20Mops f32 sustained`),
    /// NOT unit-resolved -- the Python bridge parses the quantity.
    pub value: String,
}

/// One abstract resource block's raw capability demand, projected from a
/// single `resources:`/`memories:`/`peripherals:` entry that carries a
/// `promises:` keyword argument. The `BlockRequirement`-shaped lowering
/// output WO-24's allocation search screens candidates against.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct BlockRequirement {
    /// The owning `architecture for <owner>:` target (the computer this
    /// block belongs to, `FlightCore`): grouping + traceability.
    pub owner: String,
    /// The abstract block/resource name the demand is FOR (`cpu0`,
    /// `sram`, `dma`): the allocation-search block identity.
    pub block: String,
    /// The stdlib block-contract kind the resource instantiates
    /// (`executor`, `memory`, `mover`, `fabric`): the demand's vocabulary
    /// namespace.
    pub contract: String,
    /// The raw capability demands spelled in this block's `promises:`
    /// argument, in source order (AD-6).
    pub demands: Vec<CapabilityDemand>,
}
