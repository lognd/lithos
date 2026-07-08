//! The routed-geometry extraction seam (WO-32 deliverable 2; D99/F102).
//!
//! ONE module that reads a realized-geometry record and, for a
//! path/role selector, produces the typed hydraulic parameters fluorite
//! lowering needs -- flow areas, length, bend angles/radii, roughness
//! class, elevation change -- plus (from a wall record: E, thickness,
//! diameter) wall compliance and the Korteweg wave speed. It is the
//! SHARED seam WO-34 (wire runs) reads: the result carries a per-segment
//! list with a per-segment environment `role` slot so a wire run is a
//! multi-segment path while a fluid edge is a single-segment run.
//!
//! PURITY (AD-17): this module is a pure function of its inputs. The
//! record CONTENT is passed in as bytes -- the orchestrator resolves the
//! record ref through the WO-30 content store and hands the bytes here;
//! nothing in this module reads a file, a registry, or the network.
//! Every result is cited to the geometry snapshot hash it came from.
//!
//! ERRORS ARE DATA: a malformed record, an absent selector, or an
//! unknown roughness class is a typed [`ExtractError`] value (thiserror,
//! not anyhow). Deliverable 3 (a later dispatch) turns these into
//! `regolith_diag` diagnostics at the lowering boundary; this leaf never
//! renders and never panics.
//!
//! UNITS: every field is in SI base units (m, m^2, rad, Pa, kg/m^3,
//! m^3/Pa, m/s); the emitted [`ScalarInterval`]s carry the unit string.
//! Interval bounds round OUTWARD at every operation (AD-6 soundness):
//! an extracted bound never excludes a physically reachable value. This
//! mirrors `regolith_qty::Interval`'s discipline, but composes
//! DIMENSIONLESS numeric intervals (products, quotients, square roots)
//! that the dimensional `Interval` type does not expose -- it is not a
//! second copy of that unit-conversion machinery.

use std::collections::BTreeMap;

use regolith_oblig::ScalarInterval;
use serde::{Deserialize, Serialize};

/// A closed numeric interval `[lo, hi]` with no attached unit -- the
/// internal working form the extractor composes; unit strings are
/// attached only at the [`ScalarInterval`] output boundary.
#[derive(Debug, Clone, Copy)]
struct Iv {
    lo: f64,
    hi: f64,
}

impl Iv {
    fn point(x: f64) -> Iv {
        Iv { lo: x, hi: x }
    }

    fn from_bounds(bounds: [f64; 2]) -> Iv {
        let (lo, hi) = if bounds[0] <= bounds[1] {
            (bounds[0], bounds[1])
        } else {
            (bounds[1], bounds[0])
        };
        Iv { lo, hi }
    }

    /// Interval sum (signed-safe): `[a,b] + [c,d] = [a+c, b+d]`.
    fn add(self, other: Iv) -> Iv {
        Iv {
            lo: (self.lo + other.lo).next_down(),
            hi: (self.hi + other.hi).next_up(),
        }
    }

    /// Product of two NON-NEGATIVE intervals.
    fn mul(self, other: Iv) -> Iv {
        Iv {
            lo: (self.lo * other.lo).next_down(),
            hi: (self.hi * other.hi).next_up(),
        }
    }

    /// Quotient of two POSITIVE intervals: `[a,b] / [c,d] = [a/d, b/c]`.
    fn div(self, other: Iv) -> Iv {
        Iv {
            lo: (self.lo / other.hi).next_down(),
            hi: (self.hi / other.lo).next_up(),
        }
    }

    /// Multiply by a POSITIVE scalar constant.
    fn scale(self, k: f64) -> Iv {
        Iv {
            lo: (self.lo * k).next_down(),
            hi: (self.hi * k).next_up(),
        }
    }

    /// Reciprocal of a POSITIVE interval.
    fn recip(self) -> Iv {
        Iv {
            lo: (1.0 / self.hi).next_down(),
            hi: (1.0 / self.lo).next_up(),
        }
    }

