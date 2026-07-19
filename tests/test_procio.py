"""Tests for `regolith.procio`, the ONE process-invocation seam (WO-153).

Subprocess-free where possible (not-found is naturally subprocess-free:
a nonexistent binary path); the timeout case spawns a real, trivial
``sleep`` child on purpose (there is no honest way to fake a wall-clock
timeout without spawning something).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from regolith import procio, toolenv


class _EchoModel(BaseModel):
    """A trivial pydantic model `expect_json` can validate stdout against."""

    model_config = ConfigDict(frozen=True)

    value: int


def test_run_argv_missing_binary_is_not_found_no_auto_install(tmp_path: Path) -> None:
    """A nonexistent binary is `Err(ToolFailure(kind="not_found"))`, never
    an exception, and never an install attempt (there is nothing to
    install here -- procio itself never shells out to a package manager)."""
    result = procio.run_argv(
        ("/nonexistent/procio-fixture-binary",), timeout_s=5.0, tool="fixture"
    )
    assert result.is_err
    fail = result.danger_err
    assert fail.kind == "not_found"
    assert fail.returncode is None


def test_run_argv_timeout_reports_kind_timeout() -> None:
    """A child that outlives `timeout_s` yields `Err(ToolFailure(kind="timeout"))`."""
    result = procio.run_argv(("sleep", "5"), timeout_s=0.2, tool="sleep")
    assert result.is_err
    fail = result.danger_err
    assert fail.kind == "timeout"
    assert fail.returncode is None


# frob:tests python/regolith/orchestrator/planner.py::PlannerAdapter.what
def test_run_argv_nonzero_exit_is_ok_not_an_error() -> None:
    """A nonzero exit is NOT a `run_argv`-level failure -- callers with
    their own exit-code semantics (AD-19's adapter, the layout wrapper)
    need the raw `ToolOutput` to decide what a given code means."""
    result = procio.run_argv(("false",), timeout_s=5.0, tool="false")
    assert result.is_ok
    assert result.danger_ok.returncode != 0


def test_run_tool_missing_binary_is_not_found_teaching_message(
    tmp_path: Path, monkeypatch
) -> None:
    """`run_tool` resolves through `toolenv` FIRST -- a missing binary
    never reaches a spawn attempt, and its `ToolFailure` carries the
    tool's own teaching message (name + capability + install hint)."""

    def fake_resolve(name: str, **kwargs: object) -> toolenv.ToolStatus:
        spec = toolenv.spec_for(name)
        assert spec is not None
        return toolenv.ToolStatus(spec=spec, path=None, version=None)

    monkeypatch.setattr(toolenv, "resolve", fake_resolve)

    class _NullArgs(procio.ToolArgs):
        def emit(self) -> tuple[str, ...]:
            return ()

    result = procio.run_tool("verilator", _NullArgs(), cwd=tmp_path, timeout_s=5.0)
    assert result.is_err
    fail = result.danger_err
    assert fail.kind == "not_found"
    assert "verilator" in fail.stderr_excerpt
    assert "apt" in fail.stderr_excerpt or "conda-forge" in fail.stderr_excerpt


def test_run_tool_nonzero_exit_is_a_tool_failure(tmp_path: Path, monkeypatch) -> None:
    """Unlike `run_argv`, `run_tool` DOES treat a nonzero exit as a
    `ToolFailure` -- the generalized one-shot pass/fail shape verilator
    and kicad-cli verbs want."""

    def fake_resolve(name: str, **kwargs: object) -> toolenv.ToolStatus:
        spec = toolenv.spec_for(name)
        assert spec is not None
        return toolenv.ToolStatus(spec=spec, path="/bin/false", version=None)

    monkeypatch.setattr(toolenv, "resolve", fake_resolve)

    class _NullArgs(procio.ToolArgs):
        def emit(self) -> tuple[str, ...]:
            return ()

    result = procio.run_tool("verilator", _NullArgs(), cwd=tmp_path, timeout_s=5.0)
    assert result.is_err
    assert result.danger_err.kind == "nonzero"


def test_expect_json_malformed_stdout_is_err_not_raised() -> None:
    """Malformed JSON on stdout is `Err(ToolFailure)`, never a raised
    `pydantic.ValidationError` escaping the seam."""
    output = procio.ToolOutput(
        tool="fixture", argv=("fixture",), returncode=0, stdout=b"not json"
    )
    result = procio.expect_json(output, _EchoModel)
    assert result.is_err
    assert result.danger_err.kind == "nonzero"


def test_expect_json_valid_stdout_validates() -> None:
    output = procio.ToolOutput(
        tool="fixture", argv=("fixture",), returncode=0, stdout=b'{"value": 42}'
    )
    result = procio.expect_json(output, _EchoModel)
    assert result.is_ok
    assert result.danger_ok.value == 42


def test_verilator_lint_args_emit_matches_flag_shape() -> None:
    args = procio.VerilatorLintArgs(filename="top.sv", is_sv=True)
    assert args.emit() == (
        "--lint-only",
        "-Wall",
        "-Wno-DECLFILENAME",
        "--timing",
        "-sv",
        "top.sv",
    )


def test_kicad_drc_args_emit_matches_flag_shape() -> None:
    args = procio.KicadDrcArgs(
        output_path="/tmp/x.drc.json", pcb_path="/tmp/x.kicad_pcb"
    )
    assert args.emit() == (
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-error",
        "--output",
        "/tmp/x.drc.json",
        "/tmp/x.kicad_pcb",
    )


def test_legacy_bytes_runner_never_raises_on_nonzero_exit() -> None:
    """`legacy_bytes_runner` matches `subprocess.run(check=False)`'s own
    contract: a nonzero exit is returned, never raised."""
    completed = procio.legacy_bytes_runner(["false"], timeout=5.0)
    assert completed.returncode != 0


def test_legacy_bytes_runner_raises_file_not_found_on_missing_binary() -> None:
    try:
        procio.legacy_bytes_runner(["/nonexistent/procio-fixture-binary"], timeout=5.0)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
