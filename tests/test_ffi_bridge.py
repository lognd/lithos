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
from pathlib import Path

import pytest
from regolith import _core, compiler
from regolith._schema import SCHEMA_VERSION


def test_schema_version_matches_core() -> None:
    """The facade's import-time assertion (AD-5) holds for the real wheel."""
    assert _core.schema_version() == SCHEMA_VERSION


def test_unknown_debug_stage_is_a_core_bug_not_a_crash() -> None:
    """An invalid stage name is a programmer bug: `CoreBug`, process survives."""
    with pytest.raises(_core.CoreBug):
        compiler.debug_dump(
            "not-a-real-stage", "examples/systems/cubesat/structure.hema"
        )
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
    result = compiler.check(("examples/systems/cubesat",))
    assert result.is_ok
    outcome = result.danger_ok
    assert isinstance(outcome.ok, bool)
    assert isinstance(outcome.rendered, str)
    assert isinstance(outcome.payload_json, bytes)


def test_compile_threads_registry_version_across_the_ffi(tmp_path: Path) -> None:
    """BE-1/INV-1: `compile` accepts the harness model-registry version and
    forwards it across the FFI (folded into evidence-cache keys in Rust).

    Real corpus sources discharge no toy evidence (`evidence_count == 0`),
    so the version's effect on individual keys is proven by the Rust unit
    tests (`regolith-oblig`/`regolith-lower`); here we assert the Python
    boundary marshals the argument without error under both the default
    harness version and an explicit override, staying deterministic per
    version (INV-10). Compiles in a scratch dir so the evidence cache is
    written under a throwaway `.regolith/`, never the repo tree."""
    src = tmp_path / "m.hema"
    src.write_text("part Widget:\n  mass: 5 g\n")
    root = (str(tmp_path),)

    default = compiler.compile(root)
    assert default.is_ok, default

    explicit = compiler.compile(root, registry_version="model-registry@9.9.9")
    assert explicit.is_ok, explicit

    again = compiler.compile(root, registry_version="model-registry@9.9.9")
    assert again.danger_ok.payload_json == explicit.danger_ok.payload_json


def test_check_accepts_an_empty_realized_inputs_channel_by_default() -> None:
    """WO-42 deliverable 3: the realized-input channel is optional and
    empty by default (the D128 placeholder path) -- existing callers
    that never pass it keep working unchanged."""
    result = compiler.check(("examples/systems/cubesat",))
    assert result.is_ok


def test_check_threads_a_realized_input_across_the_ffi(tmp_path: Path) -> None:
    """WO-42 deliverable 3: a `compiler.RealizedInput` marshals across the
    coarse FFI crossing (AD-4) without error; a plain hematite source
    with no fluorite flownet ignores it harmlessly (the geometry channel
    only matters to a `from=` fluorite edge)."""
    src = tmp_path / "m.hema"
    src.write_text("part Widget:\n  mass: 5 g\n")

    realized = (
        compiler.RealizedInput(
            digest="blake3:aa",
            kind="geometry.realized",
            subject="Widget",
            payload_bytes=b"{}",
        ),
    )
    result = compiler.check((str(tmp_path),), realized_inputs=realized)
    assert result.is_ok, result


def test_debug_ir_reports_no_realized_inputs_by_default() -> None:
    """`regolith debug ir` (WO-42 deliverable 3) lists the realized IRs
    supplied to a build -- none, when the caller supplies none."""
    result = compiler.debug_ir(("examples/systems/cubesat",))
    assert result.is_ok, result
    assert "(none supplied)" in result.danger_ok


def test_debug_ir_lists_a_supplied_realized_input(tmp_path: Path) -> None:
    src = tmp_path / "m.hema"
    src.write_text("part Widget:\n  mass: 5 g\n")

    realized = (
        compiler.RealizedInput(
            digest="blake3:aa",
            kind="geometry.realized",
            subject="Widget",
            payload_bytes=b"{}",
        ),
    )
    result = compiler.debug_ir((str(tmp_path),), realized_inputs=realized)
    assert result.is_ok, result
    text = result.danger_ok
    assert "kind=geometry.realized" in text
    assert "digest=blake3:aa" in text
    assert "subject=Widget" in text


def test_rust_pass_spans_reach_python_logging() -> None:
    """`check()`'s per-file parse span logs and arrives via pyo3-log."""
    env = {**os.environ, "REGOLITH_LOG": "DEBUG"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from regolith import compiler; "
            "compiler.check(('examples/systems/cubesat',))",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert "parsed source file" in result.stderr, result.stderr
    assert result.stdout == ""