    /// Square root of a NON-NEGATIVE interval.
    fn sqrt(self) -> Iv {
        Iv {
            lo: self.lo.sqrt().next_down(),
            hi: self.hi.sqrt().next_up(),
        }
    }

    fn into_scalar(self, unit: &str) -> ScalarInterval {
        ScalarInterval {
            lo: self.lo,
            hi: self.hi,
            unit: unit.to_string(),
        }
    }
}

/// Medium bulk modulus and density (SI), supplied by the caller from
/// the already-resolved medium property record so this module stays
/// medium-IO-free: the wall geometry alone cannot fix a Korteweg wave
/// speed, which folds in the fluid's compressibility.
#[derive(Debug, Clone, Copy)]
pub struct MediumProps {
    /// Fluid bulk modulus interval, Pa.
    pub bulk_modulus: [f64; 2],
    /// Fluid density interval, kg/m^3.
    pub density: [f64; 2],
}

/// A bend within a routed segment: turn angle and centreline radius.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RawBend {
    angle: [f64; 2],
    radius: [f64; 2],
}

/// A thin-wall record on a segment: Young's modulus, wall thickness,
/// and (inner) diameter -- the inputs to wall compliance and the
/// Korteweg wave speed (D93).
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RawWall {
    youngs_modulus: [f64; 2],
    thickness: [f64; 2],
    diameter: [f64; 2],
}

/// One realized routed segment (the hand-authored / WO-22-engine wire
/// shape). Bounds are `[lo, hi]` SI pairs.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RawSegment {
    /// Per-segment environment slot name (shared with WO-34 wire runs).
    role: String,
    /// Wetted flow area, m^2.
    flow_area: [f64; 2],
    /// Centreline length, m.
    length: [f64; 2],
    /// Optional bend geometry.
    #[serde(default)]
    bend: Option<RawBend>,
    /// Process-capability roughness class label.
    roughness_class: String,
    /// Signed elevation change over the segment (outlet minus inlet), m.
    elevation_change: [f64; 2],
    /// Optional wall record.
    #[serde(default)]
    wall: Option<RawWall>,
}

/// A resolved routed path within a realized record.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RawPath {
    segments: Vec<RawSegment>,
}

/// A realized-geometry record: a snapshot hash plus its routed paths,
/// keyed by selector. Hand-authored records are legitimate fixtures
/// (AD-22 producer role) until the WO-22 engine emits them.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RealizedRecord {
    /// The geometry snapshot hash every extraction result is cited to.
    snapshot_hash: String,
    /// Routed paths keyed by selector.
    paths: BTreeMap<String, RawPath>,
}

/// A wall extraction: compliance, distensibility, and (when medium
/// props were supplied) the Korteweg wave speed -- all cited to the
/// segment's snapshot hash via the enclosing [`GeometryExtraction`].
#[derive(Debug, Clone, PartialEq)]
pub struct WallExtraction {
    /// Wall compliance `dV/dp = L * pi * D^3 / (4 E t)`, m^3/Pa.
    pub wall_compliance: ScalarInterval,
    /// Wall distensibility `D / (E t)`, 1/Pa (the medium-free Korteweg
    /// term).
    pub distensibility: ScalarInterval,
    /// Korteweg wave speed `1 / sqrt(rho (1/K + D/(E t)))`, m/s; present
    /// only when [`MediumProps`] were supplied to the extraction.
    pub wave_speed: Option<ScalarInterval>,
}

/// A resolved roughness: the process-capability class and its absolute
/// roughness height interval.
#[derive(Debug, Clone, PartialEq)]
pub struct RoughnessExtraction {
    /// The process-capability class label carried on the record.
    pub class: String,
    /// The resolved absolute roughness height, m.
    pub height: ScalarInterval,
}

/// A bend extraction: turn angle and centreline radius.
#[derive(Debug, Clone, PartialEq)]
pub struct BendExtraction {
    /// Turn angle, rad.
    pub angle: ScalarInterval,
    /// Centreline radius, m.
    pub radius: ScalarInterval,
}

