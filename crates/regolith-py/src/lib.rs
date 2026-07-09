//! The `regolith._core` extension module: PyO3 marshalling ONLY (AD-2).
//!
//! No logic lives here -- every function body is a thin call into
//! `regolith-api`. If a body here grows past marshalling, it belongs in a
//! lower crate. Panic policy (AD-4): every entry point is
//! `catch_unwind`-wrapped so a Rust panic becomes a `regolith.CoreBug`
//! (carrying the panic message); infrastructure failures become a
//! `regolith.CoreError`. A failing build is NEVER an exception -- it is a
//! `BuildOutput` with error diagnostics.
#![allow(unsafe_code)]
// PyO3's generated module glue uses unsafe.
// PyO3 0.22's macros emit a `gil-refs` cfg newer rustc doesn't know; the
// warning is upstream boilerplate, not our code (removed when pyo3 bumps).
#![allow(unexpected_cfgs)]
// PyO3's #[pymethods] wrapper calls `.into()` on our already-`PyErr`
// results; the useless-conversion is in generated glue, not our bodies.
#![allow(clippy::useless_conversion)]

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::Once;

use camino::Utf8PathBuf;
use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

static LOG_INIT: Once = Once::new();

create_exception!(
    _core,
    CoreBug,
    PyException,
    "An unrecoverable programmer bug from the compiler core (a Rust panic \
     crossed the boundary). Never raised for a failing build."
);
create_exception!(
    _core,
    CoreError,
    PyException,
    "An infrastructure failure at the core boundary (unreadable file, \
     corrupt cache). Distinct from a failing build, which is data."
);

/// Run a core call, converting any Rust panic into a `CoreBug` (AD-4).
/// The one guard every entry point funnels through.
fn guard<T>(f: impl FnOnce() -> T) -> PyResult<T> {
    catch_unwind(AssertUnwindSafe(f)).map_err(|payload| {
        let msg = payload
            .downcast_ref::<&str>()
            .map(|s| (*s).to_string())
            .or_else(|| payload.downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "core panicked (no message)".to_string());
        CoreBug::new_err(msg)
    })
}

/// Convert a core infrastructure error into a `CoreError` exception.
fn core_error(err: &regolith_api::CoreError) -> PyErr {
    CoreError::new_err(format!("{err:?}"))
}

/// The result of a build, handed to Python as an opaque handle whose
/// getters marshal the underlying `regolith_api::BuildOutput`.
#[pyclass(name = "BuildOutput")]
struct PyBuildOutput {
    inner: regolith_api::BuildOutput,
}

#[pymethods]
impl PyBuildOutput {
    /// The diagnostics rendered to text (the one renderer, AD-7).
    fn rendered(&self, ansi: bool) -> PyResult<String> {
        guard(|| self.inner.rendered(ansi).to_string())
    }

    /// The structured payload as JSON bytes (parses into pydantic).
    fn payload_json<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let bytes = guard(|| self.inner.payload_json())?;
        Ok(PyBytes::new_bound(py, &bytes))
    }

    /// True when the build produced no error-severity diagnostics.
    fn ok(&self) -> PyResult<bool> {
        guard(|| self.inner.ok())
    }

    /// The number of diagnostics in the build.
    fn diagnostic_count(&self) -> PyResult<usize> {
        guard(|| self.inner.diagnostic_count())
    }
}

/// Marshal the coarse realized-input crossing (WO-42 deliverable 3,
/// AD-4): ONE list of `(digest, kind, subject, bytes)` tuples -- the
/// caller-resolved realized-domain IR bytes for this build, keyed by
/// content digest. A `Vec` (not a `HashMap`) crosses the boundary so
/// PyO3 extraction stays a single coarse conversion with no ordering
/// ambiguity; it is collected into the digest-keyed
/// `regolith_lower::RealizedInputs` map on this side.
fn marshal_realized_inputs(
    realized_inputs: Vec<(String, String, String, Vec<u8>)>,
) -> regolith_lower::RealizedInputs {
    realized_inputs
        .into_iter()
        .map(|(digest, kind, subject, bytes)| {
            (
                digest,
                regolith_lower::RealizedInput {
                    kind,
                    subject,
                    bytes,
                },
            )
        })
        .collect()
}

/// A compile session over a project root or file set (AD-4). Opening does
/// no work; `check`/`compile` run under `allow_threads`.
#[pyclass(name = "CoreSession")]
struct PyCoreSession {
    inner: regolith_api::Session,
}

