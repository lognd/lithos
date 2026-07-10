//! Pass 4: structured contract IR (interfaces, budgets) + conformance
//! checks.
//!
//! Regolith reference: `docs/spec/regolith/04-contracts.md`. Only the
//! structured surface WO-05 exposes is lowered: an `interface` decl's
//! own name (its `roles:`/`promises:`/`spec:` bodies are nested
//! `OpaqueIsland` blocks, not `Field`s at the decl's own level, so they
//! are recorded as skipped rather than hand-parsed); a decl's
//! structured `budget name: limit` statements become `regolith_ir`
//! `Budget`s and are checked with `close_budget` when the limit is a
//! literal quantity (non-literal limits are not yet resolved at this
//! pass, matching `close_budget`'s own documented behavior). `impl...for`
//! bodies are opaque islands and are skipped (see the WO-19
//! partial-lowering note). `connect:` mating instances ARE lowered
//! (WO-29 deliverable 5): each `name: Ctor(a=.., b=..)` line is a
//! structured `Field`/`CallExpr` (the shared `connect_calls_in_decl`
//! walk, `claim_scope.rs`), resolved against the `mating <Ctor>:`
//! declaration it names for `align`/`dof`/`effects`.

use regolith_diag::Diagnostic;
use regolith_ir::budget::close_budget;
use regolith_ir::nodes::{
    BoundaryEntry, Budget, FlowEdge, Impl, Interface, Mating, Reserve, SystemNode, Target, Workload,
};
use regolith_ir::system::{
    check_boundary_subsumption, check_flow_ledger, check_realization_ledger, check_target_reserves,
};
use regolith_qty::{Literal, Qty, Unit, ValueSource};
use regolith_syntax::ast::{AstNode, Decl, Field, File};
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_util::IndexMap;

use crate::claim_scope::{connect_calls_in_decl, keyword_value};
use crate::entities::{decl_is_poisoned, EntitySnapshots};
use crate::output::ParsedFile;

/// A binding between an upper contract and a lower realization for which
/// INV-13 mandates a conformance obligation: an `impl` role binding, an
/// `impl ... by extern` foreign linkage, or an `import` edge. One
/// `Obligation` is emitted per edge in pass 5 (`claims.rs`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConformanceEdge {
    /// The binding kind: `impl`, `extern`, or `import`.
    pub kind: String,
    /// The upper contract / imported symbol (`interface`, module path).
    pub upper: String,
    /// The lower realization (`for <target>`, extern ref, import path).
    pub lower: String,
    /// The enclosing declaration name (subject for the obligation's
    /// `subject_ref`); empty for a file-level `import`.
    pub subject: String,
}

/// One workload/compute-intent realization edge (cuprite/05 sec. 1
/// rules 2/3; EOPEN-15): either a declared `realizes` claim or a rule-3
/// DERIVED allocation for an intent no declared workload realizes. One
/// demand-implication obligation is emitted per edge (pass 5,
/// `claims.rs`); the derived case additionally tags its obligation
/// `cause: derived(intent <name>)` for the lockfile.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RealizationEdge {
    /// The enclosing system/computer node name (obligation subject).
    pub system: String,
    /// The realizing workload's name (for a derived edge, the intent's
    /// own name -- the synthetic workload is named after its intent).
    pub workload: String,
    /// The compute intent name being realized.
    pub intent: String,
    /// Whether this edge is a rule-3 DERIVED allocation rather than a
    /// declared `realizes` clause.
    pub derived: bool,
}

/// The (partial) contract IR this pass can build from structured
/// syntax, plus its diagnostics and resolutions.
#[derive(Debug, Clone, Default)]
pub struct ContractGraph {
    /// Interfaces named at the top level (bodies mostly opaque today).
    pub interfaces: Vec<Interface>,
    /// Matings -- none are structured yet (`connect` is opaque); always
    /// empty in this WO-19 increment.
    pub matings: Vec<Mating>,
    /// Budgets lowered from structured `budget ...:` statements.
    pub budgets: Vec<Budget>,
    /// System/assembly nodes, populated from each `system`/`assembly`
    /// decl's `boundary:`/`reserves:`/`flows:`/`intents:` blocks and its
    /// attached targets (INV-7/8/15 run over these).
    pub systems: Vec<SystemNode>,
    /// Impls -- `impl...for` bodies are opaque; always empty.
    pub impls: Vec<Impl>,
    /// Conformance/impl/extern/import bindings that require an INV-13
    /// obligation (emitted in pass 5), in file then source order.
    pub conformance: Vec<ConformanceEdge>,
    /// WO-56 deliverable 3 (D161/D168): every `impl ... by select(...)`
    /// header's typed choice point, in file then source order (AD-6) --
    /// `LowerOutput.choice_points`/`BuildPayload.choice_points` mirror
    /// this verbatim (same convention as `flownets`/`frames`), keyed by
    /// `subject_id` there.
    pub choice_points: Vec<regolith_oblig::ChoicePoint>,
    /// Workload/compute-intent realization edges (cuprite/05 sec. 1
    /// rules 2/3), declared and rule-3 DERIVED, in system then source
    /// order.
    pub realization: Vec<RealizationEdge>,
    /// Diagnostics from budget-closure checks.
    pub diagnostics: Vec<Diagnostic>,
    /// Resolutions this pass produced (none yet -- budgets with a
    /// literal limit need no resolution; unresolved limits carry no
    /// value to resolve).
    pub resolutions: Vec<regolith_qty::Resolution>,
}

/// Build the contract IR available from `files`' structured syntax.
#[must_use]
pub fn build_contract_ir(files: &[ParsedFile], _snapshots: &EntitySnapshots) -> ContractGraph {
    let span = tracing::info_span!("lower.contracts");
    let _enter = span.enter();

    let mut out = ContractGraph::default();
    // Build targets separately: a `target X of Sys` is a top-level decl
    // that must be attached to its base system after every system is
    // built (INV-8 reserve accounting sums over ALL targets of a system).
    let mut targets: Vec<Target> = Vec::new();
    // Each system with the type names it references in its `parts:` block;
    // used post-pass to attach child boundaries by name (INV-7).
    let mut systems_with_refs: Vec<(SystemNode, Vec<String>)> = Vec::new();

    // WO-29 deliverable 5: every `mating <Name>:` declaration's
    // align/dof/effects, collected FIRST (a `connect:` instance may
    // reference a mating type declared in any file, not necessarily
    // before its use) so `build_system_node` can resolve each connect
    // instance's type by name.
    let mating_specs = collect_mating_specs(files);

    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };

        // INV-13/INV-22 import edges: every `import` binding gets a
        // conformance obligation (the upper is the imported module/path;
        // the lower realization is the pinned source it resolves to).
        for import in file.imports() {
            let path = header_path_text(import.syntax());
            if !path.is_empty() {
                out.conformance.push(ConformanceEdge {
                    kind: "import".to_string(),
                    upper: path.clone(),
                    lower: path,
                    subject: String::new(),
                });
            }
        }

        for decl in file.decls() {
            // Per-subject INV-20 gating: a poisoned subject contributes
            // no contract IR (parity with entities.rs).
            if decl_is_poisoned(&decl) {
                continue;
            }

            // A top-level `impl <Iface> for <target>` / `impl <Iface> by
            // extern(...)` declaration, plus any in-body `impl` block
            // (`ImplStmt`), each yield an INV-13 conformance/extern edge.
            if decl.kind_keyword() == Some(SyntaxKind::ImplKw) {
                let top_subject = decl.name().unwrap_or_default();
                collect_impl_edge(decl.syntax(), &top_subject, &mut out);
            }
            let decl_name = decl.name().unwrap_or_default();
            for node in decl.syntax().descendants() {
                if node.kind() == SyntaxKind::ImplStmt {
                    collect_impl_edge(&node, &decl_name, &mut out);
                }
            }

            if decl.kind_keyword() == Some(SyntaxKind::InterfaceKw) {
                if let Some(name) = decl.name() {
                    out.interfaces.push(Interface {
                        name,
                        roles: Vec::new(),
                        role_kinds: Vec::new(),
                        demands: Vec::new(),
                        promises: Vec::new(),
                        params: Vec::new(),
                        spec_island: None,
                    });
                }
            }

            // `system`/`assembly` decls become populated SystemNodes
            // (boundary/reserves/flows/targets), the L2 surface INV-7/8/15
            // check against. `target ... of <Sys>` decls are collected for
            // post-pass attachment.
            match decl.kind_keyword() {
                Some(SyntaxKind::SystemKw | SyntaxKind::AssemblyKw) => {
                    if let Some(node) = build_system_node(&decl, &mating_specs) {
                        let refs = part_type_refs(decl.syntax());
                        systems_with_refs.push((node, refs));
                    }
                }
                Some(SyntaxKind::TargetKw) => {
                    if let Some(t) = build_target(&decl) {
                        targets.push(t);
                    }
                }
                _ => {}
            }

            for stmt in decl.budgets() {
                let name = stmt.name();
                let limit = stmt
                    .value()
                    .and_then(|v| literal_qty_from_text(&v.text().to_string()))
                    .map_or(ValueSource::Free, |q| {
                        ValueSource::Literal(Literal::Value(q))
                    });
                let budget = Budget {
                    name: name.clone(),
                    limit,
                    reserve: None,
                };
                // No contributions are structured yet (they live in
                // opaque bodies); an empty ledger trivially closes, but
                // the call is real -- the moment contributions land,
                // `close_budget` starts reporting E0432 with no
                // pipeline change.
                if let Err(diags) = close_budget(&budget, &[]) {
                    out.diagnostics.extend(diags);
                }
                out.budgets.push(budget);
            }
        }
    }

    finalize_systems(&mut out, systems_with_refs, &targets);

    tracing::debug!(
        interfaces = out.interfaces.len(),
        budgets = out.budgets.len(),
        systems = out.systems.len(),
        targets = targets.len(),
        conformance = out.conformance.len(),
        choice_points = out.choice_points.len(),
        "contract IR built"
    );

    out
}

