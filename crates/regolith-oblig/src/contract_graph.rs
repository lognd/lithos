//! `ContractGraphPayload`: the readable L2 contract-graph surface
//! (WO-61; interaction-surface/29 sec. 1.6 NORMATIVE; design-log
//! 2026-07-09-cycle-30 D165/D167; the WO-58 D2 completion).
//!
//! `BuildPayload` gains this schema-versioned record so the
//! `diagram.contract_graph` producer (a consumer, AD-22) can bind to a
//! real payload instead of reaching into `regolith-ir`'s own
//! `Interface`/`Mating` types directly: nodes name every interface
//! (with its promise-slot count) and every artifact/part a system
//! names, edges name every mating (with its side names and a
//! connection-kind label). This mirrors the `FlownetPayload`/
//! `FramePayload` precedent (AD-5/AD-18): wire shape defined here,
//! populated by `regolith-lower` (deliverable 2), carried unchanged by
//! `regolith-api::BuildPayload`.
//!
//! Determinism (AD-6): every collection is a `Vec` in elaboration
//! (source) order -- the builder in `regolith-lower::contracts` is
//! responsible for stable ordering before construction -- so
//! [`ContractGraphPayload::content_digest`] is stable across builds of
//! the same source.

use regolith_util::canon::{content_address, EncodeError};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every contract-graph content address (AD-18).
pub const CONTRACT_GRAPH_DOMAIN_TAG: &str = "contract_graph";

/// One node in the contract graph: either a declared `interface` (with
/// its promise-slot count) or an artifact/part name a system names in
/// its `parts:`/mating `sides` (promise-slot count `0`, since an
/// artifact is not itself an interface).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct ContractNode {
    /// The interface or artifact name (readable, never a hash).
    pub name: String,
    /// `"interface"` or `"artifact"` (D165's node-kind vocabulary).
    pub kind: String,
    /// The number of promise slots this node exposes (`0` for an
    /// artifact node).
    pub promise_slots: u32,
}

/// One edge in the contract graph: a named mating between two sides,
/// labeled with a connection kind derived from its declared effects
/// (`"mating"` when a mating declares no effect, honestly, rather than
/// a fabricated label).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct ContractEdge {
    /// The mating's own name.
    pub name: String,
    /// The connection-kind label (joined declared effects, or
    /// `"mating"` when none are declared).
    pub kind: String,
    /// The first named side.
    pub a: String,
    /// The second named side (equal to `a` for a degenerate
    /// single-sided mating -- never fabricated).
    pub b: String,
}

/// The serialized contract-graph payload: every interface/artifact node
/// and every mating edge, by name, in source order.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema, Default)]
pub struct ContractGraphPayload {
    /// Every node (elaboration-sorted for determinism).
    pub nodes: Vec<ContractNode>,
    /// Every edge (elaboration-sorted for determinism).
    pub edges: Vec<ContractEdge>,
}

impl ContractGraphPayload {
    /// The AD-18 content address of this payload under the
    /// `contract_graph` domain tag.
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug;
    /// this payload carries no floats today, so this is effectively
    /// infallible, but the signature stays honest about the encoder's
    /// real contract).
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(CONTRACT_GRAPH_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> ContractGraphPayload {
        ContractGraphPayload {
            nodes: vec![
                ContractNode {
                    name: "Bore".to_string(),
                    kind: "interface".to_string(),
                    promise_slots: 2,
                },
                ContractNode {
                    name: "housing".to_string(),
                    kind: "artifact".to_string(),
                    promise_slots: 0,
                },
                ContractNode {
                    name: "shaft".to_string(),
                    kind: "artifact".to_string(),
                    promise_slots: 0,
                },
            ],
            edges: vec![ContractEdge {
                name: "press_fit".to_string(),
                kind: "mating".to_string(),
                a: "housing".to_string(),
                b: "shaft".to_string(),
            }],
        }
    }

    #[test]
    fn contract_graph_payload_round_trips_json() {
        let payload = sample();
        let json = serde_json::to_string(&payload).unwrap();
        let back: ContractGraphPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back, payload);
    }

    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.nodes.push(ContractNode {
            name: "extra".to_string(),
            kind: "artifact".to_string(),
            promise_slots: 0,
        });
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed node list must change the digest"
        );
    }

    #[test]
    fn default_payload_is_empty() {
        let payload = ContractGraphPayload::default();
        assert!(payload.nodes.is_empty());
        assert!(payload.edges.is_empty());
    }
}
