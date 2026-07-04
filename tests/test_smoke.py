"""Day-one cross-boundary smoke tests (WO-01 acceptance).

Proves the Rust->Python crossing works and that the pyo3-log bridge
(AD-8) delivers core log records to Python ``logging``.
"""

from __future__ import annotations

import os
import subprocess
import sys

import regolith


def test_core_version_crosses_boundary() -> None:
    """`import regolith; regolith.core_version()` returns the workspace version."""
    assert regolith.core_version() == "0.1.0"


def test_console_script_reports_version() -> None:
    """The installed `regolith version` console command prints the version."""
    result = subprocess.run(
        [sys.executable, "-m", "regolith.cli", "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "0.1.0"


def test_rust_log_records_reach_python_logging() -> None:
    """A Rust core call emits a record delivered via the pyo3-log bridge.

    Run in a subprocess with ``REGOLITH_LOG=DEBUG`` set from the start so
    pyo3-log caches the debug level; the record renders on stderr,
    leaving stdout clean.
    """
    env = {**os.environ, "REGOLITH_LOG": "DEBUG"}
    result = subprocess.run(
        [sys.executable, "-c", "import regolith; regolith.core_version()"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "core_version requested" in result.stderr, result.stderr
    assert result.stdout == ""
