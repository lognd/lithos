//! The coarse compile API: `Session` and `BuildOutput` (AD-4).
//!
//! Regolith reference: `docs/spec/regolith/06-execution-model.md`. This
//! is the single, pure-Rust surface the PyO3 layer wraps -- one
//! crossing per build. It is fully testable without Python. WO-18
//! grows the real `check`/`compile` surface; WO-01 ships the version
//! and schema-version accessors the smoke test crosses on.

pub mod docextract;
pub mod net_core;
pub mod rules;
pub mod session;

pub use docextract::doc_extract;
pub use net_core::{check_elec_single_driver, ElecViolation};
pub use rules::{rules_test, rules_try};
pub use session::{BuildOutput, BuildPayload, CoreError, Session};

use camino::Utf8Path;

/// Format source `text` into its canonical spelling (the boundary
/// `format(text) -> text`, AD-4). Thin delegation to the one formatter.
// frob:doc docs/modules/regolith-api.md#format-and-unit-literal-reduction
#[must_use]
pub fn format(text: &str) -> String {
    regolith_syntax::formatter::format(text, &camino::Utf8PathBuf::from("<stdin>"))
}

/// Reduce `magnitude` in `unit_symbol` (`mrad`, `N/m`) to its SI
/// base magnitude (WO-122, F132.2: the bound-text truncation hazard).
/// `unit_symbol` is parsed through `regolith_qty::Unit::parse_expr` --
/// the SAME unit table L1 quantity literals resolve through (AD-1's
/// one-unit-engine rule) -- so a Python-side bound-text resolver never
/// grows its own parallel unit table. `None` when `unit_symbol` is not
/// a unit this table knows (dB/dBc/dBm and other log-ratio spellings
/// are NOT linear SI units and are the honest `None` case here; the
/// caller defers by name rather than guessing).
// frob:doc docs/modules/regolith-api.md#format-and-unit-literal-reduction
#[must_use]
pub fn reduce_unit_literal(magnitude: f64, unit_symbol: &str) -> Option<f64> {
    let unit = regolith_qty::Unit::parse_expr(unit_symbol).ok()?;
    Some(unit.si_magnitude(magnitude))
}

/// Dump an intermediate pipeline stage of `path`'s source as text
/// (`regolith debug tokens|cst|ast|ir`, AD-13). Thin delegation.
///
/// # Errors
/// Returns [`CoreError`] if the source file cannot be read.
///
/// # Panics
/// Panics if `stage` is not one of `tokens`/`cst`/`ast` -- an invalid
/// stage name is a caller (programmer) bug, not a user error, and
/// crosses the FFI as `CoreBug` (AD-4).
// frob:doc docs/modules/regolith-api.md#debug-dump-and-debug-ir
pub fn debug_dump(stage: &str, path: &Utf8Path) -> Result<String, CoreError> {
    // An unknown stage name is a caller (programmer) bug, not a user
    // error -- it never reaches CoreError; it panics, which crosses the
    // FFI as `CoreBug` (AD-4).
    let stage = match stage {
        "tokens" => regolith_syntax::debug::Stage::Tokens,
        "cst" => regolith_syntax::debug::Stage::Cst,
        "ast" => regolith_syntax::debug::Stage::Ast,
        other => panic!("unknown debug stage {other:?}: expected tokens|cst|ast"),
    };
    let source = std::fs::read_to_string(path).map_err(|e| CoreError::Io {
        path: path.to_path_buf(),
        message: e.to_string(),
    })?;
    Ok(regolith_syntax::debug::dump(
        stage,
        &source,
        &path.to_path_buf(),
    ))
}

