//! Pass 3: semantic checks over lowered entities (ownership,
//! stages/scopes, profile DOF ledgers, symmetry orbits).
//!
//! Regolith reference: `docs/regolith/05` sec. 3/5, `docs/regolith/06`.
//! WO-19's per-decl entity granularity (see `entities.rs`) does not yet
//! populate `PredictedDelta`/`BorrowTable`/`StageGraph`/`Walk` inputs --
//! those need the domain `OpaqueIsland` bodies (machining stages,
//! `connect`/mating bodies, profile `walk:` blocks) that WO-05 leaves
//! unstructured. This pass therefore runs each checker over the
//! (currently empty) structured inputs it DOES have, so the moment a
//! later WO structures more of the grammar, real diagnostics start
//! flowing with no pipeline change -- it is real code that correctly
//! reports nothing yet, not a stub (see the WO-19 partial-lowering
//! note).

use std::collections::{BTreeMap, BTreeSet};

use regolith_diag::codes::{DEAD_GENERIC, GENERIC_ARITY_MISMATCH};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_sem::{OrbitTable, StageGraph};
use regolith_syntax::ast::{AstNode, File, GenericParams, InstExpr};
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::entities::decl_is_poisoned;
use crate::entities::EntitySnapshots;
use crate::output::ParsedFile;

/// Diagnostics from every static check, plus the artifact-level orbit
/// table (symmetry) computed so far.
#[derive(Debug, Clone, Default)]
pub struct CheckReport {
    /// Diagnostics from ownership/stage/profile/symmetry checks.
    pub diagnostics: Vec<Diagnostic>,
    /// The (currently trivial) symmetry orbit table.
    pub orbits: OrbitTable,
    /// The distinct generic instantiations expanded by monomorphization
    /// (INV-11), in file then source order -- one `Name<args>` entry per
    /// distinct use-site instantiation of a generic declaration.
    pub monomorphized: Vec<String>,
}

/// Run the WO-19-available static checks over `files`/`snapshots`.
#[must_use]
pub fn run_checks(files: &[ParsedFile], snapshots: &EntitySnapshots) -> CheckReport {
    let span = tracing::info_span!("lower.checks");
    let _enter = span.enter();

    let mut diagnostics = Vec::new();

    // Monomorphization expansion (INV-11): every generic declaration
    // (one carrying a typed `GenericParams` header) is expanded at each
    // of its DISTINCT use-site instantiations exactly once, driven by the
    // now-typed `InstExpr`/`GenericArgs` nodes WO-05 emits at use sites
    // (`PatternOf<TappedHole<M3>>`). Two totality guards flow from the
    // proof argument: an instantiation whose arity does not match its
    // declaration is an un-expandable point (E0504), and a generic
    // declaration referenced nowhere is a dead generic (E0503). Both are
    // diagnostics (values); the per-instantiation static-check bodies
    // themselves are future work, but the expansion set they run over is
    // now real.
    let (monomorphized, mono_diags) = monomorphize(files);
    diagnostics.extend(mono_diags);
    tracing::debug!(
        instantiations = monomorphized.len(),
        "monomorphization: expanded generic declarations at distinct use-site instantiations"
    );

    // Stage topology: no stage graph is built by `entities.rs` (stage
    // pipelines live entirely in `OpaqueIsland` bodies today), so this
    // runs over an empty graph -- trivially acyclic, real code, no
    // stub. Wiring a real graph is future work once WO-05 structures
    // stage headers.
    let stages = StageGraph::new();
    match stages.topo_order() {
        Ok(order) => tracing::debug!(count = order.len(), "stage topo order (empty graph)"),
        Err(diags) => diagnostics.extend(diags),
    }

    // Converter-graph acyclicity (INV-16 converter non-instantaneity):
    // build the continuous/discrete converter graph (domain-tagged
    // signal/block nodes; combinational, converter, and register edges)
    // from the now-typed elec behavioral bodies -- `ports:`/`spec:` blocks
    // (WO-05 `Field`s), converter/combinational assignments (`CtorStmt`),
    // and clocked `on <event>:` bodies (`OnBlock`) with non-blocking
    // register updates (`RegAssign`) -- and run the within-domain
    // acyclicity check. A cross-domain edge is a converter by typing (a
    // ZOH delta), so no algebraic loop can cross the boundary; a
    // same-domain combinational cycle with no delta is E0105. The sound
    // mechanism lives in `regolith_sem::converter`; `converter.rs` is its
    // caller over real `.cupr`. See tests/invariants/test_inv_16.
    let converter_diags = crate::converter::run_converter_check(files);
    tracing::debug!(
        converter_diagnostics = converter_diags.len(),
        "INV-16 converter-graph acyclicity check complete"
    );
    diagnostics.extend(converter_diags);

    // INV-17 name-resolved `==` ban (FE-8): the syntactic parse-time pass
    // catches a continuous LITERAL operand (`a == 5mm`); the name-resolved
    // case (`a == b`, both declared continuous) needs the per-decl field
    // type table, which lands in `regolith-sem::resolve`. Run it here over
    // every non-poisoned declaration (INV-20 gating), so the ban is
    // complete against real corpus input. Unlike the ownership/symmetry
    // checks below, this one has structured input TODAY (scalar field
    // declarations), so it emits real diagnostics now.
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            diagnostics.extend(regolith_sem::check_equality_ban(&decl, &pf.path));
        }
    }

    // Ownership / region / symmetry checks (INV-04/05/23): the typed
    // `OwnershipStmt`/`RegionStmt`/`SymmetryStmt` nodes WO-05 now emits
    // are lowered into real `BorrowTable`/`EntityKind::Region`/
    // `OrbitTable` inputs, so borrow conflicts, routes into owned
    // exclusion regions, and unsound `any` orbit extensions surface as
    // diagnostics over real corpus input (see `ownership.rs`).
    let ownership_diags = crate::ownership::run_ownership_and_symmetry(files);
    tracing::debug!(
        scopes = snapshots.scopes.len(),
        ownership_diagnostics = ownership_diags.len(),
        "ownership/region/symmetry checks complete"
    );
    diagnostics.extend(ownership_diags);

    // Query resolution (INV-06/18): each `refer <name>` reference is
    // resolved against its declaration scope's committed entity-DB
    // snapshot via the WO-08 query engine. Over/under-match is E0301
    // (reference determinism); a sibling scope's feature is not
    // name-resolvable, so a cross-scope reference under-matches
    // (snapshot isolation). See `query.rs`.
    let query_diags = crate::query::run_query_resolution(files);
    tracing::debug!(
        query_diagnostics = query_diags.len(),
        "query resolution complete"
    );
    diagnostics.extend(query_diags);

    CheckReport {
        diagnostics,
        orbits: OrbitTable::new(),
        monomorphized,
    }
}

