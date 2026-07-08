//! `RealizedGeometry`: the mech realized-geometry payload (AD-25/D128,
//! WO-42 deliverable 1).
//!
//! One schema-versioned, Rust-sourced record (AD-5 precedent, mirroring
//! [`crate::flownet::FlownetPayload`]) that promotes WO-22's Python
//! forward contract (`regolith.realizer.mech.interpreter.RealizedGeometry`
//! / `TopologySummary`) per the AD-22 promotion rule: this is now the
//! source of truth, and the hand-written Python mirror is deleted in the
//! same change (the generated `_schema/` model replaces it).
//!
//! Extended beyond WO-22's forward contract with the fields the WO-32
//! `regolith-lower::extract` seam reads: per-stage wetted-geometry
//! segments (flow area, path length, bend count, roughness class,
//! elevation) and per-stage wall data (modulus, thickness, diameter) --
//! `../design/22-mech-geometry-realizer.md`'s promoted contract plus the
//! extract seam's field list. Payload kind stays `geometry.realized`
//! (already in the D96 vocabulary, `../design/20-solver-abstraction.md`
//! sec. 8.3 -- no vocabulary change needed for this slice).
//!
//! This module defines the WIRE SHAPE only. The realizer emission seam
//! (`regolith.realizer.mech` `put`-ing this into the WO-30 store) is
//! deliverable 4 (a later dispatch); nothing here reads source, touches
//! IO, or emits diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (the
//! realizer is responsible for stable ordering before construction), so
//! [`RealizedGeometry::content_digest`] is stable across builds of the
//! same feature program.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every realized-geometry content address
/// (AD-18): keeps a geometry digest from colliding with any other
/// payload kind even if the canonical CBOR bytes happened to coincide.
pub const GEOMETRY_DOMAIN_TAG: &str = "geometry.realized";

/// A platform-portable summary of a realized solid's shape (AD-6),
/// promoted verbatim from WO-22's `TopologySummary` forward contract.
/// Deliberately NOT the raw STEP bytes (OCCT's serializer is not byte-
/// stable cross-platform/version, WO-22 acceptance) -- this is the
/// cross-platform determinism golden.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct TopologySummary {
    /// Number of solids in the realized body.
    pub num_solids: u32,
    /// Number of faces.
    pub num_faces: u32,
    /// Number of edges.
    pub num_edges: u32,
    /// Number of vertices.
    pub num_vertices: u32,
    /// Solid volume in mm^3.
    pub volume_mm3: f64,
    /// Total surface area in mm^2.
    pub area_mm2: f64,
    /// Axis-aligned bounding-box minimum corner, mm.
    pub bbox_min_mm: [f64; 3],
    /// Axis-aligned bounding-box maximum corner, mm.
    pub bbox_max_mm: [f64; 3],
    /// Center of mass, mm.
    pub center_of_mass_mm: [f64; 3],
}

/// The roughness class of a wetted-flow-path surface (WO-32 extract
/// seam vocabulary; a coarse enum rather than a raw scalar so packs
/// resolve absolute roughness from a shared table keyed on manufacturing
/// process, not on a per-part guess).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum RoughnessClass {
    /// As-machined smooth bore (reamed/honed).
    Smooth,
    /// As-machined standard bore (drilled/milled, no finishing pass).
    Standard,
    /// As-cast or as-printed bore (rough).
    Rough,
}

/// One wetted-geometry segment within a realized stage: the flow-path
/// measures the WO-32 `regolith-lower::extract` seam reads to fill an
/// `EdgeParams::GeomExtract` selector.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct WettedSegment {
    /// The stable segment id (realizer-assigned; matches the extract
    /// selector's path component).
    pub id: String,
    /// Cross-sectional flow area, m^2.
    pub flow_area_m2: f64,
    /// Wetted path length along the segment centerline, m.
    pub path_length_m: f64,
    /// Number of bends (90-degree-equivalent) along the segment.
    pub bend_count: u32,
    /// The wetted surface's roughness class.
    pub roughness: RoughnessClass,
    /// Elevation of the segment's reference point relative to the part
    /// datum, m (gravity-head extraction).
    pub elevation_m: f64,
}