/// Finalize every built system: attach child boundaries (linked by
/// `parts:` type reference to another system's proven boundary, INV-7)
/// and its targets (INV-8), run the three L2 system checks, and push each
/// finished node plus its diagnostics into `out`.
fn finalize_systems(
    out: &mut ContractGraph,
    systems_with_refs: Vec<(SystemNode, Vec<String>)>,
    targets: &[Target],
) {
    // A name -> boundary map over every system, so a system referencing
    // another by type name in its `parts:` block can pick up that
    // artifact's proven boundary (INV-7 child subsumption).
    let boundary_of: regolith_util::IndexMap<String, Vec<BoundaryEntry>> = systems_with_refs
        .iter()
        .map(|(s, _)| (s.name.clone(), s.boundary.clone()))
        .collect();

    for (mut system, refs) in systems_with_refs {
        for r in refs {
            if let Some(child) = boundary_of.get(&r) {
                if !child.is_empty() {
                    system.child_boundaries.push((r, child.clone()));
                }
            }
        }
        system.target_nodes = targets
            .iter()
            .filter(|t| t.of_system == system.name)
            .cloned()
            .collect();
        out.diagnostics.extend(check_boundary_subsumption(&system));
        out.diagnostics.extend(check_target_reserves(&system));
        out.diagnostics.extend(check_flow_ledger(&system));
        out.diagnostics.extend(check_realization_ledger(&system));
        out.realization.extend(allocate_realization(&mut system));
        out.systems.push(system);
    }
}

/// EOPEN-15 rules 2/3 over one finalized system: one [`RealizationEdge`]
/// per declared `realizes` claim (rule 2, exactly-one realizers), and a
/// rule-3 DERIVED workload -- plus its own edge -- allocated for every
/// compute intent NO declared workload realizes. A double-realized
/// intent (rule 1 violation, already diagnosed by
/// `check_realization_ledger`) contributes no edge here: demand
/// implication over an ambiguous realizer set is not this pass's call to
/// make. Derived workloads are appended to `system.workloads` in place,
/// so downstream consumers (lockfile/orchestrator) see them exactly
/// like a declared one, distinguished only by `Workload::derived`.
fn allocate_realization(system: &mut SystemNode) -> Vec<RealizationEdge> {
    let mut edges = Vec::new();
    let mut derived = Vec::new();
    for intent in &system.compute_intents {
        let realizers: Vec<&str> = system
            .workloads
            .iter()
            .filter(|w| !w.derived && w.realizes.iter().any(|r| r == intent))
            .map(|w| w.name.as_str())
            .collect();
        match realizers.len() {
            1 => edges.push(RealizationEdge {
                system: system.name.clone(),
                workload: realizers[0].to_string(),
                intent: intent.clone(),
                derived: false,
            }),
            0 => {
                tracing::info!(
                    system = %system.name,
                    intent = %intent,
                    "compute intent has no declared realizer; allocating a derived workload (EOPEN-15 rule 3)"
                );
                derived.push(Workload {
                    name: intent.clone(),
                    kind: "derived".to_string(),
                    realizes: vec![intent.clone()],
                    derived: true,
                });
                edges.push(RealizationEdge {
                    system: system.name.clone(),
                    workload: intent.clone(),
                    intent: intent.clone(),
                    derived: true,
                });
            }
            _ => {}
        }
    }
    system.workloads.extend(derived);
    edges
}

/// Build a populated [`SystemNode`] from a `system`/`assembly` [`Decl`]:
/// its own `boundary:`/`reserves:`/`flows:`/`intents:` blocks.
/// `child_boundaries` and `target_nodes` are attached by the caller once
/// every system is built (INV-7 links children by parts reference; INV-8
/// sums over all of a system's targets).
fn build_system_node(
    decl: &Decl,
    mating_specs: &IndexMap<String, MatingSpec>,
) -> Option<SystemNode> {
    let name = decl.name()?;
    let boundary = boundary_entries(decl.syntax());
    let reserves = reserve_entries(decl.syntax());
    let flows = flow_edges(decl.syntax());
    // Flow participants: every name DECLARED anywhere in the system body
    // (a `name:` line -- intents, boundary, reserves, and their nested
    // fields). Over-collecting declared names is the sound direction for
    // INV-15: it never manufactures a false leak, it only narrows what the
    // ledger will flag to endpoints the source declares NOWHERE. Intents
    // often parse as opaque islands (rich value grammar), so a structural
    // Field walk misses them -- a text scan of `name:` lines does not.
    let flow_endpoints: Vec<String> = declared_names(decl.syntax());
    let workloads = workload_entries(decl.syntax());
    let compute_intents = compute_intent_names(decl.syntax());
    // WO-29 deliverable 5: real `connect:` mating instances, resolved
    // against the mating-type declarations collected across all files.
    let matings = connect_matings(decl, mating_specs);

    tracing::debug!(
        system = %name,
        boundary = boundary.len(),
        reserves = reserves.len(),
        flows = flows.len(),
        workloads = workloads.len(),
        compute_intents = compute_intents.len(),
        matings = matings.len(),
        "system node built from CST"
    );

    Some(SystemNode {
        name,
        is_system: decl.kind_keyword() == Some(SyntaxKind::SystemKw),
        parts: Vec::new(),
        boundary_datums: Vec::new(),
        connects: Vec::new(),
        matings,
        budgets: Vec::new(),
        targets: Vec::new(),
        config_vars: Vec::new(),
        boundary,
        child_boundaries: Vec::new(),
        reserves,
        flows,
        flow_endpoints,
        target_nodes: Vec::new(),
        workloads,
        compute_intents,
    })
}