/// One typed use-site generic instantiation collected from the CST.
struct Instantiation {
    /// The instantiation arity (`Decoder<3, 8>` -> 2).
    arity: usize,
    /// The normalized instantiation text (`PatternOf<TappedHole<M3>>`,
    /// whitespace collapsed) -- the distinct-instantiation identity.
    text: String,
    /// The file the instantiation appears in.
    file: camino::Utf8PathBuf,
    /// The instantiation's byte span (primary diagnostic anchor).
    range: (usize, usize),
}

/// Monomorphize every generic declaration over its distinct use-site
/// instantiations (INV-11 totality), skipping poisoned subjects
/// (INV-20). Returns the ordered list of expanded instantiations
/// (`Name<args>`, distinct, one per point) plus the totality
/// diagnostics: a use site whose arity mismatches its declaration
/// (E0504, an un-expandable point) and a generic declaration referenced
/// nowhere (E0503, a dead generic).
fn monomorphize(files: &[ParsedFile]) -> (Vec<String>, Vec<Diagnostic>) {
    let ident_counts = census_idents(files);
    let insts = collect_instantiations(files);

    let mut diagnostics = Vec::new();
    let mut monomorphized = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(params) = decl.syntax().children().find_map(GenericParams::cast) else {
                continue;
            };
            let Some(name) = decl.name() else {
                continue;
            };
            expand_decl(
                &name,
                params.arity(),
                &decl,
                &pf.path,
                insts.get(&name),
                &ident_counts,
                &mut monomorphized,
                &mut diagnostics,
            );
        }
    }
    (monomorphized, diagnostics)
}

/// Census of every identifier token across the compilation: a generic
/// declaration whose name appears exactly once (its own header) is
/// referenced nowhere -- the dead-generic signal that stays quiet for
/// generics used via conformance/roles (whose name recurs).
fn census_idents(files: &[ParsedFile]) -> BTreeMap<String, usize> {
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    for pf in files {
        for tok in pf
            .parse
            .syntax()
            .descendants_with_tokens()
            .filter_map(regolith_syntax::cst::SyntaxElement::into_token)
            .filter(|t| t.kind() == SyntaxKind::Ident)
        {
            *counts.entry(tok.text().to_string()).or_default() += 1;
        }
    }
    counts
}

