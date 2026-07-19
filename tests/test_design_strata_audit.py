from __future__ import annotations

"""Integration check binding `design/lithos.strata` (the T-0034 system
model: 10 nodes / 14 flows / 9 claims, the AD-4 ffi-bridge seam and
AD-43 layer boundaries) to the repo it models: runs `frob sys audit .`
as a real subprocess and asserts zero UNWAIVED gaps, so model/code
drift breaks loudly here instead of the model quietly going stale.
Follows the feldspar/graphite precedent test verbatim in shape."""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("frob") is None, reason="frob CLI not on PATH"
)


# frob:tests design kind="integration"
def test_sys_audit_reports_zero_unwaived_gaps() -> None:
    """`frob sys audit .` completes and reports PROVED / zero unwaived
    gaps against the committed model; a new unwaived gap means the
    model or the code moved without a ticket."""
    result = subprocess.run(
        ["frob", "sys", "audit", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined[-2000:]
    assert "zero UNWAIVED" in combined or "0 unwaived" in combined, (
        combined[-2000:]
    )
