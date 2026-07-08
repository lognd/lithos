//! The pass-pipeline driver (AD-17): parsed source -> entity DB
//! snapshots -> semantic checks -> contract IR -> content-addressed
//! obligations -> (compile only) static discharge.
//!
//! Regolith reference: `docs/regolith/06-execution-model.md`,
//! `docs/regolith/07-claims-and-evidence.md` sec. 2. This crate is a
//! PURE function of source text: no IO, no rendering, and it never
//! returns `Err` -- a failing build is diagnostics in the output
//! (AD-7). All IO (file discovery/read, evidence-cache load/store)
//! stays in `regolith-api::Session`; the ONE diagnostic renderer stays
//! invoked from `regolith-api`.

pub mod block_requirement;
pub mod checks;
pub mod claim_scope;
pub mod claims;
pub mod contracts;
pub mod converter;
pub mod discharge;
pub mod entities;
pub mod extract;
pub mod feature_program;
pub mod flownet_lower;
pub mod fluid;
pub mod output;
pub mod ownership;
pub mod query;
pub mod realized_input;
pub mod rules;
pub mod solve_pass;
pub mod waivers;

pub use output::{LowerOutput, ParsedFile, SourceFile};
pub use realized_input::{RealizedInput, RealizedInputs};
pub use regolith_oblig::EvidenceCache;

/// Parse every source file into a [`ParsedFile`], preserving the
/// caller's order (the caller -- `Session::discover_files` -- already
/// sorts for determinism, AD-6; this pass does not re-sort).
#[must_use]
pub fn parse_sources(sources: &[SourceFile]) -> Vec<ParsedFile> {
    let span = tracing::info_span!("parse", files = sources.len());
    let _enter = span.enter();

    sources
        .iter()
        .map(|source| {
            let parse = regolith_syntax::parse(&source.text, &source.path);
            tracing::debug!(
                file = %source.path,
                diagnostics = parse.diagnostics().len(),
                "parsed source file"
            );
            ParsedFile {
                path: source.path.clone(),
                parse,
            }
        })
        .collect()
}

/// Run passes 1-5 (`parse` through `lower.claims`): the `check()`
/// pipeline. Always materializes a full [`LowerOutput`]; never `Err`.
///
/// `realized_inputs` (WO-42 deliverable 3, AD-25/D128) is the
/// orchestrator-resolved set of realized-domain IR bytes this build was
/// supplied (digest -> bytes + kind/subject metadata); an empty map is
/// the D128 placeholder path (every `from=` edge falls back to its
/// deferred `GeomExtract` selector). `lower` stays pure: resolving a
/// digest against the WO-30 store is the caller's IO, done before this
/// function is ever called (AD-17).
#[must_use]
pub fn lower(
    sources: &[SourceFile],
    realized_inputs: &realized_input::RealizedInputs,
) -> LowerOutput {
    let parsed = parse_sources(sources);

    let mut diagnostics: Vec<regolith_diag::Diagnostic> = parsed
        .iter()
        .flat_map(|p| p.parse.diagnostics().iter().cloned())
        .collect();

    let entity_span = tracing::info_span!("lower.entities");
    let snapshots = {
        let _enter = entity_span.enter();
        entities::build_entities(&parsed)
    };
    diagnostics.extend(snapshots.diagnostics.iter().cloned());

    let checks_span = tracing::info_span!("lower.checks");
    let check_report = {
        let _enter = checks_span.enter();
        checks::run_checks(&parsed, &snapshots)
    };
    diagnostics.extend(check_report.diagnostics.iter().cloned());

    let fluid_span = tracing::info_span!("lower.fluid");
    let fluid_report = {
        let _enter = fluid_span.enter();
        fluid::run_fluid_checks(&parsed)
    };
    diagnostics.extend(fluid_report.diagnostics.iter().cloned());

    let contracts_span = tracing::info_span!("lower.contracts");
    let graph = {
        let _enter = contracts_span.enter();
        contracts::build_contract_ir(&parsed, &snapshots)
    };
    diagnostics.extend(graph.diagnostics.iter().cloned());

    let claims_span = tracing::info_span!("lower.claims");
    let mut obligation_set = {
        let _enter = claims_span.enter();
        claims::build_obligations(&parsed, &snapshots, &check_report, &graph, realized_inputs)
    };
    diagnostics.extend(obligation_set.diagnostics.iter().cloned());

    let statics_feed = run_statics_feed(&graph, &snapshots, &mut obligation_set.obligations);
    diagnostics.extend(statics_feed.diagnostics.iter().cloned());

    let waivers_span = tracing::info_span!("lower.waivers");
    let waiver_report = {
        let _enter = waivers_span.enter();
        waivers::build_ledger(&parsed, &snapshots, &obligation_set.obligations)
    };
    diagnostics.extend(waiver_report.diagnostics.iter().cloned());

    let feature_programs = {
        let span = tracing::info_span!("lower.feature_program");
        let _enter = span.enter();
        feature_program::build_feature_programs(&parsed)
    };

    let block_requirements = {
        let span = tracing::info_span!("lower.block_requirement");
        let _enter = span.enter();
        block_requirement::build_block_requirements(&parsed)
    };

    // WO-32 deliverable 4b: the elaborated flownets `lower.claims`
    // already produced (one `elaborate_flownets` call, AD-22), keyed
    // by name in elaboration (source) order for `BuildPayload.flownets`.
    let flownets: indexmap::IndexMap<String, regolith_oblig::FlownetPayload> = obligation_set
        .flownets
        .drain(..)
        .map(|fln| (fln.name, fln.payload))
        .collect();

    tracing::info!(
        diagnostics = diagnostics.len(),
        resolutions = snapshots.resolutions.len(),
        obligations = obligation_set.obligations.len(),
        snapshots = obligation_set.snapshots.len(),
        waivers = waiver_report.ledger.entries().len(),
        feature_programs = feature_programs.len(),
        block_requirements = block_requirements.len(),
        flownets = flownets.len(),
        "lower: check pipeline complete"
    );

    LowerOutput {
        diagnostics,
        resolutions: snapshots.resolutions,
        obligations: obligation_set.obligations,
        snapshots: obligation_set.snapshots,
        evidence: Vec::new(),
        ledger: waiver_report.ledger,
        feature_programs,
        block_requirements,
        flownets,
        field_datums: obligation_set.field_datums,
    }
}