/// One `mating <Name>:` declaration's structured surface (WO-29
/// deliverable 5): `align`/`dof`/`couples`/`effects` field text, read
/// once per mating type and shared by every `connect:` instance that
/// names it.
#[derive(Debug, Clone, Default)]
struct MatingSpec {
    /// The `align:` field's raw value text (e.g. `at(1.0, 2.0)` or
    /// `a.frame = b.frame (contact)`).
    align: Option<String>,
    /// The `dof: removed=[...]` list entries.
    dof_removed: Vec<String>,
    /// The `dof: kept=[...]` list entries.
    dof_kept: Vec<String>,
    /// `couples:` field raw value text lines, in source order.
    couples: Vec<String>,
    /// `effects:` field body lines (comments stripped, blank lines
    /// dropped), in source order -- `solve_pass.rs::mating_loads` reads
    /// any `load(fx=.., ...)`-shaped entry from this list.
    effects: Vec<String>,
}

/// Collect every `mating <Name>:` declaration's [`MatingSpec`] across
/// every file, keyed by declaration name (a `connect:` instance's ctor
/// head). A poisoned mating declaration contributes no spec (parity
/// with every other pass's INV-20 gating).
fn collect_mating_specs(files: &[ParsedFile]) -> IndexMap<String, MatingSpec> {
    let mut out = IndexMap::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl.kind_keyword() != Some(SyntaxKind::MatingKw) {
                continue;
            }
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            out.insert(name, mating_spec_from_decl(&decl));
        }
    }
    out
}

/// Build one [`MatingSpec`] from a `mating <Name>:` declaration's direct
/// fields.
fn mating_spec_from_decl(decl: &Decl) -> MatingSpec {
    let mut spec = MatingSpec::default();
    for field in decl.fields() {
        let rhs = field_rhs_text(&field);
        match field.name().as_str() {
            "align" => spec.align = Some(rhs),
            "dof" => {
                spec.dof_removed = bracket_list(&rhs, "removed");
                spec.dof_kept = bracket_list(&rhs, "kept");
            }
            "couples" => spec.couples.push(rhs),
            "effects" => spec.effects = block_field_lines(&field),
            _ => {}
        }
    }
    spec
}

