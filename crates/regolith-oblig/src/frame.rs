//! `FramePayload`: the calcite structural frame payload (calcite/03
//! sec. 4).
//!
//! One schema-versioned, Rust-sourced record (AD-25 growth rule: a
//! schemars schema in `regolith-oblig`, content-addressed via the one
//! encoder, a payload kind on the D96 channel -- kind string `frame`,
//! DECIDED D139/D145, single-homed in feldspar's kind table): elaboration
//! (WO-48 deliverable 3, a later dispatch in this same slice) turns a
//! `.calx` structure's members/transfers/loads into this serialized,
//! content-addressed record, and every structural claim lowers to an
//! ordinary obligation carrying a `PayloadRef { kind: "frame", .. }`
//! pointing at it. Closed-form beam checks and feldspar's direct-stiffness
//! frame analysis both consume the payload; nothing here solves anything.
//!
//! This module defines the WIRE SHAPE (deliverable 1) only, mirroring
//! `flownet.rs`'s precedent field for field: joints/members/supports/
//! loads/combinations, exactly the calcite/03 sec. 4 field list. The
//! lowering pass that PRODUCES it lives in `regolith_lower::frame_lower`
//! (deliverable 3); nothing here reads source, touches IO, or emits
//! diagnostics.
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (elaboration
//! sorts before construction), so [`FramePayload::content_digest`] is
//! stable across builds of the same source.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::flownet::{RecordRef, ScalarInterval};
use regolith_util::canon::{content_address, EncodeError};

/// Domain tag folded into every frame content address (AD-18): keeps a
/// frame digest from colliding with any other payload kind even if the
/// canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#frame
pub const FRAME_DOMAIN_TAG: &str = "frame";

/// A joint identifier within a frame (a stable elaboration-assigned
/// name, either a coalesced member-anchor key or a `support:<name>`
/// synthetic id for a support with no resolved anchor of its own).
// frob:doc docs/modules/regolith-oblig.md#frame
pub type JointId = String;

/// A joint's datum reference: either a named `level` (the ordinary
/// case -- calcite/02 member anchors always name a declared `level`)
/// or a raw `elevation` quantity (the sec. 4 field list's `level|
/// elevation` union, kept for a datum that names an elevation
/// directly rather than through a `level` declaration).
// NOTE: the discriminant tag is deliberately named `datum_kind`, not the
// more obvious `kind` -- `schemars`/`datamodel-code-generator` bucket
// every ANONYMOUS enum generated for a field literally named `kind`
// into one shared, order-sensitive `Kind`/`Kind1`/... name pool across
// the WHOLE exported schema document (`regolith-oblig/src/harness.rs`'s
// `RunRoute` already contributes to it). Reusing `kind` here would
// insert a new member into that shared pool and renumber every
// existing `KindN` class, silently breaking hand-written references
// elsewhere (e.g. `producers.py`'s `Kind.segment`) purely from this
// type's alphabetical position among `regolith-oblig`'s exported
// definitions (`schemars`'s `Map` is a `BTreeMap`, sorted by type
// name) -- a distinct tag name keeps `Datum`'s discriminant in its OWN
// `DatumKind` pool instead.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case", tag = "datum_kind", content = "value")]
// frob:doc docs/modules/regolith-oblig.md#frame
pub enum Datum {
    /// A named `level` declaration ref.
    Level(String),
    /// A raw elevation quantity.
    Elevation(ScalarInterval),
}

/// A joint's resolved position: the grid refs (in declaration order)
/// plus its level/elevation datum. `None` (on [`Joint::at`]) for a
/// support-only joint whose anchor is not yet resolvable at this front
/// end (the AD-25 GeomExtract placeholder idiom, applied to position
/// rather than geometry: honestly indeterminate, not fabricated).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct JointAt {
    /// The grid refs naming this joint's plan position (e.g. `["A"]`
    /// or `["A", "2"]`), in the order they appeared in the member
    /// anchor line.
    pub grid_refs: Vec<String>,
    /// The joint's vertical datum.
    pub datum: Datum,
}

