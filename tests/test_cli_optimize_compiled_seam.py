"""PROOF-F2 (WO-116, cycle-34 residue): `regolith optimize` gains the
compiled `choice_points` seam, replacing the `--spec` placeholder path
for a caller who has a real compiled design.

`--spec` still exists (hand-built domains, unchanged, WO-56 doc'd
placeholder); the new `--costs` flag pairs a closed-form cost table
with PROJECT's REAL `BuildPayload.choice_points` (compiled fresh via
`compiler.check`, never hand-supplied) through
`regolith.orchestrator.optimize.domains_from_choice_points` -- the
seam the WO-55 close-out ledger documented as the caller-supplied
half still missing from the CLI.

This is a real subprocess test (mirrors `tests/test_smoke.py`'s
`python -m regolith.cli` invocation): it proves the installed console
command, not just the in-process Typer app, drives a real compiled
`.cupr` design's choice points end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EBI_DECODE_SOURCE = _REPO_ROOT / "examples" / "tracks" / "cuprite" / "ebi_decode.cupr"
_SUBJECT = "decoder_board.AddressDecodeGlue"

# The same declared, closed-form cost table `demos/demo1_select_ebi_decode.py`
# and `tests/test_wo56_ebi_decode.py` use: mcu_chip_selects is cheapest.
_COSTS = {_SUBJECT: {"nor_glue": 2.40, "cpld": 1.10, "mcu_chip_selects": 0.0}}


def _project_dir(tmp_path: Path) -> Path:
    """A real project DIRECTORY (never a bare file) containing exactly
    the copied `ebi_decode.cupr` source -- `discover_project_root`
    walks upward from a bare file looking for `magnetite.toml` and, in
    a tree with none (this repo's `examples/tracks/` has none), falls
    back to the ORIGINAL opened path rather than its parent directory;
    passing a directory sidesteps that entirely, same discipline every
    other CLI command's `project` argument test fixture already uses."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "ebi_decode.cupr").write_text(_EBI_DECODE_SOURCE.read_text())
    return project


def _run_optimize(project: Path, costs_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "regolith.cli",
            "optimize",
            str(project),
            "--costs",
            str(costs_path),
            "--budget-evals",
            "10",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=project.parent,
    )


# frob:tests python/regolith/cli/discovery.py::discover_project_root
def test_optimize_costs_seam_runs_a_real_compiled_designs_choice_points(
    tmp_path: Path,
) -> None:
    """No hand-supplied domains anywhere: `--costs` pairs a plain cost
    table with the design's own compiled `choice_points`, and the
    winner is `mcu_chip_selects` (the declared-cheapest candidate)."""
    costs_path = tmp_path / "costs.json"
    costs_path.write_text(json.dumps(_COSTS))

    result = _run_optimize(_project_dir(tmp_path), costs_path)

    assert result.returncode == 0, result.stderr
    trace_line = result.stdout.strip().splitlines()[-1]
    trace = json.loads(trace_line)
    assert trace["termination"] == "converged"
    winner_index = trace["winner"]
    winner = trace["candidates"][winner_index]
    assignment = dict((k, v) for k, v in winner["assignment"])
    assert assignment[_SUBJECT] == "mcu_chip_selects"


def test_optimize_refuses_both_spec_and_costs(tmp_path: Path) -> None:
    """`--spec` and `--costs` are mutually exclusive -- pass both and the
    command refuses cleanly instead of silently picking one."""
    costs_path = tmp_path / "costs.json"
    costs_path.write_text(json.dumps(_COSTS))
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps({"domains": [], "costs": {}, "objective": ["minimize"]})
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "regolith.cli",
            "optimize",
            str(_project_dir(tmp_path)),
            "--spec",
            str(spec_path),
            "--costs",
            str(costs_path),
            "--budget-evals",
            "10",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0


def test_optimize_refuses_neither_spec_nor_costs(tmp_path: Path) -> None:
    """Passing neither flag refuses cleanly (no silent no-op)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "regolith.cli",
            "optimize",
            str(_project_dir(tmp_path)),
            "--budget-evals",
            "10",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0