#[pymethods]
impl PyCoreSession {
    /// Open a session over the given source paths (files or roots).
    #[new]
    fn new(paths: Vec<String>) -> PyResult<Self> {
        guard(|| {
            let files = paths.into_iter().map(Utf8PathBuf::from);
            PyCoreSession {
                inner: regolith_api::Session::open_files(files),
            }
        })
    }

    /// Run the static `check` pipeline. Releases the GIL for the compile
    /// (rayon parallelism is inside Rust, AD-4). `realized_inputs`
    /// (WO-42 deliverable 3) is the caller-resolved realized-domain IR
    /// channel: a list of `(digest, kind, subject, bytes)` tuples,
    /// empty for a build with no realized-domain inputs (the D128
    /// placeholder path).
    #[pyo3(signature = (realized_inputs=Vec::new()))]
    fn check(
        &self,
        py: Python<'_>,
        realized_inputs: Vec<(String, String, String, Vec<u8>)>,
    ) -> PyResult<PyBuildOutput> {
        let realized_inputs = marshal_realized_inputs(realized_inputs);
        let result = py.allow_threads(|| guard(|| self.inner.check(&realized_inputs)));
        match result? {
            Ok(inner) => Ok(PyBuildOutput { inner }),
            Err(e) => Err(core_error(&e)),
        }
    }

    /// Run the full `compile` pipeline. `registry_version` is the harness
    /// model-registry version (Python-side, AD-1), folded into evidence-
    /// cache keys so a model upgrade forces re-verification (BE-1/INV-1).
    /// `realized_inputs` is the same coarse channel `check` takes.
    #[pyo3(signature = (registry_version, realized_inputs=Vec::new()))]
    fn compile(
        &self,
        py: Python<'_>,
        registry_version: &str,
        realized_inputs: Vec<(String, String, String, Vec<u8>)>,
    ) -> PyResult<PyBuildOutput> {
        let realized_inputs = marshal_realized_inputs(realized_inputs);
        let result =
            py.allow_threads(|| guard(|| self.inner.compile(registry_version, &realized_inputs)));
        match result? {
            Ok(inner) => Ok(PyBuildOutput { inner }),
            Err(e) => Err(core_error(&e)),
        }
    }
}

/// The compiler core version -- proves the Rust->Python crossing.
#[pyfunction]
fn core_version() -> PyResult<&'static str> {
    guard(regolith_api::core_version)
}

/// The serialized-schema version the boundary speaks (AD-5).
#[pyfunction]
fn schema_version() -> PyResult<u32> {
    guard(regolith_api::schema_version)
}

/// Format source text into its canonical spelling.
#[pyfunction]
fn format(text: &str) -> PyResult<String> {
    guard(|| regolith_api::format(text))
}

/// Dump an intermediate pipeline stage of a source file as text.
#[pyfunction]
fn debug_dump(stage: &str, path: &str) -> PyResult<String> {
    let path = Utf8PathBuf::from(path);
    match guard(|| regolith_api::debug_dump(stage, &path))? {
        Ok(text) => Ok(text),
        Err(e) => Err(core_error(&e)),
    }
}

/// Dump the `regolith debug ir` report for `paths` (WO-42 deliverable
/// 3): the compiler's own IR-stage summary plus the realized-domain IRs
/// supplied to the build (kind, digest, subject) -- the same coarse
/// `realized_inputs` channel `check`/`compile` take.
#[pyfunction]
#[pyo3(signature = (paths, realized_inputs=Vec::new()))]
fn debug_ir(
    paths: Vec<String>,
    realized_inputs: Vec<(String, String, String, Vec<u8>)>,
) -> PyResult<String> {
    let paths: Vec<Utf8PathBuf> = paths.into_iter().map(Utf8PathBuf::from).collect();
    let refs: Vec<&camino::Utf8Path> = paths.iter().map(camino::Utf8PathBuf::as_path).collect();
    let realized_inputs = marshal_realized_inputs(realized_inputs);
    match guard(|| regolith_api::debug_ir(&refs, &realized_inputs))? {
        Ok(text) => Ok(text),
        Err(e) => Err(core_error(&e)),
    }
}

/// Extract a source file's public-surface doc model as JSON (`regolith
/// doc`, WO-41): one entry per top-level declaration with its kind,
/// name, leading `#` doc comment (verbatim, D115), fields, `require`
/// claim groups, and `budget` statements.
#[pyfunction]
fn doc_extract(path: &str) -> PyResult<String> {
    let path = Utf8PathBuf::from(path);
    match guard(|| regolith_api::doc_extract(&path))? {
        Ok(text) => Ok(text),
        Err(e) => Err(core_error(&e)),
    }
}