/// Dump the `regolith debug ir` report for the sources at `paths`
/// (WO-42 deliverable 3, AD-25's inspectability item): runs `check()`
/// over the given roots and renders a summary of the compiler's own IR
/// stages (obligation/snapshot/feature-program counts) plus a section
/// listing every realized-domain IR SUPPLIED to the build -- kind,
/// digest, subject -- so a build with realized inputs is inspectable
/// exactly like every other pipeline stage (AD-13). An empty
/// `realized_inputs` renders an explicit "(none supplied)" line rather
/// than an empty section, naming the D128 placeholder path.
///
/// # Errors
/// Returns [`CoreError`] only for infrastructure failures (unreadable
/// source), never for a failing check (AD-7).
///
/// # Panics
/// Never in practice: `BuildOutput::payload_json` always emits our own
/// JSON-safe `BuildPayload` shape, so re-parsing it back can only fail
/// on a programmer bug (a payload/schema drift), worth a panic here.
// frob:doc docs/modules/regolith-api.md#debug-dump-and-debug-ir
pub fn debug_ir(
    paths: &[&Utf8Path],
    realized_inputs: &regolith_lower::RealizedInputs,
) -> Result<String, CoreError> {
    use std::fmt::Write as _;

    let session = Session::open_files(paths.iter().map(|p| (*p).to_path_buf()));
    let out = session.check(realized_inputs)?;
    let payload: BuildPayload =
        serde_json::from_slice(&out.payload_json()).expect("BuildOutput payload is valid JSON");

    let mut text = String::new();
    text.push_str("== compiler IR ==\n");
    let _ = writeln!(text, "obligations: {}", payload.obligations.len());
    let _ = writeln!(text, "snapshots: {}", payload.snapshots.len());
    let _ = writeln!(text, "feature_programs: {}", payload.feature_programs.len());
    // WO-48 deliverable 3 acceptance: the `frame` payload is inspectable
    // through this same report (AD-13), exactly like every other
    // pipeline-stage count above.
    let _ = writeln!(text, "frames: {}", payload.frames.len());
    text.push_str("\n== realized IRs supplied ==\n");
    if realized_inputs.is_empty() {
        text.push_str("(none supplied)\n");
    } else {
        for (digest, input) in realized_inputs {
            let _ = writeln!(
                text,
                "kind={} digest={digest} subject={}",
                input.kind, input.subject
            );
        }
    }
    Ok(text)
}

/// Every `on <event>:` trigger name declared per subject, across the
/// sources at `paths` (WO-37 close-out follow-up, the repo's queue
/// file): the
/// firmware realizer's typed event surface, replacing
/// `EventDecl`'s forward-authored placeholder (AD-22) with real
/// `OnBlock` CST data. Thin parse-and-delegate, matching
/// `debug_dump`'s shape; the actual extraction lives in
/// `regolith_lower::converter::collect_on_events`.
///
/// # Errors
/// Returns [`CoreError`] if a source file cannot be read.
// frob:doc docs/modules/regolith-api.md#event-surface-extraction
pub fn on_events(paths: &[&Utf8Path]) -> Result<Vec<(String, String)>, CoreError> {
    let mut files = Vec::with_capacity(paths.len());
    for path in paths {
        let text = std::fs::read_to_string(path).map_err(|e| CoreError::Io {
            path: path.to_path_buf(),
            message: e.to_string(),
        })?;
        let parse = regolith_syntax::parse(&text, &path.to_path_buf());
        files.push(regolith_lower::ParsedFile {
            path: path.to_path_buf(),
            parse,
        });
    }
    Ok(regolith_lower::converter::collect_on_events(&files))
}

