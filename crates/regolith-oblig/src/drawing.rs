//! `DrawingModel`: the ONE documentation IR for shipped engineering
//! drawings, diagrams, and schedules (AD-27/D140, WO-50 deliverable 1).
//!
//! Design: `docs/spec/toolchain/25-drawings-and-artifacts.md` sec. 1.1.
//! Per-track PRODUCERS (Python, `regolith.backends.drawings`) project
//! realized IRs (`RealizedGeometry`, `RealizedLayout`, `FlownetPayload`)
//! into this schema; RENDERERS (SVG mandatory, DXF/PDF siblings)
//! serialize ONLY this IR to a page format -- no producer emits page
//! description, no renderer computes geometry (AD-27).
//!
//! Every [`Dimension`] carries a [`Provenance`] field: the schema makes
//! an unattributable number on a sheet unrepresentable (charter sec. 1
//! decision 3). This module defines the WIRE SHAPE only; nothing here
//! reads source, touches IO, or emits diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (a producer
//! is responsible for stable ordering before construction), so
//! [`DrawingModel::content_digest`] is stable across builds of the same
//! source state.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every drawing content address (AD-18): keeps
/// a drawing digest from colliding with any other payload kind even if
/// the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#drawing
pub const DRAWING_DOMAIN_TAG: &str = "drawing.sheet";

/// Where a rendered number on a sheet comes from (charter sec. 1
/// decision 3): a resolution cause, a content-addressed record, or an
/// obligation id. Exactly one of the three is populated -- a closed
/// enum (not a free-form struct) so an unattributed dimension is a
/// deserialization error, not a silently-accepted unknown.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case", tag = "kind")]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub enum Provenance {
    /// The lockfile resolution cause (free-string label mirroring
    /// `regolith_qty::Cause`'s own wire shape, kept free-form here so
    /// this schema never re-imports `regolith-qty` for a display-only
    /// field).
    Cause {
        /// The cause label as the lockfile records it.
        label: String,
    },
    /// A content-addressed record (e.g. a realized-geometry or
    /// flownet payload digest) this value was read from.
    Record {
        /// The blake3/sha256 digest of the source record.
        digest: String,
    },
    /// The obligation id whose discharge produced this value.
    Obligation {
        /// The obligation id.
        id: String,
    },
}

/// Sheet paper size (v1: the fixed ANSI/ISO set a title block scales
/// against; a project-specific size is future scope, charter sec. 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub enum SheetSize {
    /// ANSI A / 8.5x11 in.
    AnsiA,
    /// ANSI B / 11x17 in.
    AnsiB,
    /// ANSI C / 17x22 in.
    AnsiC,
    /// ISO A4.
    IsoA4,
    /// ISO A3.
    IsoA3,
}

/// Title-block fields (charter sec. 1.7 title-block-completeness rule
/// checks these are non-empty): the minimal set every drafting
/// standard demands.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct TitleBlock {
    /// Drawing/part/assembly title.
    pub title: String,
    /// Drawing number (project-assigned, free string).
    pub drawing_number: String,
    /// Revision label.
    pub revision: String,
    /// Scale label as drawn (e.g. "1:2").
    pub scale_label: String,
    /// The name/id of the entity this drawing documents (e.g. the
    /// realized-part or flownet subject name).
    pub subject: String,
}

/// Which realized-IR digest a [`View`] projects, and how.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct ViewSource {
    /// The realized-IR content digest this view projects (provenance:
    /// a view can never disagree with the build state it renders).
    pub source_digest: String,
    /// The payload kind the digest belongs to (`"geometry.realized"`,
    /// `"layout.realized"`, `"flownet"`) -- free string mirroring the
    /// existing domain-tag constants, kept free-form so this schema
    /// never depends on every producing crate's tag constant.
    pub source_kind: String,
}

/// One named view on a sheet: a projection (mech/civil) or a schematic
/// layout (fluid P&ID, elec one-line) of a [`ViewSource`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct View {
    /// View name (e.g. "front", "top", "isometric", "pid").
    pub name: String,
    /// The projection plane/axis label, free string (e.g. "XY", "XZ",
    /// or "schematic" for net-derived diagrams that are not a
    /// geometric projection, charter sec. 1 decision 6).
    pub plane: String,
    /// Drawing scale as a ratio, e.g. 0.5 for "1:2".
    pub scale: f64,
    /// The realized-IR source this view projects.
    pub source: ViewSource,
    /// Entity indices (into [`DrawingModel::entities`]) belonging to
    /// this view, in stable order.
    pub entity_indices: Vec<u32>,
}

