//! Canonical encoding and domain-tagged content addressing (AD-5/AD-6).
//!
//! The encoder itself lives in `regolith_util::canon` (AD-18) -- the
//! bottom of the layering, shared by `regolith-sem` snapshot hashes and
//! `regolith-oblig` obligation keys. This module re-exports it
//! unchanged so no downstream caller (`regolith-api`, `regolith-py`,
//! the Python facade, `make schema`) sees a path change, and owns the
//! schemars export, which stays in `regolith-oblig` per AD-5.

pub use regolith_util::canon::{canonical_cbor, content_address, EncodeError};

use crate::SCHEMA_VERSION;

/// Export the JSON Schema of every cross-boundary type (obligations,
/// evidence, claims, lockfile rows) for the WO-18 pydantic codegen. This
/// is the single source of truth for the shared schema (AD-5).
///
/// The document is `{"schema_version": SCHEMA_VERSION, "definitions":
/// {<type name>: <JSON Schema>, ...}}`: every boundary type gets its own
/// named definition (`datamodel-code-generator` turns each into a frozen
/// pydantic model), and `schema_version` is stamped once at the document
/// root so the facade can assert it against the core at import (AD-5).
///
/// # Panics
/// Panics if the generated schema map cannot be serialized to JSON --
/// an infallible operation for schemars' own `Schema`/`Map` types, so
/// this is a programmer bug, not a user-facing error.
#[must_use]
pub fn export_schemas() -> String {
    use schemars::gen::SchemaSettings;

    let mut generator = SchemaSettings::draft07().into_generator();

    // Every cross-boundary type (AD-5): claims, obligations, evidence,
    // signatures, and the todo/assume/waive ledger.
    generator.subschema_for::<crate::claim::Window>();
    generator.subschema_for::<crate::claim::ClaimForm>();
    generator.subschema_for::<crate::claim::Claim>();
    generator.subschema_for::<crate::claim::Assumption>();
    generator.subschema_for::<crate::obligation::Given>();
    generator.subschema_for::<crate::obligation::SweepDomain>();
    generator.subschema_for::<crate::obligation::Obligation>();
    generator.subschema_for::<crate::obligation::SnapshotRecord>();
    generator.subschema_for::<regolith_qty::Cause>();
    generator.subschema_for::<regolith_qty::Resolution>();
    generator.subschema_for::<crate::evidence::Status>();
    generator.subschema_for::<crate::evidence::Evidence>();
    generator.subschema_for::<crate::evidence::EvidenceCache>();
    generator.subschema_for::<crate::solver::SolverResponse>();
    // PayloadRef (D96) is not reached from any other Rust type -- it is
    // the D96 channel's wire shape consumed directly by the Python
    // harness's `DischargeRequest.payloads` (a Python-native model) --
    // so it needs its own root export to reach `_schema/models.py`.
    generator.subschema_for::<crate::payload::PayloadRef>();
    // WO-32 deliverable 1: the fluorite flownet payload (fluorite/03
    // sec. 2). Like `PayloadRef`, it is not reached from any other Rust
    // boundary type -- the Python orchestrator produces/stores it
    // directly (the `flownet` payload kind) -- so it needs its own root
    // export to reach `_schema/models.py`.
    generator.subschema_for::<crate::flownet::FlownetPayload>();
    generator.subschema_for::<crate::geometry::RealizedGeometry>();
    // WO-50 deliverable 1 (D140/AD-27): the drawings/schedules
    // documentation IR. Like `RealizedGeometry`, not reached from any
    // other Rust boundary type -- the Python drawing producers build
    // and store it directly -- so it needs its own root export to
    // reach `_schema/models.py`.
    generator.subschema_for::<crate::drawing::DrawingModel>();
    // WO-42 deliverable 2: the elec realized placed/routed board
    // payload. Like `RealizedGeometry`, not reached from any other Rust
    // boundary type -- the Python realizer produces/stores it directly
    // (the `layout.realized` payload kind) -- so it needs its own root
    // export to reach `_schema/models.py`.
    generator.subschema_for::<crate::layout::RealizedLayout>();
    // WO-33 deliverable 2: the computed-indexed-field datum ledger
    // entry. Like `PayloadRef`/`FlownetPayload`, it is not reached from
    // any other Rust boundary type -- the Python orchestrator's build
    // payload carries the ledger directly -- so it needs its own root
    // export to reach `_schema/models.py`.
    generator.subschema_for::<crate::field::FieldDatum>();
    // WO-34 deliverable 3 (D99): the cuprite wiring-harness routed-runs
    // payload. Like `FlownetPayload`, it is not reached from any other
    // Rust boundary type -- the Python orchestrator's build payload
    // carries it directly (the `harness` payload kind) -- so it needs
    // its own root export to reach `_schema/models.py`.
    generator.subschema_for::<crate::harness::HarnessPayload>();
    generator.subschema_for::<crate::attestation::SignatureAlgorithm>();
    generator.subschema_for::<crate::attestation::Attestation>();
    generator.subschema_for::<crate::signature::Signature>();
    generator.subschema_for::<crate::signature::ImplRecord>();
    generator.subschema_for::<crate::signature::SignatureRegistry>();
    generator.subschema_for::<crate::waiver::Waiver>();
    generator.subschema_for::<crate::waiver::WaiverRecord>();
    generator.subschema_for::<crate::waiver::LedgerEntry>();
    generator.subschema_for::<crate::waiver::WaiveLedger>();
    // WO-29 deliverable 3: the feature-program payload field (Q2).
    generator.subschema_for::<regolith_ir::ResolvedFeatureParam>();
    generator.subschema_for::<regolith_ir::FeatureOp>();
    generator.subschema_for::<regolith_ir::FeatureProgram>();
    // WO-29 deliverable 4: the binding-requirement bridge payload fields
    // (Q3/D90 -- Rust emits the raw capability demands).
    generator.subschema_for::<regolith_ir::CapabilityDemand>();
    generator.subschema_for::<regolith_ir::BlockRequirement>();
    // WO-48 deliverable 3 (calcite/03 sec. 4): the calcite structural
    // frame payload. Like `FlownetPayload`/`HarnessPayload`, it is not
    // reached from any other Rust boundary type -- the Python
    // orchestrator's build payload carries it directly (the `frame`
    // payload kind) -- so it needs its own root export to reach
    // `_schema/models.py`. Registered LAST: `schemars`/
    // `datamodel-code-generator` assign anonymous duplicate-shaped enum
    // definitions (`Kind`, `Kind1`, ...) ordinals by generation order,
    // so inserting a new root type earlier in this function renumbers
    // every later one and silently breaks hand-written references
    // elsewhere (e.g. `producers.py`'s `Kind.segment`) -- appending here
    // keeps every existing definition's generated name stable.
    generator.subschema_for::<crate::frame::FramePayload>();
    // WO-54 (toolchain/27-costing.md D147): the `std.cost` record
    // schemas + the itemized-estimate `table`-kind payload. Like
    // `FramePayload` above, none of these are reached from any other
    // Rust boundary type, so each needs its own root export. Appended
    // LAST, after `FramePayload`, for the same anonymous-enum-ordinal
    // stability reason documented on that call.
    generator.subschema_for::<crate::cost::RateRecord>();
    generator.subschema_for::<crate::cost::PricingRecord>();
    generator.subschema_for::<crate::cost::UnitCostRecord>();
    generator.subschema_for::<crate::cost::ItemizedEstimate>();
    // WO-55 (toolchain/28-optimization.md D159/D160): the optimization
    // engine's trace + choice-point payloads. Like `FramePayload`/
    // `ItemizedEstimate` above, neither is reached from any other Rust
    // boundary type -- the Python orchestrator produces/stores them
    // directly (the `optimize.trace`/`optimize.choice` payload kinds)
    // -- so each needs its own root export. Appended LAST for the same
    // anonymous-enum-ordinal stability reason documented above.
    generator.subschema_for::<crate::optimize::TerminationStatus>();
    generator.subschema_for::<crate::optimize::ObjectiveDirection>();
    generator.subschema_for::<crate::optimize::CandidateEntry>();
    generator.subschema_for::<crate::optimize::OptimizationTrace>();
    generator.subschema_for::<crate::optimize::ChoicePoint>();

    let definitions = generator.take_definitions();
    let document = serde_json::json!({
        "schema_version": SCHEMA_VERSION,
        "definitions": definitions,
    });
    serde_json::to_string_pretty(&document).expect("schemars Map<String, Schema> always serializes")
}

#[cfg(test)]
mod tests {
    use super::export_schemas;

    #[test]
    fn export_schemas_carries_schema_version_and_definitions() {
        let doc = export_schemas();
        let parsed: serde_json::Value = serde_json::from_str(&doc).unwrap();
        assert_eq!(parsed["schema_version"], crate::SCHEMA_VERSION);
        assert!(parsed["definitions"]["Obligation"].is_object());
        assert!(parsed["definitions"]["Evidence"].is_object());
        assert!(parsed["definitions"]["SolverResponse"].is_object());
        assert!(parsed["definitions"]["PayloadRef"].is_object());
        assert!(parsed["definitions"]["FlownetPayload"].is_object());
        assert!(parsed["definitions"]["RealizedGeometry"].is_object());
        assert!(parsed["definitions"]["RealizedLayout"].is_object());
        assert!(parsed["definitions"]["FieldDatum"].is_object());
        assert!(parsed["definitions"]["FramePayload"].is_object());
        assert!(parsed["definitions"]["OptimizationTrace"].is_object());
        assert!(parsed["definitions"]["ChoicePoint"].is_object());
    }
}
