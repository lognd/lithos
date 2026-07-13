//! Pass `lower.programs` (WO-29 deliverable 3, completed by WO-51):
//! the feature/stage program payload, built from the SAME `then:`
//! claim-scope walk deliverable 2's entity projector reads
//! (`claim_scope::feature_calls_in_decl` -- ONE traversal, two
//! consumers, AD-17/NO DUPLICATION). WO-51 adds, per D150/D151/D152:
//!
//! - the typed sketch payload per referenced profile
//!   (`regolith_ir::sketch::sketch_closure_from_walk` -- promoted or a
//!   NAMED unsupported reason, zero silent gaps);
//! - a NAMED `E0443` warning for every `then:` op with no projection
//!   into the v1 feature-op set (never silent truncation);
//! - `flow_paths` derived from the feature-op chain each
//!   `.cavity(inlet=..., outlet=...)` query touches (D151: per-segment
//!   fields each from a DECLARED source fact, else honestly
//!   indeterminate -- the AD-25 GeomExtract rule verbatim; D152: this
//!   derivation is flow_paths' ONLY source), with `E0444` (unresolved
//!   port) and `E0445` (chain the op set cannot express, hematite/07
//!   sec. 2a's escalation diagnostic) as the misuse surface.
//!
//! WO-77 (charter 34 phase 1, D200) adds the declared material-removal
//! families: `Ribs`/`PocketGrid`/`Shell`/`Lattice` project into
//! ordinary `FeatureOp`s (kinds `ribs`/`pocket_grid`/`shell`/
//! `lattice`) through the ONE family-vocabulary home
//! (`crate::removal`); malformed family params are the constructive
//! `E0451` (the op is omitted, never guessed). `Lattice` LOWERS here
//! like its siblings -- its honest named skip is the REALIZER
//! projection's (`regolith.realizer.mech.coverage`: "lattice: no v1
//! projection"), not an E0443.
//!
//! Runs over hematite files only (the registry decides, AD-14 -- the
//! feature-op set is a mech concept; a `.cupr` converter ctor is not
//! an unsupported MECH op).

use regolith_diag::{codes, Diagnostic};
use regolith_ir::feature_program::{DerivedFact, FlowPathIr, FlowSegmentIr};
use regolith_ir::sketch::sketch_closure_from_walk;
use regolith_ir::{FeatureOp, FeatureProgram, ResolvedFeatureParam};
use regolith_sem::EntityKind;
use regolith_syntax::ast::{AstNode, Decl, File};
use regolith_syntax::extension::{language_for_extension, Language};
use regolith_syntax::walk::{parse_walk, Walk};
use regolith_util::IndexMap;

use crate::claim_scope::{keyword_value, positional_value, FeatureCall};
use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// The `lower.programs` pass output: the per-part programs plus the
/// named projection/cavity diagnostics (values, AD-7).
#[derive(Debug, Clone, Default)]
pub struct ProgramsReport {
    /// One program per declaration whose `then:` scopes construct at
    /// least one feature op (absence is absence, never an empty
    /// placeholder).
    pub programs: Vec<FeatureProgram>,
    /// `E0443` unsupported-op warnings and `E0444`/`E0445` cavity
    /// misuse errors, in file then source order (AD-6).
    pub diagnostics: Vec<Diagnostic>,
}

/// Build the feature program for every hematite declaration across
/// every file, in sorted-file then source-decl order (AD-6), plus the
/// WO-51 projection diagnostics.
#[must_use]
pub fn build_feature_programs(files: &[ParsedFile]) -> ProgramsReport {
    let span = tracing::info_span!("lower.programs");
    let _enter = span.enter();

    let walks = profile_walks(files);
    let mut report = ProgramsReport::default();
    for pf in files {
        if pf
            .path
            .extension()
            .and_then(language_for_extension)
            .is_none_or(|l| l != Language::Hematite)
        {
            continue;
        }
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            build_decl_program(&name, &decl, &walks, &mut report);
        }
    }
    report
}

