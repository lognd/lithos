//! `RealizedAssembly`: the mech realized-assembly payload (AD-25/AD-32,
//! WO-62 slice B deliverable 4; charter `30-geometry-lowering.md`
//! sec. 1.4).
//!
//! One more first-class L4 IR by the AD-25 growth rule (schemars
//! schema in `regolith-oblig`, content-addressed via the one encoder,
//! payload kind `assembly.realized` on the D96 channel): a mating
//! graph over parts with [`crate::geometry::RealizedGeometry`] digests
//! solves (Python realizer, `regolith.realizer.mech.assembly`) to a
//! placed part set, dof states, extracted mass/COM, and pairwise
//! interference facts.
//!
//! This module defines the WIRE SHAPE only (mirrors `geometry.rs`'s
//! precedent field for field): nothing here reads source, touches IO,
//! solves a mate graph, or emits diagnostics -- that is the Python
//! realizer's job (deliverable 5).
//!
//! Determinism (AD-6): every collection is an ordered `Vec`/`BTreeMap`
//! (the realizer sorts by part/pair id before construction), so
//! [`RealizedAssembly::content_digest`] is stable across builds of the
//! same mating graph.

use std::collections::BTreeMap;

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use regolith_util::canon::{content_address, EncodeError};

/// Domain tag folded into every realized-assembly content address
/// (AD-18): keeps an assembly digest from colliding with any other
/// payload kind even if the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#assembly
pub const ASSEMBLY_DOMAIN_TAG: &str = "assembly.realized";

/// A rigid-body placement: translation (metres, world frame) plus an
/// intrinsic XYZ Euler rotation (degrees) -- the wire shape the STEP
/// assembly exporter's `Location(position, rotation)` call consumes
/// directly (no quaternion round-trip needed at this v1 scope).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#assembly
pub struct Transform {
    /// World-frame translation, metres.
    pub translation_m: [f64; 3],
    /// Intrinsic XYZ Euler rotation, degrees.
    pub rotation_deg: [f64; 3],
}

impl Transform {
    /// The identity placement (the mate-solve root part's transform,
    /// charter sec. 1.4: "root part at identity").
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#assembly
    pub const fn identity() -> Self {
        Self {
            translation_m: [0.0, 0.0, 0.0],
            rotation_deg: [0.0, 0.0, 0.0],
        }
    }
}

/// One placed part: its declared id, the [`crate::geometry::
/// RealizedGeometry`] digest it was placed from, and its solved
/// world-frame [`Transform`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#assembly
pub struct AssemblyPart {
    /// The part's declared id (source order -- AD-6).
    pub id: String,
    /// The content digest of the part's `RealizedGeometry` payload.
    pub geometry_digest: String,
    /// The part's solved placement.
    pub transform: Transform,
}

/// One pairwise interference fact (charter sec. 1.4: "an interference
/// is a release-gated diagnostic with both part names and the overlap
/// measure"): the two part ids (source-sorted) and the overlap volume
/// (mm^3, axis-aligned-bbox measure -- the v1 interference test).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#assembly
pub struct Interference {
    /// The first part's id (sorted before `part_b`).
    pub part_a: String,
    /// The second part's id.
    pub part_b: String,
    /// The overlap volume, mm^3.
    pub overlap_mm3: f64,
}

/// One typed mate edge of the solved assembly graph (WO-104): the
/// two parts a declared mate joins, the hematite/03 sec. 3 vocabulary
/// word it spells (`align`/`coincident`/`distance`/`angle`), and the
/// rigid degrees of freedom the mate consumes. EXPOSED from the mate
/// solve, never re-derived: the placement math already ran, this only
/// surfaces the edge the solve consumed so assembly-instruction
/// producers (WO-96/WO-100) can read a real ordering. `dof_consumed`
/// is the count of the 6 rigid DOF the mate removes (a full rigid mate
/// = 6), reported by the realizer alongside the placement.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#assembly
pub struct MateEdge {
    /// The mate's declared id (source order -- AD-6).
    pub id: String,
    /// The `from_part` id (the already-placed side the solve composed
    /// against).
    pub part_a: String,
    /// The `to_part` id (placed by this mate).
    pub part_b: String,
    /// The hematite/03 sec. 3 vocabulary word this mate spells
    /// (`align`, `coincident`, `distance`, `angle`) -- provenance only,
    /// exactly the label the mate solve carried.
    pub kind: String,
    /// The count of rigid degrees of freedom (of 6) this mate consumes.
    pub dof_consumed: u32,
}

