"""WO-93 D196.2 artifact bar: `regolith preview --out` over the real
cubesat flagship produces its sheet/graph set stamped with the
honest gate state, mirroring `tests/test_cli_preview.py`'s real
subprocess recipe (not a synthetic fixture) for the promoted
flagship.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "regolith.cli", *args],
        capture_output=True,
        text=True,
    )


def test_cubesat_preview_produces_contract_graph_stamped_not_released(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "preview"
    result = _run("preview", "examples/flagships/cubesat", "--out", str(out_dir))

    assert result.returncode == 0, result.stderr
    gate_summary = json.loads((out_dir / "gate_summary.json").read_text())
    # cubesat carries honest deferrals fleet-wide (D196.2 baseline); the
    # artifact bar is "preview succeeds with artifacts", never "the
    # gate happens to be clean".
    assert gate_summary["release_ok"] is False
    assert gate_summary["counts"]["indeterminate"] > 0

    drawing_files = list((out_dir / "drawings").glob("*.drawing.json"))
    assert drawing_files, "preview must write at least the contract-graph sheet"
    names = {p.name for p in drawing_files}
    assert "contract_graph.drawing.json" in names

    model = json.loads(
        (out_dir / "drawings" / "contract_graph.drawing.json").read_text()
    )
    stamp_texts = [a["text"] for a in model["sheets"][0]["annotations"]]
    assert any(t.startswith("PREVIEW -- NOT RELEASED:") for t in stamp_texts)

    # ship-only artifacts never appear from preview.
    assert not (out_dir / "manifest.json").exists()
    written = {p.name for p in out_dir.rglob("*") if p.is_file()}
    assert not any("bom" in name.lower() for name in written)
