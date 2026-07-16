"""`regolith.harness.models.hdl.verilator_adapter` absent-tool posture.

verilator is REQUIRED for any hdl.* claim (WO-82); its absence must be
a loud, teaching diagnostic -- the tool name, why this design needs
it, and install guidance -- never a bare "not found" string. This
subprocess-free test injects a missing-binary `ToolStatus` at the
`regolith.toolenv` seam `regolith.procio.run_tool` resolves through
(WO-153), so it passes whether or not the host actually has verilator
installed.
"""

from __future__ import annotations

from pathlib import Path

from regolith import toolenv
from regolith.harness.models.hdl import verilator_adapter
from regolith.procio import VerilatorLintArgs


def test_run_verilator_missing_binary_is_teaching_diagnostic(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_resolve(name: str, **kwargs: object) -> toolenv.ToolStatus:
        spec = toolenv.spec_for(name)
        assert spec is not None
        return toolenv.ToolStatus(spec=spec, path=None, version=None)

    monkeypatch.setattr(toolenv, "resolve", fake_resolve)

    result = verilator_adapter.run_verilator(
        VerilatorLintArgs(filename="x.v"), cwd=tmp_path
    )
    assert result.is_err
    message = result.danger_err.stderr_excerpt
    assert "verilator" in message
    assert "apt" in message or "conda-forge" in message