/// Resolve a custom extrusion section's radiused tangent-arc walk into
/// its closed outline + per-arc endpoints (F123/D231/WO116-F1), for the
/// `saw_stock(extrusion(<profile>, l=<len>))` realizer path. Parses the
/// sources at `paths`, finds `profile <profile>`'s walk, promotes it
/// (`sketch_closure_from_walk`), and resolves the outline with the
/// closed-form `arc_chord` math (`regolith_ir::solve::sketch::
/// resolve_outline`) -- so the arc geometry stays single-sourced in
/// Rust, never recomputed in Python (D205), and no versioned schema
/// shape changes (D231's bump is spent): the result crosses as a
/// marshalled JSON string, the `obligation_content_hashes` precedent.
///
/// Returns `Ok(Some(json))` with the resolved outline when the profile
/// exists and is fully determined (every straight leg pinned, every arc
/// radius-captured); `Ok(None)` (an honest skip, never a guess) when the
/// profile is missing, unpromotable, or not fully determined.
///
/// # Errors
/// Returns [`CoreError::Io`] if a source file cannot be read.
// frob:doc docs/modules/regolith-api.md#extrusion-outline-resolution
pub fn resolve_extrusion_outline(
    paths: &[&Utf8Path],
    profile: &str,
) -> Result<Option<String>, CoreError> {
    use regolith_ir::sketch::WalkPromotion;
    let mut files = Vec::with_capacity(paths.len());
    for path in paths {
        let text = std::fs::read_to_string(path).map_err(|e| CoreError::Io {
            path: path.to_path_buf(),
            message: e.to_string(),
        })?;
        let parse = regolith_syntax::parse(&text, &path.to_path_buf());
        files.push(regolith_lower::ParsedFile {
            path: path.to_path_buf(),
            parse,
        });
    }
    let walks = regolith_lower::feature_program::profile_walks(&files);
    let Some(walk) = walks.get(profile) else {
        tracing::info!(
            profile,
            "extrusion outline: profile not found (honest skip)"
        );
        return Ok(None);
    };
    let WalkPromotion::Promoted(closure) =
        regolith_ir::sketch::sketch_closure_from_walk(profile, walk)
    else {
        tracing::info!(
            profile,
            "extrusion outline: walk not promotable (honest skip)"
        );
        return Ok(None);
    };
    let Some(outline) = regolith_ir::solve::sketch::resolve_outline(&closure) else {
        tracing::info!(
            profile,
            "extrusion outline: walk not fully determined (honest skip)"
        );
        return Ok(None);
    };
    let json = serde_json::to_string(&outline)
        .map_err(|e| CoreError::CacheCorrupt(format!("resolved outline JSON: {e}")))?;
    Ok(Some(json))
}

/// The compiler core version -- the workspace package version, the one
/// truth the Python `regolith.core_version()` smoke test reads back.
// frob:doc docs/modules/regolith-api.md#version-and-extension-registry-accessors
#[must_use]
pub fn core_version() -> &'static str {
    let version = env!("CARGO_PKG_VERSION");
    tracing::debug!(version, "core_version requested");
    version
}

/// The serialized-schema version the boundary is speaking (AD-5). The
/// facade asserts this against the generated pydantic models at import.
// frob:doc docs/modules/regolith-api.md#version-and-extension-registry-accessors
#[must_use]
pub fn schema_version() -> u32 {
    regolith_oblig::SCHEMA_VERSION
}

/// Every recognized `(extension, language)` pair, read from the ONE
/// registry (`regolith-syntax::extension`, ground rule 6 / AD-14) so
/// `magnetite new` never hard-codes an extension string (WO-41's
/// tripwire). `language` is the lower-case variant name (`"hematite"`,
/// `"cuprite"`, `"fluorite"`).
// frob:doc docs/modules/regolith-api.md#version-and-extension-registry-accessors
#[must_use]
pub fn extensions() -> Vec<(&'static str, &'static str)> {
    regolith_syntax::EXTENSIONS
        .iter()
        .map(|&(ext, lang)| {
            let name = match lang {
                regolith_syntax::Language::Hematite => "hematite",
                regolith_syntax::Language::Cuprite => "cuprite",
                regolith_syntax::Language::Fluorite => "fluorite",
                regolith_syntax::Language::Calcite => "calcite",
            };
            (ext, name)
        })
        .collect()
}