/// The typed extraction of one routed segment.
#[derive(Debug, Clone, PartialEq)]
pub struct SegmentExtraction {
    /// Per-segment environment slot (shared with WO-34 wire runs).
    pub role: String,
    /// Wetted flow area, m^2.
    pub flow_area: ScalarInterval,
    /// Centreline length, m.
    pub length: ScalarInterval,
    /// Bend geometry, when the segment turns.
    pub bend: Option<BendExtraction>,
    /// Resolved roughness.
    pub roughness: RoughnessExtraction,
    /// Signed elevation change, m.
    pub elevation_change: ScalarInterval,
    /// Wall compliance / wave speed, when the segment carries a wall.
    pub wall: Option<WallExtraction>,
}

/// The typed extraction of a whole routed path (a fluid edge is a
/// single-segment run; a WO-34 wire run is the multi-segment case).
#[derive(Debug, Clone, PartialEq)]
pub struct GeometryExtraction {
    /// The geometry snapshot hash every field is cited to.
    pub snapshot_hash: String,
    /// The routed segments, in record order.
    pub segments: Vec<SegmentExtraction>,
    /// Sum of the segment lengths, m.
    pub total_length: ScalarInterval,
    /// Sum of the segment elevation changes (signed), m.
    pub total_elevation_change: ScalarInterval,
}

/// A failure extracting from a realized-geometry record -- a value the
/// lowering boundary (deliverable 3) renders as a diagnostic.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ExtractError {
    /// The record bytes did not decode into a realized-geometry record.
    #[error("realized-geometry record failed to decode: {0}")]
    Decode(String),
    /// No routed path matched the selector.
    #[error("selector `{selector}` not found in realized record")]
    SelectorNotFound {
        /// The unmatched selector.
        selector: String,
    },
    /// The selected path had no segments to extract.
    #[error("selector `{selector}` resolved an empty routed path")]
    EmptyPath {
        /// The empty path's selector.
        selector: String,
    },
    /// The segment's roughness class is not in the process-capability
    /// table.
    #[error("unknown roughness class `{class}` on segment `{role}`")]
    UnknownRoughnessClass {
        /// The unresolved class label.
        class: String,
        /// The segment role it appeared on.
        role: String,
    },
}

/// The process-capability roughness table (fluorite/03 sec. 1: "a
/// laser-cut channel and a drawn tube differ"): class label -> absolute
/// roughness height interval `[lo, hi]`, metres. The single home for
/// these values (NO DUPLICATION); extend here, never inline at a call
/// site.
const ROUGHNESS_TABLE: &[(&str, [f64; 2])] = &[
    ("drawn_tube", [1.0e-6, 2.0e-6]),
    ("machined", [1.5e-6, 6.3e-6]),
    ("laser_cut", [6.0e-6, 1.5e-5]),
    ("cast", [2.5e-4, 5.0e-4]),
    ("commercial_steel", [4.0e-5, 5.0e-5]),
];

fn resolve_roughness(class: &str, role: &str) -> Result<ScalarInterval, ExtractError> {
    ROUGHNESS_TABLE
        .iter()
        .find(|(name, _)| *name == class)
        .map(|(_, bounds)| Iv::from_bounds(*bounds).into_scalar("m"))
        .ok_or_else(|| ExtractError::UnknownRoughnessClass {
            class: class.to_string(),
            role: role.to_string(),
        })
}

/// Wall compliance `dV/dp = L * pi * D^3 / (4 E t)` (m^3/Pa) and the
/// distensibility `D / (E t)` (1/Pa) for a thin-wall segment.
fn wall_terms(length: Iv, wall: &RawWall) -> (Iv, Iv) {
    let diameter = Iv::from_bounds(wall.diameter);
    let modulus = Iv::from_bounds(wall.youngs_modulus);
    let thickness = Iv::from_bounds(wall.thickness);

    let d_cubed = diameter.mul(diameter).mul(diameter);
    let et = modulus.mul(thickness);
    // dA/dp = pi * D^3 / (4 E t)
    let da_dp = d_cubed.scale(std::f64::consts::PI).div(et.scale(4.0));
    let compliance = length.mul(da_dp);
    // distensibility = D / (E t)
    let distensibility = diameter.div(et);
    (compliance, distensibility)
}

