//! Pass 3d (WO-47 deliverable 4, WO-48 slice A): the calcite civil net
//! disciplines.
//!
//! Runs the front-end-decidable circulation and load-path compile
//! checks (calcite/03 sec. 3) over every parsed `.calx` file's typed
//! [`CirculationDecl`]/[`StructureDecl`] AST, riding the SAME AD-23 net
//! core (`regolith_sem::net_core`) the elec/fluid disciplines use --
//! `net_core::CirculationDiscipline` wired to E0204, and
//! `net_core::LoadPathDiscipline` wired to E0208.
//!
//! WO-48 slice A adds the three REACHABILITY/declaration checks the
//! WO-47 close-out named as a scope cut (see the removed comment this
//! replaces, and `regolith_sem::net_core::LoadPathDiscipline`'s doc
//! comment, which still names the cut for the plugin layer -- this
//! module's checks are plain graph walks over the typed AST, not new
//! `NetDiscipline` plugins, since a discipline only counts imposer
//! terminals per net and reachability needs an actual edge walk):
//!
//! - **E0205** (`CIRCULATION_UNREACHABLE`): a circulation net's
//!   declared space cannot reach its `reference:` set (`exterior`)
//!   by walking the net's declared `edges:` (resolved against the
//!   file's top-level `access:` openings, `(a -> b)` sense taken as
//!   the egress direction, plain BFS).
//! - **E0206** (`EGRESS_EDGE_UNDECLARED`): an access opening named in
//!   a circulation's `edges:` (i.e. on a required egress path) whose
//!   constructor declares no `width=` keyword arg (or a non-positive
//!   one), or declares a non-positive `path_length=` when present --
//!   `path_length=` absence alone is NOT flagged here, see the scope
//!   cut below.
//! - **E0207** (`MEMBER_UNSUPPORTED`): a declared member cannot reach
//!   any `support:` node by walking the structure's `transfers:`
//!   edges (the load LEAK: INV-15's ledger-conservation family) --
//!   the same BFS shape as E0205, over the load-path net instead of
//!   the circulation net.
//!
//! SCOPE CUT (still open, named explicitly): the tributary-partition
//! half of E0209 ("declared `tributary=` shares must partition the
//! surface's declared area") needs partition arithmetic over declared
//! areas, which this module does not do -- only the member end/
//! bearing terminal-ledger half of E0209 (a declared member joining no
//! transfer and not `unloaded`) ships, unchanged from WO-47, the
//! direct analog of fluorite's `UNJOINED_TERMINAL` (E0202). E0206's
//! "dead-end" travel-distance/exit-capacity ARITHMETIC (calcite/03
//! sec. 5's `civil.travel_distance`/`civil.dead_end`/`civil.exit_
//! capacity` claim forms) is claim lowering (WO-48 deliverable 2), not
//! a diagnostic -- out of this module's scope.
//!
//! Like `fluid.rs`, this is a PURE function of parsed source: no IO, no
//! rendering. A file with no `circulation`/`structure` declaration
//! contributes nothing.

use std::collections::{HashSet, VecDeque};