/// The AD-18 canonical content hash of every obligation in
/// `obligations_json` (a JSON array of `Obligation`, exactly the
/// `BuildPayload.obligations` wire shape), in the array's own order.
///
/// This is the ONE encoder (AD-18) exposed for the Python release gate:
/// a `WaiveLedger` entry records the obligations it accepted by content
/// hash (`WaiverRecord.matched`), and the gate needs the SAME hash per
/// discharge result to decide which results a deviation accepts.
/// Reproducing the canonical CBOR address in Python would be a second
/// encoder (forbidden, AD-18), so the address is computed here and
/// marshalled across.
///
/// # Errors
/// Returns [`CoreError::CacheCorrupt`] if `obligations_json` is not a
/// valid `Vec<Obligation>` -- a boundary-contract violation by the
/// caller (the payload it passes is always core-produced), surfaced as
/// a value rather than a panic.
// frob:doc docs/modules/regolith-api.md#obligation-content-hashes
pub fn obligation_content_hashes(obligations_json: &str) -> Result<Vec<String>, CoreError> {
    let obligations: Vec<regolith_oblig::Obligation> = serde_json::from_str(obligations_json)
        .map_err(|e| CoreError::CacheCorrupt(format!("obligations JSON: {e}")))?;
    Ok(obligations
        .iter()
        .map(regolith_oblig::Obligation::content_hash)
        .collect())
}

#[cfg(test)]
mod tests {
    use camino::Utf8PathBuf;