/// Run passes 1-6 (adds `lower.discharge`): the `compile()` pipeline.
/// Consults and updates `cache` for the statically dischargeable toy
/// subset (WO-13); a second call over the same sources hits the cache.
///
/// `registry_version` is the harness model-registry version (Python-side,
/// AD-1), folded into every evidence-cache key so a model upgrade forces
/// re-verification (BE-1/INV-1).
#[must_use]
pub fn lower_and_discharge(
    sources: &[SourceFile],
    cache: &mut regolith_oblig::EvidenceCache,
    registry_version: &str,
    realized_inputs: &realized_input::RealizedInputs,
) -> LowerOutput {
    let parsed = parse_sources(sources);

    let mut diagnostics: Vec<regolith_diag::Diagnostic> = parsed
        .iter()
        .flat_map(|p| p.parse.diagnostics().iter().cloned())
        .collect();

    let snapshots = {
        let span = tracing::info_span!("lower.entities");
        let _enter = span.enter();
        entities::build_entities(&parsed)
    };
    diagnostics.extend(snapshots.diagnostics.iter().cloned());

    let check_report = {
        let span = tracing::info_span!("lower.checks");
        let _enter = span.enter();
        checks::run_checks(&parsed, &snapshots)
    };
    diagnostics.extend(check_report.diagnostics.iter().cloned());

    let fluid_report = {
        let span = tracing::info_span!("lower.fluid");
        let _enter = span.enter();
        fluid::run_fluid_checks(&parsed)
    };
    diagnostics.extend(fluid_report.diagnostics.iter().cloned());

    let graph = {
        let span = tracing::info_span!("lower.contracts");
        let _enter = span.enter();
        contracts::build_contract_ir(&parsed, &snapshots)
    };
    diagnostics.extend(graph.diagnostics.iter().cloned());

    let mut obligation_set = {
        let span = tracing::info_span!("lower.claims");
        let _enter = span.enter();
        claims::build_obligations(&parsed, &snapshots, &check_report, &graph, realized_inputs)
    };
    diagnostics.extend(obligation_set.diagnostics.iter().cloned());

    let statics_feed = run_statics_feed(&graph, &snapshots, &mut obligation_set.obligations);
    diagnostics.extend(statics_feed.diagnostics.iter().cloned());

    let waiver_report = {
        let span = tracing::info_span!("lower.waivers");
        let _enter = span.enter();
        waivers::build_ledger(&parsed, &snapshots, &obligation_set.obligations)
    };
    diagnostics.extend(waiver_report.diagnostics.iter().cloned());

    let discharge_outcome = {
        let span = tracing::info_span!("lower.discharge");
        let _enter = span.enter();
        discharge::discharge_static(&obligation_set.obligations, &graph, cache, registry_version)
    };
    diagnostics.extend(discharge_outcome.diagnostics.iter().cloned());

    let feature_programs = {
        let span = tracing::info_span!("lower.feature_program");
        let _enter = span.enter();
        feature_program::build_feature_programs(&parsed)
    };

    let block_requirements = {
        let span = tracing::info_span!("lower.block_requirement");
        let _enter = span.enter();
        block_requirement::build_block_requirements(&parsed)
    };

    // WO-32 deliverable 4b (see `lower`'s matching comment).
    let flownets: indexmap::IndexMap<String, regolith_oblig::FlownetPayload> = obligation_set
        .flownets
        .drain(..)
        .map(|fln| (fln.name, fln.payload))
        .collect();

    tracing::info!(
        diagnostics = diagnostics.len(),
        obligations = obligation_set.obligations.len(),
        evidence = discharge_outcome.evidence.len(),
        waivers = waiver_report.ledger.entries().len(),
        feature_programs = feature_programs.len(),
        block_requirements = block_requirements.len(),
        flownets = flownets.len(),
        "lower: compile pipeline complete"
    );

    LowerOutput {
        diagnostics,
        resolutions: snapshots.resolutions,
        obligations: obligation_set.obligations,
        snapshots: obligation_set.snapshots,
        evidence: discharge_outcome.evidence,
        ledger: waiver_report.ledger,
        feature_programs,
        block_requirements,
        flownets,
        field_datums: obligation_set.field_datums,
    }
}

