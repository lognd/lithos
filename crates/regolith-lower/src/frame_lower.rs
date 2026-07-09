//! Pass 3d (WO-48 deliverable 3): calcite `frame` payload elaboration.
//!
//! Walks every parsed `.calx` file's typed `structure` AST (calcite/02
//! sec. 6) into an in-memory [`FramePayload`] (calcite/03 sec. 4):
//! joints synthesized from member anchors and declared supports,
//! members with role/geometry/section/material, supports, literal load
//! entries, and the require group's combination-set ref.
//!
//! PURITY (AD-17): this pass reads no IO. Section/material refs are
//! NAME-ONLY pins (the `AstFlownetInputs` idiom, WO-32 deliverable 4a):
//! the digest is IO-resolved registry content, not available in this
//! pure pass. `dof: kept=` releases and support fixity resolve through
//! `std.civil` transfer/support-role records -- a different slice's
//! deliverable (WO-48 std.civil authoring) -- so both stay honestly
//! empty here (the AD-25 GeomExtract placeholder idiom, applied to
//! unresolved release/fixity data rather than geometry).
//!
//! GEOMETRY (calcite/03 sec. 4): a member's two anchors (`from (refs..)
//! to (refs..)`) resolve against the file's declared `grid`/`level`
//! datums: a grid ref's position is its declaration-order index times
//! the grid's `spacing` quantity; a level ref's position is its
//! declared elevation quantity. Two anchors sharing the SAME datum
//! tuple coalesce onto the same joint id (calcite/03 sec. 4: "member
//! ends meeting at a shared anchor coalesce"). A declared `support:`
//! node with no member anchor of its own gets a distinct
//! `support:<name>` joint with an unresolved (`at: None`) position --
//! v1 does not attempt to infer which member end a support physically
//! sits at from the transfer graph alone.
//!
//! DETERMINISM (AD-6): structures are elaborated in caller (sorted)
//! file order, and every payload collection is sorted before
//! construction, so an [`ElaboratedFrame`]'s payload digest is stable
//! across builds of the same source.

use std::collections::BTreeMap;

use regolith_oblig::{
    Datum, FrameLoad, FrameMember, FramePayload, Joint, JointAt, JointId, LoadKind, MemberRole,
    RecordRef, Releases, ScalarInterval, Support,
};
use regolith_syntax::ast::{AstNode, File, MemberDecl, StructureDecl};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::calcite::field_idents;
use crate::flownet_lower::quantity_scalar;
use crate::output::ParsedFile;

/// One elaborated frame: the structure's declared name plus its
/// content-addressable payload.
#[derive(Debug, Clone)]
pub struct ElaboratedFrame {
    /// The structure's declared name.
    pub name: String,
    /// The elaborated payload.
    pub payload: FramePayload,
}

/// The result of elaborating every `structure` in a set of parsed files.
#[derive(Debug, Clone, Default)]
pub struct FrameLowerReport {
    /// The elaborated frames, in file/source order.
    pub frames: Vec<ElaboratedFrame>,
}

/// Elaborate every `structure` declaration across `files` into a
/// [`FramePayload`]. Pure and IO-free (AD-17); deterministic (AD-6).
/// This is the WO-48 deliverable-3 entry point.
#[must_use]
pub fn elaborate_frames(files: &[ParsedFile]) -> FrameLowerReport {
    let span = tracing::info_span!("lower.frame");
    let _enter = span.enter();

    let mut report = FrameLowerReport::default();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        let grids = GridIndex::build(&file);
        let levels = LevelIndex::build(&file);
        let members_by_name: BTreeMap<String, MemberDecl> = file
            .members()
            .into_iter()
            .filter_map(|m| m.name().map(|n| (n, m)))
            .collect();
        let combinations = combo_ref(&file);
        let loads_by_case = load_entries(&file);

        for structure in file.structures() {
            let Some(name) = structure.name() else {
                continue;
            };
            let payload = elaborate_structure(
                &structure,
                &members_by_name,
                &grids,
                &levels,
                &loads_by_case,
                combinations.clone(),
            );
            report.frames.push(ElaboratedFrame { name, payload });
        }
    }
    tracing::info!(frames = report.frames.len(), "frame elaboration complete");
    report
}

