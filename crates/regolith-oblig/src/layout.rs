//! `RealizedLayout`: the elec realized placed/routed board payload
//! (AD-25/D128, WO-42 deliverable 2).
//!
//! One schema-versioned, Rust-sourced record (AD-5 precedent, mirroring
//! [`crate::geometry::RealizedGeometry`]) for the placed/routed board
//! content WO-24's KiCad layout adapter produces: board outline
//! reference, component placements, routed segments, a copper summary,
//! extracted parasitic slots, and a `.kicad_pcb` content-hash pin.
//!
//! Unlike deliverable 1, WO-24's layout half has no landed Python
//! forward contract to promote (the KiCad-unavailable deferral means
//! `regolith.realizer.elec.kicad`/`extraction` only carry a thin
//! `LayoutResponse`/`LayoutExtraction` wire shape, not a placement/
//! routing model -- confirmed by reading both modules). This schema is
//! therefore built fresh from this WO's own field list (deliverable 2's
//! text) rather than promoted from an existing type; there is nothing to
//! delete or demote in the same change. Payload kind is the NEW
//! `layout.realized` (D96 vocabulary, `../design/20-solver-abstraction.md`
//! sec. 8.3 -- added by a prior dispatch alongside the feldspar channel
//! contract note).
//!
//! This module defines the WIRE SHAPE only. The realizer emission seam
//! (`regolith.realizer.elec` `put`-ing this into the WO-30 store once
//! its layout half runs for real) is deliverable 4's remainder (a later
//! dispatch); nothing here reads source, touches IO, or emits
//! diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (the
//! realizer is responsible for stable ordering before construction), so
//! [`RealizedLayout::content_digest`] is stable across builds of the
//! same bound netlist + outline.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Domain tag folded into every realized-layout content address
/// (AD-18): keeps a layout digest from colliding with any other payload
/// kind even if the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#layout
pub const LAYOUT_DOMAIN_TAG: &str = "layout.realized";

/// Which side of the board a placement sits on.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#layout
pub enum BoardSide {
    /// Top (component) side.
    Top,
    /// Bottom side.
    Bottom,
}

/// One placed footprint on the board.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct Placement {
    /// The reference designator (e.g. `U1`, `R12`) the placement binds.
    pub reference: String,
    /// The footprint name resolved from the registry record.
    pub footprint: String,
    /// Placement position on the board, mm, board-outline-relative.
    pub position_mm: [f64; 2],
    /// Placement rotation, degrees, board-outline-relative.
    pub rotation_deg: f64,
    /// Which side of the board this footprint is placed on.
    pub side: BoardSide,
}

/// One routed copper segment (a track) belonging to a net.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct RoutedSegment {
    /// The net this segment belongs to.
    pub net: String,
    /// The copper layer this segment was routed on (e.g. `F.Cu`,
    /// `B.Cu`, an inner layer name).
    pub layer: String,
    /// Track width, mm.
    pub width_mm: f64,
    /// Segment length, mm.
    pub length_mm: f64,
}

/// Board-wide copper-usage summary (post-route extraction surface,
/// mirroring `regolith.realizer.elec.extraction.LayoutExtraction`'s
/// field shapes but keyed for the schema, not a bare mapping).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct CopperSummary {
    /// Total routed track length per net, mm.
    pub net_lengths_mm: Vec<NetLength>,
    /// Total copper area per named copper region (a zone/pour), mm^2.
    pub copper_areas_mm2: Vec<CopperArea>,
}

/// One net's total routed length (a `CopperSummary` entry; a `Vec` of
/// pairs rather than a map for AD-6 deterministic ordering across the
/// FFI/JSON boundary).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct NetLength {
    /// The net name.
    pub net: String,
    /// Total routed length for this net, mm.
    pub length_mm: f64,
}

/// One named copper region's area (a `CopperSummary` entry).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct CopperArea {
    /// The copper region name (a zone/pour identifier).
    pub region: String,
    /// Copper area, mm^2.
    pub area_mm2: f64,
}