/// A 2D point in sheet-space (mm), used by every entity/annotation
/// geometry field.
// frob:doc docs/modules/regolith-oblig.md#drawing
pub type Point2 = [f64; 2];

/// One projected or schematic 2D drawing primitive. Entities are
/// PROJECTED (mech/civil) or drawn from symbol RECORDS (diagrams,
/// charter sec. 1 decision 6) by a producer -- never authored, never
/// computed by a renderer (AD-27).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case", tag = "kind")]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub enum Entity {
    /// A straight segment.
    Segment {
        /// Segment start point.
        from: Point2,
        /// Segment end point.
        to: Point2,
    },
    /// A circular arc.
    Arc {
        /// Arc center.
        center: Point2,
        /// Arc radius, mm.
        radius: f64,
        /// Start angle, radians.
        start_angle: f64,
        /// End angle, radians.
        end_angle: f64,
    },
    /// An ordered polyline.
    Polyline {
        /// Vertices, in order.
        points: Vec<Point2>,
    },
    /// A symbol instance (diagram glyph from a pack record, charter
    /// sec. 1 decision 6 -- never hard-coded art).
    Symbol {
        /// The hash-pinned symbol record digest.
        record_digest: String,
        /// Placement origin.
        origin: Point2,
        /// Rotation, radians.
        rotation: f64,
    },
}

/// One dimension on a sheet: a resolved value with a MANDATORY
/// provenance field (charter sec. 1 decision 3 -- the schema makes an
/// unattributed number unrepresentable).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct Dimension {
    /// The interface/feature role this dimension documents (e.g.
    /// `"bore.diameter"`), matched against contract-coverage checking.
    pub role: String,
    /// The resolved value, in `unit`.
    pub value: f64,
    /// The unit the value is expressed in.
    pub unit: String,
    /// Optional tolerance band `[lo, hi]` in `unit`; a toleranced
    /// dimension is what the contract-coverage check demands appear
    /// somewhere on the sheet set.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tolerance: Option<[f64; 2]>,
    /// Anchor point on the sheet (leader/witness-line origin).
    pub anchor: Point2,
    /// The view (by name) this dimension is drawn against.
    pub view_name: String,
    /// MANDATORY: where this value came from (never omittable).
    pub provenance: Provenance,
}

/// A free-text or symbolic annotation (notes, GD&T frames, per:
/// citations).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct Annotation {
    /// Annotation text (a GD&T frame renders as its text form here;
    /// v1 does not model frame glyph geometry separately).
    pub text: String,
    /// Anchor point on the sheet.
    pub anchor: Point2,
    /// Text height, mm (drives the minimum-text-height rule).
    pub text_height_mm: f64,
    /// Referenced datum labels, if this annotation is a GD&T frame.
    #[serde(default)]
    pub datum_refs: Vec<String>,
    /// Optional standard-clause citation (`per:` prefix convention,
    /// e.g. "ASME Y14.5 7.2").
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub per: Option<String>,
}

/// One typed row in a [`Table`] (schedules: member/opening/area/BOM).
/// Cells are stored as strings (the display form); numeric cells still
/// trace back to a [`Dimension`]/record elsewhere when they represent
/// a toleranced value.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct TableRow {
    /// Cell values, in column order.
    pub cells: Vec<String>,
}

/// A schedule table (member schedule, opening schedule, area schedule,
/// BOM) -- the ONE schedule mechanism (charter/AD-27: schedules are
/// `tables` in the same IR, not a second mechanism).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct Table {
    /// Table title (e.g. "Member Schedule", "Bill of Materials").
    pub title: String,
    /// Column headers, in order.
    pub columns: Vec<String>,
    /// Rows, in order.
    pub rows: Vec<TableRow>,
}