/// Project one declaration's `then:` ops, referenced-profile sketches,
/// and cavity-derived flow paths into its `FeatureProgram` (plus the
/// named diagnostics); a declaration with no feature calls contributes
/// nothing.
fn build_decl_program(
    part: &str,
    decl: &Decl,
    walks: &IndexMap<String, Walk>,
    report: &mut ProgramsReport,
) {
    let calls = crate::claim_scope::feature_calls_in_decl(decl);
    if calls.is_empty() {
        return;
    }

    let mut features = Vec::new();
    let mut unsupported: Vec<&FeatureCall> = Vec::new();
    for call in &calls {
        // Declared material-removal families (charter 34 phase 1,
        // D200/WO-77): project through the ONE family-vocabulary home;
        // malformed params are the constructive E0451 and the op is
        // omitted (never a guessed value) -- NOT an E0443 (the verb is
        // recognized vocabulary, its spelling is what is wrong).
        if let Some(family) = crate::removal::family_for_constructor(call.effective_constructor()) {
            if let Some(op) = project_family_op(part, family, call, &mut report.diagnostics) {
                features.push(op);
            }
            continue;
        }
        if let Some(op) = project_op(call) {
            if op.kind == "blank" && !op.params.contains_key("thickness") && !stage_is_milled(call)
            {
                tracing::info!(
                    part,
                    binding = %call.binding,
                    "blank op has no thickness value source (E0448, named -- not silent)"
                );
                report.diagnostics.push(Diagnostic::error(
                    codes::SHEET_BLANK_NO_GAUGE_SOURCE,
                    format!(
                        "part `{part}`: `{binding} = {ctor}(...)` is a sheet-metal blank \
                         with no thickness source -- assert `thickness=<qty>` on the op or \
                         give its stage a gauge-bearing process (`process=laser_cut(sheet=\
                         <t>)` or a sibling sheet process)",
                        binding = call.binding,
                        ctor = call.effective_constructor(),
                    ),
                ));
            }
            features.push(op);
            continue;
        }
        tracing::info!(
            part,
            binding = %call.binding,
            constructor = %call.effective_constructor(),
            "op outside the v1 feature-op set (E0443, named -- not silent)"
        );
        report.diagnostics.push(Diagnostic::warning(
            codes::UNSUPPORTED_FEATURE_OP,
            format!(
                "part `{part}`: op `{binding} = {ctor}(...)` has no projection into \
                 the v1 feature-op set; the emitted feature program omits it",
                binding = call.binding,
                ctor = call.effective_constructor(),
            ),
        ));
        unsupported.push(call);
    }

    // Typed sketch payload for every profile the ops reference (WO-51
    // d1's promotion; a non-promotable walk is carried as its NAMED
    // unsupported reason -- zero silent gaps).
    let mut sketches = IndexMap::new();
    for call in &calls {
        for word in ident_words(&call.args_text) {
            if let Some(walk) = walks.get(word) {
                if !sketches.contains_key(word) {
                    sketches.insert(word.to_string(), sketch_closure_from_walk(word, walk));
                }
            }
        }
    }

    // Cavity-derived flow paths (D151/D152: the ONLY flow_paths source).
    let flow_paths = derive_flow_paths(part, decl, &calls, &unsupported, &mut report.diagnostics);

    if features.is_empty() && sketches.is_empty() && flow_paths.is_empty() {
        return;
    }
    tracing::debug!(
        part,
        features = features.len(),
        sketches = sketches.len(),
        flow_paths = flow_paths.len(),
        "feature program built from then: claim scopes"
    );
    report.programs.push(FeatureProgram {
        part_name: part.to_string(),
        features,
        sketches,
        flow_paths,
    });
}

/// Every profile declaration's parsed walk across the file set, by
/// profile name (the promotion's input; consumed once per referenced
/// profile).
pub fn profile_walks(files: &[ParsedFile]) -> IndexMap<String, Walk> {
    let mut out = IndexMap::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let Some(name) = decl.name() else { continue };
            let is_profile = decl
                .syntax()
                .text()
                .to_string()
                .trim_start()
                .starts_with("profile ");
            if !is_profile {
                continue;
            }
            if let Some(walk) = parse_walk(decl.syntax()) {
                out.insert(name, walk);
            }
        }
    }
    out
}

/// Project one material-removal family call (D200/WO-77) into its
/// ordinary `FeatureOp` through the ONE family-vocabulary home
/// (`crate::removal`); a malformed call emits the constructive `E0451`
/// naming the family signature and yields `None` (the op is omitted,
/// never guessed).
fn project_family_op(
    part: &str,
    family: &crate::removal::FamilySpec,
    call: &FeatureCall,
    diagnostics: &mut Vec<Diagnostic>,
) -> Option<FeatureOp> {
    match crate::removal::validate_family_params(family, &call.args_text) {
        Ok(params) => {
            tracing::debug!(
                part,
                binding = %call.binding,
                family = family.ctor,
                "material-removal family op projected (WO-77)"
            );
            Some(FeatureOp {
                kind: family.kind_word.to_string(),
                name: call.binding.clone(),
                constructor: family.ctor.to_string(),
                count: u32::try_from(call.count).unwrap_or(u32::MAX),
                params,
                stage: call.stage.clone(),
                process: call.stage_process.clone(),
            })
        }
        Err(problems) => {
            tracing::info!(
                part,
                binding = %call.binding,
                family = family.ctor,
                ?problems,
                "malformed material-removal family params (E0451, named)"
            );
            diagnostics.push(Diagnostic::error(
                codes::REMOVAL_FAMILY_MALFORMED,
                format!(
                    "part `{part}`: `{binding} = {ctor}(...)` is malformed -- {problems}; \
                     the signature is `{signature}` (slots take a literal, `in [lo, hi]`, \
                     or `in {{a, b}}` value); the op is omitted from the feature program",
                    binding = call.binding,
                    ctor = family.ctor,
                    problems = problems.join("; "),
                    signature = family.signature,
                ),
            ));
            None
        }
    }
}

/// Project one feature call into the v1 op set: the WO-29 hole/bend
/// scalar projection plus WO-51's `blank`/`pocket` rows (the profile
/// consumers). `None` means no projection exists (the caller emits the
/// NAMED `E0443`).
fn project_op(call: &FeatureCall) -> Option<FeatureOp> {
    let ctor = call.effective_constructor();
    let kind_word = match EntityKind::from_constructor_word(ctor) {
        Some(EntityKind::Hole) => "hole",
        Some(EntityKind::Bend) => "bend",
        _ => match ctor {
            "Blank" => "blank",
            "Pocket" => "pocket",
            _ => return None,
        },
    };
    Some(FeatureOp {
        kind: kind_word.to_string(),
        name: call.binding.clone(),
        constructor: ctor.to_string(),
        count: u32::try_from(call.count).unwrap_or(u32::MAX),
        params: feature_params(kind_word, call),
        stage: call.stage.clone(),
        process: call.stage_process.clone(),
    })
}

