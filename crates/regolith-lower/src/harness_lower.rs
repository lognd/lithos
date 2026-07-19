//! WO-34 deliverable 2: cuprite `harness:` elaboration (D99).
//!
//! Walks every parsed file's typed `harness` AST (D1 grammar) into a
//! [`HarnessLowerReport`] carrying one [`HarnessPayload`] per harness.
//! A run's `along <structural refs>` path is extracted through the ONE
//! shared routed-geometry seam ([`crate::extract::extract_path`]) --
//! the SAME module `flownet_lower` reads for `Pipe(from=...)` edges,
//! never a second copy (WO acceptance criterion: "no routing/
//! extraction logic outside the WO-32 `extract` module and this WO's
//! elaboration pass"). A `route: free` run lowers with an unresolved
//! length (INV-21: no fabricated value; a later planner dispatch
//! materializes it as a `Cause::Planner` [`regolith_qty::Resolution`]).
//!
//! PURITY (AD-17): this pass reads no IO. The orchestrator resolves
//! every structural ref's realized-geometry bytes through the WO-30
//! content store and hands them in via [`HarnessInputs`]; this module
//! only decodes the AST and calls the pure extraction seam -- mirrors
//! `flownet_lower`'s `FlownetInputs` seam exactly.
//!
//! ERRORS ARE DATA: an extraction failure, a cross-net run, a dangling
//! endpoint, or an unknown bundle is a typed [`HarnessLowerError`]
//! value (thiserror), collected and returned; the lowering boundary
//! (`claims.rs`/`lib.rs` driver) renders these as `regolith_diag`
//! diagnostics. This module never renders and never panics.
//!
//! DETERMINISM (AD-6): harnesses are elaborated in caller (sorted) file
//! order; within a payload, `runs` is an `IndexMap` sorted by name and
//! `environments` is a `BTreeMap`, so a [`HarnessPayload`]'s content
//! digest is stable across builds of the same source.

use std::collections::BTreeMap;

use regolith_diag::codes::{
    RUN_CROSS_NET, RUN_DANGLING_ENDPOINT, RUN_EXTRACT_FAILED, RUN_UNKNOWN_BUNDLE,
};
use regolith_diag::{Diagnostic, LabeledSpan, Span};
use regolith_oblig::{HarnessPayload, RunRecord, RunRoute, RunSegment, ScalarInterval};
use regolith_syntax::ast::{AstNode, EnvironmentStmt, File, HarnessDecl, RunStmt};

use crate::extract::{extract_path, ExtractError, MediumProps};
use crate::output::ParsedFile;

/// A caller-resolved realized-geometry source for one structural ref:
/// the record bytes (resolved from the WO-30 store, keeping this
/// module IO-free) and the digest they decoded from.
// frob:doc docs/modules/regolith-lower.md#harness-lower
#[derive(Debug, Clone)]
pub struct ResolvedStructuralGeometry {
    /// The record's serialized bytes (the [`extract_path`] input).
    pub bytes: Vec<u8>,
    /// The realized-geometry payload's content digest.
    pub digest: String,
}

/// The orchestrator-side resolver every `harness:` ref goes through
/// (AD-17: the only route to resolved content). Unit tests supply an
/// in-memory implementation; a real, store-backed implementation
/// mirrors `flownet_lower::RealizedFlownetInputs`.
// frob:doc docs/modules/regolith-lower.md#harness-lower
pub trait HarnessInputs {
    /// Resolve a structural ref (e.g. `"frame.spine_tube"`) named by an
    /// `along` clause to its realized-geometry record; `None` when no
    /// realized record backs the ref (the run's length stays honestly
    /// unresolved for that segment, an [`HarnessLowerError::Extract`]).
    fn structural_geometry(&self, structural_ref: &str) -> Option<ResolvedStructuralGeometry>;

    /// Resolve an endpoint (`component.port` text) to its net name;
    /// `None` when net membership cannot be determined at this layer.
    /// The AST-pure implementation honestly returns `None` for every
    /// endpoint (net inference is not wired to this pass -- see
    /// `AstHarnessInputs`'s doc comment); the cross-net check only
    /// fires when a resolver supplies both endpoints' nets.
    fn net_of(&self, endpoint: &str) -> Option<String>;
}