/// The serialized realized-assembly payload (charter sec. 1.4,
/// verbatim): every placed part, each part's DOF state after solve,
/// extracted mass/COM, and every pairwise interference fact.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#assembly
pub struct RealizedAssembly {
    /// The content hash of the mating-graph input this assembly was
    /// solved from (provenance; the G42 anti-staleness citation,
    /// mirroring `RealizedGeometry::feature_program_hash`). Now hashes
    /// the exposed [`RealizedAssembly::mates`] too (they are part of the
    /// solved graph -- a changed mate edge changes the digest, G42).
    pub mating_graph_hash: String,
    /// Every placed part, source-order sorted by id (AD-6).
    pub parts: Vec<AssemblyPart>,
    /// The typed mate edges of the solved graph, source order (AD-6):
    /// what WO-96/WO-100 read for real instruction ordering. EXPOSED
    /// from the solve, never re-derived (WO-104).
    pub mates: Vec<MateEdge>,
    /// Each part's solved degree-of-freedom state (`"fixed"` for the
    /// mate-solve root, `"placed"` for a part solved by a spanning
    /// mate, `"underconstrained"` for a part with no path to the root
    /// -- honestly recorded, never silently dropped), keyed by part id.
    pub dof_states: BTreeMap<String, String>,
    /// Extracted total mass, kg.
    pub mass_kg: f64,
    /// Extracted assembly-level center of mass, world frame, metres.
    pub com_m: [f64; 3],
    /// Every pairwise interference fact found by the v1 AABB overlap
    /// test, sorted by `(part_a, part_b)`.
    pub interferences: Vec<Interference>,
}

impl RealizedAssembly {
    /// The AD-18 content address of this payload under the
    /// `assembly.realized` domain tag -- the digest a `PayloadRef` pins
    /// and the store keys on. Stable across builds of the same mating
    /// graph (AD-6); a changed field (including a changed placement or
    /// interference) changes the digest (G42).
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#assembly
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(ASSEMBLY_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
#[allow(clippy::float_cmp)]
mod tests {
    use super::*;

    fn sample() -> RealizedAssembly {
        let mut dof_states = BTreeMap::new();
        dof_states.insert("Base".to_string(), "fixed".to_string());
        dof_states.insert("Arm".to_string(), "placed".to_string());
        RealizedAssembly {
            mating_graph_hash: "blake3:aa".to_string(),
            parts: vec![
                AssemblyPart {
                    id: "Arm".to_string(),
                    geometry_digest: "blake3:bb".to_string(),
                    transform: Transform {
                        translation_m: [0.1, 0.0, 0.0],
                        rotation_deg: [0.0, 0.0, 0.0],
                    },
                },
                AssemblyPart {
                    id: "Base".to_string(),
                    geometry_digest: "blake3:cc".to_string(),
                    transform: Transform::identity(),
                },
            ],
            mates: vec![MateEdge {
                id: "m1".to_string(),
                part_a: "Base".to_string(),
                part_b: "Arm".to_string(),
                kind: "coincident".to_string(),
                dof_consumed: 6,
            }],
            dof_states,
            mass_kg: 1.5,
            com_m: [0.05, 0.0, 0.0],
            interferences: Vec::new(),
        }
    }

    // frob:tests crates/regolith-oblig/src/assembly.rs::RealizedAssembly.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.parts[0].transform.translation_m[0] = 0.2;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed placement must change the digest (G42)"
        );
    }

    #[test]
    fn identity_transform_is_all_zero() {
        let t = Transform::identity();
        assert_eq!(t.translation_m, [0.0, 0.0, 0.0]);
        assert_eq!(t.rotation_deg, [0.0, 0.0, 0.0]);
    }

    #[test]
    fn mate_edges_are_exposed_and_change_the_digest() {
        let payload = sample();
        assert_eq!(payload.mates.len(), 1);
        assert_eq!(payload.mates[0].part_a, "Base");
        assert_eq!(payload.mates[0].part_b, "Arm");
        assert_eq!(payload.mates[0].kind, "coincident");
        assert_eq!(payload.mates[0].dof_consumed, 6);

        let d1 = payload.content_digest().unwrap();
        let mut other = sample();
        other.mates[0].dof_consumed = 3;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed mate edge must change the digest (G42)"
        );
    }

    #[test]
    fn interference_carries_both_names_and_a_measure() {
        let mut payload = sample();
        payload.interferences.push(Interference {
            part_a: "Arm".to_string(),
            part_b: "Base".to_string(),
            overlap_mm3: 12.5,
        });
        let json = serde_json::to_string(&payload).unwrap();
        let back: RealizedAssembly = serde_json::from_str(&json).unwrap();
        assert_eq!(back.interferences.len(), 1);
        assert_eq!(back.interferences[0].part_a, "Arm");
        assert_eq!(back.interferences[0].overlap_mm3, 12.5);
    }
}