/// Korteweg wave speed `a = 1 / sqrt(rho (1/K + D/(E t)))` (m/s) from the
/// medium-free distensibility and the medium's bulk modulus / density.
fn wave_speed(distensibility: Iv, medium: &MediumProps) -> Iv {
    let bulk = Iv::from_bounds(medium.bulk_modulus);
    let density = Iv::from_bounds(medium.density);
    // rho * (1/K + distensibility)   [s^2 / m^2]
    let inner = bulk.recip().add(distensibility);
    let per_c_squared = density.mul(inner);
    per_c_squared.sqrt().recip()
}

fn extract_segment(
    segment: &RawSegment,
    medium: Option<&MediumProps>,
) -> Result<SegmentExtraction, ExtractError> {
    let length = Iv::from_bounds(segment.length);
    let roughness = resolve_roughness(&segment.roughness_class, &segment.role)?;

    let bend = segment.bend.as_ref().map(|bend| BendExtraction {
        angle: Iv::from_bounds(bend.angle).into_scalar("rad"),
        radius: Iv::from_bounds(bend.radius).into_scalar("m"),
    });

    let wall = segment.wall.as_ref().map(|wall| {
        let (compliance, distensibility) = wall_terms(length, wall);
        WallExtraction {
            wall_compliance: compliance.into_scalar("m^3/Pa"),
            distensibility: distensibility.into_scalar("1/Pa"),
            wave_speed: medium.map(|m| wave_speed(distensibility, m).into_scalar("m/s")),
        }
    });

    Ok(SegmentExtraction {
        role: segment.role.clone(),
        flow_area: Iv::from_bounds(segment.flow_area).into_scalar("m^2"),
        length: length.into_scalar("m"),
        bend,
        roughness: RoughnessExtraction {
            class: segment.roughness_class.clone(),
            height: roughness,
        },
        elevation_change: Iv::from_bounds(segment.elevation_change).into_scalar("m"),
        wall,
    })
}

/// Extract the routed path named by `selector` from a realized-geometry
/// record's `bytes`, resolving hydraulic parameters and (when `medium`
/// is supplied) Korteweg wave speeds. Pure and IO-free (AD-17); every
/// result is cited to the record's snapshot hash.
///
/// # Errors
/// [`ExtractError`] when the bytes do not decode, the selector is
/// absent, the path is empty, or a segment names an unknown roughness
/// class.
pub fn extract_path(
    bytes: &[u8],
    selector: &str,
    medium: Option<&MediumProps>,
) -> Result<GeometryExtraction, ExtractError> {
    let span = tracing::debug_span!("extract_path", selector);
    let _enter = span.enter();

    let record: RealizedRecord =
        serde_json::from_slice(bytes).map_err(|err| ExtractError::Decode(err.to_string()))?;

    let path = record
        .paths
        .get(selector)
        .ok_or_else(|| ExtractError::SelectorNotFound {
            selector: selector.to_string(),
        })?;
    if path.segments.is_empty() {
        return Err(ExtractError::EmptyPath {
            selector: selector.to_string(),
        });
    }

    let segments = path
        .segments
        .iter()
        .map(|segment| extract_segment(segment, medium))
        .collect::<Result<Vec<_>, _>>()?;

    // Aggregate length and elevation change over the run (a fluid edge's
    // single segment reduces to that segment's own values).
    let mut total_length = Iv::point(0.0);
    let mut total_elevation = Iv::point(0.0);
    for segment in &path.segments {
        total_length = total_length.add(Iv::from_bounds(segment.length));
        total_elevation = total_elevation.add(Iv::from_bounds(segment.elevation_change));
    }

    tracing::debug!(
        segments = segments.len(),
        snapshot = %record.snapshot_hash,
        "routed-geometry extraction complete"
    );

    Ok(GeometryExtraction {
        snapshot_hash: record.snapshot_hash,
        segments,
        total_length: total_length.into_scalar("m"),
        total_elevation_change: total_elevation.into_scalar("m"),
    })
}

