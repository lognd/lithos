//! Obligation, evidence, and lockfile-row schemas; canonical CBOR
//! encoding; domain-tagged content addressing; schemars export.
//!
//! Regolith reference: `docs/spec/regolith/07-claims-and-evidence.md`.
//! These types are the single source of truth that crosses the FFI and
//! lands on disk (AD-5): defined once here, generated into pydantic on
//! the Python side (WO-18). Claims lower to self-contained, serializable
//! [`obligation::Obligation`]s; [`evidence::Evidence`] is the only
//! return type of discharge (WO-13).

pub mod assembly;
pub mod attestation;
pub mod claim;
pub mod contract_graph;
pub mod cost;
pub mod drawing;
pub mod encoding;
pub mod evidence;
pub mod field;
pub mod flownet;
pub mod frame;
pub mod geometry;
pub mod harness;
pub mod layout;
pub mod obligation;
pub mod optimize;
pub mod payload;
pub mod signature;
pub mod solver;
pub mod waiver;

pub use assembly::{AssemblyPart, Interference, RealizedAssembly, Transform, ASSEMBLY_DOMAIN_TAG};
pub use attestation::{Attestation, SignatureAlgorithm};
pub use claim::{Assumption, Claim, ClaimForm, Window};
pub use contract_graph::{
    ContractEdge, ContractGraphPayload, ContractNode, CONTRACT_GRAPH_DOMAIN_TAG,
};
pub use cost::{
    EstimateLineItem, ItemizedEstimate, PriceBreak, PricingRecord, RateRecord, UnitCostRecord,
    ITEMIZED_ESTIMATE_DOMAIN_TAG,
};
pub use drawing::{
    Annotation, Dimension, DrawingModel, Entity, Provenance, Sheet, SheetSize, Table, TableRow,
    TitleBlock, View, ViewSource, DRAWING_DOMAIN_TAG,
};
pub use encoding::{canonical_cbor, content_address, export_schemas, EncodeError};
pub use evidence::{
    decide_margin, Coverage, CoverageAxis, CoverageDomain, CoverageMethod, Evidence, EvidenceCache,
    Status,
};
pub use field::FieldDatum;
pub use flownet::{
    Compliance, EdgeKind, EdgeParams, FlowEdge, FlownetPayload, MediumRef, NodeId, RecordRef,
    Reference, ScalarInterval, StateDomain, FLOWNET_DOMAIN_TAG,
};
pub use frame::{
    Datum, FrameLoad, FrameMember, FramePayload, FrameTransfer, Joint, JointAt, JointId, LoadKind,
    MemberRole, Releases, Support, FRAME_DOMAIN_TAG,
};
pub use geometry::{
    Bend, Bounds, PathSegment, RealizedGeometry, RoutedPath, TopologySummary, Wall,
    GEOMETRY_DOMAIN_TAG,
};
pub use harness::{HarnessPayload, RunRecord, RunRoute, RunSegment, HARNESS_DOMAIN_TAG};
pub use layout::{
    BoardSide, CopperArea, CopperSummary, NetLength, ParasiticSlot, Placement, RealizedLayout,
    RoutedSegment, LAYOUT_DOMAIN_TAG,
};
pub use obligation::{Given, Obligation, SnapshotRecord, SweepDomain};
pub use optimize::{
    CandidateEntry, ChoicePoint, ObjectiveDirection, OptimizationTrace, TerminationStatus,
    CHOICE_POINT_DOMAIN_TAG, OPTIMIZATION_TRACE_DOMAIN_TAG,
};
pub use payload::PayloadRef;
pub use signature::{ImplRecord, Signature, SignatureRegistry};
pub use solver::SolverResponse;
pub use waiver::{LedgerEntry, WaiveLedger, Waiver, WaiverKind, WaiverRecord};

/// Schema version stamped on every cross-boundary payload (AD-5). Now
/// defined in `regolith_util::canon` (AD-18), the bottom of the
/// layering, and re-exported here unchanged so no caller sees a path
/// change. Bumped whenever a serialized shape changes; the facade
/// asserts it against the core at import.
pub use regolith_util::canon::SCHEMA_VERSION;

