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
    Datum, FrameLoad, FrameMember, FramePayload, FrameTransfer, Joint, JointAt, JointId, LoadKind,
    MemberRole, RecordRef, Releases, ScalarInterval, Support,
};
use regolith_syntax::ast::{AstNode, File, MemberDecl, StructureDecl};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_syntax::SyntaxNode;

use crate::calcite::field_idents;
use crate::flownet_lower::{
    arg_quantity, callee_name, collect_args, edge_endpoints, quantity_scalar,
};
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

    // Grid/level datums are declared once per project (typically in
    // `site.calx`, calcite/02 sec. 1) and consumed by member anchors in
    // OTHER files (e.g. `frame.calx`) through ordinary cross-file
    // resolution -- the same relationship `check` already accepts.
    // Building the position table per-file (the earlier shape) silently
    // starved every anchor in a file with no grid/level declarations of
    // its own: `grids`/`levels` were empty there, so every anchor
    // component failed to resolve and `anchor_length` fell back to its
    // zero-datum sum. Aggregate every file's `grid`/`level` declarations
    // into ONE project-wide table first, then elaborate each file's
    // structures against that shared table (AD-6 determinism preserved:
    // both indices key on declared names, indifferent to file order).
    let all_files: Vec<File> = files
        .iter()
        .filter_map(|pf| File::cast(pf.parse.syntax()))
        .collect();
    let grids = GridIndex::build_all(&all_files);
    let levels = LevelIndex::build_all(&all_files);

    let mut report = FrameLowerReport::default();
    for file in &all_files {
        let members_by_name: BTreeMap<String, MemberDecl> = file
            .members()
            .into_iter()
            .filter_map(|m| m.name().map(|n| (n, m)))
            .collect();
        let combinations = combo_ref(file);
        let loads_by_case = load_entries(file);

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

    /// Every declared grid ref across a WHOLE project's files (calcite/02
    /// sec. 1: `grid`/`level` datums are declared once, typically in
    /// `site.calx`, and consumed by member anchors in other files via
    /// ordinary cross-file resolution). Later files win on a name clash,
    /// same as a single-file `BTreeMap::insert` would -- no project
    /// fixture in this corpus declares the same grid ref twice, so this
    /// is an honest tie-break, not a silently-swallowed conflict.
    fn build_all(files: &[File]) -> Self {
        let mut merged = BTreeMap::new();
        for file in files {
            merged.extend(Self::build(file).0);
        }
        Self(merged)
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

    /// Every declared level ref across a WHOLE project's files --
    /// `GridIndex::build_all`'s counterpart, same cross-file-datum
    /// rationale.
    fn build_all(files: &[File]) -> Self {
        let mut merged = BTreeMap::new();
        for file in files {
            merged.extend(Self::build(file).0);
        }
        Self(merged)
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
            // WO-68: `section: in registry(<family>)` is a DOMAIN
            // declaration, not a resolved value (the exact `in [lo,
            // hi]` semantics, D181) -- stays the `free` placeholder
            // (AD-25's GeomExtract rule) so a searchable member never
            // reads as falsely pre-resolved to its family's name; the
            // declared family itself lives in `section_domain`
            // (`section_domain_ref`, this member's dedicated
            // extraction), never here.
            "section" if is_in_value_source(&field) => {}
            "section" => section.name = registry_or_bare_name(&field),
            "material" => material.name = registry_or_bare_name(&field),
            _ => {}
        }
    }
    (section, material)
}

