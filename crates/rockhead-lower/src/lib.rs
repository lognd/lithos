//! The pass-pipeline driver (AD-17): parsed source -> entity DB
//! snapshots -> semantic checks -> contract IR -> content-addressed
//! obligations -> (compile only) static discharge.
//!
//! Substrate reference: `docs/substrate/06-execution-model.md`,
//! `docs/substrate/07-claims-and-evidence.md` sec. 2. This crate is a
//! PURE function of source text: no IO, no rendering, and it never
//! returns `Err` -- a failing build is diagnostics in the output
//! (AD-7). All IO (file discovery/read, evidence-cache load/store)
//! stays in `rockhead-api::Session`; the ONE diagnostic renderer stays
//! invoked from `rockhead-api`.

pub mod checks;
pub mod claims;
pub mod contracts;
pub mod discharge;
pub mod entities;
pub mod output;

pub use output::{LowerOutput, ParsedFile, SourceFile};
pub use rockhead_oblig::EvidenceCache;

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
            let parse = rockhead_syntax::parse(&source.text, &source.path);
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
#[must_use]
pub fn lower(sources: &[SourceFile]) -> LowerOutput {
    let parsed = parse_sources(sources);

    let mut diagnostics: Vec<rockhead_diag::Diagnostic> = parsed
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
        checks::run_checks(&snapshots)
    };
    diagnostics.extend(check_report.diagnostics.iter().cloned());

    let contracts_span = tracing::info_span!("lower.contracts");
    let graph = {
        let _enter = contracts_span.enter();
        contracts::build_contract_ir(&parsed, &snapshots)
    };
    diagnostics.extend(graph.diagnostics.iter().cloned());

    let claims_span = tracing::info_span!("lower.claims");
    let obligation_set = {
        let _enter = claims_span.enter();
        claims::build_obligations(&parsed, &snapshots, &check_report, &graph)
    };
    diagnostics.extend(obligation_set.diagnostics.iter().cloned());

    tracing::info!(
        diagnostics = diagnostics.len(),
        resolutions = snapshots.resolutions.len(),
        obligations = obligation_set.obligations.len(),
        snapshots = obligation_set.snapshots.len(),
        "lower: check pipeline complete"
    );

    LowerOutput {
        diagnostics,
        resolutions: snapshots.resolutions,
        obligations: obligation_set.obligations,
        snapshots: obligation_set.snapshots,
        evidence: Vec::new(),
    }
}

/// Run passes 1-6 (adds `lower.discharge`): the `compile()` pipeline.
/// Consults and updates `cache` for the statically dischargeable toy
/// subset (WO-13); a second call over the same sources hits the cache.
#[must_use]
pub fn lower_and_discharge(
    sources: &[SourceFile],
    cache: &mut rockhead_oblig::EvidenceCache,
) -> LowerOutput {
    let parsed = parse_sources(sources);

    let mut diagnostics: Vec<rockhead_diag::Diagnostic> = parsed
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
        checks::run_checks(&snapshots)
    };
    diagnostics.extend(check_report.diagnostics.iter().cloned());

    let graph = {
        let span = tracing::info_span!("lower.contracts");
        let _enter = span.enter();
        contracts::build_contract_ir(&parsed, &snapshots)
    };
    diagnostics.extend(graph.diagnostics.iter().cloned());

    let obligation_set = {
        let span = tracing::info_span!("lower.claims");
        let _enter = span.enter();
        claims::build_obligations(&parsed, &snapshots, &check_report, &graph)
    };
    diagnostics.extend(obligation_set.diagnostics.iter().cloned());

    let evidence = {
        let span = tracing::info_span!("lower.discharge");
        let _enter = span.enter();
        discharge::discharge_static(&obligation_set.obligations, &graph, cache)
    };

    tracing::info!(
        diagnostics = diagnostics.len(),
        obligations = obligation_set.obligations.len(),
        evidence = evidence.len(),
        "lower: compile pipeline complete"
    );

    LowerOutput {
        diagnostics,
        resolutions: snapshots.resolutions,
        obligations: obligation_set.obligations,
        snapshots: obligation_set.snapshots,
        evidence,
    }
}

#[cfg(test)]
mod tests {
    use super::{parse_sources, SourceFile};
    use camino::Utf8PathBuf;

    #[test]
    fn parse_sources_preserves_caller_order() {
        let sources = vec![
            SourceFile {
                path: Utf8PathBuf::from("b.hem"),
                text: "part B:\n".to_string(),
            },
            SourceFile {
                path: Utf8PathBuf::from("a.hem"),
                text: "part A:\n".to_string(),
            },
        ];
        let parsed = parse_sources(&sources);
        assert_eq!(parsed[0].path, Utf8PathBuf::from("b.hem"));
        assert_eq!(parsed[1].path, Utf8PathBuf::from("a.hem"));
    }
}
