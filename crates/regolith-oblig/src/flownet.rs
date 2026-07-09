//! `FlownetPayload`: the fluorite flownet payload (fluorite/03 sec. 2).
//!
//! One schema-versioned, Rust-sourced record (AD-5 precedent) that rides
//! the D96 payload-ref channel as the `flownet` payload KIND: elaboration
//! (WO-32 deliverable 3, a later dispatch) turns a `.fluo` flownet's
//! geometry + topology into this serialized, content-addressed record,
//! and every fluid claim lowers to an ordinary obligation carrying a
//! `PayloadRef { kind: "flownet", .. }` pointing at it. Solver packs
//! (feldspar `fluids`/`prop`) consume the payload and solve the network
//! entirely pack-side.
//!
//! This module defines the WIRE SHAPE only (deliverable 1). The lowering
//! passes that PRODUCE it, the `BuildPayload.flownets` field, and the
//! orchestrator `put` wiring are deliverables 3-4 (a later dispatch);
//! nothing here reads source, touches IO, or emits diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (elaboration
//! is responsible for sorting before construction) or a `BTreeMap` (key
//! order is intrinsic), so [`FlownetPayload::content_digest`] is stable
//! across builds of the same source.

use std::collections::BTreeMap;

use regolith_util::canon::{content_address, EncodeError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every flownet content address (AD-18): keeps
/// a flownet digest from colliding with any other payload kind even if
/// the canonical CBOR bytes happened to coincide.
pub const FLOWNET_DOMAIN_TAG: &str = "flownet";

/// A node identifier within a flownet (a stable elaboration-assigned
/// name); nodes are the network's pressure/flow junctions.
pub type NodeId = String;

/// A hash-pinned reference to a registry record (property table, vendor
/// curve, wall record, realized-geometry snapshot). Refs are by digest
/// ONLY -- resolution is the orchestrator's content-addressed store,
/// never a pack's own IO (mirrors [`crate::payload::PayloadRef`]).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct RecordRef {
    /// The blake3 content digest of the referenced record's bytes.
    pub digest: String,
    /// The producing record name, for diagnostics only (never part of
    /// the digest/identity).
    pub name: String,
}

/// A closed scalar interval `[lo, hi]` in a named unit -- the boundary
/// representation for every numeric flownet field (a schema-friendly
/// wire form of `regolith_qty::Interval`, whose internal representation
/// is not itself a boundary type).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct ScalarInterval {
    /// The lower bound.
    pub lo: f64,
    /// The upper bound (`hi >= lo`).
    pub hi: f64,
    /// The unit both bounds are expressed in (e.g. `"Pa"`, `"m"`).
    pub unit: String,
}

/// The property-record refs pinning the working medium (density, bulk
/// modulus, viscosity, vapour pressure). A flownet is single-medium at
/// the payload level (FOPEN-1 is enforced upstream of construction, in
/// `regolith_lower::fluid::check_flownet`'s `impl FluidPort<medium=...>`
/// binding check, WO-49 -- diagnostic `E0204`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct MediumRef {
    /// The hash-pinned property records describing the medium.
    pub records: Vec<RecordRef>,
}

/// The datum node and its imposed reference state (the one node whose
/// pressure/temperature is fixed, anchoring the network solve).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct Reference {
    /// The datum node id.
    pub node: NodeId,
    /// The imposed pressure interval at the datum.
    pub p: ScalarInterval,
    /// The imposed temperature interval at the datum.
    pub t: ScalarInterval,
}

/// The constructor kind of a flow edge (fluorite/02 sec. 3 vocabulary).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum EdgeKind {
    /// A rigid pipe run (hydraulic loss from wetted geometry).
    Pipe,
    /// A flexible hose run (may carry a wall-compliance record).
    Hose,
    /// A fixed restriction / metering orifice.
    Orifice,
    /// A valve (curve record, possibly with a commanded state var).
    Valve,
    /// A pump (head/flow curve record; imposes pressure rise).
    Pump,
    /// A regulator (imposes a controlled downstream pressure).
    Regulator,
    /// A filter (loss curve record).
    Filter,
    /// An imposer (imposes a value via the derivation machinery).
    Imposer,
    /// A heat-exchanger segment (couples to a hematite zone datum).
    HxSegment,
}

/// An edge's hydraulic parameters: either literal scalar givens or a
/// deferred extraction from a realized-geometry record (the seam the
/// deliverable-2 `regolith_lower::extract` module fills in at lowering
/// time; the payload records WHICH record/selector, resolved by digest).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case", tag = "source")]
pub enum EdgeParams {
    /// Literal scalar-interval parameters keyed by name (e.g.
    /// `"area"`, `"length"`, `"roughness"`).
    Scalars {
        /// Parameter name -> interval; `BTreeMap` for deterministic key
        /// order (AD-6).
        values: BTreeMap<String, ScalarInterval>,
    },
    /// Parameters derived from a realized-geometry record via a
    /// path/role selector (D99/F102 extraction seam).
    GeomExtract {
        /// The realized-geometry record the parameters are extracted
        /// from.
        record: RecordRef,
        /// The path/role selector into that record (e.g.
        /// `"coolant_jacket.wetted"`).
        selector: String,
    },
}

