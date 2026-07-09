"""WO-43 `regolith build [--release]` CLI verb: end-to-end subprocess tests
(the system-tester pattern, `tests/test_smoke.py`'s own precedent) --
exact exit codes and the stdout/stderr split over the REAL console
entry point, not `CliRunner` (which does not exercise a real process
boundary or prove logs never leak onto stdout, AD-10).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_CLEAN_MANIFEST = '[package]\nname = "wo43-clean"\n'
_CLEAN_SOURCE = "part p:\n    a: 1mm\n"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "regolith.cli", *args],
        capture_output=True,
        text=True,
    )


def _clean_project(tmp_path: Path) -> Path:
    (tmp_path / "magnetite.toml").write_text(_CLEAN_MANIFEST)
    source = tmp_path / "trivial.hema"
    source.write_text(_CLEAN_SOURCE)
    return source


def test_build_release_over_a_clean_project_exits_zero_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    source = _clean_project(tmp_path)
    out_dir = tmp_path / "out"
    result = _run("build", str(source), "--release", "--out", str(out_dir))

    assert result.returncode == 0, result.stderr
    assert (out_dir / "regolith.lock").is_file()
    assert (out_dir / "build_report.json").is_file()
    report = json.loads((out_dir / "build_report.json").read_text())
    assert report["final"]["ok"] is True
    assert report["final"]["release_ok"] is True
    # AD-10: stdout is data, never a log line.
    assert "lower." not in result.stdout
    assert "parse; files=" not in result.stdout


def test_build_release_over_a_violated_fixture_exits_nonzero_with_refusal_on_stdout(
    tmp_path: Path,
) -> None:
    violated = tmp_path / "broken.hema"
    violated.write_text("part p:\n    a: [1mm .. 3]\n")
    out_dir = tmp_path / "out"
    result = _run("build", str(violated), "--release", "--out", str(out_dir))

    assert result.returncode != 0
    assert "E0103" in result.stdout
    assert "lower." not in result.stdout


def test_build_json_report_is_valid_json_on_stdout(tmp_path: Path) -> None:
    source = _clean_project(tmp_path)
    out_dir = tmp_path / "out"
    result = _run("build", str(source), "--release", "--out", str(out_dir), "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["final"]["ok"] is True


def test_build_release_then_ship_build_is_the_two_command_demo(tmp_path: Path) -> None:
    """`regolith build --release --out DIR` then `regolith ship --build DIR
    --out DIR2` is the two-command corpus demo WO-43 exists to make
    possible (WO-25's first named blocker) -- `ship` here consumes the
    prior build's outputs without re-running the pipeline (deliverable 3).
    """
    source = _clean_project(tmp_path)
    build_dir = tmp_path / "build"
    build_result = _run("build", str(source), "--release", "--out", str(build_dir))
    assert build_result.returncode == 0, build_result.stderr

    ship_dir = tmp_path / "ship"
    ship_result = _run(
        "ship", str(source), "--build", str(build_dir), "--out", str(ship_dir)
    )
    assert ship_result.returncode == 0, ship_result.stderr
    assert (ship_dir / "manifest.json").is_file()
    assert "lower." not in ship_result.stdout


def test_build_unknown_tier_is_an_internal_error(tmp_path: Path) -> None:
    source = _clean_project(tmp_path)
    result = _run("build", str(source), "--tier", "nonsense")
    assert result.returncode == 2