/// One sheet: paper size, title block, its views, and the entities/
/// dimensions/annotations/tables placed on it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct Sheet {
    /// Sheet paper size.
    pub size: SheetSize,
    /// Title-block fields.
    pub title_block: TitleBlock,
    /// Named views on this sheet, in stable order.
    pub views: Vec<View>,
    /// Projected/schematic entities, in stable order (referenced by
    /// index from [`View::entity_indices`]).
    pub entities: Vec<Entity>,
    /// Dimensions on this sheet, in stable order.
    pub dimensions: Vec<Dimension>,
    /// Annotations on this sheet, in stable order.
    pub annotations: Vec<Annotation>,
    /// Schedule tables on this sheet, in stable order.
    pub tables: Vec<Table>,
}

/// The serialized documentation payload (AD-27): an ordered set of
/// sheets, content-addressed as a whole so a sheet SET (e.g. a civil
/// plan + its member schedule) can be pinned by one digest.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#drawing
pub struct DrawingModel {
    /// The subject name this drawing set documents (e.g. the part,
    /// assembly, or net subject string).
    pub subject: String,
    /// Sheets, in stable order.
    pub sheets: Vec<Sheet>,
}

impl DrawingModel {
    /// The AD-18 content address of this drawing set under the
    /// `drawing.sheet` domain tag. Stable across builds of the same
    /// source state (AD-6); a changed field (including a changed
    /// dimension's provenance) changes the digest -- the same
    /// anti-staleness property `RealizedGeometry::content_digest`
    /// documents, applied to attestation invalidation (charter
    /// sec. 1 decision 7, AD-20/INV-28): re-signing after
    /// regeneration is impossible by construction because the address
    /// itself moved.
    ///
    /// # Errors
    /// Propagates [`regolith_util::canon::EncodeError`] from the
    /// canonical encoder (only a non-finite float or a serializer
    /// failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#drawing
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, regolith_util::canon::EncodeError> {
        regolith_util::canon::content_address(DRAWING_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> DrawingModel {
        DrawingModel {
            subject: "pillow_block".to_string(),
            sheets: vec![Sheet {
                size: SheetSize::AnsiB,
                title_block: TitleBlock {
                    title: "Pillow Block".to_string(),
                    drawing_number: "DWG-001".to_string(),
                    revision: "A".to_string(),
                    scale_label: "1:1".to_string(),
                    subject: "pillow_block".to_string(),
                },
                views: vec![View {
                    name: "front".to_string(),
                    plane: "XY".to_string(),
                    scale: 1.0,
                    source: ViewSource {
                        source_digest: "blake3:aa".to_string(),
                        source_kind: "geometry.realized".to_string(),
                    },
                    entity_indices: vec![0],
                }],
                entities: vec![Entity::Segment {
                    from: [0.0, 0.0],
                    to: [10.0, 0.0],
                }],
                dimensions: vec![Dimension {
                    role: "bore.diameter".to_string(),
                    value: 12.0,
                    unit: "mm".to_string(),
                    tolerance: Some([11.98, 12.02]),
                    anchor: [5.0, 0.0],
                    view_name: "front".to_string(),
                    provenance: Provenance::Record {
                        digest: "blake3:aa".to_string(),
                    },
                }],
                annotations: vec![],
                tables: vec![],
            }],
        }
    }

    // frob:tests crates/regolith-oblig/src/drawing.rs::DrawingModel.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let model = sample();
        let d1 = model.content_digest().unwrap();
        let d2 = model.content_digest().unwrap();
        assert_eq!(d1, d2, "same drawing -> same digest (AD-6)");

        let mut other = sample();
        other.sheets[0].dimensions[0].value = 12.1;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed dimension must change the digest (regeneration \
             invalidates any attestation over the old address, sec. 1.7)"
        );
    }

    #[test]
    fn dimension_provenance_is_mandatory_at_the_type_level() {
        // Compile-time property: `Dimension.provenance` is not an
        // `Option<Provenance>` -- there is no way to construct a
        // `Dimension` without it. This test documents/pins that shape.
        let model = sample();
        match &model.sheets[0].dimensions[0].provenance {
            Provenance::Record { digest } => assert_eq!(digest, "blake3:aa"),
            _ => panic!("expected Record provenance"),
        }
    }
}
