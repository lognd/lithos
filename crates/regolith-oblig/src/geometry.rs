//! `RealizedGeometry`: the mech realized-geometry payload (AD-25/D128,
//! WO-42 deliverable 1; unified per D131).
//!
//! One schema-versioned, Rust-sourced record (AD-5 precedent, mirroring
//! [`crate::flownet::FlownetPayload`]) that promotes WO-22's Python
//! forward contract (`regolith.realizer.mech.interpreter.RealizedGeometry`
//! / `TopologySummary`) per the AD-22 promotion rule: this is now the
//! source of truth, and the hand-written Python mirror is deleted in the
//! same change (the generated `_schema/` model replaces it).
//!
//! D131 (design-log `2026-07-08-cycle-25.md`): this is the ONE wire shape
//! for realized mech geometry. WO-42 deliverable 1 originally landed a
//! `stages` list with a `RoughnessClass` enum, `WettedSegment.bend_count`,
//! and per-stage `WallData` -- a shape that had already drifted from the
//! WO-32 `regolith-lower::extract` seam's consumed record shape (selector-
//! keyed `paths`, `[lo, hi]` interval bounds, free-string roughness
//! labels, per-SEGMENT wall). D131 repairs the drift: the CONSUMER's shape
//! wins. `RealizedGeometry` now carries selector-keyed `paths` whose
//! segments carry the extract seam's field list verbatim; there is no
//! per-stage struct -- "per-stage structure" is realized purely by the
//! pinned `<stage_name>.wetted` selector convention (D130). Removed,
//! never shipped to any consumer, no migration: `RealizedStage`,
//! `WettedSegment.bend_count`, the `RoughnessClass` enum, per-stage
//! `WallData`, point-valued scalars.
//!
//! This module defines the WIRE SHAPE only. The realizer emission seam
//! (`regolith.realizer.mech` `put`-ing this into the WO-30 store) is
//! deliverable 4 (a later dispatch); nothing here reads source, touches
//! IO, or emits diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered/keyed container (the
//! realizer is responsible for stable ordering/keys before construction),
//! so [`RealizedGeometry::content_digest`] is stable across builds of the
//! same feature program.

use std::collections::BTreeMap;

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every realized-geometry content address
/// (AD-18): keeps a geometry digest from colliding with any other
/// payload kind even if the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#geometry
pub const GEOMETRY_DOMAIN_TAG: &str = "geometry.realized";

/// A platform-portable summary of a realized solid's shape (AD-6),
/// promoted verbatim from WO-22's `TopologySummary` forward contract.
/// Deliberately NOT the raw STEP bytes (OCCT's serializer is not byte-
/// stable cross-platform/version, WO-22 acceptance) -- this is the
/// cross-platform determinism golden.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
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

/// A closed numeric interval `[lo, hi]` in SI units -- the wire form
/// every resolved measure on a [`PathSegment`] uses (D131: soundness,
/// realized dimensions carry process capability; a v1 producer may emit
/// a degenerate point interval).
// frob:doc docs/modules/regolith-oblig.md#geometry
pub type Bounds = [f64; 2];

/// A bend within a routed segment: turn angle (rad) and centreline
/// radius (m), each an `[lo, hi]` interval.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
pub struct Bend {
    /// Turn angle interval, rad.
    pub angle: Bounds,
    /// Centreline radius interval, m.
    pub radius: Bounds,
}

/// A thin-wall record on a segment: Young's modulus (Pa), wall
/// thickness (m), and (inner) diameter (m) -- the inputs to wall
/// compliance and the Korteweg wave speed (D93), each an `[lo, hi]`
/// interval.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
pub struct Wall {
    /// Young's modulus interval, Pa.
    pub youngs_modulus: Bounds,
    /// Wall thickness interval, m.
    pub thickness: Bounds,
    /// Inner diameter interval, m.
    pub diameter: Bounds,
}