/// The comma-separated entries of a `key=[...]` list found in `text`
/// (e.g. `dof`'s `removed=[fx, fy, mz]`); empty when `key=[` is absent.
fn bracket_list(text: &str, key: &str) -> Vec<String> {
    let marker = format!("{key}=[");
    let Some(start) = text.find(&marker) else {
        return Vec::new();
    };
    let rest = &text[start + marker.len()..];
    let Some(end) = rest.find(']') else {
        return Vec::new();
    };
    rest[..end]
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

/// A block-shaped field's (`effects:`) body lines: the header line is
/// dropped, each remaining line has its trailing `#` comment stripped
/// and is trimmed, and blank lines are dropped.
fn block_field_lines(field: &Field) -> Vec<String> {
    field
        .syntax()
        .text()
        .to_string()
        .lines()
        .skip(1)
        .map(|line| line.split('#').next().unwrap_or("").trim().to_string())
        .filter(|line| !line.is_empty())
        .collect()
}

/// The real `Mating` values a `connect:` block's instance lines
/// construct (WO-29 deliverable 5): each `name: Ctor(a=.., b=..)` line
/// (`connect_calls_in_decl`, `claim_scope.rs`) becomes one `Mating`
/// named after its binding, with sides read from the `a=`/`b=` keyword
/// arguments and align/dof/couples/effects resolved against the
/// `mating <Ctor>:` declaration `mating_specs` names. An unrecognized
/// mating type (no matching spec) still yields a `Mating` with empty
/// align/dof/effects -- a real sides-only connection, not dropped
/// silently, but one the statics feed (`solve_pass.rs`) will not treat
/// as a support (no `dof_removed` entries to react). A `pairwise(...)
/// by <Mating>` orbit-zip connection is NOT promoted here (D91 scope:
/// exactly the `a=`/`b=` two-sided form) and is skipped with a log.
fn connect_matings(decl: &Decl, mating_specs: &IndexMap<String, MatingSpec>) -> Vec<Mating> {
    let mut out = Vec::new();
    for call in connect_calls_in_decl(decl) {
        if call.head == "pairwise" {
            tracing::debug!(
                binding = %call.binding,
                "pairwise connect orbit not promoted (D91 scope); skipped"
            );
            continue;
        }
        let sides: Vec<String> = ["a", "b"]
            .iter()
            .filter_map(|k| keyword_value(&call.args_text, k))
            .collect();
        let spec = mating_specs.get(&call.head);
        if spec.is_none() {
            tracing::debug!(
                binding = %call.binding,
                mating_type = %call.head,
                "connect instance names a mating type with no `mating <Name>:` declaration in this build"
            );
        }
        out.push(Mating {
            name: call.binding,
            sides,
            align: spec.and_then(|s| s.align.clone()),
            dof_removed: spec.map(|s| s.dof_removed.clone()).unwrap_or_default(),
            dof_kept: spec.map(|s| s.dof_kept.clone()).unwrap_or_default(),
            couples: spec.map(|s| s.couples.clone()).unwrap_or_default(),
            // Preload's value-source grammar is not resolved here (out
            // of D5's scope note: the statics feed does not consume
            // preload); a future consumer needing it resolves via the
            // same `ValueSource` machinery `entities.rs` already uses.
            preload: None,
            effects: spec.map(|s| s.effects.clone()).unwrap_or_default(),
        });
    }
    out
}

/// The declared [`Workload`]s of a decl's typed `workloads:` block
/// (cuprite/05 sec. 1): one per [`WorkloadStmt`], with its kind word and
/// any trailing `realizes <intent>...` clause. `derived` is always
/// `false` here -- rule-3 allocation happens post-pass, once every
/// system's compute intents and declared workloads are known
/// (`finalize_systems`).
fn workload_entries(decl: &SyntaxNode) -> Vec<Workload> {
    let Some(block) = decl
        .children()
        .find_map(regolith_syntax::ast::WorkloadsBlock::cast)
    else {
        return Vec::new();
    };
    block
        .workloads()
        .into_iter()
        .map(|w| Workload {
            name: w.name(),
            kind: w.kind_word().unwrap_or_default(),
            realizes: w.realizes().map(|r| r.intents()).unwrap_or_default(),
            derived: false,
        })
        .collect()
}

/// The compute intent names a decl's `intents:` block declares: the
/// entries whose value opens with the `compute(` verb (cuprite/05 sec.
/// 1 rules 1/3 scope to compute intents specifically; other intent
/// verbs -- `sense`/`actuate`/`communicate`/`store` -- may still be named
/// in a workload's `realizes` clause for traceability, but only compute
/// intents are subject to the exactly-one-realization ledger and rule-3
/// derivation). The `intents:` body is a rich, mostly-opaque value
/// grammar (WO-05), so this is a text-level scan like `declared_names`
/// and `flow_edges`, matching the module's existing idiom.
fn compute_intent_names(decl: &SyntaxNode) -> Vec<String> {
    let Some(block) = decl
        .children()
        .filter_map(Field::cast)
        .find(|f| f.name() == "intents")
    else {
        return Vec::new();
    };
    block
        .syntax()
        .text()
        .to_string()
        .lines()
        .filter_map(|line| {
            let line = line.split('#').next().unwrap_or("");
            let (head, rest) = line.split_once(':')?;
            let name = head.trim();
            if name.is_empty()
                || !name
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
            {
                return None;
            }
            rest.trim_start()
                .starts_with("compute(")
                .then(|| name.to_string())
        })
        .collect()
}

/// The type names a system references in its `parts:` block: each entry's
/// right-hand side (`imu: Imu` -> `Imu`, `imu of Imu` -> `Imu`). These
/// name the child artifacts whose proven boundary the enclosing system
/// must be subsumed by (INV-7).
fn part_type_refs(decl: &SyntaxNode) -> Vec<String> {
    let Some(block) = decl.children().find(|c| c.kind() == SyntaxKind::PartsBlock) else {
        return Vec::new();
    };
    block
        .children()
        .filter_map(Field::cast)
        .filter_map(|f| {
            // The type is the last whitespace-separated word of the RHS
            // (handles both `imu: Imu` and `imu of Imu`).
            field_rhs_text(&f)
                .split_whitespace()
                .last()
                .map(str::to_string)
        })
        .collect()
}

/// Build a [`Target`] from a `target <name> of <Sys>` [`Decl`]: the base
/// system (the `Ident` after the bare `of` word) and the numeric draws in
/// its `draws:` block (`reserve: amount` sub-entries). A nominal
/// `draws: reserves` carries no quantified draw.
fn build_target(decl: &Decl) -> Option<Target> {
    let name = decl.name()?;
    // `of <Sys>`: the Ident after the `of` word in the header.
    let of_system = header_word_after(decl.syntax(), "of").unwrap_or_default();
    let draws: Vec<Reserve> = decl
        .syntax()
        .children()
        .filter_map(Field::cast)
        .find(|f| f.name() == "draws")
        .map(|block| {
            block
                .syntax()
                .children()
                .filter_map(Field::cast)
                .map(|f| {
                    let raw = field_rhs_text(&f);
                    Reserve {
                        name: f.name(),
                        amount: parse_amount(&raw),
                        raw,
                    }
                })
                .collect()
        })
        .unwrap_or_default();
    tracing::debug!(target = %name, of = %of_system, draws = draws.len(), "target built from CST");
    Some(Target {
        name,
        of_system,
        draws,
    })
}

/// The `Ident` token immediately following a bare header word (`of`),
/// used to read `target X of <Sys>`.
fn header_word_after(node: &SyntaxNode, word: &str) -> Option<String> {
    let mut idents: Vec<String> = Vec::new();
    for child in node.children_with_tokens() {
        let Some(t) = child.as_token() else { continue };
        if matches!(t.kind(), SyntaxKind::Newline | SyntaxKind::Indent) {
            break;
        }
        if t.kind() == SyntaxKind::Ident {
            idents.push(t.text().to_string());
        }
    }
    idents
        .iter()
        .position(|w| w == word)
        .and_then(|p| idents.get(p + 1).cloned())
}

/// The `BoundaryEntry`s of a decl's `boundary:` block, or empty when it
/// declares none.
fn boundary_entries(decl: &SyntaxNode) -> Vec<BoundaryEntry> {
    let Some(block) = decl
        .children()
        .find(|c| c.kind() == SyntaxKind::BoundaryBlock)
    else {
        return Vec::new();
    };
    block
        .children()
        .filter_map(Field::cast)
        .map(|f| {
            let raw = field_rhs_text(&f);
            let (lo, hi, unit) = parse_bounds(&raw);
            BoundaryEntry {
                name: f.name(),
                lo,
                hi,
                unit,
                raw,
            }
        })
        .collect()
}

/// The `Reserve`s of a decl's `reserves:` field block, or empty.
fn reserve_entries(decl: &SyntaxNode) -> Vec<Reserve> {
    decl.children()
        .filter_map(Field::cast)
        .find(|f| f.name() == "reserves")
        .map(|block| {
            block
                .syntax()
                .children()
                .filter_map(Field::cast)
                .map(|f| {
                    let raw = field_rhs_text(&f);
                    Reserve {
                        name: f.name(),
                        amount: parse_amount(&raw),
                        raw,
                    }
                })
                .collect()
        })
        .unwrap_or_default()
}

/// The `FlowEdge`s of a decl's `flows:` block. The arrow lines parse as
/// opaque islands (WO-05 defers the `a -> b` grammar), so this reads the
/// block's text back and splits each `->` line into its two endpoints.
fn flow_edges(decl: &SyntaxNode) -> Vec<FlowEdge> {
    let Some(block) = decl.children().find(|c| c.kind() == SyntaxKind::FlowsBlock) else {
        return Vec::new();
    };
    block
        .text()
        .to_string()
        .lines()
        .filter_map(|line| {
            let line = line.split('#').next().unwrap_or("").trim();
            let (from, to) = line.split_once("->")?;
            let (from, to) = (from.trim(), to.trim());
            if from.is_empty() || to.is_empty() {
                return None;
            }
            Some(FlowEdge {
                from: from.to_string(),
                to: to.to_string(),
            })
        })
        .collect()
}

/// Every name DECLARED in a system body: the leading identifier of every
/// `name:` line in the decl's source text (intents, boundary, reserves,
/// and their nested fields). This is a deliberately broad, text-level
/// scan because intents frequently parse as opaque islands -- a
/// structural Field walk misses them. Used as the INV-15 flow-ledger
/// participant set: over-collecting declared names never manufactures a
/// false leak (the sound direction), it only limits the ledger to
/// flagging endpoints the source declares nowhere.
fn declared_names(decl: &SyntaxNode) -> Vec<String> {
    decl.text()
        .to_string()
        .lines()
        .filter_map(|line| {
            let line = line.split('#').next().unwrap_or("");
            let (head, _) = line.split_once(':')?;
            let name = head.trim();
            // A bare `identifier` (optionally dotted) before the colon --
            // not an expression, arrow, or bracketed value.
            if !name.is_empty()
                && name
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.')
            {
                Some(name.to_string())
            } else {
                None
            }
        })
        .collect()
}

/// The raw text of a field's value: everything after the first `:` in
/// the field's own text (trimmed). Bare scalar values (`gpio: 4`) are not
/// wrapped in a value node, so `Field::value` returns `None` for them;
/// this reads the source text directly, which works for both scalar and
/// interval right-hand sides.
fn field_rhs_text(field: &Field) -> String {
    let text = field.syntax().text().to_string();
    text.split_once(':')
        .map(|(_, rhs)| rhs.trim().to_string())
        .unwrap_or_default()
}

/// Parse a `[lo, hi]` interval's leading numeric bounds and shared unit.
/// Returns `(lo, hi, unit)` only when both endpoints parse to a number in
/// the SAME unit spelling; otherwise the bounds are `None` (INV-7 leaves
/// an incomparable envelope indeterminate rather than guessing).
fn parse_bounds(text: &str) -> (Option<f64>, Option<f64>, Option<String>) {
    let inner = text.trim().trim_start_matches('[').trim_end_matches(']');
    let Some((a, b)) = inner.split_once(',') else {
        return (None, None, None);
    };
    let (lo, lu) = split_number_unit(a.trim());
    let (hi, hu) = split_number_unit(b.trim());
    if lu != hu {
        return (None, None, None);
    }
    (lo, hi, lu)
}

/// Parse a leading magnitude off a `reserves:`/`draws:` entry text
/// (`4`, `50mW avg`), ignoring any trailing unit/qualifier words.
fn parse_amount(text: &str) -> Option<f64> {
    split_number_unit(text.trim()).0
}

/// Split a leading `<number><unit?>` token into `(number, unit)`. The
/// number is the leading `[-.0-9]` run; the unit is the following
/// alphabetic run (empty -> `None`).
fn split_number_unit(text: &str) -> (Option<f64>, Option<String>) {
    let number_part: String = text
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+')
        .collect();
    let number = number_part.parse::<f64>().ok();
    let unit: String = text[number_part.len()..]
        .chars()
        .take_while(char::is_ascii_alphabetic)
        .collect();
    (number, (!unit.is_empty()).then_some(unit))
}

/// The tokens of a node's header LINE (everything before the body
/// `Indent`/`Newline`), as `(kind, text)` pairs, skipping only the
/// generic-parameter node (which is part of the header). Body statement
/// nodes end the header. Shared by the impl/import edge extractors so
/// they read structure, not a raw text scan.
fn header_tokens(node: &SyntaxNode) -> Vec<(SyntaxKind, String)> {
    let mut out = Vec::new();
    for child in node.children_with_tokens() {
        if let Some(t) = child.as_token() {
            match t.kind() {
                SyntaxKind::Newline | SyntaxKind::Indent | SyntaxKind::Dedent => break,
                SyntaxKind::Whitespace => {}
                k => out.push((k, t.text().to_string())),
            }
        } else if let Some(n) = child.as_node() {
            // The generic-parameter list is part of the header; any other
            // child node is a body statement, so the header is over.
            if n.kind() != SyntaxKind::GenericParams {
                break;
            }
        }
    }
    out
}

/// Join a statement's leading path tokens (`Ident`/`Dot`/`String`) into
/// one reference string (an `import` path, dotted or quoted).
fn header_path_text(node: &SyntaxNode) -> String {
    header_tokens(node)
        .into_iter()
        .skip_while(|(k, _)| *k == SyntaxKind::ImportKw)
        .take_while(|(k, _)| matches!(k, SyntaxKind::Ident | SyntaxKind::Dot | SyntaxKind::String))
        .map(|(_, t)| t.trim_matches('"').to_string())
        .collect::<String>()
}

/// One `impl` header's conformance edge AND (WO-56 D161/D168) its
/// `select` choice point, both pushed onto `out` -- factored out of
/// `build_contract_ir`'s decl loop to keep that function under the
/// line-count lint (the established `drain_frame_payloads`-style
/// pattern this crate already uses elsewhere).
fn collect_impl_edge(node: &SyntaxNode, subject: &str, out: &mut ContractGraph) {
    if let Some(edge) = impl_edge(node, subject) {
        out.conformance.push(edge);
    }
    if let Some(cp) = select_choice_point(node, subject) {
        out.choice_points.push(cp);
    }
}

/// The ordered, duplicate-preserving candidate `Ident` list inside a
/// header's `select(...)` parens, or `None` if the header has no
/// `select` keyword or the parens are malformed (mirrors
/// `regolith_syntax::checks::check_select_candidates`'s own token-scan
/// shape, over the already-collected header tokens rather than a fresh
/// walk -- this crate's L1 checks sibling already rejected an empty or
/// duplicate list at the syntax tier, so this function stays a plain
/// extractor and does not re-diagnose).
fn select_candidate_idents(toks: &[(SyntaxKind, String)]) -> Option<Vec<String>> {
    let select_pos = toks.iter().position(|(k, _)| *k == SyntaxKind::SelectKw)?;
    let open_pos = toks[select_pos + 1..]
        .iter()
        .position(|(k, _)| *k == SyntaxKind::LParen)
        .map(|i| select_pos + 1 + i)?;
    let close_pos = toks[open_pos + 1..]
        .iter()
        .position(|(k, _)| *k == SyntaxKind::RParen)
        .map(|i| open_pos + 1 + i)?;
    Some(
        toks[open_pos + 1..close_pos]
            .iter()
            .filter(|(k, _)| *k == SyntaxKind::Ident)
            .map(|(_, t)| t.clone())
            .collect(),
    )
}

/// WO-56 deliverable 3 (D161/D168): project an `impl <Iface> by
/// select(...)` header into the typed [`regolith_oblig::ChoicePoint`]
/// the D96 channel carries. `subject_id` is `"<subject>.<interface>"`
/// (the enclosing declaration plus the interface being chosen for --
/// distinct choice points in the same subject choosing different
/// interfaces never collide). Candidates are recorded in declared
/// order verbatim (AD-6); a duplicate/empty list has already been
/// rejected structurally by the L1 check (E0107/E0446), so this
/// function never re-diagnoses -- it just returns `None` when no
/// `select` header is present.
fn select_choice_point(node: &SyntaxNode, subject: &str) -> Option<regolith_oblig::ChoicePoint> {
    let toks = header_tokens(node);
    let mut iter = toks.iter().skip_while(|(k, _)| *k != SyntaxKind::ImplKw);
    iter.next();
    let interface = iter
        .clone()
        .find(|(k, _)| *k == SyntaxKind::Ident)
        .map(|(_, t)| t.clone())?;
    let candidates = select_candidate_idents(&toks)?;
    Some(regolith_oblig::ChoicePoint {
        subject_id: format!("{subject}.{interface}"),
        candidate_refs: candidates,
        policy_context: String::new(),
    })
}

/// Extract the INV-13 conformance edge from an `impl` header (top-level
/// `Decl` or in-body `ImplStmt`): the interface is the first `Ident`
/// after the `impl` keyword; a `by extern("ref", ...)` marks an
/// `extern` linkage (lower = the quoted ref); a `for <target>` marks an
/// ordinary `impl` binding (lower = the target). Returns `None` if no
/// interface name is present.
pub(crate) fn impl_edge(node: &SyntaxNode, subject: &str) -> Option<ConformanceEdge> {
    let toks = header_tokens(node);
    // First Ident after the `impl` keyword is the interface.
    let mut iter = toks.iter().skip_while(|(k, _)| *k != SyntaxKind::ImplKw);
    iter.next(); // the `impl` keyword itself
    let interface = iter
        .clone()
        .find(|(k, _)| *k == SyntaxKind::Ident)
        .map(|(_, t)| t.clone())?;

    // `by extern("ref", ...)`: the first String after `extern` is the
    // foreign reference.
    if let Some(pos) = toks.iter().position(|(k, _)| *k == SyntaxKind::ExternKw) {
        let reference = toks[pos + 1..]
            .iter()
            .find(|(k, _)| *k == SyntaxKind::String)
            .map_or_else(
                || "extern".to_string(),
                |(_, t)| t.trim_matches('"').to_string(),
            );
        return Some(ConformanceEdge {
            kind: "extern".to_string(),
            upper: interface,
            lower: reference,
            subject: subject.to_string(),
        });
    }

    // `by select(<ref>, <ref>, ...)` (WO-56, D161, D168): a conformance
    // edge is still recorded (kind `"select"`, INV-13 parity with
    // `extern`/`impl`) with an honest human-readable `lower` label --
    // the REAL candidate-list representation downstream consumers read
    // is the typed `ChoicePoint` this same header also produces
    // (`select_choice_point`, folded into `ContractGraph.choice_points`
    // by the caller), never this string.
    if let Some(candidates) = select_candidate_idents(&toks) {
        return Some(ConformanceEdge {
            kind: "select".to_string(),
            upper: interface,
            lower: format!("select({} candidates)", candidates.len()),
            subject: subject.to_string(),
        });
    }

    // `for <target>`: the Ident after the bare `for` word.
    let target = toks
        .iter()
        .position(|(k, t)| *k == SyntaxKind::Ident && t == "for")
        .and_then(|pos| {
            toks[pos + 1..]
                .iter()
                .find(|(k, _)| *k == SyntaxKind::Ident)
                .map(|(_, t)| t.clone())
        })
        .unwrap_or_default();
    Some(ConformanceEdge {
        kind: "impl".to_string(),
        upper: interface,
        lower: target,
        subject: subject.to_string(),
    })
}

/// WO-69 (regolith/08 sec. 4's L6 row): the fields a `plan: extern(<ref>,
/// <dialect>) machine=<ref>, tooling=<ref>, resolution=<qty>` clause
/// carries. `machine`/`tooling` mirror the existing `process=<head>(args)`
/// key=value spelling (`claim_scope.rs`'s convention) rather than
/// inventing a new argument shape; `resolution` is the declared voxel
/// error term `cam.removal` needs (33-cam-verification.md sec. 1's D3
/// conservatism -- the caller states the tier it pays for). The target
/// RealizedGeometry digest is NOT a field here: it is the enclosing
/// subject's own realized geometry, resolved the same way a fluid edge's
/// `from=` ref is (`flownet_lower::RealizedFlownetInputs::geometry`),
/// keyed on the subject name rather than a second declared reference.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct PlanClause {
    /// The extern ref (the first quoted string in `extern(...)`), or
    /// empty when the clause supplied none (E0449).
    pub plan_ref: String,
    /// The dialect identifier (the first bare ident in `extern(...)`),
    /// unvalidated against the known `fmt.gcode_*` set here (the caller
    /// checks membership and emits E0449 for an unknown name).
    pub dialect: Option<String>,
    /// The declared `machine=<dotted-ref>` record reference, if any.
    pub machine_ref: Option<String>,
    /// The declared `tooling=<dotted-ref>` record reference, if any.
    pub tooling_ref: Option<String>,
    /// The declared `resolution=<qty>` text (e.g. `"0.05mm"`), if any --
    /// carried as raw text; the orchestrator resolves the unit the same
    /// way every other quantity literal reaches it (`given.loads`).
    pub resolution_text: Option<String>,
}