use regolith_diag::codes::{
    CIRCULATION_UNREACHABLE, EGRESS_EDGE_UNDECLARED, MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH,
    MEMBER_UNSUPPORTED, POINT_LOAD_NEEDS_STATION, SPACE_NOT_IN_CIRCULATION, STRUCTURE_NO_SUPPORT,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::net_core::{
    first_violation, CirculationDiscipline, LoadPathDiscipline, NetEntry, Terminal,
};
use regolith_syntax::ast::{AccessDecl, AstNode, CirculationDecl, File, StructureDecl};

use crate::flownet_lower::{arg_quantity, collect_args, edge_endpoints};
use crate::output::ParsedFile;

/// The diagnostics from the calcite net disciplines over every file.
#[derive(Debug, Clone, Default)]
// frob:doc docs/modules/regolith-lower.md#calcite
pub struct CalciteReport {
    /// Diagnostics from the circulation and load-path checks (E02xx
    /// family, calcite's E0204/E0208/E0209 offsets).
    pub diagnostics: Vec<Diagnostic>,
}

/// Run the calcite net disciplines over `files`, in caller (sorted)
/// order.
#[must_use]
// frob:doc docs/modules/regolith-lower.md#calcite
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn run_calcite_checks(files: &[ParsedFile]) -> CalciteReport {
    let span = tracing::info_span!("lower.calcite");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        let access_map = build_access_map(&file);
        for circulation in file.circulations() {
            check_circulation(&pf.path, &circulation, &access_map, &mut diagnostics);
        }
        for structure in file.structures() {
            check_structure(&pf.path, &structure, &mut diagnostics);
        }
        check_loads(&pf.path, &file, &mut diagnostics);
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "calcite discipline: circulation/structure checks complete"
    );
    CalciteReport { diagnostics }
}

/// One access opening resolved to its endpoints and constructor args
/// (the pieces E0205/E0206 need): the declared `(a -> b)` sense and the
/// keyword-arg list off the opening's constructor value.
struct AccessEdge {
    from: String,
    to: String,
    args: Vec<crate::flownet_lower::Arg>,
}

/// Every `access:` opening in `file`, keyed by its declared name
/// (`oo1_door: Door(...) (OpenOffice1 -> Corridor1)` -> `"oo1_door"`).
/// A circulation's `edges:` field names into this map to resolve which
/// spaces an egress edge actually joins (the WO-47 close-out's named
/// gap: "per-SPACE unjoined-terminal detection ... needs the WO-32-
/// style connectivity extraction this front-end layer does not have"
/// -- it has it now, read straight off the typed `AccessDecl`/
/// `EdgeStmt` AST, no new grammar).
fn build_access_map(file: &File) -> std::collections::HashMap<String, AccessEdge> {
    let mut map = std::collections::HashMap::new();
    for access in file_accesses(file) {
        for edge in access.openings() {
            let (from, to) = edge_endpoints(&edge);
            let args = edge.value().map(|v| collect_args(&v)).unwrap_or_default();
            map.insert(edge.name(), AccessEdge { from, to, args });
        }
    }
    map
}

/// `File::accesses` (top-level `access:` blocks, calcite/02 sec. 2).
fn file_accesses(file: &File) -> Vec<AccessDecl> {
    file.accesses()
}

/// Breadth-first reachability: every node reachable from `start` by
/// following `edges` (`Vec<(from, to)>`) in their declared direction,
/// including `start` itself. Plain BFS -- the net_core module only
/// counts imposer terminals per net, it does not walk edges, so this
/// lives here rather than growing a new `NetDiscipline` shape (see the
/// module doc comment).
fn reachable_from(start: &str, edges: &[(String, String)]) -> HashSet<String> {
    let mut seen = HashSet::new();
    seen.insert(start.to_string());
    let mut queue = VecDeque::new();
    queue.push_back(start.to_string());
    while let Some(node) = queue.pop_front() {
        for (a, b) in edges {
            if a == &node && seen.insert(b.clone()) {
                queue.push_back(b.clone());
            }
        }
    }
    seen
}