/// The declared candidate FAMILY for a member's `section: in
/// registry(<family-ref>)` value source (WO-68, D181): the dotted
/// family ref text between `registry(` and its closing `)`, or `None`
/// for every other section form -- `free` (no domain declared,
/// WO-65's honest `family_not_landed` deferral stands unchanged), a
/// resolved `registry(<ref>)` literal (no `in`, already resolved), an
/// `in [lo, hi]`/`in {a, b}` numeric/discrete domain (not a record
/// family), or a malformed `in registry(...)` (empty ref; a
/// non-`registry` callee) -- the negative-fixture shapes this WO
/// names degrade to `None` here rather than panicking or guessing
/// (AD-3: structure recorded, never invented). Read via whole-node
/// text + string ops (the `registry_or_bare_name`/`combo_ref` pattern
/// this module already uses for loosely-shaped value text) because
/// `ValueSource` wraps `in [lo, hi]` and `in registry(<ref>)` in the
/// identical node shape -- only the text disambiguates them.
/// True when a field's value source is an `in <domain>` form (any of
/// them -- `in [lo, hi]`, `in {a, b}`, `in registry(<ref>)`): the
/// whole-node-text check `member_section_material` uses to keep
/// `section` at its `free` placeholder for a searchable member instead
/// of misreading the domain's own tokens as a resolved name.
fn is_in_value_source(field: &regolith_syntax::ast::Field) -> bool {
    field
        .value()
        .is_some_and(|v| v.text().to_string().trim_start().starts_with("in "))
}