/// The pure AST-sourced [`HarnessInputs`]: never resolves realized
/// geometry bytes (IO) or net membership (no net-inference seam is
/// wired to `regolith-lower` for cuprite endpoints today -- unlike
/// fluid's flownet-scoped net, an electrical net spans the whole
/// entity DB via `connect`/Mating machinery this pass does not query;
/// WO-34's own escalation notes this as a named gap, not an invented
/// answer). Every run elaborates with its structural refs deferred to
/// an honest [`HarnessLowerError::Extract`] and every endpoint pair
/// skips the cross-net check.
// frob:doc docs/modules/regolith-lower.md#harness-lower
#[derive(Debug, Clone, Copy, Default)]
pub struct AstHarnessInputs;

impl HarnessInputs for AstHarnessInputs {
    fn structural_geometry(&self, _structural_ref: &str) -> Option<ResolvedStructuralGeometry> {
        None
    }

    fn net_of(&self, _endpoint: &str) -> Option<String> {
        None
    }
}

/// The WO-42-channel-backed [`HarnessInputs`]: layers realized-geometry
/// lookup on top of [`AstHarnessInputs`], mirroring
/// `flownet_lower::RealizedFlownetInputs`. `structural_geometry`
/// resolves a ref against the caller-supplied
/// [`crate::realized_input::RealizedInputs`] by subject match.
// frob:doc docs/modules/regolith-lower.md#harness-lower
pub struct RealizedHarnessInputs<'a> {
    realized: &'a crate::realized_input::RealizedInputs,
}

impl<'a> RealizedHarnessInputs<'a> {
    /// Build the resolver over `realized`, the orchestrator-supplied
    /// realized-geometry inputs for this build.
    // frob:doc docs/modules/regolith-lower.md#harness-lower
    #[must_use]
    pub fn new(realized: &'a crate::realized_input::RealizedInputs) -> Self {
        Self { realized }
    }
}

impl HarnessInputs for RealizedHarnessInputs<'_> {
    fn structural_geometry(&self, structural_ref: &str) -> Option<ResolvedStructuralGeometry> {
        let (digest, input) = self
            .realized
            .iter()
            .find(|(_, input)| input.subject == structural_ref)?;
        Some(ResolvedStructuralGeometry {
            bytes: input.bytes.clone(),
            digest: digest.clone(),
        })
    }

    fn net_of(&self, _endpoint: &str) -> Option<String> {
        // Net-membership inference is not wired to this pass (see
        // `AstHarnessInputs`'s doc comment) -- carried over unchanged.
        None
    }
}

/// One elaborated harness: its payload, keyed by declaration name.
// frob:doc docs/modules/regolith-lower.md#harness-lower
#[derive(Debug, Clone)]
pub struct ElaboratedHarness {
    /// The harness's declared name.
    pub name: String,
    /// The elaborated, content-addressable payload.
    pub payload: HarnessPayload,
}

/// A failure elaborating a harness -- a value the lowering boundary
/// renders as a diagnostic. Never a panic; collected and returned.
// frob:doc docs/modules/regolith-lower.md#harness-lower
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum HarnessLowerError {
    /// A run's `from`/`to` header names no non-empty endpoint text on
    /// one (or both) sides (`E0307`).
    #[error("harness `{harness}` run `{run}` has a dangling endpoint ({side})")]
    DanglingEndpoint {
        /// The owning harness.
        harness: String,
        /// The run name.
        run: String,
        /// Which side was dangling (`"from"`, `"to"`, or both).
        side: String,
    },
    /// A run's `bundle` clause is present but names no group text
    /// (`E0308`).
    #[error("harness `{harness}` run `{run}` has an unknown bundle group")]
    UnknownBundle {
        /// The owning harness.
        harness: String,
        /// The run name.
        run: String,
    },
    /// A run's `along` structural ref failed extraction.
    #[error("harness `{harness}` run `{run}` structural ref `{structural_ref}`: {source}")]
    Extract {
        /// The owning harness.
        harness: String,
        /// The run name.
        run: String,
        /// The structural ref that failed.
        structural_ref: String,
        /// The underlying extraction error.
        #[source]
        source: ExtractError,
    },
    /// A run's endpoints resolved to two different nets with no inline
    /// component between them (`E0306`).
    #[error("harness `{harness}` run `{run}` crosses nets `{net_a}` and `{net_b}`")]
    CrossNet {
        /// The owning harness.
        harness: String,
        /// The run name.
        run: String,
        /// The `from` endpoint's net.
        net_a: String,
        /// The `to` endpoint's net.
        net_b: String,
    },
}