#[cfg(test)]
// Point-valued fixtures pass exact bounds through, so `assert_eq!` on a
// bound against its literal is the correct comparison here (not an
// epsilon), and the extractor is what widens by ULPs when it computes.
#[allow(clippy::float_cmp)]
mod tests {
    use std::f64::consts::{FRAC_PI_2, FRAC_PI_4};

    use super::*;

    /// A single straight tube run with two bends and a wall record --
    /// the acceptance fixture (area, length, two bends, compliance).
    /// Point-valued so hand computation is unambiguous.
    fn tube_record() -> Vec<u8> {
        serde_json::json!({
            "snapshot_hash": "blake3:snap-tube",
            "paths": {
                "coolant.wetted": {
                    "segments": [
                        {
                            "role": "coolant_jacket",
                            "flow_area": [1.0e-4, 1.0e-4],
                            "length": [2.0, 2.0],
                            "bend": {"angle": [FRAC_PI_2, FRAC_PI_2],
                                     "radius": [0.05, 0.05]},
                            "roughness_class": "drawn_tube",
                            "elevation_change": [0.3, 0.3],
                            "wall": {"youngs_modulus": [2.0e11, 2.0e11],
                                     "thickness": [1.0e-3, 1.0e-3],
                                     "diameter": [0.02, 0.02]}
                        },
                        {
                            "role": "return_leg",
                            "flow_area": [1.0e-4, 1.0e-4],
                            "length": [1.5, 1.5],
                            "bend": {"angle": [FRAC_PI_4, FRAC_PI_4],
                                     "radius": [0.04, 0.04]},
                            "roughness_class": "drawn_tube",
                            "elevation_change": [-0.1, -0.1],
                            "wall": null
                        }
                    ]
                }
            }
        })
        .to_string()
        .into_bytes()
    }

    #[test]
    fn extracts_area_length_and_two_bends() {
        let out = extract_path(&tube_record(), "coolant.wetted", None).unwrap();
        assert_eq!(out.snapshot_hash, "blake3:snap-tube");
        assert_eq!(out.segments.len(), 2);

        // Both segments carry the flow area; both are bends.
        assert_eq!(out.segments[0].flow_area.lo, 1.0e-4);
        assert!(out.segments[0].bend.is_some());
        assert!(out.segments[1].bend.is_some());
        assert_eq!(out.segments[0].role, "coolant_jacket");

        // Total length = 2.0 + 1.5 = 3.5 (outward-rounded around 3.5).
        assert!(out.total_length.lo <= 3.5 && 3.5 <= out.total_length.hi);
        // Signed elevation sum = 0.3 + (-0.1) = 0.2.
        assert!(out.total_elevation_change.lo <= 0.2 && 0.2 <= out.total_elevation_change.hi);
    }

    #[test]
    fn wall_compliance_matches_hand_computation() {
        let out = extract_path(&tube_record(), "coolant.wetted", None).unwrap();
        let wall = out.segments[0].wall.as_ref().unwrap();

        // C = L * pi * D^3 / (4 E t)
        //   = 2.0 * pi * (0.02)^3 / (4 * 2e11 * 1e-3)
        let d: f64 = 0.02;
        let expected = 2.0 * std::f64::consts::PI * d.powi(3) / (4.0 * 2.0e11 * 1.0e-3);
        // The true value lies within the outward-rounded bounds...
        assert!(
            wall.wall_compliance.lo <= expected && expected <= wall.wall_compliance.hi,
            "expected {expected} within [{}, {}]",
            wall.wall_compliance.lo,
            wall.wall_compliance.hi
        );
        // ...and the interval is at most a couple of ULPs wide (point in).
        assert!(wall.wall_compliance.hi - wall.wall_compliance.lo < expected * 1.0e-12);
        assert_eq!(wall.wall_compliance.unit, "m^3/Pa");

        // distensibility = D / (E t) = 0.02 / (2e11 * 1e-3)
        let expected_dist = d / (2.0e11 * 1.0e-3);
        assert!(wall.distensibility.lo <= expected_dist && expected_dist <= wall.distensibility.hi);

        // No medium supplied -> no wave speed.
        assert!(wall.wave_speed.is_none());
        // Rigid second segment carries no wall.
        assert!(out.segments[1].wall.is_none());
    }

