"""`regolith.harness.models.hdl.verilator_adapter` absent-tool posture.

verilator is REQUIRED for any hdl.* claim (WO-82); its absence must be
a loud, teaching diagnostic -- the tool name, why this design needs
it, and install guidance -- never a bare "not found" string. This
subprocess-free test injects `FileNotFoundError` the same way an
absent binary would raise it, so it passes whether or not the host
actually has verilator installed.
"""

from __future__ import annotations

from pathlib import Path

from regolith.harness.models.hdl import verilator_adapter


def test_run_verilator_missing_binary_is_teaching_diagnostic(
    tmp_path: Path, monkeypatch
) -> None:
    def raise_not_found(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("no such file: verilator")

    monkeypatch.setattr(verilator_adapter.subprocess, "run", raise_not_found)

    result = verilator_adapter.run_verilator(["--version"], cwd=tmp_path)
    assert result.is_err
    message = result.danger_err.stderr_excerpt
    assert "verilator" in message
    assert "apt" in message or "conda-forge" in message