fn section_domain_ref(member: &MemberDecl) -> Option<String> {
    for field in member.fields() {
        if field.name() != "section" {
            continue;
        }
        let value = field.value()?;
        let text = value.text().to_string();
        let after_in = text.trim().strip_prefix("in")?.trim_start();
        let after_registry = after_in.strip_prefix("registry(")?;
        let close = after_registry.find(')')?;
        let family = after_registry[..close].trim();
        return if family.is_empty() {
            None
        } else {
            Some(family.to_string())
        };
    }
    None
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

/// A load row's quantity magnitude WITH its full compound unit text
/// (WO-85/D194): a plain `1.4kPa` is a [`SyntaxKind::QuantityLit`]
/// value node, but `3.5kN/m` (and a `5kN-m` moment) parse as a binary
/// expression -- `QuantityLit`, then `/` (or `-`), then a one-ident
/// `NameRef` denominator -- because the lexer's unit run stops at the
/// operator. Reconstruct the compound unit ONLY when the operator and
/// denominator are byte-ADJACENT to the quantity (no interleaved
/// whitespace): `9kN - m` spaced apart is genuine arithmetic, not a
/// unit spelling, and degrades to `None` here (recorded, never
/// invented -- AD-3).
pub(crate) fn load_quantity(value: &SyntaxNode) -> Option<ScalarInterval> {
    if value.kind() == SyntaxKind::QuantityLit {
        return quantity_scalar(value);
    }
    let parts: Vec<_> = value
        .children_with_tokens()
        .filter(|el| el.kind() != SyntaxKind::Whitespace)
        .collect();
    let [quantity, op, denom] = parts.as_slice() else {
        return None;
    };
    let quantity = quantity
        .as_node()
        .filter(|n| n.kind() == SyntaxKind::QuantityLit)?;
    let op = op.as_token()?;
    let sep = match op.kind() {
        SyntaxKind::Slash => "/",
        SyntaxKind::Minus => "-",
        _ => return None,
    };
    let denom = denom
        .as_node()
        .filter(|n| n.kind() == SyntaxKind::NameRef)?;
    if quantity.text_range().end() != op.text_range().start()
        || op.text_range().end() != denom.text_range().start()
    {
        return None;
    }
    let denom_idents: Vec<String> = denom
        .children_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    let [denom_unit] = denom_idents.as_slice() else {
        return None;
    };
    let base = quantity_scalar(quantity)?;
    Some(ScalarInterval {
        lo: base.lo,
        hi: base.hi,
        unit: format!("{}{sep}{denom_unit}", base.unit),
    })
}

/// Force-unit spellings this pass recognizes as a concentrated load's
/// magnitude numerator (D194's unit-dimension dispatch; the small
/// fixed-vocabulary posture `frame_resolve`'s own unit tables use --
/// an unrecognized unit is skipped with a log line, never guessed).
const FORCE_UNITS: &[&str] = &["N", "kN", "MN"];

/// The [`LoadKind`] a load row's unit dimension selects (D194: kind is
/// DERIVED from the quantity's unit dimension -- dimensions partition,
/// so the dispatch cannot collide): pressure (`*Pa`) -> area, force/
/// length (`kN/m`) -> line, force (`kN`) -> point, force-length
/// (`kN-m`) -> moment. `None` for a unit outside the vocabulary.
pub(crate) fn load_kind_for_unit(unit: &str) -> Option<LoadKind> {
    if unit.ends_with("Pa") {
        return Some(LoadKind::Distributed);
    }
    if let Some((numer, denom)) = unit.split_once('/') {
        return (FORCE_UNITS.contains(&numer) && denom == "m").then_some(LoadKind::Line);
    }
    if let Some((numer, denom)) = unit.split_once('-') {
        return (FORCE_UNITS.contains(&numer) && denom == "m").then_some(LoadKind::Moment);
    }
    FORCE_UNITS.contains(&unit).then_some(LoadKind::Point)
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
///
/// WO-85/D194: the load's KIND derives from its unit dimension
/// (:func:`load_kind_for_unit`), and a member-targeted point/moment
/// row carries its normalized `@<station>` refinement. A concentrated
/// load on a bare MEMBER target (no station) never lowers -- guessing
/// its location would fabricate a demand; `calcite::run_calcite_checks`
/// rejects that source shape as the constructive E0211, and this pass
/// skips the row (with a log line) so the payload never carries a
/// location-less concentrated load. An out-of-range or unparseable
/// station is the same E0211 family and is likewise never lowered.
fn load_entries(file: &File) -> Vec<FrameLoad> {
    let member_names: std::collections::BTreeSet<String> = file
        .members()
        .into_iter()
        .filter_map(|m| m.name())
        .collect();
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
            let Some(magnitude) = load_quantity(&value) else {
                continue;
            };
            let Some(kind) = load_kind_for_unit(&magnitude.unit) else {
                tracing::info!(
                    case = %field.name(),
                    unit = %magnitude.unit,
                    "load row's unit is outside the recognized load \
                     vocabulary; row skipped (not guessed)"
                );
                continue;
            };
            let full_text = field.syntax().text().to_string();
            let Some((target, station)) = on_target(&full_text) else {
                continue;
            };
            let concentrated = matches!(kind, LoadKind::Point | LoadKind::Moment);
            if concentrated && station.is_none() && member_names.contains(&target) {
                // The E0211 source shape (`calcite.rs` emits the
                // diagnostic); the payload honestly omits the row.
                tracing::info!(
                    case = %field.name(),
                    target = %target,
                    "concentrated load on a bare member target has no \
                     station; row not lowered (E0211)"
                );
                continue;
            }
            if let Some(f) = station {
                if !(0.0..=1.0).contains(&f) {
                    tracing::info!(
                        case = %field.name(),
                        target = %target,
                        station = f,
                        "load station outside [0, 1]; row not lowered (E0211)"
                    );
                    continue;
                }
            }
            // A station is only meaningful on a concentrated load; an
            // area/line row never carries one into the payload
            // (`calcite.rs` flags the source shape).
            let station = if concentrated { station } else { None };
            out.push(FrameLoad {
                case: field.name(),
                target,
                kind,
                station,
                value: magnitude,
                direction: "gravity".to_string(),
            });
        }
    }
    out
}

/// The first `on [<target>, ...]` bracket's first name from a load
/// field's raw text, split into `(target, station)`: `on [G1]` ->
/// `("G1", None)`; `on [G1@0.5]` -> `("G1", Some(0.5))` (WO-85/D194's
/// normalized-station target refinement). An UNPARSEABLE station keeps
/// the whole raw `<t>@<junk>` text as the target (station `None`), so
/// the row can never silently match a bare member name -- `calcite.rs`
/// reads the same raw text and names the malformation (E0211).
fn on_target(text: &str) -> Option<(String, Option<f64>)> {
    let first = on_target_raw(text)?;
    match first.split_once('@') {
        Some((target, station_text)) => {
            let target = target.trim();
            if target.is_empty() {
                return None;
            }
            match station_text.trim().parse::<f64>() {
                Ok(f) => Some((target.to_string(), Some(f))),
                Err(_) => Some((first.to_string(), None)),
            }
        }
        None => Some((first, None)),
    }
}