/// One extracted parasitic slot: a layout-dependent parasitic value
/// (e.g. a trace's parasitic resistance/inductance/capacitance) shaped
/// as a model-pack input, keyed by the net or segment it belongs to.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct ParasiticSlot {
    /// The net or segment this parasitic value is extracted for.
    pub subject: String,
    /// The kind of parasitic quantity (e.g. `resistance_ohm`,
    /// `inductance_nh`, `capacitance_pf`) -- a coarse label rather than
    /// a closed enum since the extraction surface grows per WO-25 model
    /// pack needs.
    pub kind: String,
    /// The extracted value, in the unit implied by `kind`.
    pub value: f64,
}

/// The serialized realized-layout payload (AD-25, WO-24's placed/routed
/// board content): a board outline reference, every placement, every
/// routed segment, a copper summary, extracted parasitic slots, and the
/// `.kicad_pcb` content-hash pin.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#layout
pub struct RealizedLayout {
    /// The content hash of the bound netlist this layout was routed
    /// from (provenance; the G42 anti-staleness citation).
    pub netlist_hash: String,
    /// A reference to the board outline this layout was placed within
    /// (e.g. the mech interface outline-import record id/hash).
    pub board_outline_ref: String,
    /// The SHA-256 content hash of the routed `.kicad_pcb` file (the
    /// pinned native side artifact; verify-only L4 re-import per
    /// regolith/08).
    pub kicad_pcb_content_hash: String,
    /// Every placed footprint (realizer-sorted for determinism, AD-6).
    pub placements: Vec<Placement>,
    /// Every routed segment (realizer-sorted for determinism, AD-6).
    pub routed_segments: Vec<RoutedSegment>,
    /// The board-wide copper-usage summary.
    pub copper: CopperSummary,
    /// Every extracted parasitic slot (realizer-sorted for determinism,
    /// AD-6).
    pub parasitics: Vec<ParasiticSlot>,
}

impl RealizedLayout {
    /// The AD-18 content address of this payload under the
    /// `layout.realized` domain tag -- the digest a `PayloadRef` pins
    /// and the store keys on. Stable across builds of the same bound
    /// netlist + outline (AD-6); a changed field (including a changed
    /// placement or segment) changes the digest, which is the G42
    /// anti-staleness property.
    ///
    /// # Errors
    /// Propagates [`regolith_util::canon::EncodeError`] from the
    /// canonical encoder (only a non-finite float or a serializer
    /// failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#layout
    pub fn content_digest(&self) -> Result<String, regolith_util::canon::EncodeError> {
        regolith_util::canon::content_address(LAYOUT_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> RealizedLayout {
        RealizedLayout {
            netlist_hash: "blake3:cc".to_string(),
            board_outline_ref: "mech:kestrel_pc104_outline".to_string(),
            kicad_pcb_content_hash: "sha256:dd".to_string(),
            placements: vec![Placement {
                reference: "U1".to_string(),
                footprint: "QFN-32".to_string(),
                position_mm: [10.0, 20.0],
                rotation_deg: 90.0,
                side: BoardSide::Top,
            }],
            routed_segments: vec![RoutedSegment {
                net: "VCC".to_string(),
                layer: "F.Cu".to_string(),
                width_mm: 0.25,
                length_mm: 12.5,
            }],
            copper: CopperSummary {
                net_lengths_mm: vec![NetLength {
                    net: "VCC".to_string(),
                    length_mm: 12.5,
                }],
                copper_areas_mm2: vec![CopperArea {
                    region: "GND_pour".to_string(),
                    area_mm2: 450.0,
                }],
            },
            parasitics: vec![ParasiticSlot {
                subject: "VCC".to_string(),
                kind: "resistance_ohm".to_string(),
                value: 0.05,
            }],
        }
    }

    // frob:tests crates/regolith-oblig/src/layout.rs::RealizedLayout.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.routed_segments[0].length_mm = 13.0;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed segment field must change the digest (G42)"
        );
    }

    #[test]
    fn board_side_serializes_snake_case() {
        let json = serde_json::to_value(BoardSide::Bottom).unwrap();
        assert_eq!(json, "bottom");
    }

    #[test]
    fn parasitics_and_placements_may_be_empty() {
        let mut layout = sample();
        layout.parasitics.clear();
        layout.placements.clear();
        let digest = layout.content_digest().unwrap();
        assert!(!digest.is_empty());
    }
}