#[cfg(test)]
mod tests {
    #[test]
    fn schema_version_is_pinned() {
        // Bumped 5 -> 6 by WO-30 (F100, ONE bump): structured coverage
        // (D95), the payload-ref channel (D96), Given.refs + regime
        // tags (D97/D103), and the D102/D105(d) claim-form/waiver
        // fields all ride this single schema-version bump.
        // Bumped 6 -> 7 by WO-29 deliverable 3: the `feature_programs`
        // `BuildPayload` field.
        // Bumped 7 -> 8 by WO-29 deliverable 4: the `block_requirements`
        // `BuildPayload` field.
        // Bumped 8 -> 9 by WO-32 deliverable 1: the `FlownetPayload`
        // schema type (fluorite/03 sec. 2), the `flownet` payload kind.
        // Bumped 9 -> 10 by WO-32 D4a (D129): `Obligation.payloads`.
        // Bumped 10 -> 11 by WO-42 deliverable 1 (AD-25/D128): the
        // `RealizedGeometry` schema, promoted from WO-22's Python
        // forward contract, extended with per-stage wetted-geometry +
        // wall data for the WO-32 `regolith-lower::extract` seam.
        // Bumped 11 -> 12 by WO-32 D4b: the `flownets` `BuildPayload`/
        // `LowerOutput` field (payload emission).
        // Bumped 12 -> 13 by WO-42 deliverable 2 (AD-25/D128): the
        // `RealizedLayout` schema, built fresh (no existing Python
        // forward contract to promote), the `layout.realized` payload
        // kind.
        // Bumped 13 -> 14 by design-log 2026-07-08-cycle-25 D131: the
        // `RealizedGeometry` shape unification onto the WO-32
        // `regolith-lower::extract` seam's consumed record shape
        // (selector-keyed `paths`, `[lo, hi]` interval bounds,
        // free-string `roughness_class`, per-segment `wall`) --
        // removing `RealizedStage`, `WettedSegment.bend_count`, the
        // `RoughnessClass` enum, and per-stage `WallData`.
        // Bumped 14 -> 15 by WO-33 deliverable 2: the `ClaimForm::Compute`
        // variant, the `FieldDatum` schema type, and
        // `CoverageMethod::Undischarged` (the pre-discharge axis state).
        // Bumped 15 -> 16 by WO-34 deliverable 3 (HarnessPayload,
        // D99); 16 -> 17 by WO-51 (FeatureProgram sketches +
        // flow_paths, D150-D152; renumbered from a second 16 at
        // integration).
        // Bumped 17 -> 18 by WO-50 (D140/AD-27): the `DrawingModel`
        // schema (sheets/views/entities/dimensions/annotations/
        // tables), the `drawing.sheet` payload/domain-tag kind. Every
        // `Dimension` carries a mandatory `Provenance` field.
        // Bumped 18 -> 19 by WO-48 deliverable 3 (calcite/03 sec. 4,
        // D139/D145): the `FramePayload` schema (joints/members/
        // supports/loads/combinations) in `regolith-oblig`, the
        // `frame` payload/domain-tag kind, and the `BuildPayload.frames`
        // field.
        // Bumped 19 -> 20 by WO-54 (toolchain/27-costing.md D147): the
        // `std.cost` record schemas + itemized-estimate table payload,
        // plus the WO-26 rider adding an optional `window` field to
        // `ClaimForm::StaysWithin`.
        // Bumped 20 -> 21 by WO-55 (toolchain/28-optimization.md
        // D159/D160): the `OptimizationTrace` and `ChoicePoint` schemas
        // in `regolith-oblig`, the `optimize.trace`/`optimize.choice`
        // payload kinds on the D96 ref channel.
        // Bumped 21 -> 22 by WO-61 (D167, the ONE permitted follow-up
        // bump after WO-55's): the `ContractGraphPayload` schema (node/
        // edge L2 contract-graph surface, interaction-surface/29 sec.
        // 1.6) and the `BuildPayload.contract_graph` field.
        // Bumped 22 -> 23 by WO-56's completion dispatch (D168, the
        // ruling that CLOSES the cycle-30 schema train): no new schema
        // TYPE (the `ChoicePoint` shape is unchanged, landed by WO-55)
        // -- the bump is for the new first-class `BuildPayload.
        // choice_points` field (subject-keyed `ChoicePoint` map,
        // `regolith-lower::contracts` emission), the same
        // flownets/frames/harnesses precedent WO-61 used for
        // `contract_graph`.
        // Bumped 23 -> 24 by WO-62 slice B (D171/AD-32; ONE bump, D168
        // train rule): the `RealizedAssembly` schema (kind
        // `assembly.realized`) and, riding the same train per the D176
        // addendum ruling, `FramePayload.transfers` (the calcite
        // `structure ... transfers:` block, lowered).
        // Bumped 24 -> 25 by WO-68 (D181): `FrameMember.section_domain:
        // Option<String>` -- a calcite member's `section: in
        // registry(<family-ref>)` lowered domain declaration.
        // Bumped 25 -> 26 by WO-83 slice A (D190): `BuildPayload.tests`
        // + `regolith_ir::{TestDeclPayload, TestExpectationPayload}`.
        assert_eq!(super::SCHEMA_VERSION, 26);
    }
}