/// WO-23 pass 5b: solve rigid statics over every system with populated
/// matings and feed the computed reaction envelopes into obligations'
/// `given.loads`, mapping each system to its entity-snapshot subject
/// hash. Runs after `lower.claims` and BEFORE waivers/discharge so
/// obligation identity includes the computed loads (INV-1).
fn run_statics_feed(
    graph: &contracts::ContractGraph,
    snapshots: &entities::EntitySnapshots,
    obligations: &mut [regolith_oblig::Obligation],
) -> solve_pass::StaticsFeedReport {
    let system_subjects: Vec<(String, String)> = graph
        .systems
        .iter()
        .filter_map(|s| {
            snapshots
                .scopes
                .get(&s.name)
                .map(|db| (s.name.clone(), db.snapshot_hash()))
        })
        .collect();
    solve_pass::feed_interface_loads(graph, &system_subjects, obligations)
}

#[cfg(test)]
mod tests {
    use super::{lower, lower_and_discharge, parse_sources, RealizedInputs, SourceFile};
    use camino::Utf8PathBuf;
    use regolith_oblig::{EvidenceCache, Status};

    #[test]
    fn lower_populates_flownets_from_a_fluid_source() {
        // WO-32 deliverable 4b: `LowerOutput.flownets` is the seam
        // `BuildPayload.flownets` copies verbatim (session.rs).
        let src = "medium Water: liquid\n\
                   \x20   props: registry(potable_water_nist)\n\
                   flownet Loop(medium=Water):\n\
                   \x20   reference: ambient(101kPa, 293K)\n\
                   \x20   nodes: a, b\n\
                   \x20   edges:\n\
                   \x20       supply: Pipe(from=line.run) (a -> b)\n\
                   require Margin:\n\
                   \x20   dp: fluids.dp(a -> b) <= 40kPa\n";
        let sources = vec![SourceFile {
            path: Utf8PathBuf::from("t.fluo"),
            text: src.to_string(),
        }];
        let out = lower(&sources, &RealizedInputs::new());
        assert_eq!(out.flownets.len(), 1, "one elaborated flownet emitted");
        assert!(out.flownets.contains_key("Loop"));
        assert_eq!(out.obligations.len(), 1);
        assert_eq!(
            out.obligations[0].payloads[0].digest,
            out.flownets["Loop"].content_digest().unwrap(),
            "the obligation's payload ref names the emitted flownet's digest"
        );
    }

    #[test]
    fn parse_sources_preserves_caller_order() {
        let sources = vec![
            SourceFile {
                path: Utf8PathBuf::from("b.hema"),
                text: "part B:\n".to_string(),
            },
            SourceFile {
                path: Utf8PathBuf::from("a.hema"),
                text: "part A:\n".to_string(),
            },
        ];
        let parsed = parse_sources(&sources);
        assert_eq!(parsed[0].path, Utf8PathBuf::from("b.hema"));
        assert_eq!(parsed[1].path, Utf8PathBuf::from("a.hema"));
    }

    #[test]
    fn stiffness_tier_discharges_end_to_end_from_source() {
        // WO-23: the L2 stiffness tier through the REAL pipeline --
        // source text declares the spring network in its `loads:`
        // block (threaded into `given.loads` by `given_for_decl`) and
        // a fat-margin `mech.stiffness(...) >= ...` claim; compile()
        // discharges it statically with the network model.
        let src = "part Mount:\n\
                   \x20   loads:\n\
                   \x20       s1: spring(base, mid, k=200)\n\
                   \x20       s2: spring(mid, tip, k=300)\n\
                   \x20       g: ground(base)\n\
                   \x20   require Stiff:\n\
                   \x20       k_tip: mech.stiffness(tip) >= 50\n";
        let sources = vec![SourceFile {
            path: Utf8PathBuf::from("mount.hema"),
            text: src.to_string(),
        }];
        let mut cache = EvidenceCache::new();
        let realized_inputs = RealizedInputs::new();
        let out = lower_and_discharge(&sources, &mut cache, "registry@1", &realized_inputs);

        let ev: Vec<_> = out
            .evidence
            .iter()
            .filter(|e| e.model_id == "l2_stiffness_network")
            .collect();
        assert_eq!(ev.len(), 1, "evidence: {:?}", out.evidence);
        assert_eq!(ev[0].status, Status::Discharged);
    }
}