/// The first `on [<target>, ...]` bracket entry's RAW text (station
/// refinement included, untouched) from a load field's text --
/// `on [G1@0.5] by ...` -> `"G1@0.5"`. Shared with `calcite.rs`'s
/// E0211 check so the diagnostic and the lowering read the SAME
/// target text (NO DUPLICATION).
pub(crate) fn on_target_raw(text: &str) -> Option<String> {
    let idx = text.find("on [")?;
    let after = &text[idx + "on [".len()..];
    let close = after.find(']')?;
    let first = after[..close].split(',').next()?.trim();
    if first.is_empty() {
        return None;
    }
    Some(first.to_string())
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
        let section_domain = section_domain_ref(decl);
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
            section_domain,
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

    let mut transfers = transfer_entries(structure);

    let mut joints: Vec<Joint> = joints.into_values().collect();
    joints.sort_by(|a, b| a.id.cmp(&b.id));
    members.sort_by(|a, b| a.id.cmp(&b.id));
    supports.sort_by(|a, b| a.joint.cmp(&b.joint));
    transfers.sort_by(|a, b| a.id.cmp(&b.id));
    let mut loads = loads.to_vec();
    loads.sort_by(|a, b| {
        (a.case.clone(), a.target.clone()).cmp(&(b.case.clone(), b.target.clone()))
    });

    FramePayload {
        joints,
        members,
        supports,
        transfers,
        loads,
        combinations,
    }
}

