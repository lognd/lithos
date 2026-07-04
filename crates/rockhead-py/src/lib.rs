//! The `rockhead._core` extension module: PyO3 marshalling ONLY (AD-2).
//!
//! No logic lives here -- every function body is a thin call into
//! `rockhead-api`. If a body here grows past marshalling, it belongs in a
//! lower crate. Panics are caught by PyO3 and surface as exceptions
//! (AD-4); WO-18 adds the `CoreBug`/`CoreError` policy. WO-01 exposes
//! only what the day-one smoke tests cross: `core_version` and
//! `init_logging`.
#![allow(unsafe_code)] // PyO3's generated module glue uses unsafe.

use std::sync::Once;

use pyo3::prelude::*;

static LOG_INIT: Once = Once::new();

/// The compiler core version -- proves the Rust->Python crossing.
#[pyfunction]
fn core_version() -> &'static str {
    rockhead_api::core_version()
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

/// PyO3 module initializer for `rockhead._core`.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(core_version, m)?)?;
    m.add_function(wrap_pyfunction!(init_logging, m)?)?;
    Ok(())
}