/// The registered `fmt.gcode_*` dialect names (regolith/11 sec. formats
/// row) a `plan:` clause may declare. ONE list, here, so the negative
/// diagnostic and the obligation emitter agree on membership.
pub(crate) const KNOWN_PLAN_DIALECTS: [&str; 2] = ["gcode_fanuc", "gcode_marlin"];

/// Every non-trivia token inside `field`'s VALUE (descending into the
/// `OpaqueIsland` an unrecognized field value parses into), stopping at
/// the field's own `Newline`/`Indent`/`Dedent`. Unlike `header_tokens`
/// (siblings-only, built for decl/impl headers whose extern tokens sit
/// inline), a `Field`'s `extern(...)` value is one level deeper -- this
/// walks the whole subtree instead.
fn field_value_tokens(field: &SyntaxNode) -> Vec<(SyntaxKind, String)> {
    let mut out = Vec::new();
    for elem in field.descendants_with_tokens() {
        if let Some(t) = elem.as_token() {
            match t.kind() {
                SyntaxKind::Newline | SyntaxKind::Indent | SyntaxKind::Dedent => break,
                SyntaxKind::Whitespace => {}
                k => out.push((k, t.text().to_string())),
            }
        }
    }
    out
}

/// A trailing `<key>=<dotted.path>` argument's value, scanning `toks`
/// for a plain `Ident` token equal to `key` immediately followed by `=`
/// (mirrors `claim_scope.rs`'s `process=<head>(args)` convention, WO-69's
/// chosen spelling). `None` when `key` is absent or has no `=` after it.
fn trailing_kwarg(toks: &[(SyntaxKind, String)], key: &str) -> Option<String> {
    let pos = toks
        .iter()
        .position(|(k, t)| *k == SyntaxKind::Ident && t == key)?;
    let after = &toks[pos + 1..];
    if after.first().map(|(k, _)| *k) != Some(SyntaxKind::Eq) {
        return None;
    }
    let value: String = after[1..]
        .iter()
        .take_while(|(k, _)| matches!(k, SyntaxKind::Ident | SyntaxKind::Dot))
        .map(|(_, t)| t.clone())
        .collect();
    (!value.is_empty()).then_some(value)
}