/// W4 fix (post-WO-64 phase B): true when the call's stage names a
/// process whose capability-record roughness class is a solid-removal
/// or solid-forming family (`machined`/`cast`, `PROCESS_ROUGHNESS`
/// below) rather than a sheet family. Charter 30 sec. 1.2 (D171 #2)
/// scopes the sheet-gauge-source rule to SHEET parts; a milled or cast
/// blank (e.g. `process=cnc_mill(...)`) is not sheet stock and carries
/// no gauge to source, so `E0448` must never fire for it. A stage with
/// no declared process, or a declared sheet-family process (e.g.
/// `laser_cut`), stays in scope for the rule -- only a KNOWN non-sheet
/// process opts a blank out.
fn stage_is_milled(call: &FeatureCall) -> bool {
    let Some(process) = call.stage_process.as_deref() else {
        return false;
    };
    matches!(
        PROCESS_ROUGHNESS
            .iter()
            .find_map(|(p, class)| (*p == process).then_some(*class)),
        Some("machined" | "cast")
    )
}

/// WO-62 D171/AD-32: the sheet-gauge thickness value source for a
/// `blank` op -- an explicit `thickness=` arg on the `Blank(...)` call
/// (asserted), else the enclosing stage's `process=<proc>(sheet=<t>)`
/// argument (the gauge source, `cause: process(<proc>.sheet)` per
/// INV-21); `None` when neither supplies a value (the caller emits the
/// NAMED compile diagnostic -- a gauge-less unasserted sheet blank is
/// never silently unthickened).
fn blank_thickness(call: &FeatureCall) -> Option<ResolvedFeatureParam> {
    if let Some(v) = keyword_value(&call.args_text, "thickness") {
        return Some(resolved_param(v));
    }
    let process = call.stage_process.as_deref()?;
    let process_args = call.stage_process_args.as_deref()?;
    let sheet = keyword_value(process_args, "sheet")?;
    Some(ResolvedFeatureParam {
        text: sheet,
        cause: format!("process({process}.sheet)"),
    })
}