/// A grid ref's resolved axis position: the owning grid's name (the
/// axis identity), its declaration-order offset, and the spacing
/// quantity's unit.
#[derive(Debug, Clone)]
struct GridPos {
    /// The owning grid's declared name (the axis identity) -- kept for
    /// diagnostics/future multi-axis disambiguation, not read by the
    /// current single-scalar length/orientation derivation.
    #[allow(dead_code)]
    axis: String,
    offset: f64,
    unit: String,
}

/// Every declared grid ref's resolved axis position, across all `grid`
/// declarations in a file.
#[derive(Debug, Clone, Default)]
struct GridIndex(BTreeMap<String, GridPos>);

impl GridIndex {
    fn build(file: &File) -> Self {
        let mut map = BTreeMap::new();
        for grid in file.grids() {
            let Some(gname) = grid.name() else {
                continue;
            };
            let toks: Vec<_> = grid
                .syntax()
                .children_with_tokens()
                .filter_map(rowan::NodeOrToken::into_token)
                .collect();
            let Some(colon_idx) = toks.iter().position(|t| t.kind() == SyntaxKind::Colon) else {
                continue;
            };
            let Some(spacing_idx) = toks
                .iter()
                .position(|t| t.kind() == SyntaxKind::Ident && t.text() == "spacing")
            else {
                continue;
            };
            let refs: Vec<String> = toks[colon_idx + 1..spacing_idx]
                .iter()
                .filter(|t| matches!(t.kind(), SyntaxKind::Ident | SyntaxKind::Number))
                .map(|t| t.text().to_string())
                .collect();
            let tail = &toks[spacing_idx + 1..];
            let Some(spacing) = tail
                .iter()
                .find(|t| t.kind() == SyntaxKind::Number)
                .and_then(|t| t.text().parse::<f64>().ok())
            else {
                continue;
            };
            let unit = tail
                .iter()
                .find(|t| t.kind() == SyntaxKind::Ident)
                .map(|t| t.text().to_string())
                .unwrap_or_default();
            for (i, r) in refs.iter().enumerate() {
                // A grid line count never approaches 2^52 (the f64
                // mantissa width): the cast is exact in practice, only
                // "lossy" in the general `usize` case clippy checks for.
                #[allow(clippy::cast_precision_loss)]
                let offset = i as f64 * spacing;
                map.insert(
                    r.clone(),
                    GridPos {
                        axis: gname.clone(),
                        offset,
                        unit: unit.clone(),
                    },
                );
            }
        }
        Self(map)
    }

    fn get(&self, r: &str) -> Option<&GridPos> {
        self.0.get(r)
    }
}

/// Every declared level ref's resolved elevation, across all `level`
/// declarations in a file.
#[derive(Debug, Clone, Default)]
struct LevelIndex(BTreeMap<String, ScalarInterval>);

impl LevelIndex {
    fn build(file: &File) -> Self {
        let mut map = BTreeMap::new();
        for level in file.levels() {
            let Some(name) = level.name() else {
                continue;
            };
            let toks: Vec<_> = level
                .syntax()
                .children_with_tokens()
                .filter_map(rowan::NodeOrToken::into_token)
                .collect();
            let Some(colon_idx) = toks.iter().position(|t| t.kind() == SyntaxKind::Colon) else {
                continue;
            };
            let tail = &toks[colon_idx + 1..];
            let Some(n) = tail
                .iter()
                .find(|t| t.kind() == SyntaxKind::Number)
                .and_then(|t| t.text().parse::<f64>().ok())
            else {
                continue;
            };
            let unit = tail
                .iter()
                .find(|t| t.kind() == SyntaxKind::Ident)
                .map(|t| t.text().to_string())
                .unwrap_or_default();
            map.insert(name, ScalarInterval { lo: n, hi: n, unit });
        }
        Self(map)
    }

    fn get(&self, r: &str) -> Option<&ScalarInterval> {
        self.0.get(r)
    }
}