/// A trailing `resolution=<qty>` argument's raw text (`Number` token
/// plus an immediately-following unit `Ident`, if any).
fn trailing_resolution(toks: &[(SyntaxKind, String)]) -> Option<String> {
    let pos = toks
        .iter()
        .position(|(k, t)| *k == SyntaxKind::Ident && t == "resolution")?;
    let after = &toks[pos + 1..];
    if after.first().map(|(k, _)| *k) != Some(SyntaxKind::Eq) {
        return None;
    }
    let mut out = String::new();
    for (k, t) in &after[1..] {
        match k {
            SyntaxKind::Number => out.push_str(t),
            SyntaxKind::Ident if !out.is_empty() => {
                out.push_str(t);
                break;
            }
            _ => break,
        }
    }
    (!out.is_empty()).then_some(out)
}

/// Extract a `plan:` field's [`PlanClause`], or `None` if `field` is not
/// named `plan` or carries no `extern(...)` call at all (a `plan:` field
/// with no `extern(` is not this WO's concern -- regolith/08 sec. 4 only
/// defines the extern-linkage form for L6).
pub(crate) fn plan_clause(field: &Field) -> Option<PlanClause> {
    if field.name() != "plan" {
        return None;
    }
    let toks = field_value_tokens(field.syntax());
    let extern_pos = toks.iter().position(|(k, _)| *k == SyntaxKind::ExternKw)?;
    let after_extern = &toks[extern_pos + 1..];
    let open = after_extern
        .iter()
        .position(|(k, _)| *k == SyntaxKind::LParen)?;
    let close = after_extern[open + 1..]
        .iter()
        .position(|(k, _)| *k == SyntaxKind::RParen)
        .map(|i| open + 1 + i)?;
    let inner = &after_extern[open + 1..close];
    let plan_ref = inner
        .iter()
        .find(|(k, _)| *k == SyntaxKind::String)
        .map_or_else(String::new, |(_, t)| t.trim_matches('"').to_string());
    let dialect = inner
        .iter()
        .find(|(k, _)| *k == SyntaxKind::Ident)
        .map(|(_, t)| t.clone());
    let trailing = &after_extern[close + 1..];
    Some(PlanClause {
        plan_ref,
        dialect,
        machine_ref: trailing_kwarg(trailing, "machine"),
        tooling_ref: trailing_kwarg(trailing, "tooling"),
        resolution_text: trailing_resolution(trailing),
    })
}

/// Parse a very small subset of quantity-literal text (`"4 mm"`,
/// `"100 g"`) into a dimensionless-unit `Qty`. A real unit lookup table
/// (mapping unit spellings to `regolith_qty::Unit`s) is WO-05/WO-12
/// territory already recorded as deferred (unit-checking cut, cycle
/// 11 notes); this is a documented placeholder that recognizes a bare
/// leading number and otherwise reports no literal.
fn literal_qty_from_text(text: &str) -> Option<Qty> {
    let trimmed = text.trim();
    let number_part: String = trimmed
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();
    let magnitude: f64 = number_part.parse().ok()?;
    Some(Qty::new(magnitude, Unit::dimensionless()))
}

/// WO-61 deliverable 2: project a [`ContractGraph`] into the readable
/// L2 [`regolith_oblig::ContractGraphPayload`] surface (interaction-
/// surface/29 sec. 1.6): one node per declared `interface` (named,
/// with its promise-slot count) plus one node per distinct
/// artifact/part name any system names (in its `parts:` or a mating's
/// `sides`), and one edge per mating (named, labeled with its declared
/// effects joined by `+`, or the honest `"mating"` fallback when none
/// are declared -- never a fabricated label).
///
/// Runs in the same `lower.contracts` pass span (AD-17: one span per
/// pass) immediately after `build_contract_ir`, over data that pass
/// already assembled -- no second read path into compiler internals
/// (AD-22).
#[must_use]
pub fn build_contract_graph_payload(graph: &ContractGraph) -> regolith_oblig::ContractGraphPayload {
    use regolith_oblig::{ContractEdge, ContractGraphPayload, ContractNode};
    use std::collections::BTreeSet;

    let mut interface_names: BTreeSet<&str> = BTreeSet::new();
    let mut nodes: Vec<ContractNode> = Vec::new();
    for iface in &graph.interfaces {
        if interface_names.insert(iface.name.as_str()) {
            nodes.push(ContractNode {
                name: iface.name.clone(),
                kind: "interface".to_string(),
                promise_slots: u32::try_from(iface.promises.len()).unwrap_or(u32::MAX),
            });
        }
    }

    let mut artifact_names: BTreeSet<String> = BTreeSet::new();
    let mut edges: Vec<ContractEdge> = Vec::new();
    for system in &graph.systems {
        for part in &system.parts {
            if !interface_names.contains(part.as_str()) {
                artifact_names.insert(part.clone());
            }
        }
        for mating in &system.matings {
            let a = mating.sides.first().cloned().unwrap_or_default();
            let b = mating.sides.get(1).cloned().unwrap_or_else(|| a.clone());
            for side in [&a, &b] {
                if !side.is_empty() && !interface_names.contains(side.as_str()) {
                    artifact_names.insert(side.clone());
                }
            }
            let kind = if mating.effects.is_empty() {
                "mating".to_string()
            } else {
                mating.effects.join("+")
            };
            edges.push(ContractEdge {
                name: mating.name.clone(),
                kind,
                a,
                b,
            });
        }
    }
    for name in artifact_names {
        nodes.push(ContractNode {
            name,
            kind: "artifact".to_string(),
            promise_slots: 0,
        });
    }
    // Source order was already stable per-collection; the artifact-name
    // BTreeSet above sorts lexically for determinism (AD-6) since
    // artifacts have no other intrinsic cross-system order.
    edges.sort_by(|a, b| a.name.cmp(&b.name));

    ContractGraphPayload { nodes, edges }
}

