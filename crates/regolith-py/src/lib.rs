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
    /// (rayon parallelism is inside Rust, AD-4).
    fn check(&self, py: Python<'_>) -> PyResult<PyBuildOutput> {
        let result = py.allow_threads(|| guard(|| self.inner.check()));
        match result? {
            Ok(inner) => Ok(PyBuildOutput { inner }),
            Err(e) => Err(core_error(&e)),
        }
    }

    /// Run the full `compile` pipeline. `registry_version` is the harness
    /// model-registry version (Python-side, AD-1), folded into evidence-
    /// cache keys so a model upgrade forces re-verification (BE-1/INV-1).
    fn compile(&self, py: Python<'_>, registry_version: &str) -> PyResult<PyBuildOutput> {
        let result = py.allow_threads(|| guard(|| self.inner.compile(registry_version)));
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
            "init_logging",
            "CoreSession",
            "BuildOutput",
            "CoreBug",
            "CoreError",
        ],
    )?;
    Ok(())
}