/// Every declared `transfers:` edge (calcite/02 sec. 6; D176, WO-62
/// slice B): id, connection-class name (the constructor's leading
/// `Ident`, e.g. `Bearing`), the `(<from> -> <to>)` endpoints
/// (:func:`edge_endpoints`, the fluid/E0207 discipline's own
/// degradation-tolerant reader, reused verbatim -- NO DUPLICATION),
/// the declared `tributary=` quantity argument, and (WO-85/D194) the
/// declared `depth=` quantity argument (`EmbeddedPost(depth=1.3m)`,
/// the `civil.embedment` claim's declared-depth input), each when
/// present.
fn transfer_entries(structure: &StructureDecl) -> Vec<FrameTransfer> {
    let Some(edges) = structure.transfers() else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for edge in edges.edges() {
        let id = edge.name();
        let Some(value) = edge.value() else {
            continue;
        };
        let kind = callee_name(&value).unwrap_or_default();
        let args = collect_args(&value);
        // WO-96 bearing close-out: a `BasePlate(..., bearing=<area>)`
        // declares its bearing-plate area through the SAME area-unit
        // `tributary` field the Python `declared_footing_area_m2` reader
        // already consumes -- no new serialized field (SCHEMA_VERSION 27
        // is frozen). `resolve_tributary_demand` ignores non-`Bearing`
        // transfers, so a BasePlate's plate area never pollutes the
        // tributary-load sum. An explicit `tributary=` (the Bearing
        // idiom) still wins if both are somehow present.
        let tributary =
            arg_quantity(&args, "tributary").or_else(|| arg_quantity(&args, "bearing"));
        let depth = arg_quantity(&args, "depth");
        let (from, to) = edge_endpoints(&edge);
        out.push(FrameTransfer {
            id,
            kind,
            from,
            to,
            tributary,
            depth,
        });
    }
    out
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
    fn section_in_registry_declares_a_domain_and_stays_the_free_placeholder() {
        // WO-68 deliverable 4 (D181): `section: in registry(<family>)`
        // lowers its family into `section_domain` and leaves `section`
        // itself at the ordinary `free` placeholder (AD-25) -- it is a
        // DOMAIN declaration, not a resolved value.
        let src = "grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: in registry(std.civil.w_shape)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";
        let report = elaborate(src);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.section.name, "free", "domain declared, not resolved");
        assert_eq!(g1.section_domain.as_deref(), Some("std.civil.w_shape"));
    }

    #[test]
    fn section_free_declares_no_domain() {
        // WO-65 D181 finding 2, unchanged by this WO: `free` alone
        // infers no family.
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.section_domain, None);
    }

    #[test]
    fn section_in_registry_empty_ref_declares_no_domain() {
        // WO-68 negative shape: an empty `registry()` ref degrades to
        // `None` honestly rather than a malformed family string.
        let src = "grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: in registry()\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";
        let report = elaborate(src);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.section_domain, None);
        assert_eq!(g1.section.name, "free");
    }

    #[test]
    fn section_in_non_registry_callee_declares_no_domain() {
        // WO-68 negative shape: `in <numeric interval>` (not a
        // `registry(...)` call) is the ordinary D105a bounded-freedom
        // form, not a record domain -- no family to declare.
        let src = "grid ends: A, B spacing 12.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: in [100mm, 400mm]\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n";
        let report = elaborate(src);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.section_domain, None);
        assert_eq!(g1.section.name, "free");
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
    fn transfers_carry_id_kind_endpoints_and_tributary() {
        let report = elaborate(FOOTBRIDGE_SRC);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.transfers.len(), 2, "{:?}", payload.transfers);
        let d_g1 = payload
            .transfers
            .iter()
            .find(|t| t.id == "d_g1")
            .expect("d_g1 transfer");
        assert_eq!(d_g1.kind, "Bearing");
        assert_eq!(d_g1.from, "Deck");
        assert_eq!(d_g1.to, "G1");
        assert_eq!(d_g1.tributary.as_ref().unwrap().lo, 10.8);
        let g1_a = payload
            .transfers
            .iter()
            .find(|t| t.id == "g1_a")
            .expect("g1_a transfer");
        assert_eq!(g1_a.kind, "Pinned");
        assert!(g1_a.tributary.is_none(), "Pinned() declares no tributary");
    }

    #[test]
    fn elaboration_is_deterministic() {
        let a = elaborate(FOOTBRIDGE_SRC);
        let b = elaborate(FOOTBRIDGE_SRC);
        let da = a.frames[0].payload.content_digest().unwrap();
        let db = b.frames[0].payload.content_digest().unwrap();
        assert_eq!(da, db, "same source -> identical payload digest (AD-6)");
    }

    /// Elaborate several source strings as SEPARATE files (mirrors a
    /// real project's `site.calx` + `frame.calx` split, calcite/02
    /// section 1, rather than one monolithic source) -- the shape the
    /// cross-file grid/level regression below needs.
    fn elaborate_multi(sources: &[(&str, &str)]) -> FrameLowerReport {
        let files = parse_sources(
            &sources
                .iter()
                .map(|(path, text)| SourceFile {
                    path: camino::Utf8PathBuf::from(*path),
                    text: (*text).to_string(),
                })
                .collect::<Vec<_>>(),
        );
        elaborate_frames(&files)
    }

    const SPLIT_SITE_SRC: &str = "grid cols: A, B spacing 7.2m\n\
grid rows: 1, 2 spacing 6.0m\n\
level ground: 0m\n\
level roof: 3.6m\n";

    /// Regression for the split-file defect: `grid`/`level` declared in
    /// one file (`site.calx`), members anchored to them in another
    /// (`frame.calx`) -- the exact small_office shape. Before the
    /// `build_all` aggregation fix, `frame_lower` built its grid/level
    /// position table per-file, so a member file with NO grid/level
    /// declarations of its own resolved every anchor component to
    /// `None` and every length silently collapsed to zero.
    #[test]
    fn cross_file_vertical_member_resolves_nonzero_length() {
        let frame_src = "member C_A: column\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, 2, ground) to (A, 2, roof)\n\
structure Frame:\n\
\x20   support: FA: footing\n\
\x20   members: C_A\n\
\x20   transfers:\n\
\x20       ca_fa: Pinned() (C_A -> FA)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(FA) <= site.soil.bearing\n";
        let report = elaborate_multi(&[("site.calx", SPLIT_SITE_SRC), ("frame.calx", frame_src)]);
        let payload = &report.frames[0].payload;
        let c_a = payload.members.iter().find(|m| m.id == "C_A").unwrap();
        assert_eq!(
            c_a.length.lo, 3.6,
            "level-only delta: roof(3.6m) - ground(0m)"
        );
        assert_eq!(c_a.orientation, "vertical");
    }

    #[test]
    fn cross_file_horizontal_member_resolves_nonzero_length_each_axis() {
        let frame_src = "member G_col: beam\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, 1, ground) to (B, 1, ground)\n\
member G_row: beam\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, 1, ground) to (A, 2, ground)\n\
structure Frame:\n\
\x20   support: FA: footing\n\
\x20   members: G_col, G_row\n\
\x20   transfers:\n\
\x20       g_fa: Pinned() (G_col -> FA)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(FA) <= site.soil.bearing\n";
        let report = elaborate_multi(&[("site.calx", SPLIT_SITE_SRC), ("frame.calx", frame_src)]);
        let payload = &report.frames[0].payload;
        let g_col = payload.members.iter().find(|m| m.id == "G_col").unwrap();
        assert_eq!(g_col.length.lo, 7.2, "cols axis: B(7.2m) - A(0m)");
        assert_eq!(g_col.orientation, "horizontal");
        let g_row = payload.members.iter().find(|m| m.id == "G_row").unwrap();
        assert_eq!(g_row.length.lo, 6.0, "rows axis: 2(6.0m) - 1(0m)");
        assert_eq!(g_row.orientation, "horizontal");
    }

    /// The monolithic (single-file) regression: `span_length_derives_
    /// from_grid_spacing` above already covers this shape, but this
    /// test pins it explicitly against `elaborate_multi` with a single
    /// source entry, so a future refactor of the multi-file aggregation
    /// path cannot silently regress the single-file case.
    #[test]
    fn single_file_member_length_unchanged_by_aggregation_fix() {
        let report = elaborate_multi(&[("t.calx", FOOTBRIDGE_SRC)]);
        let payload = &report.frames[0].payload;
        let g1 = payload.members.iter().find(|m| m.id == "G1").unwrap();
        assert_eq!(g1.length.lo, 12.0);
        assert_eq!(g1.orientation, "horizontal");
    }

    /// A one-member fixture with a caller-supplied `loads:` block, for
    /// the WO-85/D194 load-vocabulary tests below.
    fn one_beam_src(loads: &str) -> String {
        format!(
            "grid ends: A, B spacing 6.0m\n\
level deck: 0m\n\
member G1: beam\n\
\x20   section: registry(w250x73)\n\
\x20   material: registry(astm_a992)\n\
\x20   from (A, deck) to (B, deck)\n\
structure Bridge:\n\
\x20   support: AB1: footing\n\
\x20   members: G1\n\
\x20   transfers:\n\
\x20       g1_a: Pinned() (G1 -> AB1)\n\
loads:\n\
{loads}\
require Structure:\n\
\x20   bearing: civil.bearing_pressure(AB1) <= site.soil.bearing\n"
        )
    }

    #[test]
    fn line_load_lowers_with_compound_unit_and_line_kind() {
        // WO-85/D194: a direct `kN/m on [member]` row -- previously
        // silently absent from the payload (the WO-73/W4 wall) -- now
        // lowers as `LoadKind::Line` with its compound unit intact.
        let src = one_beam_src("\x20   plat: 3.5kN/m on [G1] by catalog(x)\n");
        let report = elaborate(&src);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.loads.len(), 1, "{:?}", payload.loads);
        let load = &payload.loads[0];
        assert_eq!(load.kind, LoadKind::Line);
        assert_eq!(load.value.unit, "kN/m");
        assert_eq!(load.value.lo, 3.5);
        assert_eq!(load.station, None);
    }

    #[test]
    fn point_load_with_station_lowers() {
        // WO-85/D194: a force-unit row with the `member@<fraction>`
        // station refinement lowers as a stationed point load.
        let src = one_beam_src("\x20   hoist: 2kN on [G1@0.5] by catalog(y)\n");
        let report = elaborate(&src);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.loads.len(), 1, "{:?}", payload.loads);
        let load = &payload.loads[0];
        assert_eq!(load.kind, LoadKind::Point);
        assert_eq!(load.value.unit, "kN");
        assert_eq!(load.station, Some(0.5));
    }

    #[test]
    fn point_load_on_bare_member_target_is_not_lowered() {
        // WO-85/D194: a concentrated load on a bare member target has
        // no location -- the row never enters the payload (E0211 is
        // the source-side diagnostic; guessing a station here would
        // fabricate a demand).
        let src = one_beam_src("\x20   hoist: 2kN on [G1] by catalog(y)\n");
        let report = elaborate(&src);
        assert!(
            report.frames[0].payload.loads.is_empty(),
            "{:?}",
            report.frames[0].payload.loads
        );
    }

    #[test]
    fn point_load_with_out_of_range_station_is_not_lowered() {
        let src = one_beam_src("\x20   hoist: 2kN on [G1@1.5] by catalog(y)\n");
        let report = elaborate(&src);
        assert!(report.frames[0].payload.loads.is_empty());
    }

    #[test]
    fn point_load_on_support_joint_target_lowers_without_station() {
        // A joint/support target IS the location -- no station needed
        // (D194: "the load targets a joint (no station)").
        let src = one_beam_src("\x20   thrust: 2kN on [AB1] by catalog(y)\n");
        let report = elaborate(&src);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.loads.len(), 1, "{:?}", payload.loads);
        assert_eq!(payload.loads[0].kind, LoadKind::Point);
        assert_eq!(payload.loads[0].target, "AB1");
        assert_eq!(payload.loads[0].station, None);
    }

    #[test]
    fn unrecognized_load_unit_is_skipped_not_guessed() {
        // A unit outside the D194 vocabulary (neither pressure, force,
        // force/length, nor force-length) never lowers.
        let src = one_beam_src("\x20   odd: 3kg on [G1] by catalog(z)\n");
        let report = elaborate(&src);
        assert!(report.frames[0].payload.loads.is_empty());
    }

    #[test]
    fn moment_unit_lowers_as_moment_kind_with_station() {
        let src = one_beam_src("\x20   twist: 5kN-m on [G1@0.25] by catalog(m)\n");
        let report = elaborate(&src);
        let payload = &report.frames[0].payload;
        assert_eq!(payload.loads.len(), 1, "{:?}", payload.loads);
        assert_eq!(payload.loads[0].kind, LoadKind::Moment);
        assert_eq!(payload.loads[0].value.unit, "kN-m");
        assert_eq!(payload.loads[0].station, Some(0.25));
    }

    #[test]
    fn embedded_post_depth_is_extracted_onto_the_transfer() {
        // WO-85/D194: `EmbeddedPost(depth=1.4m)` -> `FrameTransfer.depth`.
        let src = "grid ends: A spacing 1.0m\n\
level ground: 0m\n\
level eave: 4.3m\n\
member P1: column\n\
\x20   section: registry(sawn_150x150)\n\
\x20   material: registry(sp_no2_treated)\n\
\x20   from (A, ground) to (A, eave)\n\
structure Barn:\n\
\x20   support: E1: footing\n\
\x20   members: P1\n\
\x20   transfers:\n\
\x20       p1_e1: EmbeddedPost(depth=1.4m) (P1 -> E1)\n\
loads:\n\
\x20   dead: derived\n\
require Structure:\n\
\x20   frost: civil.embedment(P1) >= site.frost_depth\n";
        let report = elaborate(src);
        let payload = &report.frames[0].payload;
        let t = payload.transfers.iter().find(|t| t.id == "p1_e1").unwrap();
        assert_eq!(t.kind, "EmbeddedPost");
        assert_eq!(t.depth.as_ref().unwrap().lo, 1.4);
        assert_eq!(t.depth.as_ref().unwrap().unit, "m");
        assert!(t.tributary.is_none());
    }
}