#[cfg(test)]
mod tests {
    use super::{build_contract_ir, plan_clause};
    use crate::entities::build_entities;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_syntax::ast::{AstNode, Decl, File};

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    fn first_plan_field(src: &str) -> Option<super::PlanClause> {
        let files = parsed(src);
        let file = File::cast(files[0].parse.syntax())?;
        let decl: Decl = file.decls().into_iter().next()?;
        decl.fields().into_iter().find_map(|f| plan_clause(&f))
    }

    #[test]
    fn plan_clause_extracts_ref_dialect_and_kwargs() {
        let src = "part p:\n    plan: extern(\"op10.nc\", gcode_fanuc) machine=std.machines.haas_vf2, tooling=std.tooling.endmill_6mm, resolution=0.05mm\n";
        let clause = first_plan_field(src).expect("plan clause present");
        assert_eq!(clause.plan_ref, "op10.nc");
        assert_eq!(clause.dialect.as_deref(), Some("gcode_fanuc"));
        assert_eq!(clause.machine_ref.as_deref(), Some("std.machines.haas_vf2"));
        assert_eq!(
            clause.tooling_ref.as_deref(),
            Some("std.tooling.endmill_6mm")
        );
        assert_eq!(clause.resolution_text.as_deref(), Some("0.05mm"));
    }

    #[test]
    fn plan_clause_bare_extern_has_no_kwargs() {
        let src = "part p:\n    plan: extern(\"op10.nc\", gcode_fanuc)\n";
        let clause = first_plan_field(src).expect("plan clause present");
        assert_eq!(clause.plan_ref, "op10.nc");
        assert_eq!(clause.dialect.as_deref(), Some("gcode_fanuc"));
        assert!(clause.machine_ref.is_none());
        assert!(clause.tooling_ref.is_none());
        assert!(clause.resolution_text.is_none());
    }

    #[test]
    fn plan_clause_missing_ref_is_empty_not_a_panic() {
        let src = "part p:\n    plan: extern(gcode_fanuc)\n";
        let clause = first_plan_field(src).expect("plan clause present");
        assert_eq!(clause.plan_ref, "");
        assert_eq!(clause.dialect.as_deref(), Some("gcode_fanuc"));
    }

    #[test]
    fn plan_clause_unknown_dialect_is_extracted_unvalidated() {
        // Membership validation is the caller's job (E0449); the
        // extractor itself never guesses or rejects.
        let src = "part p:\n    plan: extern(\"op10.nc\", not_a_dialect)\n";
        let clause = first_plan_field(src).expect("plan clause present");
        assert_eq!(clause.dialect.as_deref(), Some("not_a_dialect"));
        assert!(!super::KNOWN_PLAN_DIALECTS.contains(&clause.dialect.unwrap().as_str()));
    }

    #[test]
    fn non_plan_field_is_not_a_plan_clause() {
        let src = "part p:\n    material: AISI_304\n";
        assert!(first_plan_field(src).is_none());
    }