/// Structural wall data for a realized stage's pressure boundary: the
/// measures a compliance/burst-margin pack reads via extraction.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct WallData {
    /// Elastic modulus of the wall material, Pa.
    pub modulus_pa: f64,
    /// Wall thickness, m.
    pub thickness_m: f64,
    /// Wetted-bore diameter, m.
    pub diameter_m: f64,
}

/// One realized stage: the wetted-geometry segments and wall data
/// belonging to a single named build stage (a `FeatureProgram` stage,
/// e.g. one manifold body or one coolant jacket).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct RealizedStage {
    /// The stable stage id (realizer-assigned, matches the
    /// `FeatureProgram` stage it was built from).
    pub id: String,
    /// Every wetted-geometry segment in this stage (realizer-sorted for
    /// determinism, AD-6).
    pub wetted_segments: Vec<WettedSegment>,
    /// Wall data for this stage, when the stage forms a pressure
    /// boundary; `None` for a stage with no wetted wall (e.g. a purely
    /// structural bracket feature).
    pub wall: Option<WallData>,
}

/// The serialized realized-geometry payload (AD-25, WO-22's forward
/// contract promoted verbatim + the WO-32 extract-seam extension): one
/// realized part's STEP content hash, mass/topology summary, and
/// per-stage wetted-geometry + wall data.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct RealizedGeometry {
    /// The content hash of the `FeatureProgram` this geometry was
    /// realized from (provenance; the G42 anti-staleness citation).
    pub feature_program_hash: String,
    /// The SHA-256 content hash of the normalized STEP export (WO-22's
    /// determinism note: OCCT's own STEP serialization is not byte-
    /// stable cross-platform, so `topology` is the cross-platform
    /// golden and this hash pins the side-artifact STEP bytes).
    pub step_content_hash: String,
    /// The cross-platform-stable topology/mass-properties summary.
    pub topology: TopologySummary,
    /// Every realized stage (realizer-sorted for determinism, AD-6).
    pub stages: Vec<RealizedStage>,
}

impl RealizedGeometry {
    /// The AD-18 content address of this payload under the
    /// `geometry.realized` domain tag -- the digest a `PayloadRef` pins
    /// and the store keys on. Stable across builds of the same feature
    /// program (AD-6); a changed field (including a changed stage)
    /// changes the digest, which is the G42 anti-staleness property.
    ///
    /// # Errors
    /// Propagates [`regolith_util::canon::EncodeError`] from the
    /// canonical encoder (only a non-finite float or a serializer
    /// failure -- an upstream bug).
    pub fn content_digest(&self) -> Result<String, regolith_util::canon::EncodeError> {
        regolith_util::canon::content_address(GEOMETRY_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> RealizedGeometry {
        RealizedGeometry {
            feature_program_hash: "blake3:aa".to_string(),
            step_content_hash: "sha256:bb".to_string(),
            topology: TopologySummary {
                num_solids: 1,
                num_faces: 6,
                num_edges: 12,
                num_vertices: 8,
                volume_mm3: 1000.0,
                area_mm2: 600.0,
                bbox_min_mm: [0.0, 0.0, 0.0],
                bbox_max_mm: [10.0, 10.0, 10.0],
                center_of_mass_mm: [5.0, 5.0, 5.0],
            },
            stages: vec![RealizedStage {
                id: "coolant_jacket".to_string(),
                wetted_segments: vec![WettedSegment {
                    id: "coolant_jacket.wetted".to_string(),
                    flow_area_m2: 1.0e-4,
                    path_length_m: 0.2,
                    bend_count: 2,
                    roughness: RoughnessClass::Standard,
                    elevation_m: 0.05,
                }],
                wall: Some(WallData {
                    modulus_pa: 2.0e11,
                    thickness_m: 0.002,
                    diameter_m: 0.012,
                }),
            }],
        }
    }

    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.stages[0].wetted_segments[0].path_length_m = 0.3;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed segment field must change the digest (G42)"
        );
    }

    #[test]
    fn roughness_class_serializes_snake_case() {
        let json = serde_json::to_value(RoughnessClass::Standard).unwrap();
        assert_eq!(json, "standard");
    }

    #[test]
    fn wall_is_optional_for_non_pressure_stages() {
        let mut geom = sample();
        geom.stages.push(RealizedStage {
            id: "bracket".to_string(),
            wetted_segments: vec![],
            wall: None,
        });
        let digest = geom.content_digest().unwrap();
        assert!(!digest.is_empty());
    }
}