/// One realized routed segment: the wetted-geometry measures the WO-32
/// `regolith-lower::extract` seam reads to fill an
/// `EdgeParams::GeomExtract` selector (D131 -- the seam's field list
/// verbatim).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
pub struct PathSegment {
    /// Per-segment environment slot name (shared with WO-34 wire runs).
    pub role: String,
    /// Wetted flow area interval, m^2.
    pub flow_area: Bounds,
    /// Centreline length interval, m.
    pub length: Bounds,
    /// Optional bend geometry.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bend: Option<Bend>,
    /// Process-capability roughness class label (free string, resolved
    /// against `regolith-lower::extract`'s `ROUGHNESS_TABLE`; not an
    /// enum -- the table is the single home for valid labels, D131).
    pub roughness_class: String,
    /// Signed elevation change over the segment (outlet minus inlet)
    /// interval, m.
    pub elevation_change: Bounds,
    /// Optional wall record (geometry only; the seam combines this with
    /// a medium's properties to derive compliance/wave speed).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wall: Option<Wall>,
}

/// A resolved routed path: an ordered list of segments (D131). Keyed by
/// selector in [`RealizedGeometry::paths`]; the pinned convention for
/// mech-emitted paths is `<stage_name>.wetted` (D130).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
pub struct RoutedPath {
    /// The path's segments, in order.
    pub segments: Vec<PathSegment>,
}

/// The serialized realized-geometry payload (AD-25, WO-22's forward
/// contract promoted + unified per D131 onto the WO-32 extract seam's
/// consumed shape): one realized part's STEP content hash, mass/topology
/// summary, and selector-keyed routed paths.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#geometry
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
    /// Every routed path, keyed by selector (`<stage_name>.wetted`
    /// convention, D130). No per-stage struct: per-stage structure is
    /// realized purely by the selector-key convention (D131).
    pub paths: BTreeMap<String, RoutedPath>,
}

impl RealizedGeometry {
    /// The AD-18 content address of this payload under the
    /// `geometry.realized` domain tag -- the digest a `PayloadRef` pins
    /// and the store keys on. Stable across builds of the same feature
    /// program (AD-6); a changed field (including a changed path)
    /// changes the digest, which is the G42 anti-staleness property.
    ///
    /// # Errors
    /// Propagates [`regolith_util::canon::EncodeError`] from the
    /// canonical encoder (only a non-finite float or a serializer
    /// failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#geometry
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, regolith_util::canon::EncodeError> {
        regolith_util::canon::content_address(GEOMETRY_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> RealizedGeometry {
        let mut paths = BTreeMap::new();
        paths.insert(
            "coolant_jacket.wetted".to_string(),
            RoutedPath {
                segments: vec![PathSegment {
                    role: "coolant_jacket".to_string(),
                    flow_area: [1.0e-4, 1.0e-4],
                    length: [0.2, 0.2],
                    bend: None,
                    roughness_class: "drawn_tube".to_string(),
                    elevation_change: [0.05, 0.05],
                    wall: Some(Wall {
                        youngs_modulus: [2.0e11, 2.0e11],
                        thickness: [0.002, 0.002],
                        diameter: [0.012, 0.012],
                    }),
                }],
            },
        );
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
            paths,
        }
    }

    // frob:tests crates/regolith-oblig/src/geometry.rs::RealizedGeometry.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other
            .paths
            .get_mut("coolant_jacket.wetted")
            .unwrap()
            .segments[0]
            .length = [0.3, 0.3];
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed segment field must change the digest (G42)"
        );
    }

    #[test]
    fn roughness_class_is_a_free_string() {
        let payload = sample();
        assert_eq!(
            payload.paths["coolant_jacket.wetted"].segments[0].roughness_class,
            "drawn_tube"
        );
    }

    #[test]
    fn wall_is_optional_per_segment() {
        let mut geom = sample();
        geom.paths.insert(
            "bracket.wetted".to_string(),
            RoutedPath {
                segments: vec![PathSegment {
                    role: "bracket".to_string(),
                    flow_area: [0.0, 0.0],
                    length: [0.0, 0.0],
                    bend: None,
                    roughness_class: "machined".to_string(),
                    elevation_change: [0.0, 0.0],
                    wall: None,
                }],
            },
        );
        let digest = geom.content_digest().unwrap();
        assert!(!digest.is_empty());
    }
}