    #[test]
    fn import_and_impl_edges_are_collected() {
        let src =
            "import std.mech.cnc (saw_stock)\npart p:\n    impl Seat for self:\n        x: 1\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "import" && e.upper.contains("std")),
            "import edge collected: {:?}",
            graph.conformance
        );
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "impl" && e.upper == "Seat"),
            "impl edge collected: {:?}",
            graph.conformance
        );
    }

    #[test]
    fn extern_linkage_is_an_extern_edge() {
        let src = "impl Mux by extern(\"rtl/mux.v\", verilog2005) as Hand\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "extern" && e.upper == "Mux"),
            "extern edge collected: {:?}",
            graph.conformance
        );
    }

    #[test]
    fn select_header_emits_a_choice_point_and_a_select_conformance_edge() {
        // WO-56 deliverable 3 (D161/D168): a body `by select(...)` (the
        // shape the negative fixtures/checks.rs unit tests use) both
        // records a "select"-kind conformance edge (INV-13 parity) AND
        // a typed `ChoicePoint` carrying the real candidate list.
        let src = "board decoder_board:\n    impl AddressDecodeGlue by select(nor_glue, cpld, mcu_chip_selects)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .conformance
                .iter()
                .any(|e| e.kind == "select" && e.upper == "AddressDecodeGlue"),
            "select conformance edge collected: {:?}",
            graph.conformance
        );
        assert_eq!(graph.choice_points.len(), 1, "{:?}", graph.choice_points);
        let cp = &graph.choice_points[0];
        assert_eq!(cp.subject_id, "decoder_board.AddressDecodeGlue");
        assert_eq!(
            cp.candidate_refs,
            vec![
                "nor_glue".to_string(),
                "cpld".to_string(),
                "mcu_chip_selects".to_string(),
            ]
        );
    }

    #[test]
    fn select_with_one_candidate_is_a_degenerate_choice_point() {
        // Charter sec. 2: "one candidate = a degenerate pin, legal."
        let src = "board decoder_board:\n    impl AddressDecodeGlue by select(nor_glue)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert_eq!(graph.choice_points.len(), 1);
        assert_eq!(
            graph.choice_points[0].candidate_refs,
            vec!["nor_glue".to_string()]
        );
    }

    fn diag_codes(src: &str) -> Vec<regolith_diag::DiagCode> {
        let files = parsed(src);
        let snaps = build_entities(&files);
        build_contract_ir(&files, &snaps)
            .diagnostics
            .iter()
            .map(|d| d.code)
            .collect()
    }

    #[test]
    fn boundary_within_child_is_clean_but_wider_fails() {
        use regolith_diag::codes::BOUNDARY_NOT_SUBSUMED;
        // Enclosing envelope contained in the child's proven one: clean.
        let ok = "system Imu:\n    boundary:\n        ambient: [-40degC, 85degC]\n\nsystem Outer:\n    parts:\n        imu: Imu\n    boundary:\n        ambient: [0degC, 40degC]\n";
        assert!(
            !diag_codes(ok).contains(&BOUNDARY_NOT_SUBSUMED),
            "clean: {:?}",
            diag_codes(ok)
        );
        // Enclosing envelope WIDER than the child's proven one: INV-7 fail.
        let bad = "system Imu:\n    boundary:\n        ambient: [-10degC, 50degC]\n\nsystem Outer:\n    parts:\n        imu: Imu\n    boundary:\n        ambient: [-40degC, 85degC]\n";
        assert!(
            diag_codes(bad).contains(&BOUNDARY_NOT_SUBSUMED),
            "violation: {:?}",
            diag_codes(bad)
        );
    }

    #[test]
    fn reserve_over_allocation_is_caught_but_within_is_clean() {
        use regolith_diag::codes::BUDGET_CANNOT_CLOSE;
        let ok = "system Sys:\n    reserves:\n        gpio: 4\n\ntarget debug of Sys:\n    draws:\n        gpio: 3\n";
        assert!(
            !diag_codes(ok).contains(&BUDGET_CANNOT_CLOSE),
            "clean: {:?}",
            diag_codes(ok)
        );
        let bad = "system Sys:\n    reserves:\n        gpio: 4\n\ntarget debug of Sys:\n    draws:\n        gpio: 5\n";
        assert!(
            diag_codes(bad).contains(&BUDGET_CANNOT_CLOSE),
            "over: {:?}",
            diag_codes(bad)
        );
    }

    #[test]
    fn flow_ledger_catches_an_undeclared_endpoint() {
        use regolith_diag::codes::LEDGER_IMBALANCE;
        let ok = "system Sys:\n    intents:\n        sense: sense(x)\n        decide: compute(y)\n    flows:\n        sense -> decide\n";
        assert!(
            !diag_codes(ok).contains(&LEDGER_IMBALANCE),
            "clean: {:?}",
            diag_codes(ok)
        );
        let bad = "system Sys:\n    intents:\n        sense: sense(x)\n        decide: compute(y)\n    flows:\n        sense -> decide\n        decide -> ghost\n";
        assert!(
            diag_codes(bad).contains(&LEDGER_IMBALANCE),
            "leak: {:?}",
            diag_codes(bad)
        );
    }

    #[test]
    fn single_realization_emits_one_declared_edge_and_no_diagnostic() {
        use regolith_diag::codes::REALIZATION_NOT_EXACTLY_ONE;
        let src = "system Sys:\n    intents:\n        decide: compute(law):\n            rate: 4Hz\n    workloads:\n        att: loop(rate=4Hz) realizes decide\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            !graph
                .diagnostics
                .iter()
                .any(|d| d.code == REALIZATION_NOT_EXACTLY_ONE),
            "clean: {:?}",
            graph.diagnostics
        );
        assert_eq!(graph.realization.len(), 1);
        let edge = &graph.realization[0];
        assert_eq!(edge.workload, "att");
        assert_eq!(edge.intent, "decide");
        assert!(!edge.derived);
        let sys = graph.systems.iter().find(|s| s.name == "Sys").unwrap();
        assert_eq!(sys.compute_intents, vec!["decide".to_string()]);
        assert!(!sys.workloads.iter().any(|w| w.derived));
    }

    #[test]
    fn double_realization_is_flagged_and_emits_no_edge() {
        use regolith_diag::codes::REALIZATION_NOT_EXACTLY_ONE;
        let src = "system Sys:\n    intents:\n        decide: compute(law)\n    workloads:\n        att: loop(rate=4Hz) realizes decide\n        backup: loop(rate=4Hz) realizes decide\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(
            graph
                .diagnostics
                .iter()
                .any(|d| d.code == REALIZATION_NOT_EXACTLY_ONE),
            "violation: {:?}",
            graph.diagnostics
        );
        assert!(
            !graph.realization.iter().any(|e| e.intent == "decide"),
            "an ambiguous realizer set emits no demand-implication edge: {:?}",
            graph.realization
        );
    }

    #[test]
    fn unrealized_intent_derives_a_workload_and_edge() {
        let src = "system Sys:\n    intents:\n        decide: compute(law)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        let sys = graph.systems.iter().find(|s| s.name == "Sys").unwrap();
        let derived = sys
            .workloads
            .iter()
            .find(|w| w.name == "decide")
            .expect("derived workload allocated");
        assert!(derived.derived);
        assert_eq!(derived.realizes, vec!["decide".to_string()]);
        let edge = graph
            .realization
            .iter()
            .find(|e| e.intent == "decide")
            .expect("derived realization edge emitted");
        assert!(edge.derived);
        assert_eq!(edge.workload, "decide");
    }

    #[test]
    fn realizes_naming_a_non_compute_intent_is_out_of_ledger_scope() {
        // Corpus shape (kestrel.cupr): a workload may `realizes` a
        // store/communicate intent for traceability; only compute()
        // intents are subject to the ledger/derivation.
        use regolith_diag::codes::REALIZATION_NOT_EXACTLY_ONE;
        let src = "system Sys:\n    intents:\n        keep: store(images(2GB))\n    workloads:\n        keepw: stream(store, 4MB/s) realizes keep\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        assert!(!graph
            .diagnostics
            .iter()
            .any(|d| d.code == REALIZATION_NOT_EXACTLY_ONE));
        assert!(graph.realization.is_empty());
        let sys = graph.systems.iter().find(|s| s.name == "Sys").unwrap();
        assert!(sys.compute_intents.is_empty());
        assert!(!sys.workloads.iter().any(|w| w.derived));
    }

    #[test]
    fn connect_instance_lowers_to_a_real_mating_with_sides_and_dof() {
        // WO-29 deliverable 5: a `connect:` instance line resolved
        // against its `mating <Name>:` declaration -- sides from the
        // `a=`/`b=` keyword args, align/dof/effects from the type.
        let src = "mating AxisMount:\n    between: a: ShoulderSeat, b: AxisFoot\n    align:   at(1.0, 2.0)\n    dof:     removed=[fx,fy,mz]\n    effects:\n        load(fx=100, fy=-500, x=1.0, y=2.0)\n\nassembly Frame:\n    connect:\n        seat: AxisMount(a=frame.shoulder_l, b=x_p.AxisFoot)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        let sys = graph.systems.iter().find(|s| s.name == "Frame").unwrap();
        assert_eq!(sys.matings.len(), 1, "one connect line -> one Mating");
        let mating = &sys.matings[0];
        assert_eq!(mating.name, "seat");
        assert_eq!(
            mating.sides,
            vec!["frame.shoulder_l".to_string(), "x_p.AxisFoot".to_string()]
        );
        assert_eq!(mating.align.as_deref(), Some("at(1.0, 2.0)"));
        assert_eq!(
            mating.dof_removed,
            vec!["fx".to_string(), "fy".to_string(), "mz".to_string()]
        );
        assert_eq!(
            mating.effects,
            vec!["load(fx=100, fy=-500, x=1.0, y=2.0)".to_string()]
        );
    }

    #[test]
    fn connect_mating_feeds_a_real_statics_reaction_from_source() {
        // The end-to-end acceptance shape: a `connect`-carrying fixture
        // produces `Mating` values AND a computed reaction, entirely
        // from source -- the statics feed (`solve_pass.rs`) was already
        // wired to `system.matings`; this proves the producer side.
        use crate::solve_pass::feed_interface_loads;
        let src = "mating Foot:\n    between: a: Pad, b: Ground\n    align:   at(0.0, 0.0)\n    dof:     removed=[fx,fy,mz]\n    effects:\n        load(fx=100, fy=-1000, mz=5, x=0.0, y=0.0)\n\nassembly Bracket:\n    connect:\n        base: Foot(a=frame.pad, b=ground.mount)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        let sys = graph.systems.iter().find(|s| s.name == "Bracket").unwrap();
        assert_eq!(sys.matings.len(), 1);
        let report = feed_interface_loads(&graph, &[], &mut []);
        // A single support with fy removed and one fy load balances
        // trivially (reaction = -load); the point is that the solve
        // actually RAN against a real, source-derived mating rather
        // than a hand-built fixture.
        assert!(
            report.diagnostics.is_empty(),
            "no determinacy diagnostics expected: {:?}",
            report.diagnostics
        );
    }

    #[test]
    fn contract_graph_payload_names_matings_by_readable_sides() {
        // WO-61 deliverable 2/4: the payload names sides by their
        // readable connect-instance strings (never a hash), and the
        // mating's declared effect joins into the edge's kind label.
        use super::build_contract_graph_payload;
        let src = "mating Foot:\n    between: a: Pad, b: Ground\n    align:   at(0.0, 0.0)\n    dof:     removed=[fx,fy,mz]\n    effects:\n        load(fx=100, fy=-1000, mz=5, x=0.0, y=0.0)\n\nassembly Bracket:\n    connect:\n        base: Foot(a=frame.pad, b=ground.mount)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        let payload = build_contract_graph_payload(&graph);
        assert_eq!(payload.edges.len(), 1);
        let edge = &payload.edges[0];
        assert_eq!(edge.name, "base");
        assert_eq!(edge.a, "frame.pad");
        assert_eq!(edge.b, "ground.mount");
        assert!(edge.kind.contains("load"));
        let names: Vec<&str> = payload.nodes.iter().map(|n| n.name.as_str()).collect();
        assert!(names.contains(&"frame.pad"));
        assert!(names.contains(&"ground.mount"));
    }

    #[test]
    fn contract_graph_payload_is_deterministic_across_two_runs() {
        use super::build_contract_graph_payload;
        let src = "mating Foot:\n    between: a: Pad, b: Ground\n    align:   at(0.0, 0.0)\n    dof:     removed=[fx,fy,mz]\n    effects:\n        load(fx=100, fy=-1000, mz=5, x=0.0, y=0.0)\n\nassembly Bracket:\n    connect:\n        base: Foot(a=frame.pad, b=ground.mount)\n";
        let files = parsed(src);
        let snaps = build_entities(&files);
        let graph = build_contract_ir(&files, &snaps);
        let p1 = build_contract_graph_payload(&graph);
        let p2 = build_contract_graph_payload(&graph);
        assert_eq!(p1, p2);
    }
}