/// Wall compliance and wave-speed parameters for a compliant edge
/// (D93). Present only for edges named by transient/volume-budget
/// claims; a rigid edge carries `None`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct Compliance {
    /// The wall compliance `dV/dp` interval (volume gained per unit
    /// pressure rise over the edge's wetted length).
    pub wall_compliance: ScalarInterval,
    /// The Korteweg wave speed interval for the edge.
    pub wave_speed: ScalarInterval,
    /// The realized-geometry snapshot hash the fields were cited to
    /// (extraction provenance; empty when compliance came from a
    /// record ref rather than extraction).
    pub snapshot_hash: String,
}

/// One flow edge: a directed (positive-sense `a -> b`) network element
/// with its kind, parameters, optional wall compliance, and any vendor
/// curve records.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct FlowEdge {
    /// The stable edge id (elaboration-assigned).
    pub id: String,
    /// The constructor kind.
    pub kind: EdgeKind,
    /// The positive-sense tail node.
    pub a: NodeId,
    /// The positive-sense head node.
    pub b: NodeId,
    /// The edge's hydraulic parameters (scalars or a geometry-extract
    /// selector).
    pub params: EdgeParams,
    /// Wall compliance + wave speed, when the edge is compliant.
    pub compliance: Option<Compliance>,
    /// Hash-pinned vendor/datasheet curve records (valve/pump/filter).
    pub curves: Vec<RecordRef>,
}

/// A symbolic state domain: either an edge parameter or a net-level
/// state variable, left symbolic for the ONE-swept-obligation rule
/// (regolith/07 sec. 2) rather than enumerated into obligation copies.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct StateDomain {
    /// The target the state applies to (edge id or net name).
    pub target: String,
    /// The state variable name (e.g. a valve line-up config).
    pub var: String,
    /// The domain expression (the symbolic sweep set / discrete axis).
    pub domain: String,
}

/// The serialized flownet payload (fluorite/03 sec. 2, verbatim): a
/// content-addressed record carrying the medium, topology, datum, edges,
/// and symbolic state domains a solver pack needs to solve the network.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct FlownetPayload {
    /// The working-medium property-record refs.
    pub medium: MediumRef,
    /// Every node in the network (elaboration-sorted for determinism).
    pub nodes: Vec<NodeId>,
    /// The datum node and its imposed reference state.
    pub reference: Reference,
    /// Every flow edge (elaboration-sorted for determinism).
    pub edges: Vec<FlowEdge>,
    /// Symbolic edge-parameter and net-level state domains.
    pub states: Vec<StateDomain>,
}

impl FlownetPayload {
    /// The AD-18 content address of this payload under the `flownet`
    /// domain tag -- the digest a `PayloadRef` pins and the store keys
    /// on. Stable across builds of the same source (AD-6).
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(FLOWNET_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> FlownetPayload {
        let mut values = BTreeMap::new();
        values.insert(
            "area".to_string(),
            ScalarInterval {
                lo: 1.0e-4,
                hi: 1.0e-4,
                unit: "m^2".to_string(),
            },
        );
        FlownetPayload {
            medium: MediumRef {
                records: vec![RecordRef {
                    digest: "blake3:aa".to_string(),
                    name: "water_20c".to_string(),
                }],
            },
            nodes: vec!["n0".to_string(), "n1".to_string()],
            reference: Reference {
                node: "n0".to_string(),
                p: ScalarInterval {
                    lo: 1.0e5,
                    hi: 1.0e5,
                    unit: "Pa".to_string(),
                },
                t: ScalarInterval {
                    lo: 293.0,
                    hi: 293.0,
                    unit: "K".to_string(),
                },
            },
            edges: vec![FlowEdge {
                id: "e0".to_string(),
                kind: EdgeKind::Pipe,
                a: "n0".to_string(),
                b: "n1".to_string(),
                params: EdgeParams::Scalars { values },
                compliance: None,
                curves: vec![],
            }],
            states: vec![],
        }
    }

    #[test]
    fn flownet_payload_round_trips_json() {
        let payload = sample();
        let json = serde_json::to_string(&payload).unwrap();
        let back: FlownetPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back, payload);
    }

    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.nodes.push("n2".to_string());
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed field must change the digest"
        );
    }

    #[test]
    fn edge_params_variants_tag_on_source() {
        let extract = EdgeParams::GeomExtract {
            record: RecordRef {
                digest: "blake3:bb".to_string(),
                name: "jacket.step".to_string(),
            },
            selector: "coolant.wetted".to_string(),
        };
        let json = serde_json::to_value(&extract).unwrap();
        assert_eq!(json["source"], "geom_extract");
    }
}