/// Check one circulation net: E0204 (no `edges:`/`reference:` at all,
/// the front-end-decidable slice of calcite/03 sec. 3's terminal
/// ledger, unchanged from WO-47); E0205 (a declared space cannot reach
/// the `reference:` set by walking the net's declared edges); E0206
/// (an edge on that required path with no positive `width=`/
/// `path_length=`).
fn check_circulation(
    path: &camino::Utf8Path,
    circulation: &CirculationDecl,
    access_map: &std::collections::HashMap<String, AccessEdge>,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let name = circulation.name().unwrap_or_default();
    let reference_names = field_idents(circulation, "reference");
    let edge_names = field_idents(circulation, "edges");
    let node_names = field_idents(circulation, "nodes");

    let net = NetEntry {
        name: name.clone(),
        terminals: vec![Terminal {
            component: name.clone(),
            terminal: "net".to_string(),
            imposes: !reference_names.is_empty() || !edge_names.is_empty(),
        }],
    };
    if first_violation(&CirculationDiscipline, &[net]).is_some() {
        tracing::info!(circulation = %name, "E0204: circulation net has no edges or reference");
        let sp = circulation_span(path, circulation);
        diagnostics.push(
            Diagnostic::error(
                SPACE_NOT_IN_CIRCULATION,
                format!(
                    "circulation net `{name}` declares no `edges:` and no `reference:`; no \
                     space can join an egress path with neither (calcite/03 sec. 3, the \
                     circulation discipline)"
                ),
            )
            .with_span(LabeledSpan::new(
                sp,
                "declare a reference or at least one edge",
            )),
        );
        // No usable edges/reference to walk -- E0205/E0206 would be
        // noise on top of E0204, so stop here (fail-fast, the
        // net_core precedent).
        return;
    }

    // Resolve the declared `edges:` names against the file's access
    // map, dropping any name the map does not carry (an unresolved
    // edge name is a different problem -- e.g. a typo -- outside this
    // module's scope; it simply contributes no graph edge).
    //
    // L2 (cycle-28 audit L2): an access opening's `(from -> to)` arrow
    // names its positive egress SENSE (metadata: swing/hardware/flow
    // bookkeeping), not a one-way restriction on physical passage --
    // calcite/02 sec. 2 is explicit that "direction of travel is
    // computed, not asserted" for these openings, exactly as a
    // flownet edge's arrow names positive flow sense while the actual
    // flow direction is solved, not fixed by the declaration. A real
    // door/stair/ramp is walkable both ways for reachability purposes
    // regardless of which endpoint its author wrote first, so E0205
    // reachability walks each opening as an UNDIRECTED edge: push both
    // `(from, to)` and `(to, from)` into the graph. (Contrast the
    // load-path discipline's transfer edges, which stay directed --
    // gravity load only flows one way down a structure.)
    let mut graph_edges: Vec<(String, String)> = Vec::new();
    let mut resolved: Vec<(&str, &AccessEdge)> = Vec::new();
    for edge_name in &edge_names {
        if let Some(access_edge) = access_map.get(edge_name) {
            graph_edges.push((access_edge.from.clone(), access_edge.to.clone()));
            graph_edges.push((access_edge.to.clone(), access_edge.from.clone()));
            resolved.push((edge_name, access_edge));
        }
    }

    let reference_set: HashSet<&String> = reference_names.iter().collect();

    // E0205: every declared space must reach the reference set.
    for node in &node_names {
        let reach = reachable_from(node, &graph_edges);
        if !reference_set.iter().any(|r| reach.contains(r.as_str())) {
            tracing::info!(
                circulation = %name,
                space = %node,
                "E0205: space cannot reach circulation reference"
            );
            let sp = circulation_span(path, circulation);
            diagnostics.push(
                Diagnostic::error(
                    CIRCULATION_UNREACHABLE,
                    format!(
                        "space `{node}` cannot reach circulation `{name}`'s reference set \
                         through its declared `edges:` (calcite/03 sec. 3, the circulation \
                         discipline)"
                    ),
                )
                .with_span(LabeledSpan::new(
                    sp,
                    "no declared edge path reaches the reference",
                )),
            );
        }
    }

    // E0206: every edge on this required egress path needs a positive
    // width. `path_length` is checked too WHEN declared (zero is always
    // wrong), but its absence is not flagged here: the ratified corpus
    // (`bus_shelter`/`pole_barn`) legitimately omits `path_length=` on a
    // single opening straight to `exterior` with no travel-distance/
    // dead-end claim to feed -- undeclared-but-needed path_length is a
    // claim-lowering-time problem (WO-48 deliverable 2: a `civil.
    // travel_distance`/`dead_end` claim over this circulation with no
    // `path_length=` to evaluate is THAT check's job), not a bare
    // structural compile diagnostic here.
    for (edge_name, access_edge) in &resolved {
        let width = arg_quantity(&access_edge.args, "width");
        let path_length = arg_quantity(&access_edge.args, "path_length");
        let width_ok = width.is_some_and(|q| q.hi > 0.0);
        let path_length_ok = path_length.is_none_or(|q| q.hi > 0.0);
        if !width_ok || !path_length_ok {
            tracing::info!(
                circulation = %name,
                edge = %edge_name,
                width_ok,
                path_length_ok,
                "E0206: egress edge missing width or has a non-positive path_length"
            );
            let sp = circulation_span(path, circulation);
            diagnostics.push(
                Diagnostic::error(
                    EGRESS_EDGE_UNDECLARED,
                    format!(
                        "egress edge `{edge_name}` on circulation `{name}`'s required path \
                         has no positive `width=`, or declares a non-positive `path_length=` \
                         (calcite/03 sec. 3, the circulation discipline)"
                    ),
                )
                .with_span(LabeledSpan::new(
                    sp,
                    "declare a positive width (and, if declared, a positive path_length) on \
                     this opening",
                )),
            );
        }
    }
}