/// One synthesized joint (calcite/03 sec. 4): member ends meeting at a
/// shared anchor coalesce onto the SAME joint id (the partition key is
/// the anchor's canonical grid/level tuple); a declared `support:` node
/// with no member anchor of its own gets a distinct joint with `at:
/// None`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct Joint {
    /// The stable joint id.
    pub id: JointId,
    /// The joint's resolved grid/level position, when known.
    pub at: Option<JointAt>,
}

/// A member's structural role (calcite/02 sec. 4 header vocabulary).
/// `Other` is the forward-compatible escape for a role word this
/// schema does not yet enumerate -- never a parse failure.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#frame
pub enum MemberRole {
    /// A beam (primarily flexural member).
    Beam,
    /// A column (primarily axial vertical member).
    Column,
    /// A brace (axial lateral-system member).
    Brace,
    /// A slab (planar surface member).
    Slab,
    /// A wall (planar vertical member).
    Wall,
    /// A footing (foundation member; MAY be point-anchored/zero-length
    /// -- calcite/03 sec. 4).
    Footing,
    /// Any other declared role word, kept verbatim.
    Other(String),
}

impl MemberRole {
    /// Parse a member header's role word (`member G1: beam` -> `beam`)
    /// into its typed [`MemberRole`], falling back to [`MemberRole::Other`]
    /// for a role word outside the calcite/02 sec. 4 vocabulary.
    #[must_use]
    // frob:doc docs/modules/regolith-oblig.md#frame
    pub fn parse(word: &str) -> Self {
        match word {
            "beam" => Self::Beam,
            "column" => Self::Column,
            "brace" => Self::Brace,
            "slab" => Self::Slab,
            "wall" => Self::Wall,
            "footing" => Self::Footing,
            other => Self::Other(other.to_string()),
        }
    }
}

/// The kept degrees of freedom at each end of a member's transfer
/// (calcite/03 sec. 4: "the mating vocabulary IS the release model; no
/// second encoding"). Empty until a transfer class's `dof: kept=` is
/// resolved -- `std.civil`'s transfer-class records are a different
/// slice's deliverable (WO-48 std.civil authoring); this schema carries
/// the field honestly empty rather than fabricating a release set.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct Releases {
    /// Kept DOF codes at the member's `a` end.
    pub a: Vec<String>,
    /// Kept DOF codes at the member's `b` end.
    pub b: Vec<String>,
}

/// One structural member (calcite/03 sec. 4): its joints, geometry
/// (derived from grid/level datums), resolved section/material, and
/// end releases.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct FrameMember {
    /// The member's declared name.
    pub id: String,
    /// The member's structural role.
    pub role: MemberRole,
    /// The `a`-end joint id.
    pub a: JointId,
    /// The `b`-end joint id (equal to `a` for a point-anchored footing
    /// -- calcite/03 sec. 4, legal, not a lowering error).
    pub b: JointId,
    /// The member's span length, derived from its two anchors'
    /// grid/level datums (zero for a point-anchored footing).
    pub length: ScalarInterval,
    /// A deterministic descriptor of the member's spatial orientation
    /// (`"vertical"` / `"horizontal"` / `"inclined"` / `"point"`),
    /// derived from which datum axes differ between its two anchors.
    pub orientation: String,
    /// The resolved section record ref (post-L3); the pre-resolution
    /// placeholder (`RecordRef { name: "free", digest: "" }`) when the
    /// member's `section: free` has not yet been resolved (AD-25 verbatim).
    pub section: RecordRef,
    /// The resolved material record ref.
    pub material: RecordRef,
    /// The declared candidate FAMILY for a `section: in
    /// registry(<family-ref>)` member (WO-68, D181, SCHEMA_VERSION
    /// 25): the family ref text (e.g. `"std.civil.w_shape"`) the
    /// section-search evaluator resolves `section` against. `None` for
    /// every other section form (`free` -- honest indeterminate, no
    /// inferred family, WO-65 D181 finding 2; a resolved `section:
    /// registry(<ref>)` literal -- already resolved, no domain to
    /// declare).
    pub section_domain: Option<String>,
    /// The kept-DOF releases at each end.
    pub releases: Releases,
}

/// One synthesized support (calcite/03 sec. 4): a `support:` node's
/// joint plus its fixed degrees of freedom.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct Support {
    /// The support's joint id.
    pub joint: JointId,
    /// The fixed DOF codes. Empty until the support role's fixity is
    /// resolved through `std.civil` (out of this slice's scope,
    /// honestly deferred rather than guessed).
    pub fixity: Vec<String>,
}