/// A member's two anchor tuples (`from (refs..) to (refs..)`), read
/// off its `OpaqueIsland` anchor line (the front end records this line
/// whole -- see `MemberDecl`'s doc comment; it is never a typed
/// `Field`). Each tuple is the ref components in source order (e.g.
/// `["A", "deck"]` or `["A", "2", "ground"]`).
fn member_anchor(member: &MemberDecl) -> Option<(Vec<String>, Vec<String>)> {
    let opaque = member.syntax().children().find(|n| {
        n.kind() == SyntaxKind::OpaqueIsland
            && n.text().to_string().trim_start().starts_with("from")
    })?;
    let mut groups: Vec<Vec<String>> = Vec::new();
    let mut depth: u32 = 0;
    let mut current: Vec<String> = Vec::new();
    for tok in opaque
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
    {
        match tok.kind() {
            SyntaxKind::LParen => {
                depth += 1;
                if depth == 1 {
                    current.clear();
                }
            }
            SyntaxKind::RParen => {
                if depth == 1 {
                    groups.push(std::mem::take(&mut current));
                }
                depth = depth.saturating_sub(1);
            }
            SyntaxKind::Ident | SyntaxKind::Number if depth >= 1 => {
                current.push(tok.text().to_string());
            }
            _ => {}
        }
    }
    if groups.len() >= 2 {
        Some((groups[0].clone(), groups[1].clone()))
    } else {
        None
    }
}

/// The member header's role word (`member G1: beam` -> `"beam"`): the
/// third `Ident` token among the member's direct header tokens (the
/// first is the `member` keyword, the second the declared name).
fn member_role_word(member: &MemberDecl) -> Option<String> {
    member
        .syntax()
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .nth(2)
        .map(|t| t.text().to_string())
}

/// The member's `section:`/`material:` field values as name-only
/// [`RecordRef`]s (digest is IO-resolved registry content, not
/// available in this pure pass -- the `AstFlownetInputs` precedent).
/// `section: free` keeps the literal `"free"` name, the AD-25
/// pre-resolution placeholder verbatim.
fn member_section_material(member: &MemberDecl) -> (RecordRef, RecordRef) {
    let mut section = RecordRef {
        digest: String::new(),
        name: "free".to_string(),
    };
    let mut material = RecordRef {
        digest: String::new(),
        name: String::new(),
    };
    for field in member.fields() {
        match field.name().as_str() {
            "section" => section.name = registry_or_bare_name(&field),
            "material" => material.name = registry_or_bare_name(&field),
            _ => {}
        }
    }
    (section, material)
}

/// A field's value name: `registry(<ref>)` yields `<ref>`; a bare cause
/// value (`free`) yields its own text; anything else falls back to the
/// field's full value text.
fn registry_or_bare_name(field: &regolith_syntax::ast::Field) -> String {
    let Some(value) = field.value() else {
        return String::new();
    };
    let idents: Vec<String> = value
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    // `registry(name)` -> two idents (`registry`, `name`); take the
    // second. A bare cause value (`free`) has NO `Ident` token at all
    // (`free` lexes as the reserved `FreeKw`, not an identifier) -- fall
    // back to the value node's own trimmed text for that case.
    idents
        .last()
        .cloned()
        .unwrap_or_else(|| value.text().to_string().trim().to_string())
}

/// A canonical joint key for an anchor tuple (`["A", "deck"]` ->
/// `"A|deck"`) -- the coalescing partition key (calcite/03 sec. 4).
fn anchor_key(anchor: &[String]) -> String {
    anchor.join("|")
}

/// The resolved [`JointAt`] for an anchor tuple, when every component
/// resolves against the file's grid/level datums. Grid refs are kept in
/// their declared order; the last component that resolves as a LEVEL
/// ref becomes the joint's datum (the calcite/02 anchor convention: the
/// level ref is always the tuple's final component).
fn resolve_anchor_at(anchor: &[String], grids: &GridIndex, levels: &LevelIndex) -> Option<JointAt> {
    let mut grid_refs = Vec::new();
    let mut datum = None;
    for component in anchor {
        if let Some(elev) = levels.get(component) {
            datum = Some(Datum::Level(component.clone()));
            let _ = elev;
        } else if grids.get(component).is_some() {
            grid_refs.push(component.clone());
        }
    }
    datum.map(|datum| JointAt { grid_refs, datum })
}

