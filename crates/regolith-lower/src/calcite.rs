//! Pass 3d (WO-47 deliverable 4): the calcite civil net disciplines.
//!
//! Runs the front-end-decidable circulation and load-path compile
//! checks (calcite/03 sec. 3) over every parsed `.calx` file's typed
//! [`CirculationDecl`]/[`StructureDecl`] AST, riding the SAME AD-23 net
//! core (`regolith_sem::net_core`) the elec/fluid disciplines use --
//! `net_core::CirculationDiscipline` wired to E0204, and
//! `net_core::LoadPathDiscipline` wired to E0208.
//!
//! SCOPE CUT (named at close-out, the WO-31 D3 precedent): E0205
//! (circulation reference reachability), E0206 (egress edge on a
//! required path with zero/undeclared width), E0207 (member support
//! reachability), and the tributary-partition half of E0209 are NOT
//! decidable by this module -- E0205/E0207 need a reachability
//! traversal `net_core` does not yet provide (see
//! `regolith_sem::net_core::LoadPathDiscipline`'s doc comment), E0206
//! needs quantity-value evaluation over declared widths, and the
//! tributary check needs partition arithmetic over declared areas.
//! Only the member end/bearing terminal-ledger HALF of E0209 (a
//! declared member joining no transfer and not `unloaded`) ships here,
//! the direct analog of fluorite's `UNJOINED_TERMINAL` (E0202).
//!
//! Like `fluid.rs`, this is a PURE function of parsed source: no IO, no
//! rendering. A file with no `circulation`/`structure` declaration
//! contributes nothing.

use regolith_diag::codes::{
    MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH, SPACE_NOT_IN_CIRCULATION, STRUCTURE_NO_SUPPORT,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::net_core::{
    first_violation, CirculationDiscipline, LoadPathDiscipline, NetEntry, Terminal,
};
use regolith_syntax::ast::{AstNode, CirculationDecl, File, StructureDecl};

use crate::output::ParsedFile;

/// The diagnostics from the calcite net disciplines over every file.
#[derive(Debug, Clone, Default)]
pub struct CalciteReport {
    /// Diagnostics from the circulation and load-path checks (E02xx
    /// family, calcite's E0204/E0208/E0209 offsets).
    pub diagnostics: Vec<Diagnostic>,
}

/// Run the calcite net disciplines over `files`, in caller (sorted)
/// order.
#[must_use]
pub fn run_calcite_checks(files: &[ParsedFile]) -> CalciteReport {
    let span = tracing::info_span!("lower.calcite");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for circulation in file.circulations() {
            check_circulation(&pf.path, &circulation, &mut diagnostics);
        }
        for structure in file.structures() {
            check_structure(&pf.path, &structure, &mut diagnostics);
        }
    }
    tracing::debug!(
        diagnostics = diagnostics.len(),
        "calcite discipline: circulation/structure checks complete"
    );
    CalciteReport { diagnostics }
}

/// Check one circulation net: E0204, the front-end-decidable slice of
/// calcite/03 sec. 3's terminal ledger -- a circulation net with NO
/// declared `edges:` and no `reference:` cannot join any space to
/// egress at all (the whole-net imposer-free-subnet shape
/// `net_core::CirculationDiscipline` types, mirroring
/// `FluidDiscipline`). Per-SPACE unjoined-terminal detection (which
/// declared `nodes:` entry an opaque `access:` edge id actually
/// connects) needs the WO-32-style connectivity extraction this
/// front-end layer does not have; see the module doc comment's scope
/// cut.
fn check_circulation(
    path: &camino::Utf8Path,
    circulation: &CirculationDecl,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let name = circulation.name().unwrap_or_default();
    let reference_names = field_idents(circulation, "reference");
    let edge_names = field_idents(circulation, "edges");

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
    if let Some(transfers) = structure.transfers() {
        for edge in transfers.edges() {
            if let Some(sense) = edge.sense() {
                joined_members.extend(sense.names());
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
}

/// The identifier tokens of a header field's value, dropping the
/// leading field-name ident (mirrors `fluid.rs`'s `field_idents`; the
/// shared shape is intentional reuse of the same Field/Ident grammar,
/// not a coincidence -- calcite's `nodes:`/`edges:`/`support:`/
/// `members:` fields are ordinary comma-list fields exactly like
/// fluorite's `nodes:`/`reference:`).
fn field_idents<N: HasFields>(decl: &N, field_name: &str) -> Vec<String> {
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
trait HasFields {
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
        let src = "circulation Egress:\n\
                   \x20   reference: exterior\n\
                   \x20   nodes: Lobby, Corridor\n\
                   \x20   edges: main_exit\n";
        assert!(codes(src).is_empty(), "expected clean: {:?}", codes(src));
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
}