/// The result of elaborating every harness in a set of parsed files.
// frob:doc docs/modules/regolith-lower.md#harness-lower
#[derive(Debug, Clone, Default)]
pub struct HarnessLowerReport {
    /// The elaborated harnesses, in file/source order.
    pub harnesses: Vec<ElaboratedHarness>,
    /// Typed elaboration errors, in discovery order (the `Diagnostic`
    /// form each one renders to also lands in `diagnostics`).
    pub errors: Vec<HarnessLowerError>,
    /// The rendered diagnostics for every entry in `errors`, same
    /// order (`E0306`/`E0307`/`E0308`) -- built inline (mirrors
    /// `fluid::check_flownet`'s convention, not `flownet_lower`'s
    /// deferred-rendering one: WO-34's own acceptance criteria demand
    /// a compile diagnostic, so rendering does not wait for a later
    /// dispatch).
    pub diagnostics: Vec<Diagnostic>,
}

/// Elaborate every `harness` declaration across `files` into a
/// [`HarnessPayload`], resolving structural refs through `inputs`.
/// Pure and IO-free (AD-17); deterministic (AD-6). The WO-34
/// deliverable-2 entry point.
// frob:doc docs/modules/regolith-lower.md#harness-lower
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
#[must_use]
pub fn elaborate_harnesses(files: &[ParsedFile], inputs: &dyn HarnessInputs) -> HarnessLowerReport {
    let span = tracing::info_span!("lower.harness");
    let _enter = span.enter();

    let mut report = HarnessLowerReport::default();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for harness in file.harnesses() {
            elaborate_one(&pf.path, &harness, inputs, &mut report);
        }
    }
    tracing::info!(
        harnesses = report.harnesses.len(),
        errors = report.errors.len(),
        "harness elaboration complete"
    );
    report
}

/// Render one [`HarnessLowerError`] into its `Diagnostic` form, spanned
/// over the owning run's (or harness's) full text range.
fn render_error(err: &HarnessLowerError, span: Span) -> Diagnostic {
    match err {
        HarnessLowerError::DanglingEndpoint { harness, run, side } => Diagnostic::error(
            RUN_DANGLING_ENDPOINT,
            format!(
                "harness `{harness}` run `{run}` has a dangling endpoint \
                 ({side}): elaboration cannot resolve a routed path with no \
                 endpoint on that side"
            ),
        )
        .with_span(LabeledSpan::new(span, "dangling endpoint")),
        HarnessLowerError::UnknownBundle { harness, run } => Diagnostic::error(
            RUN_UNKNOWN_BUNDLE,
            format!(
                "harness `{harness}` run `{run}` has a `bundle` clause naming \
                 no group"
            ),
        )
        .with_span(LabeledSpan::new(span, "name a bundle group")),
        HarnessLowerError::CrossNet {
            harness,
            run,
            net_a,
            net_b,
        } => Diagnostic::error(
            RUN_CROSS_NET,
            format!(
                "harness `{harness}` run `{run}` crosses nets `{net_a}` and \
                 `{net_b}` with no inline component between them"
            ),
        )
        .with_span(LabeledSpan::new(span, "endpoints are on different nets")),
        HarnessLowerError::Extract {
            harness,
            run,
            structural_ref,
            source,
        } => Diagnostic::error(
            RUN_EXTRACT_FAILED,
            format!(
                "harness `{harness}` run `{run}` structural ref \
                 `{structural_ref}` failed extraction: {source}"
            ),
        )
        .with_span(LabeledSpan::new(span, "along this structural ref")),
    }
}

