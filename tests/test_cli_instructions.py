"""`regolith preview`/`ship --spec` assembly-instructions wiring (WO-96,
D199.1): end-to-end subprocess tests over the REAL console entry point
(the `test_cli_preview.py` precedent) -- the "assemblies" spec block
reaches `preview --out`, the instructions steps JSON + document are
written, stamped, and byte-identical across two runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_CLEAN_MANIFEST = '[package]\nname = "wo96-instructions"\n'
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


def _assembly_spec_json() -> dict[str, object]:
    """A two-part `RealizedAssembly` (one fixed root, one placed part) --
    the module's own dict shape, `RealizedAssembly.model_validate`-able
    on the reading side (`_assemblies_from_spec`)."""
    return {
        "com_m": [0.0, 0.0, 0.0],
        "dof_states": {"Base": "fixed", "Arm": "placed"},
        "interferences": [],
        "mass_kg": 1.0,
        "mating_graph_hash": "blake3:cli_test_assembly",
        "parts": [
            {
                "id": "Base",
                "geometry_digest": "blake3:base",
                "transform": {
                    "translation_m": [0.0, 0.0, 0.0],
                    "rotation_deg": [0.0, 0.0, 0.0],
                },
            },
            {
                "id": "Arm",
                "geometry_digest": "blake3:arm",
                "transform": {
                    "translation_m": [0.0, 0.0, 0.02],
                    "rotation_deg": [0.0, 0.0, 0.0],
                },
            },
        ],
    }


def _write_spec(tmp_path: Path) -> Path:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"assemblies": {"gantry": _assembly_spec_json()}}))
    return spec_path


def test_preview_writes_instructions_when_assemblies_block_supplied(
    tmp_path: Path,
) -> None:
    project = _clean_project(tmp_path)
    spec_path = _write_spec(tmp_path)
    out_dir = tmp_path / "preview"
    result = _run(
        "preview", str(project), "--out", str(out_dir), "--spec", str(spec_path)
    )
    assert result.returncode == 0, result.stderr

    steps_path = out_dir / "instructions" / "gantry.steps.json"
    doc_path = out_dir / "instructions" / "gantry.instructions.md"
    assert steps_path.is_file()
    assert doc_path.is_file()

    steps = json.loads(steps_path.read_text())
    assert steps["subject"] == "gantry"
    part_refs = [s["part_ref"] for s in steps["steps"]]
    assert part_refs == ["Base", "Arm"]
    assert steps["stamp"] is not None  # D197 honesty banner, through the model

    doc_text = doc_path.read_text()
    assert "Base" in doc_text
    assert "Arm" in doc_text
    assert steps["stamp"] in doc_text


def test_preview_instructions_are_deterministic_across_two_runs(
    tmp_path: Path,
) -> None:
    project = _clean_project(tmp_path)
    spec_path = _write_spec(tmp_path)
    out_a = tmp_path / "preview_a"
    out_b = tmp_path / "preview_b"

    result_a = _run(
        "preview", str(project), "--out", str(out_a), "--spec", str(spec_path)
    )
    result_b = _run(
        "preview", str(project), "--out", str(out_b), "--spec", str(spec_path)
    )
    assert result_a.returncode == 0, result_a.stderr
    assert result_b.returncode == 0, result_b.stderr

    steps_a = (out_a / "instructions" / "gantry.steps.json").read_bytes()
    steps_b = (out_b / "instructions" / "gantry.steps.json").read_bytes()
    assert steps_a == steps_b

    doc_a = (out_a / "instructions" / "gantry.instructions.md").read_bytes()
    doc_b = (out_b / "instructions" / "gantry.instructions.md").read_bytes()
    assert doc_a == doc_b