/// A load's distribution shape over its target (calcite/03 sec. 4).
/// The kind is DERIVED from the source quantity's unit dimension
/// (D194: dimensions partition, so the dispatch cannot collide):
/// pressure (`kPa`) -> [`LoadKind::Distributed`]; force/length
/// (`kN/m`) -> [`LoadKind::Line`]; force (`kN`) -> [`LoadKind::Point`];
/// force-length (`kN-m`) -> [`LoadKind::Moment`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#frame
pub enum LoadKind {
    /// A distributed AREA load (pressure over a surface member).
    Distributed,
    /// A distributed LINE load (force per length along the member axis
    /// -- WO-85/D194, SCHEMA_VERSION 27: the direct `kN/m on [member]`
    /// row that previously had no lowered path at all).
    Line,
    /// A concentrated point load.
    Point,
    /// An applied moment.
    Moment,
}

/// One load-transfer edge (calcite/02 sec. 6, calcite/03 sec. 4;
/// D176 addendum, WO-62 slice B): the calcite `structure ...
/// transfers:` block, lowered. Mirrors the source syntax verbatim --
/// `<id>: <kind>(...)  (<from> -> <to>)` -- so feldspar WO-23's
/// tributary-resolution input can be assembled from this payload
/// without re-parsing source (AD-22).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct FrameTransfer {
    /// The transfer's declared name (e.g. `deck_g1`).
    pub id: String,
    /// The declared connection-class name (e.g. `Bearing`, `Pinned`,
    /// `Moment`, `BasePlate`, `Roller` -- `std.civil`'s mating-shaped
    /// classes, calcite/02 sec. 5; kept verbatim, never enumerated,
    /// since the class set is pack content, not toolchain vocabulary).
    pub kind: String,
    /// The source member/support name (`<from>` in `(<from> ->
    /// <to>)`).
    pub from: String,
    /// The target member/support name (`<to>`).
    pub to: String,
    /// The declared tributary value, when the transfer carries one
    /// (`Bearing(tributary=21m2)`); `None` for a transfer with no
    /// declared tributary parameter (e.g. a pure `Pinned()`/`Moment()`
    /// connection with no distributed-load share).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tributary: Option<ScalarInterval>,
    /// The declared embedment depth, when the transfer carries one
    /// (`EmbeddedPost(depth=1.3m)` -- WO-85/D194, SCHEMA_VERSION 27:
    /// the `civil.embedment` claim's declared-depth input); `None` for
    /// every other transfer class.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub depth: Option<ScalarInterval>,
}

/// One load-case entry (calcite/03 sec. 4): a literal magnitude over a
/// declared target, from a `loads:` field carrying a quantity literal
/// and an `on [...]` target clause. `derived` self-weight rows and
/// pack-model refs (`site.x -> std.civil.y`, resolved through the
/// `effects:` derivation-obligation mechanism, calcite/03 sec. 2) are
/// NOT payload load entries -- they are ordinary derived givens on the
/// obligations that consume them, not literal frame data.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct FrameLoad {
    /// The load case's declared name (e.g. `pedestrian`, `live`).
    pub case: String,
    /// The load's target (a member or joint name).
    pub target: String,
    /// The load's distribution shape.
    pub kind: LoadKind,
    /// The normalized station (0..1 along the member axis) a
    /// member-targeted POINT/MOMENT load applies at (`on [G1@0.5]` --
    /// WO-85/D194, SCHEMA_VERSION 27). `None` for area/line loads and
    /// for joint-targeted point loads (the joint IS the location). A
    /// concentrated load on a bare member target never lowers with a
    /// guessed station -- that source shape is the E0211 constructive
    /// diagnostic instead.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub station: Option<f64>,
    /// The load's magnitude interval.
    pub value: ScalarInterval,
    /// The load's direction descriptor (`"gravity"` in v1 -- calcite/03
    /// sec. 4 does not yet specify a direction vocabulary beyond the
    /// gravity-dominant case every corpus design exercises).
    pub direction: String,
}