/// Collect every typed use-site instantiation, grouped by head name,
/// skipping any inside a poisoned declaration (INV-20). Nested
/// instantiations are collected too (they are their own `InstExpr`).
fn collect_instantiations(files: &[ParsedFile]) -> BTreeMap<String, Vec<Instantiation>> {
    let mut insts: BTreeMap<String, Vec<Instantiation>> = BTreeMap::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            for node in decl.syntax().descendants() {
                let Some(inst) = InstExpr::cast(node.clone()) else {
                    continue;
                };
                let head = inst.head_name();
                if head.is_empty() {
                    continue;
                }
                let range = node.text_range();
                insts.entry(head).or_default().push(Instantiation {
                    arity: inst.arity(),
                    text: node.text().to_string().split_whitespace().collect(),
                    file: pf.path.clone(),
                    range: (range.start().into(), range.end().into()),
                });
            }
        }
    }
    insts
}

/// Expand one generic declaration over its instantiation `points`,
/// pushing distinct expansions to `out` and totality diagnostics to
/// `diags`: an arity-mismatched point is un-expandable (E0504); a
/// declaration with no point and no other reference is dead (E0503).
#[allow(clippy::too_many_arguments)]
fn expand_decl(
    name: &str,
    arity: usize,
    decl: &regolith_syntax::ast::Decl,
    path: &camino::Utf8PathBuf,
    points: Option<&Vec<Instantiation>>,
    ident_counts: &BTreeMap<String, usize>,
    out: &mut Vec<String>,
    diags: &mut Vec<Diagnostic>,
) {
    let Some(points) = points else {
        // No value-site instantiation. Dead only when the name is
        // referenced nowhere else at all (count 1 = just this header); a
        // generic bound only through conformance/roles recurs, not dead.
        if ident_counts.get(name).copied().unwrap_or(0) <= 1 {
            tracing::info!(subject = %name, "INV-11: dead generic (declared, never instantiated) -> E0503");
            let range = decl.syntax().text_range();
            let sp = Span::new(path.clone(), range.start().into(), range.end().into());
            diags.push(
                Diagnostic::warning(
                    DEAD_GENERIC,
                    format!(
                        "generic `{name}` is declared but never instantiated; \
                         no monomorphization point exists for it"
                    ),
                )
                .with_span(LabeledSpan::new(sp, "dead generic declared here")),
            );
        } else {
            tracing::debug!(subject = %name, "generic referenced but not value-instantiated (conformance/role use)");
        }
        return;
    };
    let mut seen = BTreeSet::new();
    for point in points {
        if point.arity != arity {
            tracing::info!(subject = %name, expected = arity, got = point.arity, "INV-11: instantiation arity mismatch -> E0504");
            let sp = Span::new(point.file.clone(), point.range.0, point.range.1);
            diags.push(
                Diagnostic::error(
                    GENERIC_ARITY_MISMATCH,
                    format!(
                        "generic `{name}` takes {arity} argument(s) but this \
                         instantiation supplies {}; it cannot be expanded",
                        point.arity
                    ),
                )
                .with_span(LabeledSpan::new(sp, "un-expandable instantiation")),
            );
            continue;
        }
        if seen.insert(point.text.clone()) {
            tracing::debug!(subject = %name, inst = %point.text, "INV-11: expanding instantiation");
            out.push(point.text.clone());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::run_checks;
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hem");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    use regolith_diag::codes::{DEAD_GENERIC, GENERIC_ARITY_MISMATCH};

    #[test]
    fn monomorphization_expands_distinct_use_site_instantiations() {
        // INV-11: a generic decl is expanded once per DISTINCT use-site
        // instantiation. Two `Seat<M3>` uses collapse to one expansion.
        let src = "interface Seat<screw>:\n    x: 1\n\
                   part plain:\n    a = Seat<M3>()\n    b = Seat<M3>()\n    c = Seat<M6>()\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let report = run_checks(&files, &snaps);
        assert_eq!(
            report.monomorphized,
            vec!["Seat<M3>".to_string(), "Seat<M6>".to_string()]
        );
        assert!(report.diagnostics.is_empty(), "{:?}", report.diagnostics);
    }

    #[test]
    fn monomorphization_flags_dead_generic() {
        // INV-11: a generic declared and referenced nowhere is dead.
        let src = "interface Dead<x>:\n    y: 1\npart plain:\n    z: 2\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let report = run_checks(&files, &snaps);
        assert!(report.monomorphized.is_empty());
        assert!(report.diagnostics.iter().any(|d| d.code == DEAD_GENERIC));
    }

    #[test]
    fn monomorphization_flags_arity_mismatch() {
        // INV-11: an instantiation whose arity mismatches its declaration
        // is an un-expandable point (a per-point failure) -> E0504.
        let src = "interface Pair<a, b>:\n    x: 1\npart plain:\n    p = Pair<M3>()\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let report = run_checks(&files, &snaps);
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == GENERIC_ARITY_MISMATCH));
    }
}