/// A primary span over a run declaration's full text range.
fn run_span(path: &camino::Utf8Path, run: &RunStmt) -> Span {
    let range = run.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

/// Split a run header's significant text (`"run batt_to_kill: from
/// battery.pos to kill_switch.in"`) into its `from`/`to` endpoint
/// strings. Returns empty strings for a missing side; the caller turns
/// that into a [`HarnessLowerError::DanglingEndpoint`].
fn parse_endpoints(header_text: &str) -> (String, String) {
    let from = header_text
        .split("from")
        .nth(1)
        .and_then(|rest| rest.split("to").next())
        .map(str::trim)
        .unwrap_or_default()
        .to_string();
    let to = header_text
        .rsplit("to")
        .next()
        .map(str::trim)
        .filter(|_| header_text.contains("to"))
        .unwrap_or_default()
        .to_string();
    (from, to)
}

/// Split an `along` clause's recorded ref-list text (`"along
/// frame.spine_tube, frame.hoop_gusset"`) into its structural refs, in
/// declaration order.
fn parse_along_refs(text: &str) -> Vec<String> {
    let rest = text.strip_prefix("along").unwrap_or(text).trim();
    rest.split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

/// Extract every structural ref in `refs` through the shared seam,
/// concatenating segments in declaration order. Each ref selects its
/// OWN single-segment path (`extract_path`'s `selector` == the
/// structural ref text) from its own resolved record -- a `harness`
/// run is not restricted to one realized-geometry record the way a
/// fluid edge's single `from=` selector is.
fn extract_run_segments(
    inputs: &dyn HarnessInputs,
    refs: &[String],
) -> Result<(Vec<RunSegment>, ScalarInterval, String), (String, ExtractError)> {
    let mut segments = Vec::new();
    let mut total_lo = 0.0_f64;
    let mut total_hi = 0.0_f64;
    let mut last_digest = String::new();

    for structural_ref in refs {
        let Some(resolved) = inputs.structural_geometry(structural_ref) else {
            return Err((
                structural_ref.clone(),
                ExtractError::SelectorNotFound {
                    selector: structural_ref.clone(),
                },
            ));
        };
        let extraction = extract_path(
            &resolved.bytes,
            structural_ref,
            &resolved.digest,
            None::<&MediumProps>,
        )
        .map_err(|e| (structural_ref.clone(), e))?;

        for seg in &extraction.segments {
            total_lo += seg.length.lo;
            total_hi += seg.length.hi;
            segments.push(RunSegment {
                structural_ref: structural_ref.clone(),
                role: seg.role.clone(),
                length: ScalarInterval {
                    lo: seg.length.lo,
                    hi: seg.length.hi,
                    unit: seg.length.unit.clone(),
                },
            });
        }
        last_digest = resolved.digest;
    }

    Ok((
        segments,
        ScalarInterval {
            lo: total_lo,
            hi: total_hi,
            unit: "m".to_string(),
        },
        last_digest,
    ))
}

/// Push `err` onto both `report.errors` (typed data) and
/// `report.diagnostics` (its rendered form, spanned over `run`).
fn push_error(
    report: &mut HarnessLowerReport,
    path: &camino::Utf8Path,
    run: &RunStmt,
    err: HarnessLowerError,
) {
    let diag = render_error(&err, run_span(path, run));
    report.errors.push(err);
    report.diagnostics.push(diag);
}

/// Elaborate one run, appending its record to `runs` (or an error to
/// `report.errors`/`report.diagnostics`).
fn elaborate_run(
    path: &camino::Utf8Path,
    harness_name: &str,
    run: &RunStmt,
    inputs: &dyn HarnessInputs,
    report: &mut HarnessLowerReport,
    runs: &mut indexmap::IndexMap<String, RunRecord>,
) {
    let run_name = run.name().unwrap_or_default();
    let (from, to) = parse_endpoints(&run.header_text());

    let mut dangling_side = None;
    if from.is_empty() && to.is_empty() {
        dangling_side = Some("both".to_string());
    } else if from.is_empty() {
        dangling_side = Some("from".to_string());
    } else if to.is_empty() {
        dangling_side = Some("to".to_string());
    }
    if let Some(side) = dangling_side {
        push_error(
            report,
            path,
            run,
            HarnessLowerError::DanglingEndpoint {
                harness: harness_name.to_string(),
                run: run_name.clone(),
                side,
            },
        );
        return;
    }

    let bundle = if let Some(clause) = run.bundle() {
        if let Some(group) = clause.group() {
            Some(group)
        } else {
            push_error(
                report,
                path,
                run,
                HarnessLowerError::UnknownBundle {
                    harness: harness_name.to_string(),
                    run: run_name.clone(),
                },
            );
            return;
        }
    } else {
        None
    };

    if let (Some(net_a), Some(net_b)) = (inputs.net_of(&from), inputs.net_of(&to)) {
        if net_a != net_b {
            push_error(
                report,
                path,
                run,
                HarnessLowerError::CrossNet {
                    harness: harness_name.to_string(),
                    run: run_name.clone(),
                    net_a,
                    net_b,
                },
            );
            return;
        }
    }

    let route = match run.along() {
        Some(along) if along.is_route_free() => RunRoute::PlannerFree {
            resolved_length: None,
        },
        Some(along) => {
            let refs = parse_along_refs(&along.text());
            match extract_run_segments(inputs, &refs) {
                Ok((segments, total_length, snapshot_hash)) => RunRoute::Waypoints {
                    segments,
                    total_length,
                    snapshot_hash,
                },
                Err((structural_ref, source)) => {
                    push_error(
                        report,
                        path,
                        run,
                        HarnessLowerError::Extract {
                            harness: harness_name.to_string(),
                            run: run_name.clone(),
                            structural_ref,
                            source,
                        },
                    );
                    return;
                }
            }
        }
        None => RunRoute::PlannerFree {
            resolved_length: None,
        },
    };

    runs.insert(
        run_name,
        RunRecord {
            from,
            to,
            bundle,
            route,
        },
    );
}

/// Elaborate an `environment <name>: [lo, hi]` line's bound into a
/// `ScalarInterval`. Reads the bracket's two leading numeric tokens
/// (unit-suffixed or not); a malformed/absent bound degrades to a
/// `[0, 0]` placeholder rather than panicking (a later dispatch may
/// promote this to a diagnostic -- no acceptance criterion names an
/// empty environment bound today).
fn elaborate_environment(env: &EnvironmentStmt) -> (String, ScalarInterval) {
    let name = env.name().unwrap_or_default();
    let bounds = env.bound().map_or((0.0, 0.0), |node| {
        parse_bracket_bounds(&node.text().to_string())
    });
    (
        name,
        ScalarInterval {
            lo: bounds.0.min(bounds.1),
            hi: bounds.0.max(bounds.1),
            unit: "degC".to_string(),
        },
    )
}

/// Parse `"[-30degC, 125degC]"` into its two leading numeric bounds,
/// ignoring unit suffixes (both sides of an `environment` bound share
/// one unit by construction, cuprite/04).
fn parse_bracket_bounds(text: &str) -> (f64, f64) {
    let inner = text.trim().trim_start_matches('[').trim_end_matches(']');
    let mut parts = inner.split(',').map(|p| leading_number(p.trim()));
    let lo = parts.next().flatten().unwrap_or(0.0);
    let hi = parts.next().flatten().unwrap_or(lo);
    (lo, hi)
}

/// The leading numeric literal of a unit-suffixed token (`"-30degC"` ->
/// `-30.0`).
fn leading_number(token: &str) -> Option<f64> {
    let end = token
        .char_indices()
        .find(|(_, c)| !(c.is_ascii_digit() || *c == '-' || *c == '+' || *c == '.'))
        .map_or(token.len(), |(i, _)| i);
    token[..end].parse::<f64>().ok()
}

/// Elaborate one harness declaration, appending its result (and any
/// errors) to `report`.
fn elaborate_one(
    path: &camino::Utf8Path,
    harness: &HarnessDecl,
    inputs: &dyn HarnessInputs,
    report: &mut HarnessLowerReport,
) {
    let name = harness.name().unwrap_or_default();

    let mut runs: indexmap::IndexMap<String, RunRecord> = indexmap::IndexMap::new();
    for run in harness.runs() {
        elaborate_run(path, &name, &run, inputs, report, &mut runs);
    }
    runs.sort_keys();

    let mut environments: BTreeMap<String, ScalarInterval> = BTreeMap::new();
    for env in harness.environments() {
        let (env_name, bound) = elaborate_environment(&env);
        environments.insert(env_name, bound);
    }

    report.harnesses.push(ElaboratedHarness {
        name: name.clone(),
        payload: HarnessPayload {
            name,
            runs,
            environments,
        },
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use camino::Utf8PathBuf;

    fn parse(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.cupr");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    /// A single-segment realized-geometry record for one structural
    /// ref, mirroring `extract.rs`'s own fixture shape.
    fn geometry_bytes(selector: &str, length_m: f64) -> Vec<u8> {
        serde_json::json!({
            "feature_program_hash": "blake3:feat",
            "step_content_hash": "sha256:step",
            "topology": {
                "num_solids": 1, "num_faces": 1, "num_edges": 1, "num_vertices": 1,
                "volume_mm3": 0.0, "area_mm2": 0.0,
                "bbox_min_mm": [0.0, 0.0, 0.0], "bbox_max_mm": [0.0, 0.0, 0.0],
                "center_of_mass_mm": [0.0, 0.0, 0.0]
            },
            "paths": {
                selector: {
                    "segments": [{
                        "role": selector,
                        "flow_area": [1.0e-4, 1.0e-4],
                        "length": [length_m, length_m],
                        "roughness_class": "drawn_tube",
                        "elevation_change": [0.0, 0.0]
                    }]
                }
            }
        })
        .to_string()
        .into_bytes()
    }

    struct FixtureInputs {
        geometry: BTreeMap<String, (Vec<u8>, String)>,
        nets: BTreeMap<String, String>,
    }

    impl HarnessInputs for FixtureInputs {
        fn structural_geometry(&self, structural_ref: &str) -> Option<ResolvedStructuralGeometry> {
            self.geometry
                .get(structural_ref)
                .map(|(bytes, digest)| ResolvedStructuralGeometry {
                    bytes: bytes.clone(),
                    digest: digest.clone(),
                })
        }

        fn net_of(&self, endpoint: &str) -> Option<String> {
            self.nets.get(endpoint).cloned()
        }
    }

    fn two_run_harness_src() -> String {
        "harness MainLoom:\n\
         \x20   run batt_to_kill: from battery.pos to kill_switch.in\n\
         \x20       along frame.spine_tube, frame.hoop_gusset\n\
         \x20       bundle primary\n\
         \x20   run vr_sense: from vr_sensor.sig to ecu.vr_in\n\
         \x20       along route: free\n\
         \x20       bundle shielded_signals\n\
         \x20   environment engine_bay: [-30degC, 125degC]\n"
            .to_string()
    }

    // frob:tests crates/regolith-lower/src/harness_lower.rs::elaborate_harnesses kind="unit"
    #[test]
    fn two_run_harness_lowers_extracted_lengths() {
        let files = parse(&two_run_harness_src());
        let mut geometry = BTreeMap::new();
        geometry.insert(
            "frame.spine_tube".to_string(),
            (
                geometry_bytes("frame.spine_tube", 2.0),
                "blake3:snap-a".to_string(),
            ),
        );
        geometry.insert(
            "frame.hoop_gusset".to_string(),
            (
                geometry_bytes("frame.hoop_gusset", 1.5),
                "blake3:snap-a".to_string(),
            ),
        );
        let inputs = FixtureInputs {
            geometry,
            nets: BTreeMap::new(),
        };

        let report = elaborate_harnesses(&files, &inputs);
        assert!(report.errors.is_empty(), "errors: {:?}", report.errors);
        assert_eq!(report.harnesses.len(), 1);
        let payload = &report.harnesses[0].payload;
        assert_eq!(payload.name, "MainLoom");
        assert_eq!(payload.runs.len(), 2);

        let run = &payload.runs["batt_to_kill"];
        assert_eq!(run.from, "battery.pos");
        assert_eq!(run.to, "kill_switch.in");
        assert_eq!(run.bundle.as_deref(), Some("primary"));
        match &run.route {
            RunRoute::Waypoints {
                segments,
                total_length,
                ..
            } => {
                assert_eq!(segments.len(), 2);
                // Hand-computed sum: 2.0 + 1.5 = 3.5 (outward-rounded).
                assert!(total_length.lo <= 3.5 && 3.5 <= total_length.hi);
            }
            other @ RunRoute::PlannerFree { .. } => panic!("expected Waypoints, got {other:?}"),
        }

        let free_run = &payload.runs["vr_sense"];
        assert!(matches!(
            free_run.route,
            RunRoute::PlannerFree {
                resolved_length: None
            }
        ));

        assert_eq!(payload.environments.len(), 1);
        let bay = &payload.environments["engine_bay"];
        assert!((bay.lo - (-30.0)).abs() < f64::EPSILON);
        assert!((bay.hi - 125.0).abs() < f64::EPSILON);
    }

    #[test]
    fn changed_frame_geometry_changes_extracted_length() {
        let files = parse(&two_run_harness_src());
        let mut geometry = BTreeMap::new();
        geometry.insert(
            "frame.spine_tube".to_string(),
            (
                geometry_bytes("frame.spine_tube", 5.0),
                "blake3:snap-b".to_string(),
            ),
        );
        geometry.insert(
            "frame.hoop_gusset".to_string(),
            (
                geometry_bytes("frame.hoop_gusset", 1.5),
                "blake3:snap-b".to_string(),
            ),
        );
        let inputs = FixtureInputs {
            geometry,
            nets: BTreeMap::new(),
        };
        let report = elaborate_harnesses(&files, &inputs);
        let run = &report.harnesses[0].payload.runs["batt_to_kill"];
        match &run.route {
            RunRoute::Waypoints { total_length, .. } => {
                assert!(total_length.lo <= 6.5 && 6.5 <= total_length.hi);
            }
            other @ RunRoute::PlannerFree { .. } => panic!("expected Waypoints, got {other:?}"),
        }
        // The anti-staleness property (G42): digest changes with geometry.
        let original = {
            let files = parse(&two_run_harness_src());
            let mut geometry = BTreeMap::new();
            geometry.insert(
                "frame.spine_tube".to_string(),
                (
                    geometry_bytes("frame.spine_tube", 2.0),
                    "blake3:snap-a".to_string(),
                ),
            );
            geometry.insert(
                "frame.hoop_gusset".to_string(),
                (
                    geometry_bytes("frame.hoop_gusset", 1.5),
                    "blake3:snap-a".to_string(),
                ),
            );
            let inputs = FixtureInputs {
                geometry,
                nets: BTreeMap::new(),
            };
            elaborate_harnesses(&files, &inputs).harnesses[0]
                .payload
                .content_digest()
                .unwrap()
        };
        let changed_digest = report.harnesses[0].payload.content_digest().unwrap();
        assert_ne!(original, changed_digest);
    }

    #[test]
    fn cross_net_run_is_an_error() {
        let src = "harness H:\n\
                   \x20   run r: from a.p to b.p\n\
                   \x20       along frame.spine_tube\n"
            .to_string();
        let files = parse(&src);
        let mut nets = BTreeMap::new();
        nets.insert("a.p".to_string(), "net1".to_string());
        nets.insert("b.p".to_string(), "net2".to_string());
        let inputs = FixtureInputs {
            geometry: BTreeMap::new(),
            nets,
        };
        let report = elaborate_harnesses(&files, &inputs);
        assert_eq!(
            report.errors,
            vec![HarnessLowerError::CrossNet {
                harness: "H".to_string(),
                run: "r".to_string(),
                net_a: "net1".to_string(),
                net_b: "net2".to_string(),
            }]
        );
    }

    #[test]
    fn dangling_endpoint_is_an_error() {
        let src = "harness H:\n\
                   \x20   run r: from  to b.p\n\
                   \x20       along frame.spine_tube\n"
            .to_string();
        let files = parse(&src);
        let inputs = FixtureInputs {
            geometry: BTreeMap::new(),
            nets: BTreeMap::new(),
        };
        let report = elaborate_harnesses(&files, &inputs);
        assert_eq!(
            report.errors,
            vec![HarnessLowerError::DanglingEndpoint {
                harness: "H".to_string(),
                run: "r".to_string(),
                side: "from".to_string(),
            }]
        );
    }

    #[test]
    fn unknown_bundle_is_an_error() {
        let src = "harness H:\n\
                   \x20   run r: from a.p to b.p\n\
                   \x20       along frame.spine_tube\n\
                   \x20       bundle\n"
            .to_string();
        let files = parse(&src);
        let mut geometry = BTreeMap::new();
        geometry.insert(
            "frame.spine_tube".to_string(),
            (
                geometry_bytes("frame.spine_tube", 1.0),
                "blake3:snap".to_string(),
            ),
        );
        let inputs = FixtureInputs {
            geometry,
            nets: BTreeMap::new(),
        };
        let report = elaborate_harnesses(&files, &inputs);
        assert_eq!(
            report.errors,
            vec![HarnessLowerError::UnknownBundle {
                harness: "H".to_string(),
                run: "r".to_string(),
            }]
        );
    }

    #[test]
    fn unresolved_structural_ref_is_an_extract_error() {
        let src = "harness H:\n\
                   \x20   run r: from a.p to b.p\n\
                   \x20       along frame.missing\n"
            .to_string();
        let files = parse(&src);
        let inputs = FixtureInputs {
            geometry: BTreeMap::new(),
            nets: BTreeMap::new(),
        };
        let report = elaborate_harnesses(&files, &inputs);
        assert_eq!(report.errors.len(), 1);
        assert!(matches!(
            report.errors[0],
            HarnessLowerError::Extract { .. }
        ));
    }
}
