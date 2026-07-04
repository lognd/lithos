"""WO-18 acceptance: the FFI bridge's panic/error/logging contracts.

Covers: schema_version assertion holds at import; a deliberate panic
crosses as `CoreBug`; an infrastructure failure crosses as a typani
`Err(CoreFailure)`, never an exception; and Rust `tracing` spans from
the real `check()` pipeline arrive as Python log records (AD-8).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from rockhead import _core, compiler
from rockhead._schema import SCHEMA_VERSION


def test_schema_version_matches_core() -> None:
    """The facade's import-time assertion (AD-5) holds for the real wheel."""
    assert _core.schema_version() == SCHEMA_VERSION


def test_unknown_debug_stage_is_a_core_bug_not_a_crash() -> None:
    """An invalid stage name is a programmer bug: `CoreBug`, process survives."""
    with pytest.raises(_core.CoreBug):
        compiler.debug_dump("not-a-real-stage", "examples/cubesat/structure.hem")
    # The process is alive to keep asserting -- the kill test's real proof.
    assert _core.core_version() == "0.1.0"


def test_missing_root_is_a_typani_err_never_an_exception() -> None:
    """An unreadable root surfaces as `Err(CoreFailure)`, not a raised error."""
    result = compiler.check(("examples/this-path-does-not-exist",))
    assert result.is_err
    failure = result.danger_err
    assert failure.kind == "Io"
    assert "examples/this-path-does-not-exist" in failure.message


def test_check_over_real_examples_is_ok_shaped() -> None:
    """A real source tree returns an `Ok(BuildOutcome)` regardless of verdict."""
    result = compiler.check(("examples/cubesat",))
    assert result.is_ok
    outcome = result.danger_ok
    assert isinstance(outcome.ok, bool)
    assert isinstance(outcome.rendered, str)
    assert isinstance(outcome.payload_json, bytes)


def test_rust_pass_spans_reach_python_logging() -> None:
    """`check()`'s per-file parse span logs and arrives via pyo3-log."""
    env = {**os.environ, "ROCKHEAD_LOG": "DEBUG"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from rockhead import compiler; compiler.check(('examples/cubesat',))",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "parsed source file" in result.stderr, result.stderr
    assert result.stdout == ""