/// The euclidean-ish span length between two anchors: the root-sum-
/// square of each shared axis's offset delta (grid axes plus the level
/// elevation), assuming a single consistent unit across the file's
/// grid/level declarations (true of every calcite corpus design; a
/// mixed-unit file is a documented v1 gap, not silently mis-converted).
/// Zero for a point-anchored footing (`a == b`, calcite/03 sec. 4,
/// legal).
fn anchor_length(
    a: &[String],
    b: &[String],
    grids: &GridIndex,
    levels: &LevelIndex,
) -> ScalarInterval {
    let mut sum_sq = 0.0;
    let mut unit = String::new();
    for (ca, cb) in a.iter().zip(b.iter()) {
        if ca == cb {
            continue;
        }
        if let (Some(ga), Some(gb)) = (grids.get(ca), grids.get(cb)) {
            let d = ga.offset - gb.offset;
            sum_sq += d * d;
            if unit.is_empty() {
                unit.clone_from(&ga.unit);
            }
        } else if let (Some(la), Some(lb)) = (levels.get(ca), levels.get(cb)) {
            let d = la.lo - lb.lo;
            sum_sq += d * d;
            if unit.is_empty() {
                unit.clone_from(&la.unit);
            }
        }
    }
    let length = sum_sq.sqrt();
    ScalarInterval {
        lo: length,
        hi: length,
        unit: if unit.is_empty() {
            "m".to_string()
        } else {
            unit
        },
    }
}

/// A deterministic orientation descriptor: `"point"` for a zero-length
/// (footing) anchor pair, `"vertical"` when only the level component
/// differs, `"horizontal"` when only grid components differ, else
/// `"inclined"`.
fn orientation_of(a: &[String], b: &[String], levels: &LevelIndex) -> String {
    if a == b {
        return "point".to_string();
    }
    let level_differs = a
        .iter()
        .zip(b.iter())
        .any(|(ca, cb)| ca != cb && levels.get(ca).is_some());
    let grid_differs = a
        .iter()
        .zip(b.iter())
        .any(|(ca, cb)| ca != cb && levels.get(ca).is_none());
    match (grid_differs, level_differs) {
        (false, true) => "vertical".to_string(),
        (true, false) => "horizontal".to_string(),
        _ => "inclined".to_string(),
    }
}

/// The require group's `forall combo in <ref>:` combination-set ref, a
/// name-only placeholder (digest is IO-resolved registry content) when
/// present; an empty placeholder when the file's require group names no
/// sweep (e.g. the retaining-wall stability claim, calcite/03 sec. 5).
fn combo_ref(file: &File) -> RecordRef {
    for req in file.fluid_requires() {
        let text = req.syntax().text().to_string();
        if let Some(idx) = text.find("forall combo in ") {
            let after = &text[idx + "forall combo in ".len()..];
            let name: String = after
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '.' || *c == '_')
                .collect();
            if !name.is_empty() {
                return RecordRef {
                    digest: String::new(),
                    name,
                };
            }
        }
    }
    RecordRef {
        digest: String::new(),
        name: String::new(),
    }
}

/// Every literal `loads:` field (a quantity magnitude with an `on
/// [<target>]` clause) as a [`FrameLoad`], keyed by nothing in
/// particular (returned as a flat, source-ordered `Vec` -- every
/// structure in the file shares the same `loads:` block, calcite/02
/// sec. 7, so this is built once per file and reused per structure). A
/// `derived` self-weight row or a pack-model ref (`site.x ->
/// std.civil.y`) is NOT a literal payload entry (calcite/03 sec. 2:
/// both resolve through the ordinary derivation/effects mechanism, not
/// as frame data) and is skipped here, honestly.
fn load_entries(file: &File) -> Vec<FrameLoad> {
    let mut out = Vec::new();
    for loads_decl in file.loads_blocks() {
        for field in loads_decl
            .syntax()
            .children()
            .filter_map(regolith_syntax::ast::Field::cast)
        {
            let Some(value) = field.value() else {
                continue;
            };
            if value.kind() != SyntaxKind::QuantityLit {
                continue;
            }
            let Some(magnitude) = quantity_scalar(&value) else {
                continue;
            };
            let full_text = field.syntax().text().to_string();
            let Some(target) = on_target(&full_text) else {
                continue;
            };
            let kind = if magnitude.unit.ends_with("Pa") {
                LoadKind::Distributed
            } else {
                LoadKind::Point
            };
            out.push(FrameLoad {
                case: field.name(),
                target,
                kind,
                value: magnitude,
                direction: "gravity".to_string(),
            });
        }
    }
    out
}

