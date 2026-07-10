"""`regolith preview` CLI verb (D197, cycle 33 design log): end-to-end
subprocess tests over the REAL console entry point (the `test_cli_build
.py` precedent) -- exact exit codes, the honesty stamp, and that no
ship-only artifact (manifest/signing/BOM/fab-note) ever appears.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_CLEAN_MANIFEST = '[package]\nname = "wo-preview-clean"\n'
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


def _dirty_fluid_project(tmp_path: Path) -> Path:
    """The scaffolded `fluid` template: an unresolved `conforms`
    obligation by construction (WO-12 cut), same stable "gate is never
    clean" fixture `test_cli_build.py`'s `test_ship_refused_release_gate
    _exits_nonzero` already relies on."""
    from regolith.magnetite.scaffold import scaffold_project

    scaffolded = scaffold_project("refused", "fluid", parent=tmp_path)
    assert scaffolded.is_ok, scaffolded
    return scaffolded.danger_ok


def test_preview_on_a_dirty_project_produces_artifacts_and_the_stamp_and_exits_zero(
    tmp_path: Path,
) -> None:
    project = _dirty_fluid_project(tmp_path)
    out_dir = tmp_path / "preview"
    result = _run("preview", str(project), "--out", str(out_dir))

    assert result.returncode == 0, result.stderr
    gate_summary = json.loads((out_dir / "gate_summary.json").read_text())
    assert gate_summary["release_ok"] is False
    assert (
        gate_summary["counts"]["indeterminate"] + gate_summary["counts"]["violated"] > 0
    )

    drawing_files = list((out_dir / "drawings").glob("*.drawing.json"))
    assert drawing_files, "preview must write at least one sheet/graph artifact"
    model = json.loads(drawing_files[0].read_text())
    stamp_texts = [a["text"] for a in model["sheets"][0]["annotations"]]
    assert any(t.startswith("PREVIEW -- NOT RELEASED:") for t in stamp_texts)


def test_preview_never_writes_manifest_or_signing_or_bom(tmp_path: Path) -> None:
    project = _dirty_fluid_project(tmp_path)
    out_dir = tmp_path / "preview"
    result = _run("preview", str(project), "--out", str(out_dir))

    assert result.returncode == 0, result.stderr
    assert not (out_dir / "manifest.json").exists()
    written = {p.name for p in out_dir.rglob("*") if p.is_file()}
    assert not any("bom" in name.lower() for name in written)
    assert not any("fab_note" in name.lower() for name in written)


def test_preview_on_a_clean_project_stamps_release_clean(tmp_path: Path) -> None:
    source = _clean_project(tmp_path)
    out_dir = tmp_path / "preview"
    result = _run("preview", str(source), "--out", str(out_dir))

    assert result.returncode == 0, result.stderr
    gate_summary = json.loads((out_dir / "gate_summary.json").read_text())
    assert gate_summary["release_ok"] is True
    assert gate_summary["counts"]["violated"] == 0
    assert gate_summary["counts"]["indeterminate"] == 0


def test_preview_unknown_tier_is_an_internal_error(tmp_path: Path) -> None:
    source = _clean_project(tmp_path)
    result = _run("preview", str(source), "--out", str(tmp_path / "out"), "--tier", "x")
    assert result.returncode == 2


def test_ship_behavior_unchanged_manifest_only_when_no_backends(tmp_path: Path) -> None:
    """Ship-refactor regression guard: `ship` still writes a signed/
    unsigned manifest-only package (no drawings backend configured)
    exactly as before D197's shared-helper extraction."""
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
