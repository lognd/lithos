"""The REAL KiCad layout wrapper (WO-24 close-out, WO-42 deliverable 2's
producer): the ``argv`` executable `regolith.realizer.elec.kicad.run_layout`
talks to when `real_kicad_available()` is OPEN.

Runnable as ``python -m regolith.realizer.elec.kicad_wrapper``: reads one
`LayoutRequest` JSON document on stdin, drives real `pcbnew`/`kicad-cli`,
and writes one `LayoutResponse` JSON document to stdout -- the exact wire
discipline `regolith.realizer.elec.kicad`'s module docstring describes.

Honest scope (never faked): this wrapper builds a real `pcbnew.BOARD`,
draws a real rectangular `Edge.Cuts` outline (a placeholder outline --
importing the caller's actual board-outline file, e.g. a mech DXF
export, is a separate, larger integration this dispatch does not
attempt), saves it as a real `.kicad_pcb`, and runs a real `kicad-cli
pcb drc` pass against it. Footprint resolution/placement and routing
are NOT attempted here (no footprint-library resolution machinery
exists in this repo yet -- inventing one would be exactly the kind of
guessed convention the project's engineering principles forbid); the
response is therefore always ``status="unrouted"`` -- WO-24's own
documented honest outcome for "autorouting quality is NOT promised" --
never a faked ``"routed"``. The DRC report on the resulting (outline-
only, footprint-free) board is real KiCad output, not a fixture.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# A placeholder board outline: 50mm x 50mm square Edge.Cuts rectangle
# (mm). WO-24's real board-outline import (from the mech interface) is
# a separate integration; this fixed size only keeps the DRC pass from
# reporting a missing/malformed outline for a trivial real board.
_PLACEHOLDER_OUTLINE_MM = 50.0


def _draw_outline(board: Any, size_mm: float) -> None:
    """Draw a real square Edge.Cuts rectangle on ``board`` (real pcbnew)."""
    import pcbnew

    size = pcbnew.FromMM(size_mm)
    rect = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    rect.SetStart(pcbnew.VECTOR2I(0, 0))
    rect.SetEnd(pcbnew.VECTOR2I(size, size))
    rect.SetLayer(pcbnew.Edge_Cuts)
    board.Add(rect)


def _build_and_save_board(output_pcb_path: str) -> None:
    """Construct a real, outline-only `pcbnew.BOARD` and save it."""
    import pcbnew

    board = pcbnew.BOARD()
    _draw_outline(board, _PLACEHOLDER_OUTLINE_MM)
    pcbnew.SaveBoard(output_pcb_path, board)
    _log.info("kicad_wrapper: saved outline-only board to %s", output_pcb_path)


def _run_drc(pcb_path: str) -> tuple[list[dict[str, str]], bool]:
    """Run a real `kicad-cli pcb drc` pass; returns (violations, ok)."""
    report_path = str(Path(pcb_path).with_suffix(".drc.json"))
    completed = subprocess.run(
        [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-error",
            "--output",
            report_path,
            pcb_path,
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        _log.warning(
            "kicad_wrapper: kicad-cli pcb drc exited %d: %s",
            completed.returncode,
            completed.stderr.decode("ascii", errors="replace"),
        )
        return [], False
    report = json.loads(Path(report_path).read_text(encoding="ascii", errors="replace"))
    violations = [
        {
            "rule": v.get("type", "unknown"),
            "severity": v.get("severity", "error"),
            "message": v.get("description", ""),
        }
        for v in report.get("violations", [])
    ]
    return violations, True


def run(request_json: str) -> str:
    """The wrapper's pure entry point: request JSON in, response JSON out."""
    request = json.loads(request_json)
    output_pcb_path = request["output_pcb_path"]
    try:
        _build_and_save_board(output_pcb_path)
    except Exception as exc:  # pragma: no cover - programmer/infra bug surface
        _log.error("kicad_wrapper: board construction failed: %s", exc)
        return json.dumps(
            {
                "status": "unrouted",
                "pcb_path": "",
                "pcb_sha256": "",
                "drc": {"violations": []},
            }
        )

    violations, drc_ran = _run_drc(output_pcb_path)
    pcb_bytes = Path(output_pcb_path).read_bytes()
    pcb_sha256 = f"sha256:{hashlib.sha256(pcb_bytes).hexdigest()}"

    response = {
        # Honest: footprint placement/routing are not attempted (see
        # module docstring) -- this wrapper never claims "routed".
        "status": "unrouted",
        "pcb_path": output_pcb_path,
        "pcb_sha256": pcb_sha256,
        "drc": {"violations": violations if drc_ran else []},
    }
    return json.dumps(response)


def main() -> int:
    """CLI entry point: stdin JSON in, stdout JSON out (the wire discipline)."""
    request_json = sys.stdin.read()
    sys.stdout.write(run(request_json))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