/// Check one structure (load-path net): every declared support must be
/// present (E0208, the load-path discipline's imposer-count analog)
/// and every declared member must be joined by a transfer or be
/// `unloaded` (the terminal-ledger half of E0209).
fn check_structure(
    path: &camino::Utf8Path,
    structure: &StructureDecl,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let name = structure.name().unwrap_or_default();
    let support_names = field_idents(structure, "support");
    let declared_members = field_idents(structure, "members");

    let mut joined_members: Vec<String> = Vec::new();
    let mut transfer_edges: Vec<(String, String)> = Vec::new();
    if let Some(transfers) = structure.transfers() {
        for edge in transfers.edges() {
            if let Some(sense) = edge.sense() {
                joined_members.extend(sense.names());
            }
            let (a, b) = edge_endpoints(&edge);
            if !a.is_empty() || !b.is_empty() {
                transfer_edges.push((a.clone(), b.clone()));
                // Transfers carry a load in either direction along the
                // mating (a member bears on a support, but the support
                // also braces the member back) -- reachability walks
                // both ways, the same undirected-for-egress-purposes
                // choice `check_circulation` takes for a person walking
                // an opening in reverse.
                transfer_edges.push((b, a));
            }
        }
    }

    // E0208: a subnet (this structure) with no support node.
    let net = NetEntry {
        name: name.clone(),
        terminals: support_names
            .iter()
            .map(|s| Terminal {
                component: s.clone(),
                terminal: "support".to_string(),
                imposes: true,
            })
            .collect(),
    };
    if let Some(violation) = first_violation(&LoadPathDiscipline, &[net]) {
        tracing::info!(structure = %name, "E0208: structure has no support");
        let sp = structure_span(path, structure);
        diagnostics.push(
            Diagnostic::error(
                STRUCTURE_NO_SUPPORT,
                format!(
                    "structure `{name}` has no `support:` node; a load-path subnet cannot \
                     discharge its reactions with no support (calcite/03 sec. 3, the \
                     load-path discipline)"
                ),
            )
            .with_span(LabeledSpan::new(sp, "declare at least one support")),
        );
        let _ = violation;
    }

    // E0209 (terminal-ledger half): a declared member joining no
    // transfer edge and not marked `unloaded` elsewhere (the `unloaded`
    // escape is a member-end marker this front-end layer does not yet
    // decode per-end; a member is flagged only when it joins NO
    // transfer edge at all, the unambiguous case).
    for member in &declared_members {
        if !joined_members.iter().any(|j| j == member) {
            tracing::info!(structure = %name, member = %member, "E0209: member unjoined");
            let sp = structure_span(path, structure);
            diagnostics.push(
                Diagnostic::error(
                    MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH,
                    format!(
                        "member `{member}` in structure `{name}` joins no transfer edge and \
                         is not `unloaded`; every member end must join exactly one transfer \
                         or be explicitly `unloaded` (calcite/03 sec. 3)"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "this member joins no transfer")),
            );
        }
    }

    // E0207: every declared member must reach a support node by walking
    // the structure's transfer edges -- a joined member whose transfer
    // chain dead-ends before any `support:` node is a load LEAK (INV-15's
    // ledger-conservation family), distinct from E0209's simpler
    // "joins nothing at all" case above (both may fire together for a
    // fully isolated member -- that is not a bug, they are two separate
    // conditions over the same declaration).
    // Skip when there is no support at all -- E0208 above already
    // covers that (every member would trivially fail to reach a
    // nonexistent support, which is noise on top of E0208, not new
    // information).
    let support_set: HashSet<&String> = support_names.iter().collect();
    if !support_set.is_empty() {
        for member in &declared_members {
            let reach = reachable_from(member, &transfer_edges);
            if !support_set.iter().any(|s| reach.contains(s.as_str())) {
                tracing::info!(
                    structure = %name,
                    member = %member,
                    "E0207: member cannot reach a support"
                );
                let sp = structure_span(path, structure);
                diagnostics.push(
                    Diagnostic::error(
                        MEMBER_UNSUPPORTED,
                        format!(
                            "member `{member}` in structure `{name}` cannot reach a \
                             `support:` node through the declared transfer edges; the load \
                             has no path to a foundation (calcite/03 sec. 3, the load-path \
                             discipline)"
                        ),
                    )
                    .with_span(LabeledSpan::new(sp, "this member's load path dead-ends")),
                );
            }
        }
    }
}