/// The well-known scalar params for one feature call, Cause-tagged
/// (INV-21): a param whose spelled text is a recognized value-source
/// keyword (`free`/`derived`/`allocated`, or an `in [..]` planner form)
/// carries that Cause; anything else is `literal` (an ordinary spelled
/// quantity, e.g. `28mm`). Shares the exact measure-key set
/// `entities.rs::feature_measures` uses so the two never disagree on
/// which keys a kind carries.
fn feature_params(kind_word: &str, call: &FeatureCall) -> IndexMap<String, ResolvedFeatureParam> {
    let mut params = IndexMap::new();
    let args = &call.args_text;
    match kind_word {
        "hole" => {
            if let Some(v) = positional_value(args, "dia") {
                params.insert("diameter".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "depth") {
                params.insert("depth".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "edge_distance") {
                params.insert("edge_distance".to_string(), resolved_param(v));
            }
        }
        "bend" => {
            if let Some(v) = keyword_value(args, "angle") {
                params.insert("angle".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "radius") {
                params.insert("radius".to_string(), resolved_param(v));
            }
        }
        "blank" | "pocket" => {
            // `args_text` is the full RHS (`Blank(Flat)`): the profile
            // ref is the first ident that is not the constructor head.
            if let Some(profile) = ident_words(args)
                .find(|w| *w != call.head && Some(*w) != call.pattern_inner.as_deref())
            {
                params.insert(
                    "profile".to_string(),
                    ResolvedFeatureParam {
                        text: profile.to_string(),
                        cause: "literal".to_string(),
                    },
                );
            }
            if let Some(v) = keyword_value(args, "depth") {
                params.insert("depth".to_string(), resolved_param(v));
            }
            if kind_word == "blank" {
                if let Some(thickness) = blank_thickness(call) {
                    params.insert("thickness".to_string(), thickness);
                }
            }
        }
        _ => {}
    }
    params
}

/// Wrap one spelled param value with its INV-21 Cause, decided
/// structurally from the value-source keyword vocabulary
/// (regolith/03 sec. 2): `free`/`derived`/`allocated` verbatim, an
/// `in [...]` interval as `planner`, anything else `literal`.
fn resolved_param(text: String) -> ResolvedFeatureParam {
    let cause = match text.as_str() {
        "free" => "free",
        "derived" => "derived",
        "allocated" => "allocated",
        _ if text.starts_with('[') => "planner",
        _ => "literal",
    };
    ResolvedFeatureParam {
        text,
        cause: cause.to_string(),
    }
}

/// Derive the wetted flow paths for every `.cavity(inlet=...)` query
/// the declaration spells (D151's op-graph walk): the source-order
/// feature-op chain from the inlet-face op to the outlet-face op, one
/// [`FlowSegmentIr`] per op, fields per [`DerivedFact`]. Misuse is
/// `E0444` (port resolves to no op binding) / `E0445` (chain contains
/// an op the v1 set cannot express).
fn derive_flow_paths(
    part: &str,
    decl: &Decl,
    calls: &[FeatureCall],
    unsupported: &[&FeatureCall],
    diagnostics: &mut Vec<Diagnostic>,
) -> Vec<FlowPathIr> {
    let text = decl.syntax().text().to_string();
    let mut out = Vec::new();
    for query in cavity_queries(&text) {
        let Some(inlet_idx) = position_of(calls, &query.inlet) else {
            push_port_unresolved(part, &query.inlet, calls, diagnostics);
            continue;
        };
        let outlet_idx = if let Some(outlet) = &query.outlet {
            if let Some(i) = position_of(calls, outlet) {
                i
            } else {
                push_port_unresolved(part, outlet, calls, diagnostics);
                continue;
            }
        } else {
            inlet_idx
        };
        let (lo, hi) = (inlet_idx.min(outlet_idx), inlet_idx.max(outlet_idx));
        let chain = &calls[lo..=hi];

        if let Some(bad) = chain
            .iter()
            .find(|c| unsupported.iter().any(|u| u.binding == c.binding))
        {
            tracing::info!(
                part,
                op = %bad.binding,
                "cavity chain contains an inexpressible op (E0445, hematite/07 sec. 2a)"
            );
            diagnostics.push(Diagnostic::error(
                codes::CAVITY_CHAIN_INEXPRESSIBLE,
                format!(
                    "part `{part}`: the cavity chain from `{}` to `{}` passes through \
                     `{bad_binding} = {bad_ctor}(...)`, which the v1 feature-op set cannot \
                     express -- no wetted path can be derived (hematite/07 sec. 2a)",
                    query.inlet,
                    query.outlet.as_deref().unwrap_or(&query.inlet),
                    bad_binding = bad.binding,
                    bad_ctor = bad.effective_constructor(),
                ),
            ));
            continue;
        }

        let selector = match &chain[0].stage {
            Some(stage) => format!("{stage}.wetted"),
            None => format!("{part}.wetted"),
        };
        let segments = chain.iter().map(flow_segment).collect();
        tracing::info!(
            part,
            selector = %selector,
            ops = chain.len(),
            "cavity query derived a wetted flow path (D151/D152)"
        );
        let path = FlowPathIr {
            selector,
            inlet: query.inlet_spelled,
            outlet: query.outlet_spelled.unwrap_or_default(),
            segments,
        };
        // Two queries over the same ports (volume + min_section)
        // derive one path, not two copies.
        if !out.contains(&path) {
            out.push(path);
        }
    }
    out
}

/// One feature op's projection into a wetted-path segment: every field
/// from a DECLARED source fact, else honestly indeterminate (D151, the
/// AD-25 GeomExtract rule verbatim -- never a plausible substitute).
fn flow_segment(call: &FeatureCall) -> FlowSegmentIr {
    let ctor = call.effective_constructor();
    let role = match EntityKind::from_constructor_word(ctor) {
        Some(EntityKind::Hole) => "bore".to_string(),
        _ => ctor.to_ascii_lowercase(),
    };
    let diameter = positional_value(&call.args_text, "dia");
    let depth = keyword_value(&call.args_text, "depth");
    FlowSegmentIr {
        role,
        bore: Some(call.binding.clone()),
        flow_area: match &diameter {
            Some(d) => DerivedFact::Declared {
                value: d.clone(),
                source: format!(
                    "{binding} dia {d} (the op's minimum section; the consumer derives \
                     area from the declared diameter)",
                    binding = call.binding,
                ),
            },
            None => DerivedFact::Indeterminate {
                reason: format!(
                    "op `{}` declares no diameter, so no minimum section is declared",
                    call.binding
                ),
            },
        },
        length: match &depth {
            Some(d) => DerivedFact::Declared {
                value: d.clone(),
                source: format!("{binding} depth={d}", binding = call.binding),
            },
            None => DerivedFact::Indeterminate {
                reason: format!("op `{}` declares no depth", call.binding),
            },
        },
        // D151 verbatim: 0 with cited provenance when no datum orients
        // gravity -- the scalar IR carries no gravity-orienting datum.
        elevation_change: DerivedFact::Declared {
            value: "0".to_string(),
            source: "part datum: none orients gravity (D151)".to_string(),
        },
        roughness_class: roughness_class(call),
        wall: DerivedFact::Indeterminate {
            reason: "the op carries no wall-thickness derivation".to_string(),
        },
    }
}

/// The process-capability roughness classes (fluorite/03 sec. 1: "a
/// laser-cut channel and a drawn tube differ" -- roughness comes from
/// the PROCESS record): the D151 "roughness_class from the
/// material/finish record the op cites" derivation. Every class here
/// must be a key of the extract seam's `ROUGHNESS_TABLE` (one
/// vocabulary; a unit test cross-checks). An unmapped process is
/// honestly indeterminate -- never guessed.
const PROCESS_ROUGHNESS: &[(&str, &str)] = &[
    ("cnc_mill", "machined"),
    ("cnc_lathe", "machined"),
    ("laser_cut", "laser_cut"),
    ("injection_mold", "cast"),
    ("casting", "cast"),
];

/// The op's roughness class from its owning stage's process record
/// (a declared source: the stage header names the process), else
/// honestly indeterminate.
fn roughness_class(call: &FeatureCall) -> DerivedFact {
    let Some(process) = call.stage_process.as_deref() else {
        return DerivedFact::Indeterminate {
            reason: format!(
                "op `{}` sits in no stage with a `process=` record, so no roughness                  class is declared",
                call.binding
            ),
        };
    };
    match PROCESS_ROUGHNESS
        .iter()
        .find_map(|(p, class)| (*p == process).then_some(*class))
    {
        Some(class) => DerivedFact::Declared {
            value: class.to_string(),
            source: format!(
                "stage `{stage}` process={process} (process capability record,                  fluorite/03 sec. 1)",
                stage = call.stage.as_deref().unwrap_or("?"),
            ),
        },
        None => DerivedFact::Indeterminate {
            reason: format!(
                "process `{process}` maps to no roughness class in the capability record"
            ),
        },
    }
}

/// One parsed `.cavity(...)` query: the inlet/outlet port refs as
/// spelled (`bore.inlet`) and their feature-binding heads (`bore`).
struct CavityQuery {
    inlet: String,
    inlet_spelled: String,
    outlet: Option<String>,
    outlet_spelled: Option<String>,
}

/// Scan declaration text for `.cavity(inlet=..., outlet=...)` call
/// sites (hematite/02 sec. 6's spelling; D152 rules this the
/// implemented surface). A query without an `inlet=` argument is not a
/// cavity query this pass resolves (the spec form requires the inlet).
fn cavity_queries(text: &str) -> Vec<CavityQuery> {
    let mut out = Vec::new();
    for (i, _) in text.match_indices(".cavity(") {
        let args_start = i + ".cavity(".len();
        let Some(rel_end) = text[args_start..].find(')') else {
            continue;
        };
        let args = &text[args_start..args_start + rel_end];
        let Some(inlet_spelled) = keyword_ref(args, "inlet") else {
            continue;
        };
        let outlet_spelled = keyword_ref(args, "outlet");
        out.push(CavityQuery {
            inlet: head_of(&inlet_spelled),
            inlet_spelled: inlet_spelled.clone(),
            outlet: outlet_spelled.as_deref().map(head_of),
            outlet_spelled,
        });
    }
    out
}

/// The `key=<dotted-ref>` argument value in a cavity arg list; `None`
/// when the key is absent.
fn keyword_ref(args: &str, key: &str) -> Option<String> {
    args.split(',').find_map(|part| {
        let (k, v) = part.split_once('=')?;
        (k.trim() == key).then(|| v.trim().to_string())
    })
}

/// The leading feature-binding component of a dotted port ref
/// (`bore.inlet` -> `bore`).
fn head_of(port_ref: &str) -> String {
    port_ref
        .split('.')
        .next()
        .unwrap_or(port_ref)
        .trim()
        .to_string()
}

/// The source-order index of the feature call a port ref's head names.
fn position_of(calls: &[FeatureCall], head: &str) -> Option<usize> {
    calls.iter().position(|c| c.binding == head)
}

/// Emit the constructive `E0444` for a port ref no op binding resolves.
fn push_port_unresolved(
    part: &str,
    head: &str,
    calls: &[FeatureCall],
    diagnostics: &mut Vec<Diagnostic>,
) {
    let bindings: Vec<&str> = calls.iter().map(|c| c.binding.as_str()).collect();
    tracing::info!(part, head, "cavity port resolves to no op binding (E0444)");
    diagnostics.push(Diagnostic::error(
        codes::CAVITY_PORT_UNRESOLVED,
        format!(
            "part `{part}`: `.cavity(...)` names port feature `{head}`, but no `then:` op \
             binds that name; this part's op bindings are: {}",
            if bindings.is_empty() {
                "(none)".to_string()
            } else {
                bindings.join(", ")
            }
        ),
    ));
}

/// The identifier-shaped words of an argument text, in order (profile
/// references are bare idents in constructor args: `Blank(BoomFlat)`,
/// `Turn(profile=LinerBore)`).
fn ident_words(args: &str) -> impl Iterator<Item = &str> {
    args.split(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
        .filter(|w| {
            !w.is_empty()
                && !w.as_bytes()[0].is_ascii_digit()
                && w.chars().any(|c| c.is_ascii_alphabetic())
        })
}

#[cfg(test)]
mod tests {
    use super::build_feature_programs;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;
    use regolith_diag::codes;
    use regolith_ir::feature_program::DerivedFact;
    use regolith_ir::sketch::WalkPromotion;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    #[test]
    fn bore_and_bend_become_cause_tagged_feature_ops() {
        let src = "part p:\n    stage s1:\n        then:\n            pilot = Bore(dia 28mm, depth=12mm)\n    stage s2:\n        then:\n            flange = Bend(edge=cut.top, angle=90deg, radius=free)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1);
        let program = &report.programs[0];
        assert_eq!(program.part_name, "p");
        assert_eq!(program.features.len(), 2);

        let hole = program.features.iter().find(|f| f.kind == "hole").unwrap();
        assert_eq!(
            hole.params.get("diameter").map(|p| p.text.as_str()),
            Some("28mm")
        );
        assert_eq!(
            hole.params.get("diameter").map(|p| p.cause.as_str()),
            Some("literal")
        );

        let bend = program.features.iter().find(|f| f.kind == "bend").unwrap();
        assert_eq!(
            bend.params.get("radius").map(|p| p.text.as_str()),
            Some("free")
        );
        assert_eq!(
            bend.params.get("radius").map(|p| p.cause.as_str()),
            Some("free")
        );
        assert!(report.diagnostics.is_empty(), "{:?}", report.diagnostics);
    }

    #[test]
    fn patternof_orbit_is_one_op_with_its_count() {
        let src = "part p:\n    stage s1:\n        then:\n            mounts = PatternOf<CBore<M8>>(n=4, rect(100mm x 70mm))\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        let op = &report.programs[0].features[0];
        assert_eq!(op.count, 4);
        assert_eq!(op.kind, "hole");
    }

    #[test]
    fn a_part_with_no_features_yields_no_program() {
        let src = "part p:\n    x: 1\n";
        let files = parsed(src);
        assert!(build_feature_programs(&files).programs.is_empty());
    }

    /// WO-51 d2: an op outside the v1 set is a NAMED E0443 warning --
    /// the program is still emitted (with the supported ops), never
    /// silently truncated.
    #[test]
    fn unsupported_op_is_a_named_warning_not_silence() {
        let src = "part p:\n    stage s1:\n        then:\n            body = FaceMill(depth=1mm)\n            pilot = Bore(dia 8mm)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1);
        assert_eq!(report.programs[0].features.len(), 1);
        let diags: Vec<_> = report
            .diagnostics
            .iter()
            .filter(|d| d.code == codes::UNSUPPORTED_FEATURE_OP)
            .collect();
        assert_eq!(diags.len(), 1);
        assert!(
            diags[0].message.contains("FaceMill"),
            "{}",
            diags[0].message
        );
    }

    /// WO-51 d1/d2: a profile an op references arrives as its typed
    /// sketch payload (here: a promoted cardinal closure).
    #[test]
    fn referenced_profile_walks_ride_the_program_as_sketches() {
        let src = "profile Flat:\n    walk:\n        from left_edge\n        a: line right\n        b: line up\n        c: line left\n        d: close\n    constraints:\n        a.length = 80mm\n        b.length = 50mm\npart p:\n    stage cut:\n        then:\n            blank = Blank(Flat)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1);
        let program = &report.programs[0];
        assert_eq!(program.features[0].kind, "blank");
        assert_eq!(
            program.features[0]
                .params
                .get("profile")
                .map(|p| p.text.as_str()),
            Some("Flat")
        );
        let Some(WalkPromotion::Promoted(sk)) = program.sketches.get("Flat") else {
            panic!("expected the promoted Flat closure: {:?}", program.sketches);
        };
        assert_eq!(sk.segments.len(), 3);
        assert_eq!(sk.close_edge.as_deref(), Some("d"));
        // WO-62 D171/AD-32: this stage carries no `process=` at all, so
        // the blank has no gauge source -- the NAMED E0448, not a
        // silently unthickened blank.
        assert!(
            report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::SHEET_BLANK_NO_GAUGE_SOURCE),
            "{:?}",
            report.diagnostics
        );
    }

    /// WO-62 D171/AD-32 deliverable 2: `process=laser_cut(sheet=<t>)`
    /// is a value SOURCE for a `Blank` op's thickness, Cause-tagged
    /// `process(<proc>.sheet)` per INV-21 -- no E0448, and the resolved
    /// param carries the gauge value with its process provenance.
    #[test]
    fn sheet_gauge_source_supplies_blank_thickness() {
        let src = "profile Flat:\n    walk:\n        from left_edge\n        a: line right\n        b: line up\n        c: line left\n        d: close\n    constraints:\n        a.length = 80mm\n        b.length = 50mm\n        c.length = 80mm\npart p:\n    stage cut: process=laser_cut(sheet=1.5mm)\n        then:\n            blank = Blank(Flat)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert!(
            !report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::SHEET_BLANK_NO_GAUGE_SOURCE),
            "{:?}",
            report.diagnostics
        );
        let program = &report.programs[0];
        let thickness = program.features[0].params.get("thickness").unwrap();
        assert_eq!(thickness.text, "1.5mm");
        assert_eq!(thickness.cause, "process(laser_cut.sheet)");
    }

    /// W4 regression (post-WO-64 phase B ledger): a milled blank
    /// (`process=cnc_mill(...)`, `coolant_gallery.hema`'s own shape --
    /// WO-51 D152) is not sheet stock and needs no gauge source, so no
    /// `E0448` fires even though the op carries no `thickness=`.
    #[test]
    fn milled_blank_has_no_gauge_source_requirement() {
        let src = "profile BlockOutline:\n    walk:\n        from left_edge\n        a: line right\n        b: line up\n        c: line left\n        d: close\n    constraints:\n        a.length = 80mm\n        b.length = 50mm\n        c.length = 80mm\npart p:\n    stage milled: process=cnc_mill(axes=3)\n        then:\n            body = Blank(BlockOutline, depth=30mm)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert!(
            !report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::SHEET_BLANK_NO_GAUGE_SOURCE),
            "{:?}",
            report.diagnostics
        );
        let program = &report.programs[0];
        assert!(!program.features[0].params.contains_key("thickness"));
    }

    /// W4 regression: a sheet-family process (`laser_cut`) with no
    /// `sheet=` gauge argument, and no `thickness=` asserted on the op,
    /// is still the genuine gauge-less-sheet-part case -- `E0448` stays
    /// (this is `dune_buggy`'s `bodywork.hema` shape: `blanks =
    /// Blank(panel_flat_set)` under a bare `process=laser_cut`).
    #[test]
    fn gaugeless_sheet_blank_still_reports_e0448() {
        let src = "profile Flat:\n    walk:\n        from left_edge\n        a: line right\n        b: line up\n        c: line left\n        d: close\n    constraints:\n        a.length = 80mm\n        b.length = 50mm\n        c.length = 80mm\npart p:\n    stage cut: process=laser_cut\n        then:\n            blank = Blank(Flat)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert!(
            report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::SHEET_BLANK_NO_GAUGE_SOURCE),
            "{:?}",
            report.diagnostics
        );
    }

    /// The explicit-assertion escape hatch: `thickness=` on the op
    /// itself wins even with no enclosing gauge-bearing process, and
    /// stays `literal` (not a process cause).
    #[test]
    fn explicit_thickness_arg_wins_over_a_missing_gauge_source() {
        let src = "profile Flat:\n    walk:\n        from left_edge\n        a: line right\n        b: line up\n        c: line left\n        d: close\n    constraints:\n        a.length = 80mm\n        b.length = 50mm\n        c.length = 80mm\npart p:\n    stage cut:\n        then:\n            blank = Blank(Flat, thickness=2mm)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert!(
            !report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::SHEET_BLANK_NO_GAUGE_SOURCE),
            "{:?}",
            report.diagnostics
        );
        let program = &report.programs[0];
        let thickness = program.features[0].params.get("thickness").unwrap();
        assert_eq!(thickness.text, "2mm");
        assert_eq!(thickness.cause, "literal");
    }

    /// WO-51 d3 (D151/D152): a cavity query derives a wetted flow path
    /// over the op chain between its ports -- declared facts cited,
    /// underivable fields honestly indeterminate.
    #[test]
    fn cavity_query_derives_flow_paths_over_the_op_chain() {
        let src = "part p:\n    stage milled:\n        then:\n            feed = Bore(dia 8mm, depth=12mm)\n            gallery = Bore(dia 6mm, depth=40mm)\n            drain = Bore(dia 8mm, depth=12mm)\n    require Hydraulics:\n        wetted: body.cavity(inlet=feed.mouth, outlet=drain.mouth).volume <= 12000mm3\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1);
        let program = &report.programs[0];
        assert_eq!(program.flow_paths.len(), 1, "{:?}", report.diagnostics);
        let path = &program.flow_paths[0];
        assert_eq!(path.selector, "milled.wetted");
        assert_eq!(path.inlet, "feed.mouth");
        assert_eq!(path.outlet, "drain.mouth");
        assert_eq!(path.segments.len(), 3);
        let seg = &path.segments[1];
        assert_eq!(seg.role, "bore");
        assert_eq!(seg.bore.as_deref(), Some("gallery"));
        assert!(matches!(
            &seg.flow_area,
            DerivedFact::Declared { value, .. } if value == "6mm"
        ));
        assert!(matches!(
            &seg.roughness_class,
            DerivedFact::Indeterminate { .. }
        ));
        assert!(report.diagnostics.is_empty(), "{:?}", report.diagnostics);
    }

    /// D152 misuse surface: an unresolvable port is E0444; a chain
    /// through an inexpressible op is E0445 (hematite/07 sec. 2a).
    #[test]
    fn cavity_misuse_is_e0444_and_e0445() {
        let unresolved = "part p:\n    stage s:\n        then:\n            feed = Bore(dia 8mm)\n    require H:\n        w: body.cavity(inlet=nope.mouth).volume <= 1mm3\n";
        let report = build_feature_programs(&parsed(unresolved));
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == codes::CAVITY_PORT_UNRESOLVED));

        let inexpressible = "part p:\n    stage s:\n        then:\n            feed = Bore(dia 8mm)\n            mix = SwirlGallery(turns=3)\n            drain = Bore(dia 8mm)\n    require H:\n        w: body.cavity(inlet=feed.mouth, outlet=drain.mouth).volume <= 1mm3\n";
        let report = build_feature_programs(&parsed(inexpressible));
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == codes::CAVITY_CHAIN_INEXPRESSIBLE));
        assert!(report.programs.iter().all(|p| p.flow_paths.is_empty()));
    }

    /// The D152 exemplar fixture end to end: the corpus
    /// coolant_gallery part yields a program with the promoted
    /// BlockOutline sketch AND the cavity-derived milled.wetted flow
    /// path -- no hand-authored program anywhere.
    #[test]
    fn the_d152_exemplar_fixture_yields_sketch_and_flow_path() {
        let src = include_str!("../../../examples/tracks/hematite/coolant_gallery.hema");
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1, "{:?}", report.diagnostics);
        let program = &report.programs[0];
        assert_eq!(program.part_name, "CoolantGallery");
        assert!(program.sketches.contains_key("BlockOutline"));
        assert!(matches!(
            program.sketches.get("BlockOutline"),
            Some(WalkPromotion::Promoted(_))
        ));
        // Two cavity queries (volume + min_section) over the same
        // ports derive ONE three-segment chain (deduplicated).
        assert_eq!(program.flow_paths.len(), 1);
        for path in &program.flow_paths {
            assert_eq!(path.selector, "milled.wetted");
            assert_eq!(path.segments.len(), 3);
        }
        assert!(
            report
                .diagnostics
                .iter()
                .all(|d| d.code != codes::CAVITY_PORT_UNRESOLVED
                    && d.code != codes::CAVITY_CHAIN_INEXPRESSIBLE),
            "{:?}",
            report.diagnostics
        );
    }

    /// WO-77 d1/d2 (charter 34 phase 1, D200): the four material-removal
    /// family verbs project into ORDINARY `FeatureOp`s -- bounded slots
    /// carry the `planner` cause, literals stay `literal`, and none of
    /// the four is an E0443 (they are recognized vocabulary now).
    #[test]
    fn removal_families_project_as_ordinary_feature_ops() {
        let src = "part p:\n    stage milled: process=cnc_mill(axes=3)\n        then:\n            body = Blank(BlockOutline, depth=18mm)\n            lightening = Ribs(count in [4, 8], pitch=30mm, thickness in [2mm, 5mm], height=12mm)\n            tray = PocketGrid(nx=3, ny=2, wall=2mm, floor=1.5mm, depth=10mm)\n            hollow = Shell(t=2mm)\n            core = Lattice(cell=gyroid, density=0.35)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert_eq!(report.programs.len(), 1);
        let program = &report.programs[0];
        assert!(
            report
                .diagnostics
                .iter()
                .all(|d| d.code != codes::UNSUPPORTED_FEATURE_OP
                    && d.code != codes::REMOVAL_FAMILY_MALFORMED),
            "{:?}",
            report.diagnostics
        );

        let ribs = program.features.iter().find(|f| f.kind == "ribs").unwrap();
        assert_eq!(ribs.constructor, "Ribs");
        assert_eq!(ribs.params["count"].text, "[4, 8]");
        assert_eq!(ribs.params["count"].cause, "planner");
        assert_eq!(ribs.params["pitch"].text, "30mm");
        assert_eq!(ribs.params["pitch"].cause, "literal");
        assert_eq!(ribs.params["thickness"].cause, "planner");

        let grid = program
            .features
            .iter()
            .find(|f| f.kind == "pocket_grid")
            .unwrap();
        assert_eq!(grid.params["nx"].text, "3");
        assert_eq!(grid.params["floor"].text, "1.5mm");

        let shell = program.features.iter().find(|f| f.kind == "shell").unwrap();
        assert_eq!(shell.params["thickness"].text, "2mm");

        // Lattice LOWERS (an ordinary op) -- the honest skip is the
        // realizer projection's, never an E0443 here (WO-77 acceptance:
        // "Lattice declares, lowers, and skips HONESTLY").
        let lattice = program
            .features
            .iter()
            .find(|f| f.kind == "lattice")
            .unwrap();
        assert_eq!(lattice.params["cell"].text, "gyroid");
        assert_eq!(lattice.params["density"].text, "0.35");
    }

    /// WO-77 d1: malformed family params are the constructive E0451
    /// naming the family signature; the op is omitted, never guessed.
    #[test]
    fn malformed_family_params_are_e0451_and_the_op_is_omitted() {
        let src = "part p:\n    stage milled: process=cnc_mill(axes=3)\n        then:\n            core = Lattice(cell=voronoi, density=1.4)\n            ok = Bore(dia 8mm, depth=10mm)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        let diags: Vec<_> = report
            .diagnostics
            .iter()
            .filter(|d| d.code == codes::REMOVAL_FAMILY_MALFORMED)
            .collect();
        assert_eq!(diags.len(), 1, "{:?}", report.diagnostics);
        let msg = &diags[0].message;
        assert!(msg.contains("unknown cell `voronoi`"), "{msg}");
        assert!(msg.contains("fraction in [0, 1]"), "{msg}");
        assert!(
            msg.contains("Lattice(cell: {gyroid, honeycomb, cubic}, density: [0, 1])"),
            "{msg}"
        );
        // The malformed op is omitted; the well-formed sibling stays.
        let program = &report.programs[0];
        assert!(program.features.iter().all(|f| f.kind != "lattice"));
        assert!(program.features.iter().any(|f| f.kind == "hole"));
    }

    /// WO-77 d1: a missing required slot is E0451 too (wrong arity).
    #[test]
    fn missing_required_family_slot_is_e0451() {
        let src = "part p:\n    stage milled: process=cnc_mill(axes=3)\n        then:\n            lightening = Ribs(count=4, pitch=18mm)\n";
        let files = parsed(src);
        let report = build_feature_programs(&files);
        assert!(
            report
                .diagnostics
                .iter()
                .any(|d| d.code == codes::REMOVAL_FAMILY_MALFORMED
                    && d.message.contains("`thickness` is missing")),
            "{:?}",
            report.diagnostics
        );
    }

    /// One roughness vocabulary: every class the process->roughness
    /// derivation can emit is a key of the extract seam's table.
    #[test]
    fn process_roughness_classes_are_extract_table_keys() {
        for (_, class) in super::PROCESS_ROUGHNESS {
            assert!(
                crate::extract::ROUGHNESS_TABLE
                    .iter()
                    .any(|(name, _)| name == class),
                "class `{class}` is not in the extract seam's ROUGHNESS_TABLE"
            );
        }
    }

    /// The pass is hematite-only (the registry decides, AD-14): a
    /// `.cupr` converter ctor is never an "unsupported mech op".
    #[test]
    fn cuprite_files_are_outside_the_pass() {
        let path = Utf8PathBuf::from("t.cupr");
        let files = vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(
                "part p:\n    stage s:\n        then:\n            x = Buck(vin=12V)\n",
                &path,
            ),
        }];
        let report = build_feature_programs(&files);
        assert!(report.programs.is_empty());
        assert!(report.diagnostics.is_empty());
    }
}