    #[test]
    fn core_version_matches_cargo() {
        assert_eq!(super::core_version(), env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn schema_version_exposed() {
        assert_eq!(
            super::schema_version(),
            regolith_util::canon::SCHEMA_VERSION
        );
    }

    /// `reduce_unit_literal` reduces a recognized unit to its SI base
    /// magnitude through the ONE unit engine, and honestly returns
    /// `None` for a symbol the table does not know (a log-ratio unit
    /// like dBm is not a linear SI unit, never a guessed reduction).
    // frob:tests crates/regolith-api/src/lib.rs::reduce_unit_literal kind="unit"
    #[test]
    fn reduce_unit_literal_reduces_known_unit_and_honestly_skips_unknown() {
        let rad = super::reduce_unit_literal(500.0, "mrad").unwrap();
        assert!((rad - 0.5).abs() < 1e-12);
        assert_eq!(super::reduce_unit_literal(1.0, "dBm"), None);
    }

    /// `debug_dump` thinly delegates to the syntax crate's own stage
    /// dumper (AD-13): a real `.hema` source's `tokens` stage dumps a
    /// non-empty text report and reads back the source content.
    // frob:tests crates/regolith-api/src/lib.rs::debug_dump kind="unit"
    #[test]
    fn debug_dump_dumps_the_tokens_stage_for_real_source() {
        let dir = std::env::temp_dir().join(format!("regolith-wo01-dump-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("m.hema");
        std::fs::write(&file, "part Widget:\n  mass: 5 g\n").unwrap();

        let text = super::debug_dump("tokens", file.as_path()).unwrap();
        assert!(!text.is_empty());
        assert!(text.contains("Widget"));

        std::fs::remove_dir_all(&dir).ok();
    }

    /// `resolve_extrusion_outline` is an honest `Ok(None)` skip -- never
    /// a guess -- when the named profile does not exist in the source
    /// (F123/D231/WO116-F1's missing-profile case).
    // frob:tests crates/regolith-api/src/lib.rs::resolve_extrusion_outline kind="unit"
    #[test]
    fn resolve_extrusion_outline_honestly_skips_a_missing_profile() {
        let dir = std::env::temp_dir().join(format!("regolith-wo116-extr-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("m.hema");
        std::fs::write(&file, "part Widget:\n  mass: 5 g\n").unwrap();

        let out = super::resolve_extrusion_outline(&[file.as_path()], "NoSuchProfile").unwrap();
        assert_eq!(out, None);

        std::fs::remove_dir_all(&dir).ok();
    }

    /// `obligation_content_hashes` hashes a JSON array of real
    /// `Obligation` values in array order, and the ONE encoder is
    /// deterministic across repeated calls over the same input (AD-18).
    // frob:tests crates/regolith-api/src/lib.rs::obligation_content_hashes kind="unit"
    #[test]
    fn obligation_content_hashes_hashes_a_json_array_of_obligations() {
        use regolith_oblig::{Claim, ClaimForm, Given, Obligation};

        let obligation = Obligation {
            claim: Claim {
                name: Some("wall_temp".to_string()),
                form: ClaimForm::Compute {
                    quantity_kind: "thermo.wall_temperature".to_string(),
                    over: "liner.zones".to_string(),
                },
                forall: vec![],
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: vec![],
                model_pin: None,
            },
            subject_ref: "blake3:subject".to_string(),
            given: Given {
                materials: vec![],
                loads: vec![],
                backing: vec![],
                refs: vec![],
            },
            hints: vec![],
            sweep: None,
            payloads: vec![],
        };
        let json = serde_json::to_string(std::slice::from_ref(&obligation)).unwrap();

        let hashes = super::obligation_content_hashes(&json).unwrap();
        assert_eq!(hashes, vec![obligation.content_hash()]);

        let hashes_again = super::obligation_content_hashes(&json).unwrap();
        assert_eq!(hashes, hashes_again, "AD-18 hashing is deterministic");
    }

    /// Malformed input is a `CoreError::CacheCorrupt` value, never a
    /// panic -- a boundary-contract violation surfaced as data (AD-7).
    #[test]
    fn obligation_content_hashes_reports_malformed_json_as_an_error() {
        assert!(super::obligation_content_hashes("not json").is_err());
    }

    /// WO-42 deliverable 3: `debug ir` lists no realized IRs when none
    /// were supplied (the D128 placeholder path stays honest about it).
    // frob:tests crates/regolith-api/src/session.rs::Session.open_files kind="unit"
    #[test]
    fn debug_ir_reports_no_realized_inputs_when_none_supplied() {
        let dir = std::env::temp_dir().join(format!("regolith-wo42-dbg-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

        let empty = regolith_lower::RealizedInputs::new();
        let file = dir.join("m.hema");
        let text = super::debug_ir(&[file.as_path()], &empty).unwrap();
        assert!(text.contains("(none supplied)"));

        std::fs::remove_dir_all(&dir).ok();
    }

    /// WO-37 close-out follow-up: `on_events` reads real `.cupr` source
    /// and returns the typed `on <event>:` trigger names, not a
    /// hand-authored placeholder.
    // frob:tests crates/regolith-api/src/lib.rs::on_events kind="unit"
    #[test]
    fn on_events_reads_real_on_block_cst() {
        let dir = std::env::temp_dir().join(format!("regolith-wo37-events-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("m.cupr"),
            "block Regulator:\n    ports:\n        ctrl_clk: clock(200kHz)\n    spec:\n        on ctrl_clk.rise:\n            a = b\n",
        )
        .unwrap();

        let file = dir.join("m.cupr");
        let events = super::on_events(&[file.as_path()]).unwrap();
        assert_eq!(
            events,
            vec![("Regulator".to_string(), "ctrl_clk".to_string())]
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    /// A supplied realized IR is listed with its kind, digest, subject.
    #[test]
    fn debug_ir_lists_every_supplied_realized_input() {
        let dir = std::env::temp_dir().join(format!("regolith-wo42-dbg2-{}", std::process::id()));
        let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

        let mut realized = regolith_lower::RealizedInputs::new();
        realized.insert(
            "blake3:aa".to_string(),
            regolith_lower::RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: "Widget".to_string(),
                bytes: vec![1, 2, 3],
            },
        );
        let file = dir.join("m.hema");
        let text = super::debug_ir(&[file.as_path()], &realized).unwrap();
        assert!(text.contains("kind=geometry.realized"));
        assert!(text.contains("digest=blake3:aa"));
        assert!(text.contains("subject=Widget"));

        std::fs::remove_dir_all(&dir).ok();
    }
}