/// The first `on [<target>, ...]` bracket's first name, from a load
/// field's raw text.
fn on_target(text: &str) -> Option<String> {
    let idx = text.find("on [")?;
    let after = &text[idx + "on [".len()..];
    let close = after.find(']')?;
    after[..close]
        .split(',')
        .next()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

/// Elaborate one `structure` declaration into a [`FramePayload`]:
/// joints (member anchors, coalesced, plus support-only joints),
/// members, supports, this file's literal loads, and the combination
/// ref.
fn elaborate_structure(
    structure: &StructureDecl,
    members_by_name: &BTreeMap<String, MemberDecl>,
    grids: &GridIndex,
    levels: &LevelIndex,
    loads: &[FrameLoad],
    combinations: RecordRef,
) -> FramePayload {
    let member_names = field_idents(structure, "members");
    let support_pairs = field_idents(structure, "support");

    let mut joints: BTreeMap<JointId, Joint> = BTreeMap::new();
    let mut members: Vec<FrameMember> = Vec::new();

    for name in &member_names {
        let Some(decl) = members_by_name.get(name) else {
            continue;
        };
        let Some((anchor_a, anchor_b)) = member_anchor(decl) else {
            continue;
        };
        let joint_a = anchor_key(&anchor_a);
        let joint_b = anchor_key(&anchor_b);
        joints.entry(joint_a.clone()).or_insert_with(|| Joint {
            id: joint_a.clone(),
            at: resolve_anchor_at(&anchor_a, grids, levels),
        });
        joints.entry(joint_b.clone()).or_insert_with(|| Joint {
            id: joint_b.clone(),
            at: resolve_anchor_at(&anchor_b, grids, levels),
        });

        let role = member_role_word(decl).map_or_else(
            || MemberRole::Other(String::new()),
            |w| MemberRole::parse(&w),
        );
        let (section, material) = member_section_material(decl);
        let length = anchor_length(&anchor_a, &anchor_b, grids, levels);
        let orientation = orientation_of(&anchor_a, &anchor_b, levels);

        members.push(FrameMember {
            id: name.clone(),
            role,
            a: joint_a,
            b: joint_b,
            length,
            orientation,
            section,
            material,
            releases: Releases::default(),
        });
    }

    let mut supports: Vec<Support> = Vec::new();
    let mut support_names = Vec::new();
    let mut pairs = support_pairs.iter();
    while let (Some(name), Some(_role)) = (pairs.next(), pairs.next()) {
        support_names.push(name.clone());
        let joint_id = format!("support:{name}");
        joints.entry(joint_id.clone()).or_insert_with(|| Joint {
            id: joint_id.clone(),
            at: None,
        });
        supports.push(Support {
            joint: joint_id,
            fixity: Vec::new(),
        });
    }

    let mut joints: Vec<Joint> = joints.into_values().collect();
    joints.sort_by(|a, b| a.id.cmp(&b.id));
    members.sort_by(|a, b| a.id.cmp(&b.id));
    supports.sort_by(|a, b| a.joint.cmp(&b.joint));
    let mut loads = loads.to_vec();
    loads.sort_by(|a, b| {
        (a.case.clone(), a.target.clone()).cmp(&(b.case.clone(), b.target.clone()))
    });

    FramePayload {
        joints,
        members,
        supports,
        loads,
        combinations,
    }
}

#[cfg(test)]
// Point-valued fixtures pass exact bounds through elaboration, so
// `assert_eq!` on a bound against its literal is the correct comparison
// (not an epsilon) -- mirrors `flownet_lower`'s test discipline.
#[allow(clippy::float_cmp)]
mod tests {
    use super::*;
    use crate::output::SourceFile;
    use crate::parse_sources;

    const FOOTBRIDGE_SRC: &str = "import std.civil (Pinned, Roller, Bearing)\n\
site Greenway:\n\
\x20   boundary:\n\
\x20       wind_speed: [0m/s, 43m/s] by catalog(asce7_fig26)\n\
grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: free\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
member Deck: slab\n\
\x20   section: registry(comp_deck_140mm)\n\
\x20   material: registry(concrete_c30)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing, AB2: footing\n\
\x20   members: G1, Deck\n\
\x20   transfers:\n\
\x20       d_g1: Bearing(tributary=10.8m2) (Deck -> G1)\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
\x20   pedestrian: 4.1kPa on [Deck] by catalog(aashto_ped)\n\
require Structure:\n\
\x20   forall combo in std.civil.aisc.strength:\n\
\x20       strength: civil.utilization(Bridge.members.all, under=combo) <= 1.0\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";

    fn elaborate(src: &str) -> FrameLowerReport {
        let files = parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.calx"),
            text: src.to_string(),
        }]);
        elaborate_frames(&files)
    }

    #[test]
    fn elaborates_one_frame_per_structure() {
        let report = elaborate(FOOTBRIDGE_SRC);
        assert_eq!(report.frames.len(), 1);
        assert_eq!(report.frames[0].name, "Bridge");
    }

    #[test]
    fn member_ends_at_shared_anchor_coalesce() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        // G1 and Deck share BOTH anchors (A,deck)/(B,deck): exactly two
        // member-derived joints, not four.
        let member_joints: Vec<_> = payload.joints.iter().filter(|j| j.at.is_some()).collect();
        assert_eq!(member_joints.len(), 2, "{:?}", payload.joints);
    }

    #[test]
    fn support_only_joints_carry_no_position() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        let ab1 = payload
            .joints
            .iter()
            .find(|j| j.id == "support:AB1")
            .expect("support:AB1 joint");
        assert!(ab1.at.is_none());
        assert_eq!(payload.supports.len(), 2);
    }

    #[test]
    fn member_role_section_and_material_resolve() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.role, MemberRole::Beam);
        assert_eq!(g1.section.name, "free");
        assert_eq!(g1.material.name, "astm_a992");
        let deck = payload.members.iter().find(|m| m.id == "Deck").unwrap();
        assert_eq!(deck.role, MemberRole::Slab);
        assert_eq!(deck.section.name, "comp_deck_140mm");
    }

    #[test]
    fn span_length_derives_from_grid_spacing() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.length.lo, 12.0);
        assert_eq!(g1.length.unit, "m");
        assert_eq!(g1.orientation, "horizontal");
    }

    #[test]
    fn footing_point_anchor_is_zero_length_and_legal() {
        let src = "grid line: A spacing 1.0m\n\
level base: 0m\n\
level top: 2.8m\n\
member Stem: wall\n\
\x20   section: registry(rc_wall_250mm)\n\
\x20   material: registry(concrete_c30)\n\
\x20   from (A, base) to (A, top)\n\
member Heel: footing\n\
\x20   section: registry(rc_footing_1800x350)\n\
\x20   material: registry(concrete_c30)\n\
\x20   from (A, base) to (A, base)\n\
structure Wall:\n\
\x20   support: SG: footing\n\
\x20   members: Stem, Heel\n\
\x20   transfers:\n\
\x20       stem_heel: Moment() (Stem -> Heel)\n\
\x20       heel_sg: Bearing() (Heel -> SG)\n\
loads:\n\
\x20   dead: derived\n\
require Stability:\n\
\x20   overturn: equilibrium(Wall, under=std.civil.geo.stability): stable\n";
        let report = elaborate(src);
        let payload = &report.frames[0].payload;
        let heel = payload.members.iter().find(|m| m.id == "Heel").unwrap();
        assert_eq!(heel.a, heel.b, "point-anchored footing: a == b");
        assert_eq!(heel.length.lo, 0.0);
        assert_eq!(heel.orientation, "point");
        // No `forall combo in ...` in this file's require group: the
        // combinations ref stays an honest empty placeholder.
        assert!(payload.combinations.name.is_empty());
    }

    #[test]
    fn load_entries_carry_literal_magnitude_and_target() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.loads.len(), 1, "{:?}", payload.loads);
        let load = &payload.loads[0];
        assert_eq!(load.case, "pedestrian");
        assert_eq!(load.target, "Deck");
        assert_eq!(load.kind, LoadKind::Distributed);
        assert_eq!(load.value.lo, 4.1);
    }

    #[test]
    fn combinations_ref_reads_the_forall_combo_pack() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.combinations.name, "std.civil.aisc.strength");
    }

    #[test]
    fn elaboration_is_deterministic() {
        let a = elaborate(FOOTBRIDGE_SRC);
        let b = elaborate(FOOTBRIDGE_SRC);
        let da = a.frames[0].payload.content_digest().unwrap();
        let db = b.frames[0].payload.content_digest().unwrap();
        assert_eq!(da, db, "same source -> identical payload digest (AD-6)");
    }
}