/// The identifier tokens of a header field's value, dropping the
/// leading field-name ident (mirrors `fluid.rs`'s `field_idents`; the
/// shared shape is intentional reuse of the same Field/Ident grammar,
/// not a coincidence -- calcite's `nodes:`/`edges:`/`support:`/
/// `members:` fields are ordinary comma-list fields exactly like
/// fluorite's `nodes:`/`reference:`).
// frob:doc docs/modules/regolith-lower.md#calcite
// frob:waive TEST001 reason="internal pass-pipeline helper exercised transitively through the crate's lower()/lower_and_discharge() pipeline tests; no isolated unit test calls it directly"
pub(crate) fn field_idents<N: HasFields>(decl: &N, field_name: &str) -> Vec<String> {
    let Some(field) = decl.fields().into_iter().find(|f| f.name() == field_name) else {
        return Vec::new();
    };
    let mut idents: Vec<String> = field
        .syntax()
        .descendants_with_tokens()
        .filter_map(rowan::NodeOrToken::into_token)
        .filter(|t| t.kind() == regolith_syntax::syntax_kind::SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    if !idents.is_empty() {
        idents.remove(0);
    }
    idents
}

/// A decl that exposes its header/body `Field`s (calcite's
/// `CirculationDecl`/`StructureDecl` both do; a tiny local trait so
/// `field_idents` stays generic over both without duplicating it).
// frob:doc docs/modules/regolith-lower.md#calcite
pub(crate) trait HasFields {
    fn fields(&self) -> Vec<regolith_syntax::ast::Field>;
}

impl HasFields for CirculationDecl {
    fn fields(&self) -> Vec<regolith_syntax::ast::Field> {
        CirculationDecl::fields(self)
    }
}

impl HasFields for StructureDecl {
    fn fields(&self) -> Vec<regolith_syntax::ast::Field> {
        StructureDecl::fields(self)
    }
}

/// A primary span over a circulation declaration's full text range.
fn circulation_span(path: &camino::Utf8Path, circulation: &CirculationDecl) -> Span {
    let range = circulation.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

/// A primary span over a structure declaration's full text range.
fn structure_span(path: &camino::Utf8Path, structure: &StructureDecl) -> Span {
    let range = structure.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

/// E0211 (WO-85/D194): a concentrated (force/moment-unit) `loads:` row
/// needs a LOCATION -- either a `member@<station>` target refinement
/// (normalized 0..1) or a joint/support target. Three conditions share
/// the one code (the E0209 two-conditions-one-code precedent):
/// a bare declared-member target with no station; a station that does
/// not parse as a number; a station outside `[0, 1]`. The message is
/// CONSTRUCTIVE, naming both valid spellings -- never inferred
/// (`frame_lower::load_entries` skips the row from the payload for the
/// same reason this check flags it: a guessed location fabricates a
/// demand).
fn check_loads(path: &camino::Utf8Path, file: &File, diagnostics: &mut Vec<Diagnostic>) {
    let member_names: HashSet<String> = file
        .members()
        .into_iter()
        .filter_map(|m| m.name())
        .collect();
    for loads_decl in file.loads_blocks() {
        for field in loads_decl
            .syntax()
            .children()
            .filter_map(regolith_syntax::ast::Field::cast)
        {
            let Some(value) = field.value() else {
                continue;
            };
            let Some(magnitude) = crate::frame_lower::load_quantity(&value) else {
                continue;
            };
            let Some(kind) = crate::frame_lower::load_kind_for_unit(&magnitude.unit) else {
                continue;
            };
            if !matches!(
                kind,
                regolith_oblig::LoadKind::Point | regolith_oblig::LoadKind::Moment
            ) {
                continue;
            }
            let full_text = field.syntax().text().to_string();
            let Some(raw_target) = crate::frame_lower::on_target_raw(&full_text) else {
                continue;
            };
            let case = field.name();
            let range = field.syntax().text_range();
            let sp = Span::new(path.to_owned(), range.start().into(), range.end().into());
            let flagged = check_concentrated_target(
                &case,
                &magnitude.unit,
                &raw_target,
                &member_names,
                sp,
                diagnostics,
            );
            if flagged {
                tracing::info!(case = %case, target = %raw_target, "E0211 on load row");
            }
        }
    }
}

/// One concentrated load row's target/station legality
/// ([`check_loads`]'s per-row half; returns whether E0211 fired).
fn check_concentrated_target(
    case: &str,
    unit: &str,
    raw_target: &str,
    member_names: &HashSet<String>,
    sp: Span,
    diagnostics: &mut Vec<Diagnostic>,
) -> bool {
    match raw_target.split_once('@') {
        None => {
            if !member_names.contains(raw_target) {
                return false;
            }
            diagnostics.push(
                Diagnostic::error(
                    POINT_LOAD_NEEDS_STATION,
                    format!(
                        "load `{case}` is a concentrated ({unit}) load on bare member \
                         `{raw_target}` -- its location along the member is ambiguous; \
                         write a station (`{raw_target}@0.5`, normalized 0..1 along the \
                         member axis) or target a joint/support instead (calcite/02 \
                         sec. 7, D194)"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "this load names no station")),
            );
            true
        }
        Some((target, station_text)) => {
            let station_text = station_text.trim();
            match station_text.parse::<f64>() {
                Err(_) => {
                    diagnostics.push(
                        Diagnostic::error(
                            POINT_LOAD_NEEDS_STATION,
                            format!(
                                "load `{case}`'s station `{station_text}` (on `{target}`) \
                                 is not a number; a station is a normalized fraction 0..1 \
                                 along the member axis (e.g. `{target}@0.5`)"
                            ),
                        )
                        .with_span(LabeledSpan::new(sp, "this station does not parse")),
                    );
                    true
                }
                Ok(f) if !(0.0..=1.0).contains(&f) => {
                    diagnostics.push(
                        Diagnostic::error(
                            POINT_LOAD_NEEDS_STATION,
                            format!(
                                "load `{case}`'s station `{station_text}` (on `{target}`) \
                                 is outside the normalized 0..1 range; stations are \
                                 fractions of the member's length (e.g. `{target}@0.5` \
                                 is midspan)"
                            ),
                        )
                        .with_span(LabeledSpan::new(sp, "station out of range")),
                    );
                    true
                }
                Ok(_) => false,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::run_calcite_checks;
    use crate::output::{ParsedFile, SourceFile};
    use crate::parse_sources;

    fn parse_one(text: &str) -> Vec<ParsedFile> {
        parse_sources(&[SourceFile {
            path: camino::Utf8PathBuf::from("t.calx"),
            text: text.to_string(),
        }])
    }

    fn codes(text: &str) -> Vec<String> {
        run_calcite_checks(&parse_one(text))
            .diagnostics
            .iter()
            .map(|d| d.code.to_string())
            .collect()
    }

    #[test]
    fn clean_circulation_passes() {
        let src = "access:\n\
                   \x20   lobby_door: Door(width=915mm, path_length=5m) (Lobby -> Corridor)\n\
                   \x20   main_exit:  Exit(width=1830mm, path_length=8m) (Corridor -> exterior)\n\
                   circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Lobby, Corridor\n\
                   \x20   edges: lobby_door, main_exit\n";
        assert!(codes(src).is_empty(), "expected clean: {:?}", codes(src));
    }

    #[test]
    fn unreachable_space_flags_e0205() {
        let src = "access:\n\
                   \x20   main_exit: Exit(width=1830mm, path_length=8m) (Corridor -> exterior)\n\
                   circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Lobby, Corridor\n\
                   \x20   edges: main_exit\n";
        // Lobby has no declared edge at all -- it cannot reach `exterior`.
        assert!(
            codes(src).contains(&"E0205".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn reverse_authored_opening_still_reaches_reference() {
        // L2 (cycle-28 audit): `main_exit`'s arrow is authored
        // (exterior -> Corridor) -- the REVERSE of the usual egress
        // sense -- but the door is a real, physically bidirectional
        // opening. Reachability must not depend on which endpoint the
        // author wrote first (calcite/02 sec. 2: "direction of travel
        // is computed, not asserted"), so Corridor must still reach
        // `exterior` and E0205 must NOT fire.
        let src = "access:\n\
                   \x20   main_exit: Exit(width=1830mm, path_length=8m) (exterior -> Corridor)\n\
                   circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Corridor\n\
                   \x20   edges: main_exit\n";
        assert!(
            !codes(src).contains(&"E0205".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn undeclared_width_flags_e0206() {
        let src = "access:\n\
                   \x20   main_exit: Exit(path_length=8m) (Corridor -> exterior)\n\
                   circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Corridor\n\
                   \x20   edges: main_exit\n";
        assert!(
            codes(src).contains(&"E0206".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn zero_path_length_flags_e0206() {
        let src = "access:\n\
                   \x20   main_exit: Exit(width=1830mm, path_length=0m) (Corridor -> exterior)\n\
                   circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Corridor\n\
                   \x20   edges: main_exit\n";
        assert!(
            codes(src).contains(&"E0206".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn no_edges_or_reference_flags_e0204() {
        let src = "circulation Egress:\n\
                   \x20   nodes: Lobby, Corridor\n";
        assert!(
            codes(src).contains(&"E0204".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn clean_structure_passes() {
        let src = "structure MainFrame:\n\
                   \x20   support: F1: footing\n\
                   \x20   members: G1, C1\n\
                   \x20   transfers:\n\
                   \x20       c1_f1: BasePlate() (C1 -> F1)\n\
                   \x20       g1_c1: Pinned() (G1 -> C1)\n";
        assert!(codes(src).is_empty(), "expected clean: {:?}", codes(src));
    }

    #[test]
    fn no_support_flags_e0208() {
        let src = "structure MainFrame:\n\
                   \x20   members: G1, C1\n\
                   \x20   transfers:\n\
                   \x20       g1_c1: Pinned() (G1 -> C1)\n";
        assert!(
            codes(src).contains(&"E0208".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn unjoined_member_flags_e0209() {
        let src = "structure MainFrame:\n\
                   \x20   support: F1: footing\n\
                   \x20   members: G1, C1, Stray\n\
                   \x20   transfers:\n\
                   \x20       c1_f1: BasePlate() (C1 -> F1)\n\
                   \x20       g1_c1: Pinned() (G1 -> C1)\n";
        assert!(
            codes(src).contains(&"E0209".to_string()),
            "{:?}",
            codes(src)
        );
    }

    #[test]
    fn dead_end_transfer_chain_flags_e0207() {
        // G1 -> C1 joins something, but C1 never reaches the support --
        // the transfer chain dead-ends before F1, distinct from E0209
        // (every member here IS joined to something).
        let src = "structure MainFrame:\n\
                   \x20   support: F1: footing\n\
                   \x20   members: G1, C1, Stray\n\
                   \x20   transfers:\n\
                   \x20       g1_c1: Pinned() (G1 -> C1)\n\
                   \x20       c1_s:  Pinned() (C1 -> Stray)\n";
        let cs = codes(src);
        assert!(cs.contains(&"E0207".to_string()), "{cs:?}");
        // F1 is declared but never joined by any transfer -- not this
        // member's problem, so E0209 should not fire for G1/C1/Stray
        // (they ARE joined, just not to a support).
        assert!(!cs.contains(&"E0209".to_string()), "{cs:?}");
    }

    #[test]
    fn clean_load_path_reaches_support_no_e0207() {
        let src = "structure MainFrame:\n\
                   \x20   support: F1: footing\n\
                   \x20   members: G1, C1\n\
                   \x20   transfers:\n\
                   \x20       g1_c1: Pinned() (G1 -> C1)\n\
                   \x20       c1_f1: BasePlate() (C1 -> F1)\n";
        assert!(
            !codes(src).contains(&"E0207".to_string()),
            "{:?}",
            codes(src)
        );
    }

    /// A one-member frame with a caller-supplied `loads:` block, for
    /// the WO-85/D194 E0211 checks below.
    fn one_beam_with_loads(loads: &str) -> String {
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
{loads}"
        )
    }

    #[test]
    // frob:tests crates/regolith-lower/src/calcite.rs::run_calcite_checks kind="unit"
    fn point_load_on_bare_member_flags_e0211() {
        let src = one_beam_with_loads("\x20   hoist: 2kN on [G1] by catalog(y)\n");
        assert!(
            codes(&src).contains(&"E0211".to_string()),
            "{:?}",
            codes(&src)
        );
        // The message is constructive: it names the station spelling.
        let report = run_calcite_checks(&parse_one(&src));
        let msg = &report
            .diagnostics
            .iter()
            .find(|d| d.code.to_string() == "E0211")
            .unwrap()
            .message;
        assert!(msg.contains("G1@0.5"), "{msg}");
        assert!(msg.contains("joint"), "{msg}");
    }

    #[test]
    fn point_load_with_bad_station_flags_e0211() {
        for loads in [
            "\x20   hoist: 2kN on [G1@1.5] by catalog(y)\n",
            "\x20   hoist: 2kN on [G1@mid] by catalog(y)\n",
        ] {
            let src = one_beam_with_loads(loads);
            assert!(
                codes(&src).contains(&"E0211".to_string()),
                "{loads}: {:?}",
                codes(&src)
            );
        }
    }

    #[test]
    fn stationed_point_line_and_joint_targeted_loads_are_clean() {
        let src = one_beam_with_loads(
            "\x20   hoist: 2kN on [G1@0.5] by catalog(y)\n\
             \x20   plat: 3.5kN/m on [G1] by catalog(x)\n\
             \x20   thrust: 1kN on [AB1] by catalog(z)\n\
             \x20   snow: 1.4kPa on [G1] by catalog(w)\n",
        );
        assert!(
            !codes(&src).contains(&"E0211".to_string()),
            "{:?}",
            codes(&src)
        );
    }
}