    #[test]
    fn korteweg_wave_speed_matches_hand_computation() {
        let medium = MediumProps {
            bulk_modulus: [2.2e9, 2.2e9],
            density: [998.0, 998.0],
        };
        let out = extract_path(&tube_record(), "coolant.wetted", Some(&medium)).unwrap();
        let wall = out.segments[0].wall.as_ref().unwrap();
        let speed = wall.wave_speed.as_ref().unwrap();

        // a = 1 / sqrt(rho (1/K + D/(E t)))
        let dist = 0.02 / (2.0e11 * 1.0e-3);
        let expected = 1.0 / (998.0_f64 * (1.0 / 2.2e9 + dist)).sqrt();
        assert!(
            speed.lo <= expected && expected <= speed.hi,
            "expected {expected} within [{}, {}]",
            speed.lo,
            speed.hi
        );
        assert_eq!(speed.unit, "m/s");
    }

    #[test]
    fn roughness_resolves_from_capability_table() {
        let out = extract_path(&tube_record(), "coolant.wetted", None).unwrap();
        assert_eq!(out.segments[0].roughness.class, "drawn_tube");
        assert_eq!(out.segments[0].roughness.height.lo, 1.0e-6);
        assert_eq!(out.segments[0].roughness.height.hi, 2.0e-6);
    }

    #[test]
    fn same_bytes_extract_identically() {
        let bytes = tube_record();
        let a = extract_path(&bytes, "coolant.wetted", None).unwrap();
        let b = extract_path(&bytes, "coolant.wetted", None).unwrap();
        assert_eq!(a, b, "extraction is a deterministic pure function (AD-6)");
    }

    #[test]
    fn missing_selector_is_an_error_value() {
        let err = extract_path(&tube_record(), "nope", None).unwrap_err();
        assert_eq!(
            err,
            ExtractError::SelectorNotFound {
                selector: "nope".to_string()
            }
        );
    }

    #[test]
    fn unknown_roughness_class_is_an_error_value() {
        let bytes = serde_json::json!({
            "snapshot_hash": "blake3:x",
            "paths": {"p": {"segments": [{
                "role": "r", "flow_area": [1.0, 1.0], "length": [1.0, 1.0],
                "roughness_class": "unobtainium", "elevation_change": [0.0, 0.0]
            }]}}
        })
        .to_string()
        .into_bytes();
        let err = extract_path(&bytes, "p", None).unwrap_err();
        assert_eq!(
            err,
            ExtractError::UnknownRoughnessClass {
                class: "unobtainium".to_string(),
                role: "r".to_string(),
            }
        );
    }

    #[test]
    fn undecodable_bytes_are_an_error_value() {
        let err = extract_path(b"not json", "p", None).unwrap_err();
        assert!(matches!(err, ExtractError::Decode(_)));
    }

    #[test]
    fn empty_path_is_an_error_value() {
        let bytes = serde_json::json!({
            "snapshot_hash": "blake3:x",
            "paths": {"p": {"segments": []}}
        })
        .to_string()
        .into_bytes();
        let err = extract_path(&bytes, "p", None).unwrap_err();
        assert_eq!(
            err,
            ExtractError::EmptyPath {
                selector: "p".to_string()
            }
        );
    }
}