/// Every recognized `(extension, language)` pair, read from the ONE
/// registry so Python-side code (`quarry new`) never hard-codes an
/// extension string (ground rule 6 / AD-14).
#[pyfunction]
fn extensions() -> PyResult<Vec<(String, String)>> {
    guard(|| {
        regolith_api::extensions()
            .into_iter()
            .map(|(ext, lang)| (ext.to_string(), lang.to_string()))
            .collect()
    })
}

/// Run the elec net discipline's single-driver check (AD-23 D4;
/// cuprite/06) over `nets_json` (a JSON array of
/// `{"name","pins":[{"component","pin","is_driver"}]}` nets, the
/// `NetlistModel.nets` wire shape). Returns a JSON object: `{"ok":
/// true}` when every net is clean, or `{"ok": false, "net", "drivers",
/// "message"}` naming the first offending net (fail-fast, matching the
/// retired Python implementation byte-for-byte). A malformed
/// `nets_json` is an infrastructure failure (`CoreError`), not a design
/// error.
#[pyfunction]
fn check_elec_single_driver(nets_json: &str) -> PyResult<String> {
    let result = guard(|| regolith_api::check_elec_single_driver(nets_json))?;
    let violation = result.map_err(CoreError::new_err)?;
    let payload = match violation {
        None => serde_json::json!({"ok": true}),
        Some(v) => serde_json::json!({
            "ok": false,
            "net": v.net,
            "drivers": v.drivers,
            "message": v.message,
        }),
    };
    Ok(payload.to_string())
}

/// Every `on <event>:` trigger name declared per subject, across
/// `paths` (WO-37 close-out follow-up): `(declaration, event)` pairs,
/// deduplicated and sorted, so `regolith.realizer.firmware` can build
/// its `EventDecl` list from the real typed `OnBlock` CST instead of a
/// forward-authored placeholder (AD-22).
#[pyfunction]
fn on_events(paths: Vec<String>) -> PyResult<Vec<(String, String)>> {
    let paths: Vec<Utf8PathBuf> = paths.into_iter().map(Utf8PathBuf::from).collect();
    let refs: Vec<&camino::Utf8Path> = paths.iter().map(camino::Utf8PathBuf::as_path).collect();
    match guard(|| regolith_api::on_events(&refs))? {
        Ok(events) => Ok(events),
        Err(e) => Err(core_error(&e)),
    }
}

/// Install the `tracing`/`log` -> Python `logging` bridge (AD-8).
///
/// Idempotent: the underlying global logger may only be set once, so
/// repeat calls (e.g. re-import) are no-ops.
#[pyfunction]
fn init_logging() {
    LOG_INIT.call_once(|| {
        pyo3_log::init();
    });
}

/// PyO3 module initializer for `regolith._core`.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(schema_version, m)?)?;
    m.add_function(wrap_pyfunction!(format, m)?)?;
    m.add_function(wrap_pyfunction!(debug_dump, m)?)?;
    m.add_function(wrap_pyfunction!(debug_ir, m)?)?;
    m.add_function(wrap_pyfunction!(doc_extract, m)?)?;
    m.add_function(wrap_pyfunction!(extensions, m)?)?;
    m.add_function(wrap_pyfunction!(on_events, m)?)?;
    m.add_function(wrap_pyfunction!(check_elec_single_driver, m)?)?;
    m.add_function(wrap_pyfunction!(init_logging, m)?)?;
    m.add_class::<PyCoreSession>()?;
    m.add_class::<PyBuildOutput>()?;
    m.add("CoreBug", m.py().get_type_bound::<CoreBug>())?;
    m.add("CoreError", m.py().get_type_bound::<CoreError>())?;
    // The full binding surface, checked against `_core.pyi` by a
    // stub-consistency pytest (WO-18 deliverable 4).
    m.add(
        "__all__",
        vec![
            "core_version",
            "schema_version",
            "format",
            "debug_dump",
            "debug_ir",
            "doc_extract",
            "extensions",
            "on_events",
            "check_elec_single_driver",
            "init_logging",
            "CoreSession",
            "BuildOutput",
            "CoreBug",
            "CoreError",
        ],
    )?;
    Ok(())
}