/// The serialized frame payload (calcite/03 sec. 4, verbatim): a
/// content-addressed record carrying one structure's joints, members,
/// supports, loads, and load-combination set.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#frame
pub struct FramePayload {
    /// Every joint in the structure (elaboration-sorted for determinism).
    pub joints: Vec<Joint>,
    /// Every member (elaboration-sorted for determinism).
    pub members: Vec<FrameMember>,
    /// Every support (elaboration-sorted for determinism).
    pub supports: Vec<Support>,
    /// Every load-transfer edge (elaboration-sorted for determinism;
    /// D176, WO-62 slice B): the structure's `transfers:` block,
    /// lowered.
    pub transfers: Vec<FrameTransfer>,
    /// Every literal load entry (elaboration-sorted for determinism).
    pub loads: Vec<FrameLoad>,
    /// The pack's combination set ref (from the structure's `require`
    /// group's `forall combo in <ref>:` clause, when present; a
    /// name-only placeholder when the file's require group names no
    /// combination sweep -- e.g. the retaining-wall stability claim,
    /// calcite/03 sec. 5).
    pub combinations: RecordRef,
}

impl FramePayload {
    /// The AD-18 content address of this payload under the `frame`
    /// domain tag -- the digest a `PayloadRef` pins and the store keys
    /// on. Stable across builds of the same source (AD-6).
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#frame
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(FRAME_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
#[allow(clippy::float_cmp)]
mod tests {
    use super::*;

    fn sample() -> FramePayload {
        FramePayload {
            joints: vec![
                Joint {
                    id: "A|deck".to_string(),
                    at: Some(JointAt {
                        grid_refs: vec!["A".to_string()],
                        datum: Datum::Level("deck".to_string()),
                    }),
                },
                Joint {
                    id: "support:AB1".to_string(),
                    at: None,
                },
            ],
            members: vec![FrameMember {
                id: "G1".to_string(),
                role: MemberRole::Beam,
                a: "A|deck".to_string(),
                b: "support:AB1".to_string(),
                length: ScalarInterval {
                    lo: 12.0,
                    hi: 12.0,
                    unit: "m".to_string(),
                },
                orientation: "horizontal".to_string(),
                section: RecordRef {
                    digest: String::new(),
                    name: "free".to_string(),
                },
                material: RecordRef {
                    digest: "blake3:aa".to_string(),
                    name: "astm_a992".to_string(),
                },
                section_domain: None,
                releases: Releases::default(),
            }],
            supports: vec![Support {
                joint: "support:AB1".to_string(),
                fixity: Vec::new(),
            }],
            transfers: vec![FrameTransfer {
                id: "g1_ab1".to_string(),
                kind: "Pinned".to_string(),
                from: "G1".to_string(),
                to: "AB1".to_string(),
                tributary: Some(ScalarInterval {
                    lo: 10.8,
                    hi: 10.8,
                    unit: "m2".to_string(),
                }),
                depth: None,
            }],
            loads: vec![FrameLoad {
                case: "pedestrian".to_string(),
                target: "Deck".to_string(),
                kind: LoadKind::Distributed,
                station: None,
                value: ScalarInterval {
                    lo: 4.1,
                    hi: 4.1,
                    unit: "kPa".to_string(),
                },
                direction: "gravity".to_string(),
            }],
            combinations: RecordRef {
                digest: String::new(),
                name: "std.civil.aisc.strength".to_string(),
            },
        }
    }

    #[test]
    fn frame_payload_round_trips_json() {
        let payload = sample();
        let json = serde_json::to_string(&payload).unwrap();
        let back: FramePayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back, payload);
    }

    // frob:tests crates/regolith-oblig/src/frame.rs::FramePayload.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.members[0].length.lo = 13.0;
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed field must change the digest"
        );
    }

    #[test]
    fn footing_zero_length_point_anchor_is_legal() {
        // calcite/03 sec. 4: a footing MAY be point-anchored (both ends
        // on the same datum, zero length): it contributes a
        // support/reaction point, not a span -- the schema does not
        // reject `a == b`.
        let mut payload = sample();
        payload.members[0].role = MemberRole::Footing;
        payload.members[0].a = "A|base".to_string();
        payload.members[0].b = "A|base".to_string();
        payload.members[0].length = ScalarInterval {
            lo: 0.0,
            hi: 0.0,
            unit: "m".to_string(),
        };
        payload.members[0].orientation = "point".to_string();
        let json = serde_json::to_string(&payload).unwrap();
        let back: FramePayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back.members[0].a, back.members[0].b);
    }

    #[test]
    fn transfer_carries_id_kind_from_to_and_optional_tributary() {
        let payload = sample();
        assert_eq!(payload.transfers.len(), 1);
        let t = &payload.transfers[0];
        assert_eq!(t.id, "g1_ab1");
        assert_eq!(t.kind, "Pinned");
        assert_eq!(t.from, "G1");
        assert_eq!(t.to, "AB1");
        assert_eq!(t.tributary.as_ref().unwrap().lo, 10.8);
    }

    #[test]
    fn line_load_with_station_round_trips_and_rekeys_the_digest() {
        // WO-85/D194 (SCHEMA_VERSION 27): the new `Line` kind and
        // `station` field serialize, round-trip, and are digest-
        // sensitive (INV-1: a moved point load is a different frame).
        let mut payload = sample();
        payload.loads[0].kind = LoadKind::Line;
        let json = serde_json::to_string(&payload).unwrap();
        assert!(json.contains("\"line\""), "{json}");
        let back: FramePayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back.loads[0].kind, LoadKind::Line);
        assert!(back.loads[0].station.is_none());

        let mut at_midspan = payload.clone();
        at_midspan.loads[0].kind = LoadKind::Point;
        at_midspan.loads[0].station = Some(0.5);
        let mut at_quarter = at_midspan.clone();
        at_quarter.loads[0].station = Some(0.25);
        assert_ne!(
            at_midspan.content_digest().unwrap(),
            at_quarter.content_digest().unwrap(),
            "a moved point load must re-key the frame digest"
        );
    }

    #[test]
    fn transfer_depth_round_trips_and_is_optional() {
        // WO-85/D194: `EmbeddedPost(depth=...)`'s declared embedment.
        let mut payload = sample();
        payload.transfers[0].kind = "EmbeddedPost".to_string();
        payload.transfers[0].depth = Some(ScalarInterval {
            lo: 1.4,
            hi: 1.4,
            unit: "m".to_string(),
        });
        let json = serde_json::to_string(&payload).unwrap();
        let back: FramePayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back.transfers[0].depth.as_ref().unwrap().lo, 1.4);
        // Absent depth stays absent on the wire (skip_serializing_if).
        let bare = serde_json::to_string(&sample()).unwrap();
        assert!(!bare.contains("\"depth\""), "{bare}");
    }

    #[test]
    fn transfer_tributary_is_optional() {
        let mut payload = sample();
        payload.transfers[0].tributary = None;
        let json = serde_json::to_string(&payload).unwrap();
        let back: FramePayload = serde_json::from_str(&json).unwrap();
        assert!(back.transfers[0].tributary.is_none());
    }

    #[test]
    fn changed_transfer_changes_the_digest() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let mut other = sample();
        other.transfers[0].kind = "Moment".to_string();
        assert_ne!(d1, other.content_digest().unwrap());
    }

    #[test]
    fn member_role_parses_known_words_and_falls_back_to_other() {
        assert_eq!(MemberRole::parse("beam"), MemberRole::Beam);
        assert_eq!(MemberRole::parse("footing"), MemberRole::Footing);
        assert_eq!(
            MemberRole::parse("truss"),
            MemberRole::Other("truss".to_string())
        );
    }

    #[test]
    fn datum_variants_tag_on_datum_kind() {
        let level = Datum::Level("deck".to_string());
        let json = serde_json::to_value(&level).unwrap();
        assert_eq!(json["datum_kind"], "level");

        let elevation = Datum::Elevation(ScalarInterval {
            lo: 3.6,
            hi: 3.6,
            unit: "m".to_string(),
        });
        let json = serde_json::to_value(&elevation).unwrap();
        assert_eq!(json["datum_kind"], "elevation");
    }

    /// A support-only joint (no member anchor of its own) round-trips
    /// with `at: None` rather than a fabricated position.
    #[test]
    fn support_only_joint_carries_no_fabricated_position() {
        let payload = sample();
        let support_joint = payload
            .joints
            .iter()
            .find(|j| j.id == "support:AB1")
            .unwrap();
        assert!(support_joint.at.is_none());
    }
}
